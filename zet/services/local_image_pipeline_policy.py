"""Shared state and artifact rules for local candidate-based image pipelines."""
from __future__ import annotations

import shutil
from pathlib import Path
import re
from typing import Any


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
) -> bool:
    """Return whether a gate result belongs to the current inputs and prompt."""
    return (
        record.get("status") in {"COMPLETE", "DISABLED"}
        and record.get("verdict") == "FALSE"
        and record.get("input_hashes") == input_hashes
        and record.get("prompt_sha256") == prompt_sha256
    )


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
