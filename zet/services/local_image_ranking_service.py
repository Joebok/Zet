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


def review_images_with_luna(*, criteria: str, candidates: list[dict], paths, owner=None,
                            comparisons: tuple[dict, ...] = (),
                            admission=None) -> tuple[list[dict[str, str]], str, str]:
    """Return a comparative rank and full per-image review from one Luna response."""
    candidate_ids = [item["candidate_id"] for item in candidates]
    if not candidate_ids:
        return [], "", ""
    images = [Path(item["image_path"]) for item in candidates]
    evidence_numbers = {}
    digests = {}

    def attach_evidence(item):
        path = Path(item.get("path") or "").resolve()
        if path not in digests:
            try:
                digests[path] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            except OSError:
                digests[path] = None
        digest = digests[path]
        if not digest or (item.get("sha256") and item["sha256"] != digest):
            return "unavailable"
        if digest not in evidence_numbers:
            images.append(path)
            evidence_numbers[digest] = len(images)
        return f"attachment {evidence_numbers[digest]}"

    lines = [
        "Rank only the finished outputs listed below. Attachment numbers are one-based. "
        "Every other attachment is evidence only. For every candidate ID, describe visible details "
        "from its assigned output before comparing it with that candidate's evidence. "
        "Use saved render prompts as descriptions of the intended result. Image numbers inside those "
        "prompts refer to original render inputs, so use the per-candidate mapping below.",
        criteria,
        "Finished outputs to rank:",
    ]
    lines.extend(f"Attachment {number}: candidate {item['candidate_id']}, slot {item['slot']}"
                 for number, item in enumerate(candidates, 1))
    saved_prompts = {}
    for item in candidates:
        request = item.get("render_request") or {}
        lines.append(f"\nEvidence for candidate {item['candidate_id']}:")
        for number, reference in enumerate(request.get("inputs") or [], 1):
            details = ", ".join(f"{key}={reference[key]}" for key in
                                ("role", "prompt_role", "view", "source_view", "body_view", "head_view", "label")
                                if reference.get(key))
            lines.append(f"Render input {number}: {attach_evidence(reference)} ({details or 'captured input'})")
        if not request.get("inputs"):
            lines.append("No captured render inputs.")
        saved = request.get("prompt") or item.get("prompt")
        if saved:
            number = saved_prompts.setdefault(saved, len(saved_prompts) + 1)
            lines.append(f"Saved render prompt {number} applies to this candidate.")
        else:
            lines.append("No saved render prompt.")
    for comparison in comparisons:
        lines.append(f"\nRanking-only comparison: {attach_evidence(comparison)}. {comparison['label']}")
    for saved, number in saved_prompts.items():
        lines.append(f"\nSaved render prompt {number}:\n{saved}")
    prompt = "\n".join(lines)
    schema = {"type": "object", "properties": {"ranking": {"type": "array", "items": {
        "type": "object", "properties": {"candidate_id": {"type": "string"}, "review": {"type": "string"}},
        "required": ["candidate_id", "review"], "additionalProperties": False}}},
        "required": ["ranking"], "additionalProperties": False}
    model = resolve_role_model(paths.config, "image_ranking")
    value, _ = paths.jobs.generate_json(model, "", prompt, schema,
        images, task_type="local_image_ranking",
        role="image_ranking", render_context={}, timeout=1800, owner=owner or {}, admission=admission)
    return validate_ranking(value, candidate_ids, require_review=True), model, prompt
