"""Shared Luna invocation for comparative local image ranking."""
from __future__ import annotations

from pathlib import Path

from zet.services.candidate_review_contract import validate_ranking


def rank_images_with_luna(
    *,
    project_root: str | Path,
    model: str,
    prompt: str,
    candidate_ids: list[str],
    image_paths: list[str | Path],
    paths,
    owner=None,
    reference_image_paths: list[str | Path] | None = None,
    timeout: int = 1800,
    admission=None,
) -> tuple[list[dict[str, str]], str]:
    """Run the common structured ranking contract over the supplied image set."""
    if len(candidate_ids) != len(image_paths):
        raise ValueError("Every ranked candidate must have exactly one image.")
    if not candidate_ids:
        return [], ""
    schema = {
        "type": "object",
        "properties": {"ranking": {"type": "array", "items": {
            "type": "object",
            "properties": {"candidate_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["candidate_id", "reason"],
            "additionalProperties": False,
        }}},
        "required": ["ranking"],
        "additionalProperties": False,
    }
    value, _ = paths.jobs.generate_json("codex:" + model.removeprefix("codex:"), "", prompt, schema,
                                      [*(reference_image_paths or []), *image_paths],
                                      task_type="local_image_ranking", timeout=timeout, owner=owner or {}, admission=admission)
    return validate_ranking(value, candidate_ids), model
