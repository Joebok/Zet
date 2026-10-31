"""Shared Luna invocation for comparative local image ranking."""
from __future__ import annotations

from zet.services.llm_role_service import resolve_role_model

from collections.abc import Callable
import hashlib
from pathlib import Path

from zet.services.candidate_review_contract import validate_ranking


def locked_draft_comparison(store, run: dict, pipeline: str, view: str, qualifier: str = "") -> dict | None:
    """Resolve the exact available Draft lock used as ranking-only evidence."""
    records = store.locked_assets(run["character"], run["phase"], pipeline, qualifier, render_mode="draft")
    record = next((item for item in records if item.get("view") == view
                   and str(item.get("qualifier") or "").casefold() == qualifier.casefold()), None)
    if not record:
        return None
    path = Path(record["image_path"])
    return {"kind": "locked_draft", "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "candidate_id": record.get("candidate_id", ""), "batch_id": record.get("batch_id", ""),
            "view": view}


def supplied_ranking_references(
    candidates: list[dict], fallback: Callable[[], list[dict]],
    *, comparisons: list[dict] | None = None, source_roles: tuple[str, ...] | None = None,
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
        if source_roles is not None:
            references = [ref for ref in references if ref.get("role") in source_roles]
            if not references:
                references = fallback()
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
    for comparison in comparisons or []:
        path = Path(comparison["path"])
        key = str(comparison.get("sha256") or path.resolve())
        if key not in indices:
            images.append(path)
            indices[key] = len(images)
        if comparison.get("kind") == "locked_draft":
            if comparison.get("body_only"):
                labels.append(
                    f"Ranking-only comparison: image {indices[key]} is the locked Draft for this view. "
                    "Compare the candidates to its body only, including body proportions, anatomy and silhouette. "
                    "Ignore differences in the mannequin head when matching to the Draft; do not reward or "
                    "penalize head matching. Explain meaningful body matches, drift and quality tradeoffs. "
                    "This comparison is not necessarily a render input.")
                continue
            labels.append(
                f"Ranking-only comparison: image {indices[key]} is the locked Draft for this view. "
                "Consider fidelity to its visible identity, design, proportions and details an important "
                "factor alongside view accuracy, anatomy, source preservation and image quality. "
                "Explain meaningful matches, drift and quality tradeoffs in the ranking reasons. "
                "This comparison is not necessarily a render input.")
            continue
        labels.append(
            f"Ranking-only comparison: image {indices[key]} is selected FRONT Assembly "
            f"{comparison['candidate_id']}. Prioritize matching its head-to-body proportions and identity "
            "when ordering these candidates: float the closest proportionality matches to the top. "
            "Compare relative head size, head width against shoulder width, neck scale, torso/limb "
            "proportions, silhouette and visible identity details. Explain proportion matches or "
            "mismatches in the ranking reasons. Preserve the requested target orientation; account for "
            "foreshortening, occlusion and intentional asymmetry. Do not reward copying FRONT's "
            "pose/camera or inventing hidden features. This comparison was not a render input.")
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
    model = resolve_role_model(paths.config, "image_ranking")
    value, _ = paths.jobs.generate_json(model, "", prompt, schema,
                                      [*(reference_image_paths or []), *image_paths],
                                      task_type="local_image_ranking", role="image_ranking", render_context={}, timeout=timeout, owner=owner or {}, admission=admission)
    return validate_ranking(value, candidate_ids), model
