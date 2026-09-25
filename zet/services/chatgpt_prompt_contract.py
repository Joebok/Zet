from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

CHATGPT_PROMPT_SCHEMA_VERSION = 2
CHATGPT_ENGINE_PROFILE = "chatgpt_images_2_5_v1"

IMAGE_INPUT_ROLES = {
    "edit_base",
    "subject_reference",
    "costume_reference",
    "object_reference",
    "group_reference",
    "background_reference",
    "style_reference",
}
RENDER_MODES = {"generate", "edit", "composite"}

_ROLE_BY_SLOT = {
    "head_image_source": "edit_base",
    "body_reference": "edit_base",
    "head_image": "subject_reference",
    "front_assembly": "subject_reference",
    "character_assembly": "edit_base",
    "scene_appearance_source": "edit_base",
    "identity_key": "edit_base",
    "supporting_subject": "subject_reference",
    "supporting_object": "object_reference",
    "background": "background_reference",
    "backdrop": "background_reference",
    "element_reference": "group_reference",
    "story_reference": "subject_reference",
}

_SEMANTIC_NULL_RE = re.compile(r"(?i)(?:^|[,:;]\s*)(?:none|n/a|not applicable)(?=$|[,.!?;])", re.MULTILINE)
_UNRESOLVED_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")
_REPEATED_PHRASE_RE = re.compile(r"(?i)\b([^,.;]{4,80})\s*,\s*\1\b")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        values: Iterable[Any] = [value]
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = value
    else:
        values = []
    return [text for item in values if (text := str(item or "").strip())]


def _prompt_role(reference: Mapping[str, Any], default_role: str) -> str:
    explicit = str(reference.get("prompt_role") or "").strip().lower()
    if explicit:
        return explicit
    slot = str(reference.get("role") or "").strip().lower()
    if slot in _ROLE_BY_SLOT:
        return _ROLE_BY_SLOT[slot]
    category = str(reference.get("category") or "").strip().lower()
    semantic = f"{slot} {category}"
    if any(token in semantic for token in ("prop", "object", "thing")):
        return "object_reference"
    if any(token in semantic for token in ("background", "backdrop", "place", "location")):
        return "background_reference"
    if "costume" in semantic:
        return "costume_reference"
    if "group" in semantic:
        return "group_reference"
    if "style" in semantic:
        return "style_reference"
    return default_role


def build_image_inputs(
    references: Iterable[Mapping[str, Any]],
    *,
    render_mode: str,
    default_role: str = "subject_reference",
    applies_to: str = "",
) -> list[dict[str, Any]]:
    """Build the one authoritative, ordered image-input contract."""
    inputs = []
    for index, reference in enumerate(references, start=1):
        item = dict(reference)
        prompt_role = _prompt_role(item, default_role)
        inputs.append({
            "index": index,
            "role": prompt_role,
            "label": str(item.get("label") or item.get("role") or f"Reference {index}").strip(),
            "tag": str(item.get("tag") or "").strip(),
            "path": str(item.get("path") or "").strip(),
            "applies_to": str(item.get("applies_to") or item.get("applies_to_element_id") or applies_to).strip(),
            "preserve": _strings(item.get("preserve")),
            "change": _strings(item.get("change")),
            "ignore": _strings(item.get("ignore")),
            "notes": str(item.get("notes") or "").strip(),
            "source_role": str(item.get("role") or "").strip(),
            "assignments": [dict(assignment) for assignment in item.get("assignments") or []],
        })
    validate_image_inputs(inputs, render_mode)
    return inputs


def validate_image_inputs(image_inputs: list[Mapping[str, Any]], render_mode: str) -> None:
    if render_mode not in RENDER_MODES:
        raise ValueError(f"Unsupported ChatGPT render mode: {render_mode}")
    indexes = [item.get("index") for item in image_inputs]
    if indexes != list(range(1, len(image_inputs) + 1)):
        raise ValueError("ChatGPT image input indexes must be contiguous and one-based.")
    invalid_roles = sorted({str(item.get("role") or "") for item in image_inputs} - IMAGE_INPUT_ROLES)
    if invalid_roles:
        raise ValueError(f"Unsupported ChatGPT image input role(s): {', '.join(invalid_roles)}")
    edit_base_count = sum(item.get("role") == "edit_base" for item in image_inputs)
    if render_mode == "generate" and edit_base_count:
        raise ValueError("Generate mode cannot contain an edit_base image input.")
    if render_mode == "edit" and edit_base_count != 1:
        raise ValueError("Edit mode requires exactly one edit_base image input.")
    if render_mode == "composite" and edit_base_count > 1:
        raise ValueError("Composite mode permits at most one edit_base image input.")


def enrich_reference_files(
    references: Iterable[Mapping[str, Any]], image_inputs: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    enriched = []
    for reference, image_input in zip(references, image_inputs, strict=True):
        item = dict(reference)
        item["image_index"] = image_input["index"]
        item["prompt_role"] = image_input["role"]
        item["applies_to"] = image_input.get("applies_to", "")
        item["preserve"] = list(image_input.get("preserve") or [])
        item["change"] = list(image_input.get("change") or [])
        item["ignore"] = list(image_input.get("ignore") or [])
        item["notes"] = str(image_input.get("notes") or "")
        item["assignments"] = [dict(assignment) for assignment in image_input.get("assignments") or []]
        enriched.append(item)
    return enriched


def manifest_contract(render_mode: str, image_inputs: list[Mapping[str, Any]]) -> dict[str, Any]:
    validate_image_inputs(image_inputs, render_mode)
    return {
        "prompt_schema_version": CHATGPT_PROMPT_SCHEMA_VERSION,
        "engine_profile": CHATGPT_ENGINE_PROFILE,
        "render_mode": render_mode,
        "image_inputs": [dict(item) for item in image_inputs],
    }


def image_input_prompt(image_inputs: list[Mapping[str, Any]]) -> str:
    if not image_inputs:
        return "No input images. Generate the requested image from the authored description."
    lines = []
    for item in image_inputs:
        label = str(item.get("label") or item.get("tag") or "reference image").strip()
        target = str(item.get("applies_to") or "").strip()
        lines.append(f"- **Image {item['index']} — {item['role']}:** {label}{f' (applies to {target})' if target else ''}.")
        for heading, key in (("Preserve", "preserve"), ("Change", "change"), ("Ignore", "ignore")):
            values = _strings(item.get(key))
            if values:
                lines.append(f"  {heading}: {'; '.join(values)}.")
        notes = str(item.get("notes") or "").strip()
        if notes:
            lines.append(f"  Notes: {notes.rstrip('.')}.")
        # The first assignment is already rendered above; add the remaining uses of this image.
        for assignment in (item.get("assignments") or [])[1:]:
            lines.append(f"  For {assignment.get('applies_to') or 'the scene'}, use as {assignment.get('prompt_role') or item['role']}.")
            for label, key in (("Preserve", "preserve"), ("Change", "change"), ("Ignore", "ignore")):
                values = _strings(assignment.get(key))
                if values:
                    lines.append(f"  {label} for this assignment: {'; '.join(values)}.")
            if assignment.get("notes"):
                lines.append(f"  Notes for this assignment: {str(assignment['notes']).rstrip('.')}.")
    return "\n".join(lines)


def change_contract_prompt(render_mode: str, image_inputs: list[Mapping[str, Any]]) -> str:
    if render_mode == "generate":
        return "Create a new image that implements the authored task and subject facts."
    edit_base = next((item for item in image_inputs if item.get("role") == "edit_base"), None)
    if render_mode == "edit":
        return f"Edit Image {edit_base['index']}. Change only the properties explicitly requested below."
    if edit_base:
        return (
            f"Use Image {edit_base['index']} as the composition base and combine only the explicitly assigned content from the other images."
        )
    return "Create a new composite from the assigned image inputs."


def preserve_contract_prompt(render_mode: str, image_inputs: list[Mapping[str, Any]]) -> str:
    if render_mode == "generate":
        return "Treat the authored visual specification as authoritative; do not add unrequested content."
    if render_mode == "edit":
        return "Keep every identity, geometry, composition, camera, lighting, and background property not explicitly changed unchanged."
    if any(item.get("role") == "edit_base" for item in image_inputs):
        return "Preserve all unassigned base-image content. Each other image controls only its stated role."
    return "Each image controls only its stated subject, costume, object, group, background, or style role."


def change_preserve_prompt(render_mode: str, image_inputs: list[Mapping[str, Any]]) -> str:
    return f"{change_contract_prompt(render_mode, image_inputs)} {preserve_contract_prompt(render_mode, image_inputs)}"


def prompt_contract_values(render_mode: str, image_inputs: list[Mapping[str, Any]]) -> dict[str, str]:
    validate_image_inputs(image_inputs, render_mode)
    return {
        "CHATGPT_IMAGE_INPUTS": image_input_prompt(image_inputs),
        "CHATGPT_CHANGE_CONTRACT": change_contract_prompt(render_mode, image_inputs),
        "CHATGPT_PRESERVE_CONTRACT": preserve_contract_prompt(render_mode, image_inputs),
        "CHATGPT_CHANGE_PRESERVE_CONTRACT": change_preserve_prompt(render_mode, image_inputs),
    }


def compile_prompt_diagnostics(
    prompt: str, image_inputs: list[Mapping[str, Any]], render_mode: str
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        validate_image_inputs(image_inputs, render_mode)
    except ValueError as exc:
        errors.append(str(exc))
    unresolved_inputs = [
        str(item.get("label") or item.get("tag") or item.get("index"))
        for item in image_inputs
        if not str(item.get("path") or "").strip()
    ]
    if unresolved_inputs:
        errors.append(f"Unresolved ChatGPT image input path(s): {', '.join(unresolved_inputs)}")
    unresolved = sorted(set(_UNRESOLVED_PLACEHOLDER_RE.findall(prompt)))
    if unresolved:
        errors.append(f"Unresolved prompt placeholders: {', '.join(unresolved)}")
    semantic_null_line = any(
        line.strip().lstrip("-* ").rstrip(".!?;:").casefold() in {"none", "n/a", "not applicable"}
        for line in prompt.splitlines()
    )
    if semantic_null_line or _SEMANTIC_NULL_RE.search(prompt):
        warnings.append("Prompt contains a semantic null value (none/n/a/not applicable).")
    if _REPEATED_PHRASE_RE.search(prompt):
        warnings.append("Prompt contains a repeated adjacent phrase.")
    bullets = [line.strip().casefold() for line in prompt.splitlines() if line.strip().startswith("-")]
    if len(bullets) != len(set(bullets)):
        warnings.append("Prompt contains a duplicate generated clause.")
    if re.search(r"(?im)^.*\b(?:walk|walking|run|running|airborne|flying)\b.*\b(?:stand|standing|stationary)\b.*$", prompt):
        warnings.append("Prompt may contain conflicting action and posture instructions.")
    if len(image_inputs) > 6:
        warnings.append("Prompt uses more than six image inputs; verify that every reference is necessary.")
    for item in image_inputs:
        marker = f"Image {item['index']}"
        if marker not in prompt:
            errors.append(f"Prompt does not identify {marker}.")
    return {
        "prompt_schema_version": CHATGPT_PROMPT_SCHEMA_VERSION,
        "engine_profile": CHATGPT_ENGINE_PROFILE,
        "render_mode": render_mode,
        "image_input_count": len(image_inputs),
        "errors": errors,
        "warnings": warnings,
    }


def write_prompt_diagnostics(
    path: Path, prompt: str, image_inputs: list[Mapping[str, Any]], render_mode: str
) -> dict[str, Any]:
    diagnostics = compile_prompt_diagnostics(prompt, image_inputs, render_mode)
    path.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    if diagnostics["errors"]:
        raise ValueError("Invalid ChatGPT image prompt: " + " ".join(diagnostics["errors"]))
    return diagnostics
