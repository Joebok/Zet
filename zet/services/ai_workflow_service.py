"""Durable, resumable Zet continuations. Pending AI yields instead of occupying a worker."""
from __future__ import annotations

from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
import json
import threading
from datetime import datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class AIPending(BaseException):
    """Internal suspension, deliberately outside workflow error handlers."""


current_workflow = ContextVar("zet_ai_workflow", default=None)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zet-ai-continuation")
_ACTIVE_LOCK = threading.Lock()
_ACTIVE: set[tuple[str, str, str]] = set()


def work_id(label="item"):
    context = current_workflow.get()
    if context is None:
        return uuid4().hex
    index = context["counts"].get(label, 0)
    context["counts"][label] = index + 1
    return uuid5(NAMESPACE_URL, f"{context['id']}:{label}:{index}").hex


class AIWorkflowService:
    METHODS = {
        "minor": {"_draft_job", "_render_job", "_review_job", "_dispatch_candidate", "_analyze_then_render"},
        "costume": {"_draft_job", "_render_job", "_refine_job"},
        "reconstruction": {"_run", "_comparison_task", "_correction_task"},
        "image_prompt": {"_run"},
        "template_revision": {"_propose_job", "_review_job"},
        "character_refinement": {"_analysis_job", "_render_job"},
        "post_render_prompt": {"_analysis_job", "_render_job"},
    }

    def __init__(self, app):
        self.app = app
        self.root = app.ai_proxy_service.ai_proxy_path_service.lifecycle.root / "Workflows"
        from zet.services.storage_health_service import recovery_root
        self.local_root = recovery_root(app.config) / "Workflows"

    def _read(self, path):
        local = self.local_root / path.name
        saved = json.loads(local.read_text(encoding="utf-8")) if local.is_file() else None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if saved is None:
                raise
            return saved
        return saved if saved and saved.get("updated_at", "") >= record.get("updated_at", "") else record

    def _save(self, path, record):
        from zet.services.storage_health_service import storage_health
        write_json_atomic(self.local_root / path.name, record)
        if storage_health(self.app.config).status()["available"]:
            write_json_atomic(path, record)

    def _paths(self):
        paths = {path.name: self.root / path.name for path in self.local_root.glob("*.json")}
        if self.root.is_dir():
            paths.update({path.name: path for path in self.root.glob("*.json")})
        return list(paths.values())

    def submit(self, target, args, *, service, owner=None, key=None, initial=None):
        if target.__name__ not in self.METHODS[service]:
            raise ValueError("Unregistered AI workflow continuation")
        task_id = key or work_id("workflow")
        path = self.root / (task_id + ".json")
        owner = owner or {"session_id": str(args[0]) if args else ""}
        with file_lock(path.with_suffix(".lock")):
            if not path.exists() and not (self.local_root / path.name).exists():
                now = datetime.now(timezone.utc).isoformat()
                self._save(path, {"version": 1, "id": task_id, "universe_id": self.app.universe_id,
                    "service": service, "method": target.__name__, "args": list(args), "owner": owner,
                    "status": "WAITING", "created_at": now, "updated_at": now})
        self._enqueue(task_id, initial)
        return task_id

    def _enqueue(self, task_id, initial=None):
        identity = (str(self.root.resolve()), self.app.universe_id, str(task_id))
        with _ACTIVE_LOCK:
            if identity in _ACTIVE:
                return False
            _ACTIVE.add(identity)
        try:
            _POOL.submit(self._run_enqueued, task_id, initial, identity)
        except BaseException:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(identity)
            raise
        return True

    def _run_enqueued(self, task_id, initial, identity):
        try:
            self.run(task_id, initial)
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(identity)

    def _service(self, name):
        if name == "post_render_prompt":
            from pathlib import Path
            from zet.services.local_post_render_prompt_service import LocalPostRenderPromptService
            return LocalPostRenderPromptService(self.app, Path(__file__).resolve().parents[2])
        if name == "character_refinement":
            from pathlib import Path
            from zet.services.local_character_refinement_service import LocalCharacterRefinementService
            return LocalCharacterRefinementService(self.app, Path(__file__).resolve().parents[2])
        if name == "template_revision":
            from pathlib import Path
            from zet.services.local_template_revision_service import LocalTemplateRevisionService
            return LocalTemplateRevisionService(self.app, Path(__file__).resolve().parents[2])
        if name == "minor":
            return self.app.minor_character_service
        if name == "costume":
            return self.app.costume_wizard_service
        if name in {"reconstruction", "image_prompt"}:
            from zet.services.ai_job_coordinator import image_services
            generation, prompt = image_services(self.app)
            return generation.reconstruction if name == "reconstruction" else prompt
        raise ValueError("Unknown AI workflow owner")

    def run(self, task_id, initial=None):
        from zet.services.storage_health_service import storage_health
        health = storage_health(self.app.config)
        if not health.poll()["available"]:
            return
        path = self.root / (task_id + ".json")
        try:
            with file_lock(path.with_suffix(".lock"), timeout=0.05):
                record = self._read(path)
                if record["universe_id"] != self.app.universe_id or record["status"] in {"COMPLETE", "FAILED"}:
                    return
                if record["method"] not in self.METHODS.get(record["service"], set()):
                    raise ValueError("Unregistered persisted workflow")
                if record.get("error"):
                    record["last_recovery_error"] = {"message": record["error"], "recorded_at": record.get("updated_at", "")}
                record.update(status="RUNNING", error="")
                record["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(path, record)
                token = current_workflow.set({"id": task_id, "counts": {}, "owner": record["owner"], "service": record["service"]})
                try:
                    target = getattr(self._service(record["service"]), record["method"])
                    if initial:
                        initial()
                    else:
                        target(*record["args"])
                    record["status"] = "COMPLETE"
                except AIPending:
                    record["status"] = "WAITING"
                except Exception as exc:
                    if health.check_error(exc):
                        record.update(status="PAUSED_STORAGE", error="Storage unavailable; resumption is automatic")
                    else:
                        record.update(status="FAILED", error=str(exc))
                finally:
                    current_workflow.reset(token)
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    if record["status"] == "COMPLETE":
                        record["completed_at"] = record["updated_at"]
                    self._save(path, record)
        except (TimeoutError, OSError):
            return

    def resume(self):
        if self.root.is_dir() or self.local_root.is_dir():
            for path in self._paths():
                try:
                    record = self._read(path)
                    if record["universe_id"] == self.app.universe_id and record["status"] in {"WAITING", "RUNNING", "PAUSED_STORAGE", "RECOVERING"}:
                        self._enqueue(record["id"])
                except (OSError, ValueError, KeyError):
                    import logging
                    logging.getLogger(__name__).exception("Unable to resume AI workflow %s", path)

    def pending(self, session_id):
        if self.root.is_dir() or self.local_root.is_dir():
            for path in self._paths():
                try:
                    record = self._read(path)
                    if (record["universe_id"] == self.app.universe_id
                            and str(session_id) in {str(value) for value in record.get("owner", {}).values()}
                            and record["status"] in {"WAITING", "RUNNING", "PAUSED_STORAGE", "RECOVERING"}):
                        return True
                except (OSError, ValueError, KeyError):
                    continue
        return False
