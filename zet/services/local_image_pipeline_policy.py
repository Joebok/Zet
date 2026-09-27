"""Shared state and artifact rules for local candidate-based image pipelines."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
import re
from functools import wraps
import inspect
from dataclasses import dataclass, asdict
from typing import Any

from zet.services.workflow_storage import file_lock


@dataclass(frozen=True)
class LocalImagePipelineConfig:
    """Generation-specific inputs for the shared local image review workflow."""

    key: str
    label: str
    identity: tuple[str, ...]
    generation_adapter: str
    compiler: str
    reference_roles: tuple[str, ...]
    optional_front_source: bool
    gate_profile: str
    ranking_profile: str
    prerequisites: tuple[str, ...] = ()
    front_anchor_rule: str = "optional"
    front_count: int = 8
    other_count: int = 4
    candidate_limit: int = 256
    review_version: int = 2

    def page_contract(self) -> dict[str, Any]:
        value = asdict(self)
        value["identity"] = list(self.identity)
        value["reference_roles"] = list(self.reference_roles)
        value["prerequisites"] = list(self.prerequisites)
        value["capabilities"] = ["human_review", "ranking", "observations"]
        if self.front_anchor_rule != "none":
            value["capabilities"].append("front_anchor")
        if self.optional_front_source:
            value["capabilities"].append("optional_source_image")
        if self.key == "costume-dressing":
            value["capabilities"].append("costume")
        # Kept as an observation capability for clients of the former page contract.
        value["analysis"] = True
        return value


LOCAL_IMAGE_PIPELINES: dict[str, LocalImagePipelineConfig] = {
    "body-reference": LocalImagePipelineConfig(
        "body-reference", "Body-Reference", ("character", "phase"), "body-reference", "body_reference",
        (), False, "body-reference", "body-reference", front_anchor_rule="required"),
    "head-image": LocalImagePipelineConfig(
        "head-image", "Head-Image", ("character", "phase"), "head-image", "head_image",
        ("front_reference",), True, "head-image", "head-image", front_anchor_rule="required"),
    "character-assembly": LocalImagePipelineConfig(
        "character-assembly", "Character-Assembly", ("character", "phase"), "character-assembly",
        "character_assembly", ("body_reference", "head_image"), False, "character-assembly",
        "character-assembly", prerequisites=("Body-Reference", "Head-Image")),
    "costume-dressing": LocalImagePipelineConfig(
        "costume-dressing", "Costume-Dressing", ("character", "phase", "costume"), "costume-dressing",
        "costume_dressing", ("character_assembly", "costume"), False, "costume-dressing",
        "costume-dressing", prerequisites=("Character-Assembly", "costume")),
}

PIPELINE_PAGE_CONFIG: dict[str, dict[str, Any]] = {
    key: config.page_contract() for key, config in LOCAL_IMAGE_PIPELINES.items()
}

RUN_STATUS_LABELS = {
    "QUEUED": "Queued", "PREFLIGHT": "Checking inputs", "RUNNING": "Running",
    "STOPPING": "Stopping", "REEVALUATING": "Re-evaluating", "READY_FOR_VIEWS": "Ready for other views",
    "AWAITING_FRONT_ANCHOR": "Awaiting FRONT selection", "AWAITING_HUMAN_SELECTION": "Awaiting selection",
    "REVIEW_REQUIRED": "Review required", "COMPLETE": "Complete", "CANCELLED": "Stopped",
    "STOPPED": "Stopped", "INTERRUPTED": "Interrupted", "ERROR": "Error",
}

VIEW_CANDIDATE_PREFIXES = {
    "FRONT": "F-", "FRONT_LEFT_3_4": "FL-", "FRONT_RIGHT_3_4": "FR-",
    "LEFT_PROFILE": "PL-", "RIGHT_PROFILE": "PR-", "BACK": "B-",
    "BACK_RIGHT_3_4": "BR-", "BACK_LEFT_3_4": "BL-",
}


def view_candidate_id(view: str, ordinal: int) -> str:
    """Return the stable, view-prefixed ID for a candidate within one view."""
    try:
        prefix = VIEW_CANDIDATE_PREFIXES[str(view)]
    except KeyError as exc:
        raise ValueError(f"Unknown local image candidate view: {view}") from exc
    if int(ordinal) < 1:
        raise ValueError("Candidate ordinal must be positive.")
    return f"{prefix}{int(ordinal):03d}"


def front_anchor_approved(candidate: dict[str, Any]) -> bool:
    """Accept a human Pass or the recorded autogenerate selection approval."""
    decision = (candidate.get("human_review") or {}).get("decision")
    approval = candidate.get("autogenerate_approval")
    return decision == "keep" or (decision != "reject" and isinstance(approval, dict)
                                  and bool(approval.get("approved_at")))


def resume_cancelled_autogenerate_state(run: dict[str, Any], state: dict[str, Any],
                                        *, ready_status: str) -> None:
    """Preserve completed work when reopening an autogenerate-owned stopped batch."""
    for candidate in run.get("candidates") or []:
        image = Path(str(candidate.get("image_path") or ""))
        if candidate.get("status") in {"QUEUED", "RUNNING"} and not image.is_file():
            state.setdefault("candidates", {}).setdefault(candidate["candidate_id"], {}).update(
                status="PENDING", image_path="", ask_id="",
            )
    state.update(status=ready_status if run.get("front_anchor") else "QUEUED",
                 stop_requested=False, error="", target_views=[], target_candidate_ids=[])


def pipeline_page_config(pipeline: str) -> dict[str, Any]:
    """Return the stable page contract for a local image pipeline."""
    try:
        value = PIPELINE_PAGE_CONFIG[str(pipeline).lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported local image pipeline: {pipeline}") from exc
    return {**value, "identity": list(value["identity"])}


def local_image_pipeline_config(pipeline: str) -> LocalImagePipelineConfig:
    """Return the generation adapter configuration for a supported pipeline."""
    try:
        return LOCAL_IMAGE_PIPELINES[str(pipeline).lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported local image pipeline: {pipeline}") from exc


def local_pipeline_batch_summary(run: dict[str, Any]) -> dict[str, Any]:
    """Project common progress and stale-selection counts for local pipeline pages."""
    candidates = list(run.get("candidates") or [])
    completed_count = 0
    for item in candidates:
        image = Path(str(item.get("image_path") or ""))
        completed_count += int(image.is_file() and image.stat().st_size > 0)
    return {
        "status": str(run.get("status") or "UNKNOWN"),
        "status_label": RUN_STATUS_LABELS.get(str(run.get("status") or ""), str(run.get("status") or "Unknown")),
        "completed_count": completed_count,
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
    candidates = []
    counts = {"PENDING": 0, "QUEUED": 0, "RUNNING": 0, "COMPLETE": 0, "FAILED": 0}
    for source in result.get("candidates") or []:
        candidate = dict(source)
        image = Path(str(candidate.get("image_path") or ""))
        if image.is_file() and image.stat().st_size > 0:
            render_status = "COMPLETE"
        elif candidate.get("render_error"):
            render_status = "FAILED"
        elif candidate.get("status") == "RUNNING":
            render_status = "RUNNING"
        elif candidate.get("status") == "QUEUED" and candidate.get("ask_id"):
            render_status = "QUEUED"
        else:
            render_status = "PENDING"
        candidate["render_status"] = render_status
        counts[render_status] += 1
        candidates.append(candidate)
    result["candidates"] = candidates
    result["render_progress"] = {
        **counts,
        "total": len(candidates),
        "remaining": counts["PENDING"] + counts["QUEUED"] + counts["RUNNING"] + counts["FAILED"],
    }
    result["pipeline_config"] = pipeline_page_config(pipeline)
    result["page_summary"] = local_pipeline_batch_summary(result)
    return result


def mutate_local_run_state(run_root: Path, mutator) -> dict[str, Any]:
    """Apply a short read/modify/write transaction to a run's state file."""
    state_path = run_root / "state.json"
    with file_lock(run_root / "state.lock"):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        mutator(state)
        from zet.services.atomic_file_service import write_json_atomic
        write_json_atomic(state_path, state)
        return state


def serialize_local_run_state(function):
    """Serialize one short run-state workflow against runner state updates."""
    signature = inspect.signature(function)

    @wraps(function)
    def wrapped(self, *args, **kwargs):
        bound = signature.bind(self, *args, **kwargs)
        run_id = str(bound.arguments.get("run_id") or "")
        costume = str(bound.arguments.get("costume") or "")
        resolver = getattr(self, "_run_root", None) or getattr(self, "_root")
        try:
            root = resolver(run_id, costume)
        except TypeError:
            root = resolver(run_id)
        with file_lock(Path(root) / "state.lock"):
            return function(self, *args, **kwargs)

    return wrapped


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
    if not re.fullmatch(r"(?:F|FL|FR|PL|PR|B|BR|BL)-\d{3,}", str(candidate_id or "")):
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
