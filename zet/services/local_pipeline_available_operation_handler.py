"""Recoverable orchestration for reserved Run available preparation."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json
from zet.services.local_pipeline_available_preparation_service import LocalPipelineAvailablePreparationService
from zet.services.local_pipeline_operation_context import OperationBlocked, OperationInputsChanged, OperationWaiting, check_operation_context
from zet.services.local_pipeline_operation_reservation import LocalPipelineOperationReservation, ReservationConflict
from zet.services.local_pipeline_slot_planning_service import plan_slot_targets, plan_view_targets
from zet.services.render_slot_service import plan_available_targets
from zet.services.workflow_storage import runner_lock_active


class LocalPipelineAvailableOperationHandler:
    """Allocate, prepare and hand off a Run available operation with checkpoints."""

    def __init__(self, repository, resolve_workflow: Callable[[str, str], object]):
        self.repository = repository
        self.resolve_workflow = resolve_workflow

    @staticmethod
    def can_resume(record: dict) -> bool:
        return record.get("request", {}).get("action") in {"run_available", "generate_slots", "regenerate_slot", "retry_render_slot", "rerun_view", "rerun_failed"}

    def __call__(self, record: dict) -> dict:
        request, operation_id = record["request"], record["id"]
        if not self.can_resume(record):
            raise ValueError("Unsupported operation for available-render preparation.")
        workflow = self.resolve_workflow(request["universe_id"], request["pipeline"])
        if workflow.pipeline != request["pipeline"] or workflow.app.universe_id != request["universe_id"]:
            raise ValueError("The operation does not belong to this pipeline and universe.")
        run = workflow.action("detail", run_id=request["run_id"], costume=request.get("costume") or "")
        root = Path(run["root"])
        reservation = LocalPipelineOperationReservation(root)
        saved = reservation.find(operation_id)

        def allocate(state):
            current = workflow.action("detail", run_id=request["run_id"], costume=request.get("costume") or "")
            check_operation_context(current, request)
            if workflow.slots._busy_reason(current):
                raise OperationBlocked(workflow.slots._busy_reason(current))
            if runner_lock_active(root):
                raise OperationWaiting("Waiting for the batch runner to finish.")
            spec = read_library_json(root / "spec.json", pipeline_library_root_for_path(root))
            if request["action"] == "run_available":
                result = plan_available_targets(current, spec, state, request["render_mode"], request.get("scope") or "available", workflow.slots._prerequisite)
            elif request["action"] in {"rerun_view", "rerun_failed"}:
                result = plan_view_targets(current, spec, state, request, workflow.slots._protected, workflow.slots._prerequisite)
            else:
                result = plan_slot_targets(current, spec, state, request, workflow.slots._protected, workflow.slots._prerequisite)
            if not result["targets"] and not result["blocked_views"] and not result["errors"]:
                result["errors"]["batch"] = "No eligible renders are available."
            return result

        if saved is None:
            saved = reservation.reserve_factory(operation_id, request["expected_context"], allocate)
        elif saved.get("expected_context") != request["expected_context"]:
            raise ReservationConflict("The saved reservation belongs to different inputs.")
        if saved.get("status") == "CANCELLED":
            if saved.get("cancelled_by_user"):
                return {"outcome": "CANCELLED", "submitted_candidate_ids": saved.get("committed_candidate_ids", []), "cancel_confirmed": True}
            if saved.get("committed_candidate_ids") and not run.get("stop_requested") and not run.get("slot_paused"):
                outcome = self._handoff(workflow, request, operation_id, reservation, saved)
                if outcome is not None:
                    return outcome
            return {**self._outcome(saved), "outcome": "PARTIAL" if saved.get("committed_candidate_ids") else "BLOCKED", "error": saved.get("cancel_reason") or "Preparation stopped before all targets were committed."}
        if saved.get("status") == "COMMITTED":
            if saved.get("committed_candidate_ids"):
                outcome = self._handoff(workflow, request, operation_id, reservation, saved)
                if outcome is not None:
                    return outcome
            return self._outcome(saved)
        if saved.get("status") != "PREPARING":
            raise ReservationConflict("The reservation is not preparing.")

        preparation = LocalPipelineAvailablePreparationService(workflow)
        try:
            total = len(saved["targets"])
            for index, target in enumerate(saved["targets"], 1):
                if self.repository.get(operation_id).get("cancel_requested"):
                    stopped = reservation.cancel(operation_id, pause=True)
                    return {"outcome": "CANCELLED", "submitted_candidate_ids": stopped["committed_candidate_ids"], "cancel_confirmed": True}
                self.repository.update(operation_id, stage=f"Preparing {target['view']}: {index} of {total}", completed=index - 1, total=total)
                prepared = preparation.prepare(request, operation_id, target["candidate_id"])
                if self.repository.get(operation_id).get("cancel_requested"):
                    stopped = reservation.cancel(operation_id, pause=True)
                    return {"outcome": "CANCELLED", "submitted_candidate_ids": stopped["committed_candidate_ids"], "cancel_confirmed": True}
                if prepared is not None:
                    preparation.commit(request, operation_id, prepared)
            if self.repository.get(operation_id).get("cancel_requested"):
                stopped = reservation.cancel(operation_id, pause=True)
                return {"outcome": "CANCELLED", "submitted_candidate_ids": stopped["committed_candidate_ids"], "cancel_confirmed": True}
            saved = reservation.finish(operation_id)
        except (OperationInputsChanged, ReservationConflict) as exc:
            saved = reservation.cancel(operation_id, reason=str(exc))
            if saved.get("committed_candidate_ids"):
                current = workflow.action("detail", run_id=request["run_id"], costume=request.get("costume") or "")
                if not current.get("stop_requested") and not current.get("slot_paused"):
                    outcome = self._handoff(workflow, request, operation_id, reservation, saved)
                    if outcome is not None:
                        return outcome
            return {**self._outcome(saved), "outcome": "PARTIAL" if saved.get("committed_candidate_ids") else "BLOCKED", "error": str(exc)}
        if saved.get("committed_candidate_ids"):
            outcome = self._handoff(workflow, request, operation_id, reservation, saved)
            if outcome is not None:
                return outcome
        return self._outcome(saved)

    def _handoff(self, workflow, request: dict, operation_id: str, reservation, saved: dict) -> dict | None:
        """Serialize Stop against durable handoff admission, then wake the collector."""
        with self.repository.batch_handoff_lock(request["universe_id"], request["pipeline"],
                                                request["run_id"], request.get("costume") or ""):
            current = self.repository.get(operation_id)
            if current.get("cancel_requested"):
                stopped = reservation.pause_committed(operation_id)
                return {"outcome": "CANCELLED", "submitted_candidate_ids": stopped.get("committed_candidate_ids", []), "cancel_confirmed": True}
            admitted = reservation.admit_handoff(operation_id)
        if not admitted:
            return {**self._outcome(saved), "outcome": "PARTIAL", "error": "The batch is paused; resume it before starting queued renders."}
        workflow.slots.start(request["run_id"], request.get("costume") or "")
        return None

    @staticmethod
    def _outcome(saved: dict) -> dict:
        submitted = saved.get("committed_candidate_ids") or []
        blocked = saved.get("blocked_views") or {}
        errors = saved.get("errors") or {}
        return {"outcome": "PARTIAL" if submitted and (blocked or errors) else "SUCCEEDED" if submitted else "BLOCKED",
                "submitted_candidate_ids": list(submitted), "blocked_views": blocked, "errors": errors}
