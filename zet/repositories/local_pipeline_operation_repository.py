"""Fixed-local records for character pipeline operation admission."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from uuid import UUID

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


# Activity records report progress and errors; execution checkpoints own guards.
ACTIVE = frozenset({"QUEUED", "PREPARING", "WAITING"})
ACTIVITY_ERRORS = frozenset({"FAILED", "RECOVERY_REQUIRED", "UNKNOWN", "BLOCKED", "PARTIAL"})


class OperationConflict(ValueError):
    def __init__(self, message: str, operation_id: str):
        super().__init__(message)
        self.operation_id = operation_id


class LocalPipelineOperationRepository:
    """Atomic local records, with admission serialized across processes."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, operation_id: str) -> Path:
        identifier = UUID(str(operation_id)).hex
        return self.root / "records" / (identifier + ".json")

    def batch_handoff_lock(self, universe_id: str, pipeline: str, run_id: str, costume: str = ""):
        """Fence Stop against handoff without blocking admission for other batches."""
        identity = json.dumps([universe_id, pipeline, run_id, costume], ensure_ascii=True, separators=(",", ":"))
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return file_lock(self.root / "handoffs" / (key + ".lock"))

    def get(self, operation_id: str) -> dict:
        path = self._path(operation_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            identifier = UUID(str(operation_id)).hex
            for record in self.list():
                if identifier in record.get("aliases", []):
                    return record
            raise

    def list(self) -> list[dict]:
        records = []
        for path in (self.root / "records").glob("*.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except FileNotFoundError:
                continue
        return records

    def list_activity(self) -> list[dict]:
        """Return in-progress operations and errors not dismissed by the user."""
        return [record for record in self.list()
                if record.get("status") in ACTIVE
                or record.get("status") in ACTIVITY_ERRORS and not record.get("dismissed_at")]

    def dismiss(self, operation_id: str) -> dict:
        """Hide a completed error without changing its execution checkpoint."""
        with file_lock(self.root / "admission.lock"):
            record = self.get(operation_id)
            if record.get("status") not in ACTIVITY_ERRORS:
                raise ValueError("Only a completed error can be dismissed.")
            if not record.get("dismissed_at"):
                record["dismissed_at"] = datetime.now(timezone.utc).isoformat()
                write_json_atomic(self._path(record["id"]), record)
            return record

    def admit(self, operation_id: str, request: dict) -> tuple[dict, bool]:
        path = self._path(operation_id)
        normalized = json.loads(json.dumps(request, sort_keys=True))
        target = tuple(normalized.get(key, "") for key in ("universe_id", "pipeline", "run_id", "costume"))
        with file_lock(self.root / "admission.lock"):
            try:
                existing = self.get(operation_id)
            except FileNotFoundError:
                existing = None
            if existing is not None:
                if existing["request"] != normalized:
                    raise OperationConflict("Operation ID already identifies a different request.", existing["id"])
                return existing, False
            for existing in self.list():
                saved = existing["request"]
                if existing["status"] not in ACTIVE or tuple(saved.get(key, "") for key in ("universe_id", "pipeline", "run_id", "costume")) != target:
                    continue
                if saved == normalized:
                    existing.setdefault("aliases", []).append(UUID(str(operation_id)).hex)
                    write_json_atomic(self._path(existing["id"]), existing)
                    return existing, False
                raise OperationConflict("Another operation is preparing this batch.", existing["id"])
            now = datetime.now(timezone.utc).isoformat()
            record = {"version": 1, "id": UUID(str(operation_id)).hex, "request": normalized,
                      "status": "QUEUED", "stage": "Waiting to prepare", "created_at": now, "updated_at": now}
            write_json_atomic(path, record)
            return record, True

    def update(self, operation_id: str, **changes) -> dict:
        with file_lock(self.root / "admission.lock"):
            record = self.get(operation_id)
            if {"id", "version", "request", "created_at", "aliases"} & changes.keys():
                raise ValueError("Operation identity is immutable.")
            record.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
            write_json_atomic(self._path(record["id"]), record)
            return record

    def transition(self, operation_id: str, expected: set[str], **changes) -> dict | None:
        """Atomically change an operation only while it is still in an expected state."""
        with file_lock(self.root / "admission.lock"):
            record = self.get(operation_id)
            if record.get("status") not in expected:
                return None
            return self.update(operation_id, **changes)

    def cancel_batch(self, universe_id: str, pipeline: str, run_id: str, costume: str = "") -> list[str]:
        """Fence queued work and request cooperative cancellation of preparation."""
        cancelled = []
        target = (universe_id, pipeline, run_id, costume)
        with file_lock(self.root / "admission.lock"):
            for record in self.list():
                request = record["request"]
                identity = tuple(request.get(key, "") for key in ("universe_id", "pipeline", "run_id", "costume"))
                if identity != target or record.get("status") not in {"QUEUED", "WAITING", "PREPARING"}:
                    continue
                if record["status"] == "PREPARING":
                    self.update(record["id"], cancel_requested=True, stage="Stopping preparation")
                else:
                    self.update(record["id"], status="CANCELLED", cancel_requested=True, stage="Cancelled before preparation")
                cancelled.append(record["id"])
        return cancelled

    def complete_preparation(self, operation_id: str, result: dict) -> dict | None:
        with file_lock(self.root / "admission.lock"):
            record = self.get(operation_id)
            if record.get("status") != "PREPARING":
                return None
            evaluation = record.get("request", {}).get("action") == "reevaluate"
            if record.get("cancel_requested"):
                confirmed = result.get("cancel_confirmed") is True and result.get("outcome") in {"CANCELLED", "PARTIAL"}
                if evaluation and result.get("outcome") == "SUCCEEDED" and result.get("evaluations"):
                    result = {**result, "outcome": "PARTIAL", "cancel_confirmed": True,
                              "error": "Stop was requested after evaluations were queued. Review the batch before submitting again."}
                    confirmed = True
                if not confirmed:
                    return self.update(operation_id, status="RECOVERY_REQUIRED", stage="Stop requested during preparation; reconcile the handoff.", result=result)
            outcome = result.get("outcome", "SUCCEEDED")
            if outcome not in {"SUCCEEDED", "PARTIAL", "BLOCKED", "CANCELLED"}:
                raise ValueError("Invalid operation outcome.")
            stage = {"SUCCEEDED": "Evaluation queued" if evaluation else "Renders queued", "PARTIAL": "Some evaluations queued; attention needed" if evaluation else "Some renders queued; attention needed",
                     "BLOCKED": "No renders queued", "CANCELLED": "Preparation stopped"}[outcome]
            if evaluation and outcome == "BLOCKED":
                stage = "No evaluation queued"
            if record.get("request", {}).get("action") in {"start", "resume"}:
                stage = {"SUCCEEDED": "Batch ready" if result.get("handoff") == "none" else "Batch work queued",
                         "PARTIAL": "Batch handoff needs review", "BLOCKED": "Batch action blocked",
                         "CANCELLED": "Batch preparation stopped"}[outcome]
            if record.get("request", {}).get("action") == "retry_candidate":
                stage = {"SUCCEEDED": "Candidate retry queued", "PARTIAL": "Candidate retry needs review",
                         "BLOCKED": "Candidate retry blocked", "CANCELLED": "Candidate retry stopped"}[outcome]
            return self.update(operation_id, status=outcome, stage=stage, result=result)

    def settle_unstarted(self, operation_id: str, status: str, stage: str, error: str = "") -> dict | None:
        """Settle a pre-reservation wait/rejection without racing a Stop request."""
        if status not in {"WAITING", "BLOCKED"}:
            raise ValueError("Invalid unstarted operation status.")
        with file_lock(self.root / "admission.lock"):
            record = self.get(operation_id)
            if record.get("status") != "PREPARING":
                return None
            if record.get("cancel_requested"):
                return self.update(operation_id, status="CANCELLED", stage="Cancelled before preparation")
            return self.update(operation_id, status=status, stage=stage, error=error)

    def ownership_lock(self, operation_id: str, timeout: float = 0):
        key = hashlib.sha256(UUID(str(self.get(operation_id)["id"])).bytes).hexdigest()
        return file_lock(self.root / "owners" / (key + ".lock"), timeout=timeout)

    def prune_successes(self, days: int = 7) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        removed = 0
        with file_lock(self.root / "admission.lock"):
            for record in self.list():
                if record.get("status") != "SUCCEEDED":
                    continue
                if datetime.fromisoformat(record["updated_at"]) < cutoff:
                    self._path(record["id"]).unlink(missing_ok=True)
                    removed += 1
        return removed
