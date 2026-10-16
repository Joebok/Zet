"""Read-only recovery inventory and explicitly invoked, fenced collection retry."""
from __future__ import annotations

import json
from pathlib import Path
import socket

from zet.services.library_reference_service import read_library_json
from zet.services.workflow_storage import file_lock, validate_image


class AIJobRecoveryService:
    def __init__(self, paths):
        self.paths = paths
        self.jobs = paths.jobs
        self.library = Path(paths.config.base_library_path).resolve()

    @staticmethod
    def _read(path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Recovery metadata must be an object")
        return value

    def inspect(self, job_id):
        info = self.jobs.inspect(job_id)
        row = {**info, "action": "INSPECT_EVIDENCE", "eligible": False}
        if info["location"] == "receipt":
            return {**row, "action": "ALREADY_RECORDED"}
        if info["location"] not in {"answer", "inbox"}:
            return row
        folder = Path(info["path"])
        try:
            if folder.is_symlink() or any(path.is_symlink() for path in folder.rglob("*")):
                return {**row, "action": "VERIFY_LINKED_PAYLOAD"}
            ask = self._read(folder / "ask_manifest.json")
            envelope = self._read(folder / "job.json")
            if (envelope.get("job_id") != job_id or ask.get("ask_id") != job_id
                    or str(envelope.get("producer_id", "")).casefold() != socket.gethostname().casefold()
                    or ask.get("universe_id") != self.paths.config.universe_id):
                return {**row, "action": "VERIFY_OWNER"}
            row.update(universe_id=ask["universe_id"], consumer=ask.get("consumer", "zet"))
            record = self.jobs.repository.get(job_id)
            if not record or any(ask.get(key) != value for key, value in record.get("manifest", {}).items()):
                return {**row, "action": "VERIFY_REQUEST_IDENTITY"}
            outcome = self._read(folder / "proxy_result.json")
            if not self.paths.file_proxy_client._inventory_complete(folder, outcome.get("output_files")):
                return {**row, "action": "COMPLETE_TRANSFER"}
            answer = self._read(folder / "answer_manifest.json")
            if outcome.get("status") != "SUCCEEDED" or answer.get("status") != "SUCCESS":
                return {**row, "action": "EXPLICIT_EXECUTION_RETRY"}
            expected = str(ask.get("expected_output") or "")
            if Path(expected).name != expected or answer.get("ask_id") != job_id or answer.get("expected_output") != expected:
                return {**row, "action": "VERIFY_OUTPUT_IDENTITY"}
            if ask.get("worker_type") == "local_image_render":
                validate_image((folder / expected).read_bytes())
            if row["consumer"] == "zet-image-generation":
                request_id = str(ask.get("ad_hoc_request_id") or "")
                self.jobs.validate_id(request_id)
                request_path = self.library / "_state/ImageGeneration" / request_id / "job.json"
                saved = read_library_json(request_path, self.library)
                if saved.get("request_id") != request_id or not any(child.get("ask_id") == job_id for child in saved.get("children", [])):
                    return {**row, "action": "VERIFY_SAVED_REQUEST"}
                row["request_id"] = request_id
                if ask.get("session_id"):
                    session_id = str(ask["session_id"])
                    self.jobs.validate_id(session_id)
                    session = self._read(self.library / "_state/QuickCharacterWizard" / session_id / "session.json")
                    candidate_id = ask.get("candidate_id")
                    working = {cid for board in session.get("boards", {}).values() for cid in board.get("slots", []) if cid}
                    if session.get("deleted_at") or candidate_id not in working:
                        return {**row, "action": "OBSOLETE_ATTEMPT"}
            elif row["consumer"] == "zet-narrative-scenes":
                from zet.repositories.narrative_repository import NarrativeRepository
                repo = NarrativeRepository(self.library)
                target = self._read(repo.path(ask["narrative_story_id"], ask["narrative_scene_id"], ask["narrative_target_id"]))
                job = target.get("jobs", {}).get(job_id)
                # Target jobs are keyed by kind; match their explicit immutable IDs.
                if not job:
                    job = next((item for item in target.get("jobs", {}).values() if item.get("id") == job_id), None)
                if not job or job.get("status") not in {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}:
                    return {**row, "action": "OBSOLETE_ATTEMPT"}
            else:
                return {**row, "action": "OWNER_REVIEW_REQUIRED"}
            block = self.paths.file_proxy_client.answer_block(folder)
            if block:
                return {**row, **block, "action": "RESTORE_VERIFIED_ROUTE" if block["reason_code"] == "MISSING_ROUTE" else "COMPLETE_TRANSFER"}
            return {**row, "action": "RETRY_COLLECTION", "eligible": True}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return {**row, "action": "RESTORE_OWNER_METADATA", "recovery_error": str(exc)}

    def report(self):
        ids = set()
        for root in (self.paths.file_proxy_client.answer_root, self.paths.lifecycle.inbox_root):
            if root.is_dir():
                ids.update(path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))
        return {"universe_id": self.paths.config.universe_id, "dry_run": True,
                "items": [self.inspect(job_id) for job_id in sorted(ids)]}

    def retry_collection(self, app, job_id):
        """Explicit operator action. Never republishes execution or reconstructs routes."""
        if (app.universe_id != self.paths.config.universe_id
                or Path(app.config.base_library_path).resolve() != self.library
                or Path(app.config.base_ai_queue_path).resolve() != Path(self.paths.config.base_ai_queue_path).resolve()):
            raise ValueError("Recovery app must match the report's universe")
        with file_lock(self.paths.lifecycle.root / "Locks/coordinator.lock"):
            with file_lock(self.paths.lifecycle.lock_path(job_id)):
                row = self.inspect(job_id)
                if not row["eligible"]:
                    raise ValueError(f"Collection retry refused: {row['action']}")
                self.jobs.repository.update(job_id, harvest_state="AWAITING_HARVEST", error="")
            from zet.services.ai_job_coordinator import AIJobCoordinator
            record = self.jobs.repository.get(job_id)
            handler = AIJobCoordinator(app).handlers[row["consumer"]]
            try:
                handler(app, record, self.jobs)
            except Exception as exc:
                self.jobs.repository.collection_failed(job_id, exc, stage="explicit_recovery")
                raise
            return self.inspect(job_id)
