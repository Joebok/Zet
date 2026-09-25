"""Shared state and artifact rules for local candidate-based image pipelines."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
import re
from typing import Any


PIPELINE_PAGE_CONFIG: dict[str, dict[str, Any]] = {
    "body-reference": {"key": "body-reference", "label": "Body-Reference", "identity": ("character", "phase"),
                       "review_version": 2, "front_count": 8, "other_count": 4, "candidate_limit": 256,
                       "references": "body-reference-prompt", "analysis": True},
    "head-image": {"key": "head-image", "label": "Head-Image", "identity": ("character", "phase"),
                   "review_version": 2, "front_count": 8, "other_count": 4, "candidate_limit": 256,
                   "references": "optional-front-source", "analysis": False},
    "character-assembly": {"key": "character-assembly", "label": "Character-Assembly", "identity": ("character", "phase"),
                           "review_version": 2, "front_count": 8, "other_count": 4, "candidate_limit": 256,
                           "references": "locked-body-and-head", "analysis": False},
    "costume-dressing": {"key": "costume-dressing", "label": "Costume-Dressing", "identity": ("character", "phase", "costume"),
                         "review_version": 2, "front_count": 8, "other_count": 4, "candidate_limit": 256,
                         "references": "locked-assembly-and-costume", "analysis": False},
}

RUN_STATUS_LABELS = {
    "QUEUED": "Queued", "PREFLIGHT": "Checking inputs", "RUNNING": "Running",
    "STOPPING": "Stopping", "REEVALUATING": "Re-evaluating", "READY_FOR_VIEWS": "Ready for other views",
    "AWAITING_FRONT_ANCHOR": "Awaiting FRONT selection", "AWAITING_HUMAN_SELECTION": "Awaiting selection",
    "REVIEW_REQUIRED": "Review required", "COMPLETE": "Complete", "CANCELLED": "Stopped",
    "STOPPED": "Stopped", "INTERRUPTED": "Interrupted", "ERROR": "Error",
}


def pipeline_page_config(pipeline: str) -> dict[str, Any]:
    """Return the stable page contract for a local image pipeline."""
    try:
        value = PIPELINE_PAGE_CONFIG[str(pipeline).lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported local image pipeline: {pipeline}") from exc
    return {**value, "identity": list(value["identity"])}


def local_pipeline_batch_summary(run: dict[str, Any]) -> dict[str, Any]:
    """Project common progress and stale-selection counts for local pipeline pages."""
    candidates = list(run.get("candidates") or [])
    return {
        "status": str(run.get("status") or "UNKNOWN"),
        "status_label": RUN_STATUS_LABELS.get(str(run.get("status") or ""), str(run.get("status") or "Unknown")),
        "completed_count": sum(bool(item.get("image_path")) for item in candidates),
        "candidate_count": int(run.get("candidate_count") or len(candidates)),
        "selected_view_count": len(run.get("selected_views") or {}),
        "front_anchor": run.get("front_anchor") or "",
        "gate_rejection_count": sum(item.get("status") == "GATE_REJECTED" for item in candidates),
        "stale_selections": list(run.get("stale_selections") or []),
        "error": str(run.get("error") or ""),
    }


def decorate_local_pipeline_detail(run: dict[str, Any], pipeline: str) -> dict[str, Any]:
    """Add the common pipeline identity and status projection to a run detail."""
    result = dict(run)
    result["pipeline_config"] = pipeline_page_config(pipeline)
    result["page_summary"] = local_pipeline_batch_summary(result)
    return result


def upgrade_legacy_review_v1(run_root: Path, spec: dict[str, Any], state: dict[str, Any], *, active: bool = False) -> bool:
    """Upgrade an idle review-v1 run in place, preserving its original JSON and assets.

    Old gate and ranking results cannot be verified against the v2 input/prompt hashes, so
    they remain visible but stale. Candidate images, decisions, selections, and snapshots
    are retained without rerendering or unlocking assets.
    """
    try:
        version = int(spec.get("review_version") or 1)
    except (TypeError, ValueError):
        version = 1
    if version >= 2 or active:
        return False

    legacy_root = run_root / "legacy_review_v1"
    legacy_root.mkdir(parents=True, exist_ok=True)
    for name in ("spec.json", "state.json"):
        source = run_root / name
        destination = legacy_root / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)

    spec["review_version"] = 2
    spec.setdefault("schema_version", 2)
    updates = state.setdefault("candidates", {})
    for candidate in spec.get("candidates", []):
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id:
            continue
        combined = {**candidate, **(updates.get(candidate_id) or {})}
        gates = dict(combined.get("gates") or {})
        for gate in gates.values():
            if isinstance(gate, dict):
                gate.update(status="STALE", stale_reason="Legacy result has no v2 input hash.")
        if combined.get("face_gate") and "face" not in gates:
            face = dict(combined["face_gate"])
            face.update(status="STALE", stale_reason="Legacy result has no v2 input hash.")
            gates["face"] = face
        updates.setdefault(candidate_id, {}).update(gates=gates, legacy_review_stale=True)

    rankings = state.setdefault("rankings", {})
    for ranking in rankings.values():
        if isinstance(ranking, dict) and ranking.get("status") in {"COMPLETE", "EMPTY"}:
            ranking.update(status="STALE", stale_reason="Legacy ranking has no v2 input hashes.")
    state.setdefault("selected_views", {})
    state["review_upgrade"] = {"from_version": 1, "to_version": 2}

    from zet.services.atomic_file_service import write_json_atomic
    write_json_atomic(run_root / "spec.json", spec)
    write_json_atomic(run_root / "state.json", state)
    return True


RUN_STATUSES = {
    "QUEUED", "PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING",
    "AWAITING_FRONT_ANCHOR", "READY_FOR_VIEWS", "AWAITING_HUMAN_SELECTION",
    "REVIEW_REQUIRED", "COMPLETE", "CANCELLED", "INTERRUPTED", "ERROR",
}
CANDIDATE_STATUSES = {
    "PENDING", "QUEUED", "RUNNING", "WAITING_FOR_GATES", "GATE_REJECTED",
    "WAITING_FOR_HUMAN_REVIEW", "COMPLETE", "FAILED",
}
GATE_STATUSES = {"QUEUED", "RUNNING", "COMPLETE", "DISABLED", "STALE", "FAILED"}
RANKING_STATUSES = {"QUEUED", "RUNNING", "EMPTY", "COMPLETE", "STALE", "FAILED"}
ACTIVE_RUN_STATUSES = {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING"}


def gate_result_is_current(
    record: dict[str, Any], *, input_hashes: dict[str, str], prompt_sha256: str,
    policy_status: str | None = None,
) -> bool:
    """Return whether a gate result is current and acceptable under its policy."""
    saved_policy = str(record.get("policy_status") or policy_status or "Active")
    if policy_status and saved_policy != policy_status:
        return False
    if record.get("input_hashes") != input_hashes or record.get("prompt_sha256") != prompt_sha256:
        return False
    if saved_policy == "Disabled":
        return record.get("status") == "DISABLED"
    if saved_policy == "Warning" and record.get("status") == "FAILED":
        return True
    if record.get("status") != "COMPLETE":
        return False
    if saved_policy == "Warning":
        return record.get("verdict") in {"TRUE", "FALSE"}
    return record.get("verdict") == "FALSE"


def clear_candidate_artifacts(run_root: Path, candidate_id: str, image_path: str | Path | None = None) -> None:
    """Delete only this run's generated image and gate-output directories."""
    if not re.fullmatch(r"c\d{3,}", str(candidate_id or "")):
        raise ValueError("Invalid local image candidate ID.")
    root = run_root.resolve()
    for relative in (
        Path("renders") / candidate_id / "Local_Test_Renders",
        Path("analyses") / candidate_id,
    ):
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Candidate artifact path escaped its run.")
        if target.is_dir():
            shutil.rmtree(target)
    if image_path:
        image = Path(image_path).resolve()
        owned_render_root = (root / "renders" / candidate_id / "Local_Test_Renders").resolve()
        if image.is_relative_to(owned_render_root) and image.is_file():
            image.unlink()
