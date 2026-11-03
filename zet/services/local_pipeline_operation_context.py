"""Compact, metadata-only character operation input fingerprints."""
from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy


class OperationInputsChanged(ValueError):
    """The displayed action inputs no longer match the batch."""


class OperationWaiting(Exception):
    """The batch is temporarily occupied and preparation can retry later."""


class OperationBlocked(ValueError):
    """The action needs a user correction before it can be submitted again."""


def check_operation_context(run: dict, request: dict) -> None:
    """Reject a stale displayed context before starting a domain transition."""
    mode = request.get("render_mode")
    view = str(request.get("view") or "")
    if request.get("action") == "run_available" and request.get("scope") == "front":
        view = "FRONT"
    if request.get("action") == "reevaluate":
        current = evaluation_context(run, mode, view)
    elif request.get("action") == "retry_candidate":
        current = candidate_retry_context(run, mode, str(request.get("candidate_id") or ""))
    else:
        current = operation_context(run, mode, view)
    expected = request.get("expected_context")
    if (not isinstance(expected, str) or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
            or not hmac.compare_digest(current, expected)):
        raise OperationInputsChanged("Inputs changed. Review the batch and submit the action again.")


def check_reserved_operation_context(run: dict, request: dict, reservation: dict) -> None:
    """Compare inputs after accounting for this operation's own slot commits.

    This must run under the batch state lock immediately before a target commit.
    It verifies the current slot still belongs to the reservation before masking
    the operation's own newly allocated IDs for comparison with the original view.
    """
    projected = deepcopy(run)
    committed = set(reservation.get("committed_candidate_ids") or [])
    modes = projected.get("slots_by_mode") or {}
    for target in reservation.get("targets") or []:
        slots = (modes.get(target.get("mode")) or {}).get(target.get("view")) or []
        position = target.get("slot")
        if type(position) is not int or not 1 <= position <= len(slots):
            raise OperationInputsChanged("A reserved slot is no longer available.")
        candidate_id = target.get("candidate_id")
        is_existing = target.get("existing") is True
        previous = target.get("previous_candidate_id")
        expected_slot = candidate_id if is_existing or candidate_id in committed else previous
        if slots[position - 1] != expected_slot:
            raise OperationInputsChanged("A reserved slot changed. Review the batch before retrying.")
        if not is_existing:
            slots[position - 1] = previous
    check_operation_context(projected, request)


def operation_context(run: dict, mode: str, view: str = "") -> str:
    """Fingerprint displayed inputs without depending on render progress labels.

    This is an optimistic comparison token, not a replacement for the existing
    source, file, selection and attempt checks at preparation and publication.
    """
    if mode not in {"draft", "final"}:
        raise ValueError("Choose Draft or Final mode.")
    views = list(run.get("views") or [])
    if view and view not in views:
        raise ValueError("Unknown character view.")
    targets = [view] if view else views
    selections = run.get("selected_views_by_mode") or {
        "draft": run.get("selected_views") or {}, "final": run.get("final_selected_views") or {}}
    selected_ids = set((selections.get("draft") or {}).values()) | set((selections.get("final") or {}).values())
    selected_ids.update((run.get("front_anchor"), run.get("final_front_anchor")))
    selected_candidates = [{key: (candidate.get(key) or "draft") if key == "render_mode" else candidate.get(key)
                            for key in ("candidate_id", "view", "render_mode", "image_path", "image_sha256", "human_review")}
                           for candidate in (run.get("candidates") or [])
                           if candidate.get("candidate_id") in selected_ids]
    selected_candidates.sort(key=lambda candidate: str(candidate.get("candidate_id") or ""))
    slots = (run.get("slots_by_mode") or {}).get(mode) or {}
    snapshot = {
        "version": 1, "run_id": run.get("run_id"), "kind": run.get("kind"),
        "mode": mode, "targets": targets, "stop_generation": run.get("stop_generation", 0),
        "template_revision": run.get("active_template_revision_id"),
        "style_variant": run.get("universe_style_variant"),
        "selections": selections, "selected_candidates": selected_candidates,
        "front_anchor": run.get("front_anchor"), "final_front_anchor": run.get("final_front_anchor"),
        "front_source_sha256": run.get("front_source_sha256"),
        "apply_phase_change": run.get("apply_phase_change"),
        "use_front_anchor": run.get("use_front_anchor"),
        "front_count": run.get("front_count"), "other_count": run.get("other_count"),
        "sources": run.get("sources"),
        "slots": {target: slots.get(target, []) for target in targets},
        "recipes": {target: (run.get("view_reference_recipes") or {}).get(target) for target in targets},
        "render_settings": {target: (run.get("render_settings") or {}).get(target) for target in targets},
    }
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _candidate_retry_context(base: str, candidate: dict) -> str:
    fields = ("candidate_id", "view", "render_mode", "status", "render_status", "review_error",
              "render_error", "ask_id", "image_path", "image_sha256", "retry_count", "luna_status",
              "local_job", "human_review", "seed", "prompt_sha256", "prompt_path", "template_revision_id",
              "render_input", "reference_images")
    snapshot = {"version": 1, "base": base, "candidate": {key: candidate.get(key) for key in fields}}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def candidate_retry_context(run: dict, mode: str, candidate_id: str) -> str:
    """Fingerprint the selected candidate and its view inputs for review retry."""
    candidate = next((item for item in run.get("candidates") or [] if item.get("candidate_id") == candidate_id), None)
    if not candidate or candidate.get("render_mode", "draft") != mode:
        raise OperationInputsChanged("The candidate is no longer available in this mode.")
    return _candidate_retry_context(operation_context(run, mode, str(candidate.get("view") or "")), candidate)


def operation_contexts(run: dict) -> dict:
    contexts = {}
    candidates = run.get("candidates") or []
    for mode in ("draft", "final"):
        views = {view: operation_context(run, mode, view) for view in run.get("views") or []}
        contexts[mode] = {"batch": operation_context(run, mode), "views": views,
                          "candidate_retry": {candidate["candidate_id"]: _candidate_retry_context(views[candidate["view"]], candidate)
                                              for candidate in candidates if candidate.get("candidate_id")
                                              and candidate.get("render_mode", "draft") == mode and candidate.get("view") in views},
                          "evaluation": {"batch": evaluation_context(run, mode),
                                         "views": {view: evaluation_context(run, mode, view) for view in run.get("views") or []}}}
    return contexts


def evaluation_context(run: dict, mode: str, view: str = "") -> str:
    """Include the target image inventory and comparison locks for evaluation."""
    base = operation_context(run, mode, view)
    targets = [view] if view else list(run.get("views") or [])
    images = [{key: candidate.get(key) for key in ("candidate_id", "view", "render_mode", "image_path", "image_sha256", "human_review")}
              for candidate in run.get("candidates") or []
              if candidate.get("view") in targets and candidate.get("render_mode", "draft") == mode]
    images.sort(key=lambda item: str(item.get("candidate_id") or ""))
    locked = run.get("locked_draft_comparisons") or {}
    snapshot = {"version": 1, "base": base, "images": images,
                "draft_comparisons": {target: locked.get(target) for target in targets}}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
