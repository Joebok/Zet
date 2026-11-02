"""Persisted candidate-retry checkpoints around atomic artifact detachment."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable
from uuid import UUID

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.local_pipeline_operation_reservation import ReservationConflict, active_preparation
from zet.services.local_pipeline_retry_artifact_service import LocalPipelineRetryArtifactService, RetryArtifactConflict
from zet.services.workflow_storage import file_lock


class LocalPipelineCandidateRetryReservation:
    """Own one candidate retry until its state transition is committed or cancelled.

    The coordinator must hold runner and slot-collector fences while detaching,
    restoring, committing and discarding, and serialize Stop with each change.
    Validation and apply callbacks must only inspect/change the supplied state;
    they must not write files, start work or perform slow preparation.
    """

    def __init__(self, run_root: Path):
        self.root = Path(run_root)
        self.path = self.root / "state.json"

    def _read(self) -> dict:
        return read_library_json(self.path, pipeline_library_root_for_path(self.root))

    def _write(self, state: dict) -> None:
        write_library_json(self.path, state, pipeline_library_root_for_path(self.root))

    @staticmethod
    def _record(state: dict, operation_id: str) -> dict:
        record = (state.get("operation_candidate_retries") or {}).get(operation_id)
        if not record:
            raise ReservationConflict("This operation has no candidate retry reservation.")
        return record

    @staticmethod
    def _running(state: dict, record: dict) -> None:
        if record.get("status") != "PREPARING":
            raise ReservationConflict("This candidate retry no longer owns preparation.")
        if state.get("slot_paused") or state.get("stop_requested"):
            raise ReservationConflict("The batch was stopped or paused.")

    def reserve(self, operation_id: str, candidate_id: str, expected_context: str,
                validate: Callable[[dict], None], *, clear_artifacts: bool = True, plan: dict | None = None) -> dict:
        operation_id = UUID(str(operation_id)).hex
        if not expected_context or type(clear_artifacts) is not bool or (plan is not None and not isinstance(plan, dict)):
            raise ValueError("A candidate input context and artifact policy are required.")
        artifacts = LocalPipelineRetryArtifactService(self.root, candidate_id, operation_id)
        with file_lock(self.root / "state.lock"):
            state = self._read()
            records = state.setdefault("operation_candidate_retries", {})
            existing = records.get(operation_id)
            if existing is not None:
                if (existing.get("candidate_id") != candidate_id or existing.get("expected_context") != expected_context
                        or existing.get("clear_artifacts", True) != clear_artifacts):
                    raise ReservationConflict("The saved candidate retry belongs to different inputs.")
                return deepcopy(existing)
            if state.get("slot_paused") or state.get("stop_requested"):
                raise ReservationConflict("The batch was stopped or paused.")
            if active_preparation(state):
                raise ReservationConflict("Another operation is preparing this batch.")
            validate(state)
            state = self._read()
            records = state.setdefault("operation_candidate_retries", {})
            if active_preparation(state):
                raise ReservationConflict("Another operation is preparing this batch.")
            source, detached = artifacts.inspect() if clear_artifacts else (False, False)
            if detached:
                raise RetryArtifactConflict("An unowned retry artifact directory already exists.")
            record = {"version": 1, "status": "PREPARING", "phase": "RESERVED",
                      "candidate_id": candidate_id, "expected_context": expected_context,
                      "clear_artifacts": clear_artifacts, "artifact_expected": source,
                      "plan": deepcopy(plan) if plan is not None else None}
            records[operation_id] = record
            self._write(state)
            return deepcopy(record)

    def find(self, operation_id: str) -> dict | None:
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            record = (self._read().get("operation_candidate_retries") or {}).get(operation_id)
            return deepcopy(record) if record else None

    def snapshot(self, operation_id: str) -> dict:
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            return deepcopy(self._record(self._read(), operation_id))

    def detach(self, operation_id: str) -> dict:
        """Detach once; recover a crash after rename but before the checkpoint."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = self._record(state, operation_id)
            self._running(state, record)
            if record.get("phase") not in {"RESERVED", "DETACHED"}:
                raise ReservationConflict("This retry is not ready for detachment.")
            artifacts = LocalPipelineRetryArtifactService(self.root, record["candidate_id"], operation_id)
            source, detached = artifacts.inspect() if record.get("clear_artifacts", True) else (False, False)
            if record["artifact_expected"]:
                if not source and not detached:
                    raise RetryArtifactConflict("The reserved candidate artifacts are missing.")
                if record["phase"] == "DETACHED" and not detached:
                    raise RetryArtifactConflict("Detached candidate artifacts were restored unexpectedly.")
                if record["phase"] == "RESERVED":
                    artifacts.detach()
            elif source or detached:
                raise RetryArtifactConflict("Candidate artifacts appeared after reservation.")
            if record["phase"] != "DETACHED":
                record["phase"] = "DETACHED"
                self._write(state)
            return deepcopy(record)

    def commit(self, operation_id: str, *, validate: Callable[[dict, dict], None],
               apply: Callable[[dict, dict], None]) -> bool:
        """Atomically update candidate state and mark the transition committed."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = self._record(state, operation_id)
            if record.get("status") == "COMMITTED":
                return False
            self._running(state, record)
            if record.get("phase") != "DETACHED":
                raise ReservationConflict("Candidate artifacts have not been detached.")
            artifacts = LocalPipelineRetryArtifactService(self.root, record["candidate_id"], operation_id)
            source, detached = artifacts.inspect() if record.get("clear_artifacts", True) else (False, False)
            if source or bool(detached) != bool(record["artifact_expected"]):
                raise RetryArtifactConflict("Candidate artifacts changed before commit.")
            validate(state, deepcopy(record))
            # Detail validation may persist a legacy-state migration. Keep that
            # write instead of committing a stale copy of the batch state.
            state = self._read()
            record = self._record(state, operation_id)
            self._running(state, record)
            if record.get("phase") != "DETACHED":
                raise ReservationConflict("Candidate retry changed during validation.")
            apply(state, deepcopy(record))
            record.update(status="COMMITTED", phase="COMMITTED")
            self._write(state)
            return True

    def cancel(self, operation_id: str) -> dict:
        """Restore uncommitted artifacts even when Stop has paused the batch."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = self._record(state, operation_id)
            if record.get("status") == "CANCELLED":
                return deepcopy(record)
            if record.get("status") != "PREPARING":
                raise ReservationConflict("A committed candidate retry cannot be cancelled.")
            artifacts = LocalPipelineRetryArtifactService(self.root, record["candidate_id"], operation_id)
            source, detached = artifacts.inspect() if record.get("clear_artifacts", True) else (False, False)
            if record["artifact_expected"]:
                if not source and not detached:
                    raise RetryArtifactConflict("The reserved candidate artifacts are missing.")
                if record.get("phase") == "DETACHED" and source:
                    raise RetryArtifactConflict("Detached candidate artifacts were restored unexpectedly.")
                if detached:
                    if record.get("phase") != "RESTORING":
                        record["phase"] = "RESTORING"
                        self._write(state)
                    artifacts.restore()
            elif source or detached:
                raise RetryArtifactConflict("Candidate artifacts appeared after reservation.")
            record.update(status="CANCELLED", phase="CANCELLED")
            self._write(state)
            return deepcopy(record)

    def discard(self, operation_id: str) -> bool:
        """Remove detached artifacts only after the candidate transition commits."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = self._record(state, operation_id)
            if record.get("status") != "COMMITTED":
                raise ReservationConflict("Candidate retry has not committed.")
            if not record.get("clear_artifacts", True):
                return False
            artifacts = LocalPipelineRetryArtifactService(self.root, record["candidate_id"], operation_id)
        return artifacts.discard()
