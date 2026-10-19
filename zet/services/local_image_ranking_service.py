"""Shared Luna invocation for comparative local image ranking."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from zet.services.candidate_review_contract import validate_ranking


def supplied_ranking_references(
    candidates: list[dict], fallback: Callable[[], list[dict]],
) -> tuple[list[Path], str]:
    """Map captured candidate references to the shared ranking attachment order."""
    images: list[Path] = []
    indices: dict[str, int] = {}
    labels = []
    legacy_references = None
    for candidate in candidates:
        saved = candidate.get("render_input") or {}
        refinement = candidate.get("refinement") or {}
        if "references" in saved:
            references = saved["references"]
        elif "reference_inputs" in refinement:
            references = refinement["reference_inputs"]
        elif "reference_images" in candidate:
            references = candidate["reference_images"]
        else:
            if legacy_references is None:
                legacy_references = fallback()
            references = legacy_references
        mapped = []
        for reference in references:
            path = Path(str(reference.get("path") or reference.get("image_path") or ""))
            if not path.is_file():
                raise ValueError(f"Ranking reference for {candidate['candidate_id']} is missing: {path}")
            key = str(reference.get("sha256") or path.resolve())
            if key not in indices:
                images.append(path)
                indices[key] = len(images)
            description = ", ".join(str(reference[field]) for field in ("role", "view", "label") if reference.get(field))
            mapped.append(f"image {indices[key]} ({description or 'supplied reference'})")
        labels.append(f"Candidate {candidate['candidate_id']} references: " + ("; ".join(mapped) or "none supplied"))
    labels.extend(f"Candidate {candidate['candidate_id']}: image {len(images) + index}"
                  for index, candidate in enumerate(candidates, 1))
    guidance = (
        "Compare each candidate against its mapped supplied references for visible identity, design, "
        "proportions and source preservation. References may show an earlier view; judge consistency "
        "across the change of view, while requiring the requested target orientation. Do not reward "
        "copying the reference camera angle or inventing details on hidden surfaces. "
        "Candidates with no supplied references must be judged on their own visual merits.\nImage mapping:\n"
        + "\n".join(labels)
    )
    return images, guidance


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
