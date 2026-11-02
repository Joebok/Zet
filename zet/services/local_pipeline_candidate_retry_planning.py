"""Plan a candidate retry without changing its artifacts or batch state."""
from __future__ import annotations

from copy import deepcopy

from zet.services.local_character_progression_service import guard_view
from zet.services.local_pipeline_operation_context import OperationBlocked, check_operation_context


def plan_candidate_retry(workflow, run: dict, request: dict, *, proxy_status: str = "UNKNOWN", proxy_answer: dict | None = None) -> dict:
    """Validate a scoped retry and freeze the existing adapter's state changes.

    Proxy status is read by the caller outside batch-state locks. The coordinator
    must revalidate the candidate and relevant proxy attempt before committing.
    """
    check_operation_context(run, request)
    candidate_id = str(request.get("candidate_id") or "")
    candidate = next((item for item in run.get("candidates") or [] if item.get("candidate_id") == candidate_id), None)
    if not candidate:
        raise OperationBlocked("The candidate is no longer available.")
    view, mode = str(candidate.get("view") or ""), candidate.get("render_mode", "draft")
    if view != request.get("view") or mode != request.get("render_mode"):
        raise OperationBlocked("The candidate no longer belongs to this view and mode.")
    if run.get("slot_paused") or run.get("stop_requested"):
        raise OperationBlocked("Resume the stopped batch before retrying this candidate.")
    reason = workflow.slots._protected(run, candidate)
    if reason:
        raise OperationBlocked(reason)
    if workflow.pipeline == "character-assembly":
        try:
            guard_view(run, view)
        except ValueError as exc:
            raise OperationBlocked(str(exc)) from exc
    if workflow.pipeline in {"character-assembly", "costume-dressing"}:
        if view != "FRONT" and workflow.adapter._requires_front_anchor(run) and not run.get("front_anchor"):
            raise OperationBlocked("Select a FRONT candidate before retrying other views.")

    clear_artifacts = workflow.pipeline != "body-reference"
    if workflow.pipeline == "body-reference":
        status = candidate.get("status")
        if status == "FAILED":
            ask_id = str(candidate.get("ask_id") or "")
            answer_status = str((proxy_answer or {}).get("status") or "").upper()
            if ask_id and (proxy_status in {"QUEUED", "RUNNING"} or answer_status == "SUCCESS"):
                changes = {"status": "QUEUED", "render_error": ""}
            else:
                changes = {"status": "PENDING", "render_error": "", "ask_id": "", "image_path": "",
                           "retry_count": int(candidate.get("retry_count") or 0) + 1}
        elif status in {"COMPLETE", "WAITING_FOR_HUMAN_REVIEW", "WAITING_FOR_ANALYSIS"}:
            if candidate.get("luna_status") != "FAILED" and (candidate.get("local_job") or {}).get("status") != "FAILED":
                raise OperationBlocked("This candidate has no failed analysis to retry.")
            changes = {"status": "WAITING_FOR_ANALYSIS",
                       "luna_status": "PENDING" if candidate.get("luna_status") == "FAILED" else candidate.get("luna_status"),
                       "local_job": {} if (candidate.get("local_job") or {}).get("status") == "FAILED" else candidate.get("local_job")}
        else:
            raise OperationBlocked("Only a failed render or analysis can be retried.")
    else:
        changes = {"status": "PENDING", "image_path": "", "ask_id": "", "render_error": "",
                   "retry_count": int(candidate.get("retry_count") or 0) + 1}
        if workflow.pipeline in {"head-image", "head-image-edit"}:
            changes["image_sha256"] = ""
        else:
            changes.update(review_error="", human_review={"decision": "undecided"})
    return {"candidate_id": candidate_id, "view": view, "render_mode": mode,
            "clear_artifacts": clear_artifacts, "candidate": deepcopy(candidate), "changes": changes}
