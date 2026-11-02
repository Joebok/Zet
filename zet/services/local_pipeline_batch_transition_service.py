"""State-only preparation for durable character batch Start and Resume."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from zet.services.local_image_pipeline_policy import resume_cancelled_autogenerate_state
from zet.services.local_image_workflow_service import LocalImageWorkflowError
from zet.services.local_pipeline_cancel_marker import cancellation_marker_digest
from zet.services.local_pipeline_operation_context import OperationBlocked, OperationInputsChanged, check_operation_context
from zet.services.local_pipeline_operation_reservation import BatchTransitionUncertain, LocalPipelineOperationReservation
from zet.services.workflow_storage import file_lock, runner_lock_active


class LocalPipelineBatchTransitionService:
    """Checkpoint one lifecycle transition without submitting a runner or collector.

    The caller must serialize this transition and its handoff with Stop. Replay
    returns the stored handoff without reapplying the state transition.
    """

    def __init__(self, workflow):
        self.workflow = workflow

    def prepare(self, request: dict, operation_id: str) -> dict:
        """Stage and commit without a handoff; intended for isolated callers."""
        return self.stage(request, operation_id)()

    def stage(self, request: dict, operation_id: str):
        """Return a short commit closure after loading and validating detail.

        Production callers must acquire the batch handoff lock only around this
        closure and its subsequent handoff, checking cancellation before both.
        """
        workflow = self.workflow
        if (request.get("pipeline") != workflow.pipeline
                or request.get("universe_id") != workflow.app.universe_id):
            raise ValueError("The operation does not belong to this pipeline and universe.")
        action = request.get("action")
        if action not in {"start", "resume"}:
            raise ValueError("Choose a batch Start or Resume operation.")
        run_id, costume = request["run_id"], request.get("costume") or ""
        run = workflow.action("detail", run_id=run_id, costume=costume)
        root = Path(run["root"])
        reservation = LocalPipelineOperationReservation(root)

        saved = reservation.find_batch_transition(operation_id, action, request["expected_context"])
        if saved is not None:
            try:
                check_operation_context(run, request)
                context_changed = False
            except OperationInputsChanged:
                context_changed = True

            def replay():
                if context_changed:
                    raise BatchTransitionUncertain("Batch inputs changed after the transition; review its handoff before retrying.")
                return reservation.verify_batch_transition(operation_id, action, request["expected_context"])

            return replay

        def revision():
            return (*tuple(sha256((root / name).read_bytes()).digest() for name in ("state.json", "spec.json")),
                    cancellation_marker_digest(root))

        with file_lock(root / "state.lock"):
            observed_revision = revision()
        current = workflow.action("detail", run_id=run_id, costume=costume)
        check_operation_context(current, request)
        if action == "start":
            try:
                workflow.action("start", run_id=run_id, costume=costume)
            except LocalImageWorkflowError as exc:
                raise OperationBlocked(str(exc)) from exc

        def validate():
            if revision() != observed_revision:
                raise OperationInputsChanged("Batch state changed while preparing. Review the batch and submit again.")

        def transition(state):
            if action == "start":
                return "runner"
            if state.get("slot_paused"):
                state["slot_paused"] = False
                return "slot"
            if current.get("status") == "CANCELLED" and current.get("created_by_autogenerate"):
                if runner_lock_active(root):
                    raise OperationBlocked("Wait for the stopped batch runner to finish before resuming.")
                if workflow.pipeline == "body-reference":
                    state["resumed_cancel_marker_sha256"] = cancellation_marker_digest(root)
                ready = "READY_FOR_VIEWS" if workflow.pipeline in {"body-reference", "head-image", "head-image-edit"} else "AWAITING_HUMAN_SELECTION"
                resume_cancelled_autogenerate_state(current, state, ready_status=ready)
                state["updated_at"] = workflow.adapter._now()
                return "runner" if state["status"] == "QUEUED" else "none"
            if current.get("status") != "INTERRUPTED":
                raise OperationBlocked("Only an interrupted batch can be resumed; cancelled batches are terminal.")
            state.update(stop_requested=False, status="QUEUED", updated_at=workflow.adapter._now())
            return "runner"

        def commit():
            return reservation.commit_batch_transition(operation_id, action, request["expected_context"], transition,
                                                       validate=validate)

        return commit
