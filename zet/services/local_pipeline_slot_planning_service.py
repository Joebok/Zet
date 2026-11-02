"""Allocate durable targets for individual character render-slot actions."""
from __future__ import annotations

from pathlib import Path
import random

from zet.services.local_image_pipeline_policy import view_candidate_id
from zet.services.local_pipeline_operation_context import OperationBlocked
from zet.services.render_slot_service import SLOT_COUNT, merge_candidates, render_count, slot_maps


def plan_slot_targets(run: dict, spec: dict, state: dict, request: dict, protected, prerequisite) -> dict:
    action, mode, view = request["action"], request["render_mode"], str(request.get("view") or "").upper()
    if action not in {"generate_slots", "regenerate_slot", "retry_render_slot"} or view not in run.get("views", []):
        raise OperationBlocked("Choose a valid view and render-slot action.")
    slots = slot_maps(run, mode)[view]
    if len(slots) > SLOT_COUNT:
        raise OperationBlocked("Clear surplus legacy candidates before adding renders.")
    index = request.get("slot")
    if index is not None and (type(index) is not int or not 1 <= index <= len(slots)):
        raise OperationBlocked("Choose an available render slot.")
    index = index - 1 if index is not None else None
    candidates = {item["candidate_id"]: item for item in run.get("candidates") or []}
    old = candidates.get(slots[index]) if index is not None else None
    if index is not None and request.get("expected_candidate_id", "") != (old or {}).get("candidate_id", ""):
        raise OperationBlocked("This slot changed. Review its current image before acting.")
    if action == "generate_slots" and old:
        raise OperationBlocked("This slot is occupied. Clear it explicitly first.")
    if action != "generate_slots" and (index is None or not old):
        raise OperationBlocked("Choose an occupied slot.")
    if old and protected(run, old):
        raise OperationBlocked(protected(run, old))
    frozen_retry = action == "retry_render_slot" and bool(old.get("render_input"))
    if not frozen_retry:
        reason = prerequisite(run, view, mode)
        if reason:
            raise OperationBlocked(reason)
    if action == "retry_render_slot" and (old.get("render_status") != "FAILED" or Path(str(old.get("image_path") or "")).is_file()):
        raise OperationBlocked("Render Retry requires a failed image render.")
    count = 1 if index is not None else render_count(request.get("count"))
    indices = [index] if index is not None else [position for position, cid in enumerate(slots) if cid is None][:count]
    if len(indices) != count:
        raise OperationBlocked("Not enough empty slots.")
    all_candidates = merge_candidates(spec, state, include_detached=True)
    template = old or next((item for item in reversed(list(all_candidates.values())) if item.get("view") == view), None)
    if not template:
        raise OperationBlocked("This view has no saved render inputs.")
    if action == "retry_render_slot" and not template.get("render_input") and not template.get("ask_id"):
        raise OperationBlocked("The original retry inputs are unavailable. Regenerate this slot instead.")
    ordinal = max((int(item.get("ordinal") or item["candidate_id"].rsplit("-", 1)[1])
                   for item in all_candidates.values() if item.get("view") == view), default=0)
    targets = []
    for position in indices:
        ordinal += 1
        targets.append({"candidate_id": view_candidate_id(view, ordinal), "view": view, "mode": mode,
            "slot": position + 1, "seed": template.get("seed") if action == "retry_render_slot"
            else str(random.SystemRandom().randrange(0, 2**63 - 1)), "existing": False,
            "previous_candidate_id": (old or {}).get("candidate_id"),
            "template_candidate_id": template["candidate_id"], "ordinal": ordinal,
            "retry": action == "retry_render_slot", "retry_input_frozen": bool(frozen_retry)})
    return {"targets": targets, "blocked_views": {}, "errors": {}}


def plan_view_targets(run: dict, spec: dict, state: dict, request: dict, protected, prerequisite) -> dict:
    """Allocate replacements for occupied slots, preserving per-slot failures."""
    mode, view = request["render_mode"], str(request.get("view") or "").upper()
    maps = slot_maps(run, mode)
    if view not in maps:
        raise OperationBlocked("Unknown character view.")
    candidates = {item["candidate_id"]: item for item in run.get("candidates") or []}
    failed_only = request["action"] == "rerun_failed"
    occupied = [(index + 1, candidates[cid]) for index, cid in enumerate(maps[view]) if cid in candidates
                and (not failed_only or candidates[cid].get("render_status") == "FAILED")]
    if not occupied:
        raise OperationBlocked("No failed renders in this view and mode." if failed_only else "No occupied slots in this view and mode.")
    all_candidates = merge_candidates(spec, state, include_detached=True)
    ordinal = max((int(item.get("ordinal") or item["candidate_id"].rsplit("-", 1)[1])
                   for item in all_candidates.values() if item.get("view") == view), default=0)
    targets, errors = [], {}
    for slot, candidate in occupied:
        single = {**request, "action": "retry_render_slot" if failed_only else "regenerate_slot",
                  "slot": slot, "expected_candidate_id": candidate["candidate_id"]}
        try:
            target = plan_slot_targets(run, spec, state, single, protected, prerequisite)["targets"][0]
            ordinal += 1
            target.update(candidate_id=view_candidate_id(view, ordinal), ordinal=ordinal,
                          recompile=bool(request.get("recompile", False)))
            targets.append(target)
        except (OperationBlocked, ValueError, OSError) as exc:
            errors[candidate["candidate_id"]] = str(exc)
    return {"targets": targets, "blocked_views": {}, "errors": errors}
