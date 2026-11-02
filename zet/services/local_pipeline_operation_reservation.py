"""Short batch-state transactions for local pipeline preparation."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable
from uuid import UUID

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.local_pipeline_cancel_marker import cancellation_marker_digest
from zet.services.workflow_storage import file_lock


class ReservationConflict(ValueError):
    """A preparation no longer owns the batch or a reserved target."""


class BatchTransitionUncertain(ValueError):
    """A committed transition may already have been handed off."""


def active_preparation(state: dict, *, owner_id: str = "") -> str:
    """Return a conflicting active preparation, optionally excluding its owner."""
    for field in ("operation_preparations", "operation_candidate_retries"):
        active = next((operation_id for operation_id, record in (state.get(field) or {}).items()
                       if operation_id != owner_id and record.get("status") == "PREPARING"), "")
        if active:
            return active
    return ""


def reject_reserved_deletion(run_root: Path) -> None:
    """Check deletion under the batch state lock held by the calling adapter."""
    root = Path(run_root)
    state = read_library_json(root / "state.json", pipeline_library_root_for_path(root))
    if active_preparation(state):
        from zet.services.render_slot_service import RenderSlotConflict
        raise RenderSlotConflict("Another operation is preparing this batch. Wait before deleting it.")


class LocalPipelineOperationReservation:
    """Persist target identity and checkpoints in the owning batch state.

    Callers must validate current domain inputs under the state lock, prepare
    files outside it, and validate inputs again in the commit callback.
    """

    def __init__(self, run_root: Path):
        self.root = Path(run_root)
        self.state_path = self.root / "state.json"

    def _read(self) -> dict:
        return read_library_json(self.state_path, pipeline_library_root_for_path(self.root))

    def _write(self, state: dict) -> None:
        write_library_json(self.state_path, state, pipeline_library_root_for_path(self.root))

    def snapshot(self, operation_id: str) -> dict:
        """Read a reservation under the same lock used for all its transitions."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_preparations") or {}).get(operation_id)
            if not record:
                raise ReservationConflict("This operation has no reservation.")
            return deepcopy(record)

    def find(self, operation_id: str) -> dict | None:
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_preparations") or {}).get(operation_id)
            return deepcopy(record) if record else None

    @staticmethod
    def _active(state: dict) -> None:
        if state.get("stop_requested") or state.get("slot_paused"):
            raise ReservationConflict("The batch was stopped or paused.")

    def find_batch_transition(self, operation_id: str, action: str, expected_context: str) -> dict | None:
        """Return an existing lifecycle checkpoint without revalidating old inputs."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_batch_transitions") or {}).get(operation_id)
            if record is None:
                return None
            if record.get("action") != action or record.get("expected_context") != expected_context:
                raise ReservationConflict("The saved batch transition belongs to different inputs.")
            return deepcopy(record)

    def _batch_transition_guard(self, state: dict) -> str:
        state = {key: value for key, value in state.items() if key != "operation_batch_transitions"}
        snapshot = json.dumps(state, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        marker = cancellation_marker_digest(self.root)
        return sha256(snapshot + b"\0" + (self.root / "spec.json").read_bytes() + b"\0" + (marker or "").encode("ascii")).hexdigest()

    def verify_batch_transition(self, operation_id: str, action: str, expected_context: str) -> dict:
        """Fence replay if the batch changed after the saved transition."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_batch_transitions") or {}).get(operation_id)
            if (not record or record.get("action") != action or record.get("expected_context") != expected_context
                    or not record.get("state_guard") or record["state_guard"] != self._batch_transition_guard(state)):
                raise BatchTransitionUncertain("Batch state changed after the transition; review its handoff before retrying.")
            return deepcopy(record)

    def commit_batch_transition(self, operation_id: str, action: str, expected_context: str,
                                apply: Callable[[dict], str], *, validate: Callable[[], None] | None = None) -> dict:
        """Commit a batch transition and its handoff identity in one state write.

        The callback must validate the current domain state and change only the
        supplied state dictionary; it must not write files or dispatch work. Its
        result identifies the required handoff. Validation runs under the lock
        before the final state read, so any detail migrations are preserved.
        Replays invoke neither callback.
        """
        operation_id = UUID(str(operation_id)).hex
        if action not in {"start", "resume"} or not expected_context:
            raise ValueError("A valid batch transition and input context are required.")
        with file_lock(self.root / "state.lock"):
            state = self._read()
            records = state.setdefault("operation_batch_transitions", {})
            existing = records.get(operation_id)
            if existing is not None:
                if existing.get("action") != action or existing.get("expected_context") != expected_context:
                    raise ReservationConflict("The saved batch transition belongs to different inputs.")
                if not existing.get("state_guard") or existing["state_guard"] != self._batch_transition_guard(state):
                    raise BatchTransitionUncertain("Batch state changed after the transition; review its handoff before retrying.")
                return deepcopy(existing)
            if validate is not None:
                validate()
                state = self._read()
                records = state.setdefault("operation_batch_transitions", {})
            if active_preparation(state):
                raise ReservationConflict("Another operation is preparing this batch.")
            handoff = apply(state)
            if handoff not in {"runner", "slot", "none"}:
                raise ValueError("The transition returned an invalid handoff.")
            record = {"version": 1, "action": action, "expected_context": expected_context,
                      "handoff": handoff, "state_guard": self._batch_transition_guard(state)}
            records[operation_id] = record
            self._write(state)
            return deepcopy(record)

    def reserve(self, operation_id: str, expected_context: str, targets: list[dict], validate: Callable[[dict], None]) -> dict:
        frozen_targets = deepcopy(targets)
        def build(state):
            validate(state)
            return frozen_targets
        return self._reserve(operation_id, expected_context, build, expected_targets=frozen_targets)

    def reserve_factory(self, operation_id: str, expected_context: str, build: Callable[[dict], list[dict] | dict]) -> dict:
        """Allocate targets under the state lock, or reuse a prior allocation.

        The builder receives a copy of current state and must perform input
        validation and produce candidate IDs and seeds without writing files.
        """
        return self._reserve(operation_id, expected_context, build)

    def _reserve(self, operation_id: str, expected_context: str, build: Callable[[dict], list[dict] | dict], *, expected_targets: list[dict] | None = None) -> dict:
        operation_id = UUID(str(operation_id)).hex
        if not expected_context:
            raise ValueError("An input context is required.")
        with file_lock(self.root / "state.lock"):
            state = self._read()
            self._active(state)
            records = state.setdefault("operation_preparations", {})
            existing = records.get(operation_id)
            if existing:
                if (existing.get("expected_context") != expected_context
                        or expected_targets is not None and existing.get("targets") != expected_targets):
                    raise ReservationConflict("The operation already has different reserved targets.")
                return deepcopy(existing)
            if active_preparation(state):
                raise ReservationConflict("Another operation is preparing this batch.")
            plan = build(deepcopy(state))
            details = {}
            if isinstance(plan, dict):
                if set(plan) - {"targets", "blocked_views", "errors"}:
                    raise ValueError("Unknown reservation plan fields.")
                targets = plan.get("targets")
                details = {key: deepcopy(plan.get(key) or {}) for key in ("blocked_views", "errors")}
                if any(not isinstance(value, dict) for value in details.values()):
                    raise ValueError("Invalid reservation outcomes.")
            else:
                targets = plan
            if (not isinstance(targets, list) or any(not isinstance(item, dict) for item in targets)
                    or not targets and not (details.get("blocked_views") or details.get("errors"))):
                raise ValueError("At least one target is required.")
            ids = [item.get("candidate_id") for item in targets]
            if any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
                raise ValueError("Each reserved target requires a distinct candidate ID.")
            frozen_targets = deepcopy(targets)
            record = {"version": 1, "status": "PREPARING", "expected_context": expected_context,
                      "targets": frozen_targets, "committed_candidate_ids": [], **details}
            records[operation_id] = record
            self._write(state)
            return deepcopy(record)

    def commit(self, operation_id: str, candidate_id: str, apply: Callable[[dict, dict], None], *,
               validate: Callable[[dict, dict], None]) -> bool:
        """Commit one target and its checkpoint together; return False on replay."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            self._active(state)
            record = (state.get("operation_preparations") or {}).get(operation_id)
            if not record or record.get("status") != "PREPARING":
                raise ReservationConflict("This operation no longer owns preparation.")
            target = next((item for item in record["targets"] if item["candidate_id"] == candidate_id), None)
            if target is None:
                raise ReservationConflict("This candidate is not reserved by the operation.")
            if candidate_id in record["committed_candidate_ids"]:
                return False
            validate(state, deepcopy(record))
            apply(state, deepcopy(target))
            record["committed_candidate_ids"].append(candidate_id)
            self._write(state)
            return True

    def finish(self, operation_id: str) -> dict:
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            self._active(state)
            record = (state.get("operation_preparations") or {}).get(operation_id)
            if not record:
                raise ReservationConflict("This operation has no reservation.")
            if record.get("status") == "COMMITTED":
                return deepcopy(record)
            if record.get("status") != "PREPARING" or len(record["committed_candidate_ids"]) != len(record["targets"]):
                raise ReservationConflict("Not every reserved target has been committed.")
            record["status"] = "COMMITTED"
            self._write(state)
            return deepcopy(record)

    def cancel(self, operation_id: str, *, pause: bool = False, reason: str = "") -> dict:
        """Release an interrupted reservation without undoing committed targets.

        The caller must hold the operation ownership lock and stop preparation
        before using this method. Already committed work remains in batch state.
        """
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_preparations") or {}).get(operation_id)
            if not record:
                raise ReservationConflict("This operation has no reservation.")
            if record.get("status") == "CANCELLED":
                return deepcopy(record)
            if record.get("status") != "PREPARING":
                raise ReservationConflict("This operation is no longer preparing.")
            record["status"] = "CANCELLED"
            record["cancelled_by_user"] = bool(pause)
            record["cancel_reason"] = str(reason)
            if pause:
                state["slot_paused"] = True
            self._write(state)
            return deepcopy(record)

    def pause_committed(self, operation_id: str) -> dict:
        """Fence a stopped handoff whose candidate commits are already durable."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_preparations") or {}).get(operation_id)
            if not record or record.get("status") not in {"COMMITTED", "CANCELLED"}:
                raise ReservationConflict("This operation does not have a completed reservation.")
            state["slot_paused"] = True
            self._write(state)
            return deepcopy(record)

    def admit_handoff(self, operation_id: str) -> bool:
        """Record that committed candidates may be handed to the collector."""
        operation_id = UUID(str(operation_id)).hex
        with file_lock(self.root / "state.lock"):
            state = self._read()
            record = (state.get("operation_preparations") or {}).get(operation_id)
            if (not record or record.get("status") not in {"COMMITTED", "CANCELLED"}
                    or record.get("status") == "CANCELLED" and record.get("cancelled_by_user")):
                raise ReservationConflict("This operation does not have a completed reservation.")
            if state.get("slot_paused") or state.get("stop_requested"):
                return False
            if not record.get("handoff_admitted"):
                record["handoff_admitted"] = True
                self._write(state)
            return True
