"""Durable, view-scoped admission of existing character evaluations."""
from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from zet.services.local_image_evaluation_service import mode_field
from zet.services.local_image_workflow_service import LocalImageWorkflowError, reevaluation_reason
from zet.services.local_pipeline_operation_context import OperationBlocked, OperationInputsChanged, check_operation_context
from zet.services.workflow_storage import file_lock


class EvaluationCancelled(Exception):
    pass


class LocalPipelineEvaluationOperationHandler:
    def __init__(self, repository, resolve_workflow):
        self.repository = repository
        self.resolve_workflow = resolve_workflow

    @staticmethod
    def can_resume(record: dict) -> bool:
        return record.get("request", {}).get("action") == "reevaluate"

    @staticmethod
    def _identity(operation_id: str, mode: str, view: str) -> str:
        return uuid5(NAMESPACE_URL, f"zet:local-evaluation:{operation_id}:{mode}:{view}").hex

    def __call__(self, record: dict) -> dict:
        request, operation_id = record["request"], record["id"]
        if not self.can_resume(record):
            raise ValueError("Unsupported evaluation operation.")
        workflow = self.resolve_workflow(request["universe_id"], request["pipeline"])
        if workflow.pipeline != request["pipeline"] or workflow.app.universe_id != request["universe_id"]:
            raise ValueError("The operation does not belong to this pipeline and universe.")
        run_id, costume, mode = request["run_id"], request.get("costume") or "", request["render_mode"]
        run = workflow.action("detail", run_id=run_id, costume=costume)
        root = Path(run["root"])
        staged = dict(record.get("evaluations") or {})
        for view, evaluation in (run.get(mode_field("evaluations", mode)) or {}).items():
            if evaluation.get("evaluation_id") == self._identity(operation_id, mode, view):
                staged[view] = evaluation["evaluation_id"]

        def before_stage(view, evaluation_id, submit):
            # Stop takes this batch's handoff lock before requesting cancellation.
            with self.repository.batch_handoff_lock(request["universe_id"], request["pipeline"], run_id, costume):
                current_operation = self.repository.get(operation_id)
                if current_operation.get("cancel_requested"):
                    raise EvaluationCancelled()
                with file_lock(root / "state.lock"):
                    current = workflow.action("detail", run_id=run_id, costume=costume)
                    check_operation_context(current, request)
                    reason = reevaluation_reason(current, request.get("view") or "", mode)
                    if reason:
                        raise OperationBlocked(reason)
                    result = submit()
                if result.get("evaluation_id") != evaluation_id:
                    raise OperationBlocked("Another evaluation already owns this view.")
                staged[view] = evaluation_id
                self.repository.update(operation_id, stage=f"Staging evaluation: {view}", evaluations=dict(staged))

        try:
            if self.repository.get(operation_id).get("cancel_requested"):
                raise EvaluationCancelled()
            check_operation_context(run, request)
            workflow.reevaluate(run_id, request.get("view") or "", costume=costume, render_mode=mode,
                                operation_id=operation_id, before_stage=before_stage)
        except EvaluationCancelled:
            if staged:
                return {"outcome": "PARTIAL", "evaluations": staged, "cancel_confirmed": True,
                        "error": "Preparation stopped after some evaluations were queued. Review the batch before submitting again."}
            return {"outcome": "CANCELLED", "evaluations": staged, "cancel_confirmed": True}
        except (OperationBlocked, OperationInputsChanged, LocalImageWorkflowError) as exc:
            return {"outcome": "PARTIAL" if staged else "BLOCKED", "evaluations": staged, "error": str(exc)}
        return {"outcome": "SUCCEEDED", "evaluations": staged}
