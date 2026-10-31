"""Read-only progress for each local character render mode."""

from pathlib import Path


def progress_by_mode(run):
    """Summarize each mode without using the shared draft progression status."""
    requested = (run.get("character_progression") or {}).get("requested_views") or run.get("views") or []
    candidates = run.get("candidates") or []
    pending_ids = set(run.get("slot_render_ids") or [])
    result = {}
    for mode in ("draft", "final"):
        items = [c for c in candidates if c.get("render_mode", "draft") == mode]
        available_ids = {c.get("candidate_id") for c in items
                         if c.get("image_available") or (c.get("image_path")
                         and (image := Path(c["image_path"])).is_file() and image.stat().st_size > 0)}
        selected = run.get("selected_views" if mode == "draft" else "final_selected_views") or {}
        by_id = {c.get("candidate_id"): c for c in items}
        selected_views = [view for view in requested if (candidate := by_id.get(selected.get(view)))
                          and candidate.get("candidate_id") in available_ids
                          and (candidate.get("human_review") or {}).get("decision") != "reject"]
        active = [c for c in items if c.get("candidate_id") in pending_ids
                  or (c.get("candidate_id") not in available_ids
                      and (c.get("render_status") in {"QUEUED", "RUNNING"}
                           or (c.get("status") in {"QUEUED", "RUNNING"} and c.get("ask_id"))))]
        rankings = run.get("rankings" if mode == "draft" else "final_rankings") or {}
        evaluations = run.get("evaluations" if mode == "draft" else "final_evaluations") or {}
        reviewing = bool(run.get("slot_review_views" if mode == "draft" else "final_slot_review_views")) or any(record.get("status") in {"QUEUED", "RUNNING", "STAGING"}
                        for records in (rankings, evaluations) for record in records.values()
                        if isinstance(record, dict))
        # Match detail's image-first projection for retained/interrupted batches.
        # Explicit pending membership above still belongs to the slot collector.
        failed = [c for c in items if c.get("candidate_id") not in available_ids
                  and (c.get("render_status") == "FAILED" or c.get("render_error"))]
        complete = len(available_ids)
        if not items:
            status = "NOT_STARTED"
        elif run.get("slot_paused") and active:
            status = "STOPPED"
        elif active:
            status = "RUNNING"
        elif reviewing:
            status = "REEVALUATING"
        elif failed:
            status = "FAILED"
        elif len(selected_views) == len(requested) and requested:
            status = "COMPLETE"
        else:
            status = "AWAITING_HUMAN_SELECTION"
        result[mode] = {"status": status, "candidate_count": len(items), "complete_count": complete,
                        "selected_count": len(selected_views), "requested_count": len(requested),
                        "current_views": sorted({c.get("view") for c in active if c.get("view")})}
    return result
