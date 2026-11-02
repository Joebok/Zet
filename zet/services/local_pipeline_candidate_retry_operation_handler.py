"""Recoverable, candidate-scoped review retry handoff."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from zet.services.local_image_evaluation_service import supersede_evaluations
from zet.services.local_pipeline_candidate_retry_planning import plan_candidate_retry
from zet.services.local_pipeline_candidate_retry_reservation import LocalPipelineCandidateRetryReservation
from zet.services.local_pipeline_operation_context import OperationBlocked, OperationInputsChanged, OperationWaiting, check_operation_context
from zet.services.local_pipeline_operation_reservation import ReservationConflict
from zet.services.storage_recovery_service import submit_recovered_run
from zet.services.workflow_storage import file_lock


class LocalPipelineCandidateRetryOperationHandler:
    """Checkpoint artifact isolation and the state reset before waking a runner."""

    def __init__(self, repository, resolve_workflow):
        self.repository = repository
        self.resolve_workflow = resolve_workflow

    @staticmethod
    def can_resume(record: dict) -> bool:
        return record.get("request", {}).get("action") == "retry_candidate"

    def __call__(self, record: dict) -> dict:
        request, operation_id = record["request"], record["id"]
        workflow = self.resolve_workflow(request["universe_id"], request["pipeline"])
        if workflow.pipeline != request["pipeline"] or workflow.app.universe_id != request["universe_id"]:
            raise ValueError("The operation does not belong to this pipeline and universe.")
        run_id, costume = request["run_id"], request.get("costume") or ""
        run = workflow.action("detail", run_id=run_id, costume=costume)
        root = Path(run["root"])
        reservation = LocalPipelineCandidateRetryReservation(root)
        saved = reservation.find(operation_id)
        if saved is None:
            candidate = next((item for item in run.get("candidates") or []
                              if item.get("candidate_id") == request["candidate_id"]), None)
            proxy_status, proxy_answer = "UNKNOWN", {}
            if workflow.pipeline == "body-reference" and candidate and candidate.get("status") == "FAILED" and candidate.get("ask_id"):
                proxy_status, proxy_answer = workflow.adapter._proxy_answer(candidate["ask_id"])
            plan = plan_candidate_retry(workflow, run, request, proxy_status=proxy_status, proxy_answer=proxy_answer)
        else:
            plan = saved.get("plan")
            if not isinstance(plan, dict):
                raise ReservationConflict("The saved candidate retry has no transition plan.")
            if saved.get("status") == "CANCELLED":
                return {"outcome": "CANCELLED" if self.repository.get(operation_id).get("cancel_requested") else "BLOCKED",
                        "cancel_confirmed": True, "error": "The candidate retry reservation was cancelled; review the batch before submitting again."}

        # Both legacy runner and independent slot collector must be idle while
        # the candidate is detached and its state is reset. Stop takes the
        # batch handoff lock before changing the batch cancellation state.
        with self.repository.batch_handoff_lock(request["universe_id"], request["pipeline"], run_id, costume):
            if self.repository.get(operation_id).get("cancel_requested"):
                if saved and saved.get("status") == "PREPARING":
                    reservation.cancel(operation_id)
                if saved and saved.get("status") == "COMMITTED":
                    reservation.discard(operation_id)
                    return {"outcome": "PARTIAL", "cancel_confirmed": True,
                            "error": "The candidate reset committed before Stop. Review its state before retrying."}
                return {"outcome": "CANCELLED", "cancel_confirmed": True}
            if saved and saved.get("status") == "PREPARING" and saved.get("phase") == "RESTORING":
                reservation.cancel(operation_id)
                return {"outcome": "BLOCKED", "error": "The earlier retry was restored; review the batch before submitting again."}
            try:
                with file_lock(root / "runner.lock", timeout=0), file_lock(root / "slot_runner.lock", timeout=0):
                    if saved is None:
                        def validate(state):
                            current = workflow.action("detail", run_id=run_id, costume=costume)
                            check_operation_context(current, request)
                            fresh_status, fresh_answer = proxy_status, proxy_answer
                            current_candidate = next((item for item in current.get("candidates") or []
                                                      if item.get("candidate_id") == request["candidate_id"]), None)
                            if workflow.pipeline == "body-reference" and current_candidate and current_candidate.get("ask_id"):
                                fresh_status, fresh_answer = workflow.adapter._proxy_answer(current_candidate["ask_id"])
                            current_plan = plan_candidate_retry(workflow, current, request,
                                                                proxy_status=fresh_status, proxy_answer=fresh_answer)
                            if current_plan["changes"] != plan["changes"]:
                                raise OperationInputsChanged("The candidate's proxy attempt changed; review it before retrying.")
                            plan["state_candidate"] = deepcopy((reservation._read().get("candidates") or {}).get(request["candidate_id"]))
                            spec = root / "spec.json"
                            plan["spec_sha256"] = sha256(spec.read_bytes()).hexdigest() if spec.is_file() else None

                        saved = reservation.reserve(operation_id, request["candidate_id"], request["expected_context"],
                                                    validate, clear_artifacts=plan["clear_artifacts"], plan=plan)
                    if saved.get("status") == "PREPARING":
                        reservation.detach(operation_id)

                        def validate_commit(state, checkpoint):
                            if ((state.get("candidates") or {}).get(request["candidate_id"]) != plan.get("state_candidate")
                                    or (sha256((root / "spec.json").read_bytes()).hexdigest() if (root / "spec.json").is_file() else None) != plan.get("spec_sha256")):
                                raise OperationInputsChanged("The retry candidate changed during preparation.")
                            current = workflow.action("detail", run_id=run_id, costume=costume)
                            if (reservation._read().get("candidates") or {}).get(request["candidate_id"]) != plan.get("state_candidate"):
                                raise OperationInputsChanged("The retry candidate changed during validation.")
                            # Detachment changes the projected render status.
                            # All other candidate and view inputs still match.
                            projected = deepcopy(current)
                            candidate = next((item for item in projected.get("candidates") or []
                                              if item.get("candidate_id") == request["candidate_id"]), None)
                            if candidate is None:
                                raise OperationInputsChanged("The retry candidate disappeared.")
                            for field in ("render_status", "image_path", "render_error"):
                                candidate[field] = plan["candidate"].get(field)
                            check_operation_context(projected, request)
                            if state.get("slot_paused") or state.get("stop_requested"):
                                raise OperationBlocked("The batch was stopped before retry preparation completed.")

                        def apply(state, checkpoint):
                            candidate = state.setdefault("candidates", {}).setdefault(request["candidate_id"], {})
                            candidate.update(deepcopy(plan["changes"]))
                            view = plan["view"]
                            supersede_evaluations(state, {view}, "A candidate in this view is being retried.",
                                                  render_mode=plan["render_mode"])
                            state.setdefault("view_reviews", {}).setdefault(view, {})["ai_observations"] = {
                                "status": "PENDING", "text": "", "auto_started": False}
                            state.update(status="QUEUED", stop_requested=False, target_views=[view],
                                         target_candidate_ids=[request["candidate_id"]],
                                         review_only=workflow.pipeline == "body-reference" and plan["changes"].get("status") == "WAITING_FOR_ANALYSIS")

                        try:
                            reservation.commit(operation_id, validate=validate_commit, apply=apply)
                        except (OperationBlocked, OperationInputsChanged):
                            reservation.cancel(operation_id)
                            raise
            except TimeoutError as exc:
                raise OperationWaiting("The batch runner is busy; retry preparation will resume shortly.") from exc

        # Cleanup is scoped to this operation's detached directory. A crash
        # here leaves a committed checkpoint and can safely repeat cleanup.
        reservation.discard(operation_id)
        if self.repository.get(operation_id).get("cancel_requested"):
            return {"outcome": "PARTIAL", "cancel_confirmed": True,
                    "error": "The candidate reset committed before Stop. Review its state before retrying."}
        options = {"views": {plan["view"]}, "candidate_ids": {request["candidate_id"]}}
        if workflow.pipeline in {"character-assembly", "costume-dressing"}:
            options["costume"] = costume
        submit_recovered_run(workflow.adapter, run_id, root, **options)
        with file_lock(root / "state.lock"):
            state = reservation._read()
        if state.get("slot_render_ids") or state.get("slot_review_views") or state.get("final_slot_review_views"):
            workflow.slots.start(run_id, costume)
        return {"outcome": "SUCCEEDED", "candidate_id": request["candidate_id"], "view": plan["view"]}
