"""Recoverable admission and handoff for character batch lifecycle transitions."""
from __future__ import annotations

from pathlib import Path

from zet.services.local_pipeline_batch_transition_service import LocalPipelineBatchTransitionService
from zet.services.local_pipeline_operation_reservation import BatchTransitionUncertain
from zet.services.storage_recovery_service import submit_recovered_run


class LocalPipelineBatchOperationHandler:
    """Commit a staged transition against Stop, then wake its existing worker."""

    def __init__(self, repository, resolve_workflow):
        self.repository = repository
        self.resolve_workflow = resolve_workflow

    @staticmethod
    def can_resume(record: dict) -> bool:
        return record.get("request", {}).get("action") in {"start", "resume"}

    def __call__(self, record: dict) -> dict:
        request, operation_id = record["request"], record["id"]
        if not self.can_resume(record):
            raise ValueError("Unsupported batch lifecycle operation.")
        workflow = self.resolve_workflow(request["universe_id"], request["pipeline"])
        transition = LocalPipelineBatchTransitionService(workflow)
        commit = transition.stage(request, operation_id)
        run_id, costume = request["run_id"], request.get("costume") or ""
        with self.repository.batch_handoff_lock(request["universe_id"], request["pipeline"], run_id, costume):
            if self.repository.get(operation_id).get("cancel_requested"):
                return {"outcome": "CANCELLED", "cancel_confirmed": True}
            try:
                checkpoint = commit()
            except BatchTransitionUncertain as exc:
                return {"outcome": "PARTIAL", "error": str(exc)}

        # Both worker entry points recheck the durable batch state after waking.
        # Waking outside the handoff lock lets Stop proceed even if detail or
        # executor scheduling is slow. Replay wakes the same committed work.
        if self.repository.get(operation_id).get("cancel_requested"):
            return {"outcome": "CANCELLED", "cancel_confirmed": True}
        handoff = checkpoint["handoff"]
        if handoff == "slot":
            workflow.slots.start(run_id, costume)
        elif handoff == "runner":
            run = workflow.action("detail", run_id=run_id, costume=costume)
            options = {"costume": costume} if workflow.pipeline in {"character-assembly", "costume-dressing"} else {}
            submit_recovered_run(workflow.adapter, run_id, Path(run["root"]), **options)
        return {"outcome": "SUCCEEDED", "handoff": handoff}
