"""Subscriber-owned fresh attempts behind a stable workflow request identity."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.storage_health_service import recovery_root, storage_health
from zet.services.workflow_storage import file_lock


class AIAttemptRecoveryService:
    def __init__(self, jobs):
        self.jobs = jobs
        self.root = recovery_root(jobs.paths.config) / "Attempts"

    def _path(self, job_id):
        return self.root / (hashlib.sha256(job_id.encode()).hexdigest() + ".json")

    def read(self, job_id):
        try:
            return json.loads(self._path(job_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    @staticmethod
    def retryable(path):
        outcome = json.loads((path / "proxy_result.json").read_text(encoding="utf-8"))
        return outcome.get("status") == "FAILED" and (outcome.get("error_type") == "PROXY_INTERRUPTED"
                or outcome.get("recovery_class") in {"STORAGE_UNAVAILABLE", "EXECUTION_INTERRUPTED"})

    def ready(self, job_id):
        jobs = self.jobs
        health = storage_health(jobs.paths.config)
        health.require("queue", "application", "library")
        from zet.services.workflow_storage import task_state_path
        if task_state_path(jobs.lifecycle.queue_root, "Superseded", job_id,
                           state_root=jobs.lifecycle.storage_root).is_file():
            return None
        with file_lock(self._path(job_id).with_suffix(".lock")):
            state = self.read(job_id)
            original = jobs._ready_answer_physical(job_id)
            if original and not self.retryable(original):
                return original
            if not state and original is None:
                return None
            if not self._current(job_id):
                state.update(status="SUPERSEDED", reason="The owning work was stopped, completed, or replaced")
                write_json_atomic(self._path(job_id), state)
                jobs.repository.update(job_id, harvest_state="SUPERSEDED", error="")
                return None
            if state.get("status") == "COMPLETE":
                return original
            if not state:
                state = {"version": 1, "logical_job_id": job_id, "original_path": str(original),
                         "attempts": [], "universe_id": jobs.paths.config.universe_id}
            active = state.get("current_attempt_id")
            if not active:
                self._reserve(state, job_id)
            active = state["current_attempt_id"]
            self._publish(state)
            answer = jobs._ready_answer_physical(active)
            if answer is None:
                return None
            if self.retryable(answer):
                state["attempts"][-1].update(status="INTERRUPTED", error=self._outcome(answer).get("error_message", ""))
                self._reserve(state, job_id)
                return None
            return self._materialize(state, answer)

    @staticmethod
    def _outcome(path):
        return json.loads((path / "proxy_result.json").read_text(encoding="utf-8"))

    def _current(self, job_id):
        """Honor explicit domain stops before spending another execution attempt."""
        jobs = self.jobs
        app = getattr(jobs.paths, "app", None)
        record = jobs.repository.get(job_id)
        ask = record.get("manifest", {})
        if app and ask.get("consumer") == "zet-narrative-scenes":
            target = app.narrative_scene_service.repository.read(ask["narrative_story_id"], ask["narrative_scene_id"], ask["narrative_target_id"])
            job = target.get("jobs", {}).get(job_id, {})
            if job.get("kind") == "image":
                candidate = target.get("candidates", {}).get(job.get("candidate_id"), {})
                if candidate.get("job_id") != job_id or candidate.get("locked"):
                    return False
            elif target.get("active_llm_job") != job_id:
                return False
            return job.get("status") in {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING", "PAUSED_STORAGE", "RECOVERING"}
        route = jobs.client.load_route(job_id)
        library = Path(jobs.paths.config.base_library_path).resolve()
        for value in route.values():
            if not isinstance(value, str):
                continue
            path = Path(value).resolve()
            if not path.is_relative_to(library):
                continue
            for parent in (path, *path.parents):
                if parent == library:
                    break
                if (parent / "spec.json").is_file() and (parent / "state.json").is_file():
                    state = json.loads((parent / "state.json").read_text(encoding="utf-8"))
                    if state.get("stop_requested") or state.get("status") in {"CANCELLED", "STOPPED", "COMPLETE"}:
                        return False
        return True

    def _reserve(self, state, job_id):
        active = "Recovery_" + uuid4().hex
        now = datetime.now(timezone.utc)
        count = state.get("attempt_count", len(state["attempts"])) + 1
        delay = min(30, 2 ** min(count - 1, 5))
        state.update(current_attempt_id=active, status="RECOVERING", reason="Execution interrupted; a fresh attempt will run automatically",
                     retry_at=(now + timedelta(seconds=delay)).isoformat(), updated_at=now.isoformat(), attempt_count=count)
        state["attempts"].append({"ask_id": active, "status": "RESERVED", "created_at": now.isoformat()})
        state["attempts"] = state["attempts"][-20:]
        write_json_atomic(self._path(job_id), state)
        from zet.services.storage_health_service import remember_request
        remember_request(self.jobs.paths.config, job_id, current_attempt_id=active, recovery_stage="RECOVERING")

    def _publish(self, state):
        jobs, client = self.jobs, self.jobs.client
        active, logical = state["current_attempt_id"], state["logical_job_id"]
        if jobs.repository.is_deleted(logical):
            return
        if any((root / active).is_dir() for root in (client.ask_root, client.running_root, client.answer_root, jobs.lifecycle.inbox_root)):
            return
        if datetime.now(timezone.utc).isoformat() < state["retry_at"]:
            return
        original = Path(state["original_path"])
        envelope = json.loads((original / "job.json").read_text(encoding="utf-8"))
        if not client._inventory_complete(original, envelope["files"]):
            raise ValueError("Cannot recover execution: frozen inputs are missing or changed")
        staging = client.staging_path(active)
        staging.mkdir(parents=True, exist_ok=True)
        for item in envelope["files"]:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe frozen input path")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / relative, target)
        ask = json.loads((staging / "ask_manifest.json").read_text(encoding="utf-8"))
        ask["logical_job_id"] = logical
        for key in ("ask_id", "ollama_attempt_id"):
            if ask.get(key) == logical:
                ask[key] = active
        write_json_atomic(staging / "ask_manifest.json", ask)
        route = client.load_route(logical)
        if envelope.get("route_required") and not route:
            raise ValueError("Cannot recover execution without its verified route")
        if route:
            from zet.services.library_reference_service import serialize_library_document
            write_json_atomic(client.route_root / (active + ".json"), serialize_library_document(route, client.library_root))
        (staging / "job.json").unlink(missing_ok=True)
        envelope.update(job_id=active, created_at=datetime.now(timezone.utc).isoformat(), files=client._file_inventory(staging))
        write_json_atomic(staging / "job.json", envelope)
        from zet.services.storage_health_service import remember_request
        remember_request(jobs.paths.config, active, ask, envelope)
        jobs.repository.register(active, ask, envelope)
        jobs.repository.update(active, logical_job_id=logical, harvest_state="RETRY_ATTEMPT")
        client._replace_with_retry(staging, client.ask_root / active)
        state["attempts"][-1]["status"] = "PUBLISHED"
        write_json_atomic(self._path(logical), state)
        jobs.repository.update(logical, current_attempt_id=active, recovery_stage="EXECUTING", error="")

    def _materialize(self, state, answer):
        """Build a verified producer-local logical answer; shared bytes stay immutable."""
        jobs = self.jobs
        logical = state["logical_job_id"]
        original = Path(state["original_path"])
        archived = jobs.lifecycle.root / "RecoveryAttempts" / logical
        if not original.is_dir() and archived.is_dir():
            original = archived
        staging = jobs.lifecycle.inbox_root / ("." + logical + ".recovery")
        if staging.exists():
            # Reuse only this recovery-owned directory; replay copies all verified files.
            if staging.is_symlink():
                raise ValueError("Recovery staging cannot be a symlink")
        staging.mkdir(parents=True, exist_ok=True)
        for item in self._outcome(answer)["output_files"]:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe recovered output path")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(answer / relative, target)
        for name in ("job.json", "ask_manifest.json"):
            shutil.copy2(original / name, staging / name)
        response = json.loads((staging / "answer_manifest.json").read_text(encoding="utf-8"))
        original_ask = json.loads((original / "ask_manifest.json").read_text(encoding="utf-8"))
        for key in ("ask_id", "ollama_attempt_id", "source_ask_id"):
            if key in original_ask:
                response[key] = original_ask[key]
        response.update(ask_id=logical, current_attempt_id=state["current_attempt_id"])
        write_json_atomic(staging / "answer_manifest.json", response)
        outcome = self._outcome(answer)
        (staging / "proxy_result.json").unlink(missing_ok=True)
        outcome.update(job_id=logical, output_files=jobs.client._file_inventory(staging))
        write_json_atomic(staging / "proxy_result.json", outcome)
        if not jobs.client._inventory_complete(staging, outcome["output_files"]):
            raise ValueError("Recovered answer failed inventory verification")
        destination = jobs.lifecycle.inbox_root / logical
        archived.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not archived.exists():
            jobs.client._replace_with_retry(destination, archived)
        jobs.client._replace_with_retry(staging, destination)
        state.update(status="COMPLETE", recovered_at=datetime.now(timezone.utc).isoformat(), reason="")
        write_json_atomic(self._path(logical), state)
        jobs.repository.update(logical, recovery_stage="COLLECTING", last_recovered_at=state["recovered_at"], error="")
        jobs.lifecycle.finish_answer(answer, {"status": "SUPERSEDED", "message": "Verified result transferred to logical request " + logical})
        return destination
