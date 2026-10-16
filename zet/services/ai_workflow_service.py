"""Durable, resumable Zet continuations. Pending AI yields instead of occupying a worker."""
from __future__ import annotations

from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class AIPending(BaseException):
    """Internal suspension, deliberately outside workflow error handlers."""


current_workflow = ContextVar("zet_ai_workflow", default=None)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zet-ai-continuation")


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
    }

    def __init__(self, app):
        self.app = app
        self.root = app.ai_proxy_service.ai_proxy_path_service.lifecycle.root / "Workflows"

    def _read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def submit(self, target, args, *, service, owner=None, key=None, initial=None):
        if target.__name__ not in self.METHODS[service]:
            raise ValueError("Unregistered AI workflow continuation")
        task_id = key or work_id("workflow")
        path = self.root / (task_id + ".json")
        owner = owner or {"session_id": str(args[0]) if args else ""}
        with file_lock(path.with_suffix(".lock")):
            if not path.exists():
                write_json_atomic(path, {"version": 1, "id": task_id, "universe_id": self.app.universe_id,
                    "service": service, "method": target.__name__, "args": list(args), "owner": owner, "status": "WAITING"})
        _POOL.submit(self.run, task_id, initial)
        return task_id

    def _service(self, name):
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
        path = self.root / (task_id + ".json")
        try:
            with file_lock(path.with_suffix(".lock"), timeout=0.05):
                record = self._read(path)
                if record["universe_id"] != self.app.universe_id or record["status"] in {"COMPLETE", "FAILED"}:
                    return
                if record["method"] not in self.METHODS.get(record["service"], set()):
                    raise ValueError("Unregistered persisted workflow")
                record["status"] = "RUNNING"
                write_json_atomic(path, record)
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
                    record.update(status="FAILED", error=str(exc))
                finally:
                    current_workflow.reset(token)
                    write_json_atomic(path, record)
        except TimeoutError:
            return

    def resume(self):
        if self.root.is_dir():
            for path in self.root.glob("*.json"):
                record = self._read(path)
                if record["universe_id"] == self.app.universe_id and record["status"] in {"WAITING", "RUNNING"}:
                    _POOL.submit(self.run, record["id"])

    def pending(self, session_id):
        if self.root.is_dir():
            return any(record["universe_id"] == self.app.universe_id
                       and str(session_id) in {str(value) for value in record.get("owner", {}).values()}
                       and record["status"] in {"WAITING", "RUNNING"}
                       for path in self.root.glob("*.json") for record in [self._read(path)])
        return False
