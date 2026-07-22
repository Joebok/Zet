#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections_with_sources, select_sections
from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Scripts.Job_File_Utils import bundle_output_paths, render_static_prompt_artifacts, safe_filename_fragment, write_json_file
from Scripts.Library_Paths import character_root, pipeline_root
from zet.services.pipeline_compiler_support import (
    expected_output_for_job,
    extract_template_field,
    job_get,
    load_bundle,
    load_body_reference_section_data,
    background_treatment_source_map,
    load_background_treatment,
    load_view_data,
    metadata_source_map,
    normalize_view,
    output_files,
    require_job_field,
    resolve_project_path,
    template_metadata,
    view_instruction,
    reference_by_role,
    reference_files_for_job,
    validate_reference,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_name(value: str) -> str:
    return safe_filename_fragment(value, "Costume")


def costume_path_for_job(project_root: Path, job: dict, character: str, phase: str) -> Path:
    explicit = job_get(job, "Costume Path", "costume_path")
    if explicit:
        return resolve_project_path(project_root, explicit)
    costume = job_get(job, "Costume", "costume") or "Canonical Adventure Gear"
    filename = f"Costume_{safe_name(costume).replace('-', '_')}.md"
    return character_root(project_root) / character / phase / filename


def output_dir_for_job(project_root: Path, job: dict, character: str, phase: str, body_view_token: str, head_view_token: str) -> Path:
    explicit = job_get(job, "Output Directory", "output_directory", "Folder", "folder")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return (
        pipeline_root(project_root)
        / character
        / phase
        / "Costume-Dressing"
        / body_view_token
        / head_view_token
    )


def costume_metadata(costume_path: Path) -> dict[str, str]:
    footwear = extract_template_field(costume_path, ["Footwear"])
    if not footwear:
        footwear = "footwear"
    footwear_contact = extract_template_field(costume_path, ["Footwear Contact", "Footwear Contact Rule"])
    if not footwear_contact:
        footwear_contact = f"Both {footwear} maintain stable ground contact. Do not turn the stance into tiptoe, a raised-foot pose, or a walking step."
    return {
        "COSTUME_NAME": extract_template_field(costume_path, ["Costume Name", "Name"]),
        "COSTUME_ROLE": extract_template_field(costume_path, ["Costume Role", "Role"]),
        "FOOTWEAR": footwear,
        "footwear": footwear,
        "FOOTWEAR_CONTACT": footwear_contact,
        "FOOTWEAR_GROUNDING": f"Both {footwear} remain grounded in a stable standing position.",
    }


def costume_metadata_sources(costume_path: Path) -> dict[str, dict]:
    return {
        "COSTUME_NAME": {
            "source_kind": "template_metadata_field",
            "source_path": str(costume_path),
            "source_label": "Costume Name",
            "metadata_key": "COSTUME_NAME",
            "editable": True,
        },
        "COSTUME_ROLE": {
            "source_kind": "template_metadata_field",
            "source_path": str(costume_path),
            "source_label": "Costume Role",
            "metadata_key": "COSTUME_ROLE",
            "editable": True,
        },
        "FOOTWEAR": {
            "source_kind": "template_metadata_field",
            "source_path": str(costume_path),
            "source_label": "Footwear",
            "metadata_key": "FOOTWEAR",
            "editable": True,
        },
        "footwear": {
            "source_kind": "template_metadata_field",
            "source_path": str(costume_path),
            "source_label": "Footwear",
            "metadata_key": "FOOTWEAR",
            "editable": True,
        },
        "FOOTWEAR_CONTACT": {
            "source_kind": "template_metadata_field",
            "source_path": str(costume_path),
            "source_label": "Footwear Contact",
            "metadata_key": "FOOTWEAR_CONTACT",
            "editable": True,
        },
        "FOOTWEAR_GROUNDING": {
            "source_kind": "template_metadata_field",
            "source_path": str(costume_path),
            "source_label": "Footwear",
            "metadata_key": "FOOTWEAR",
            "editable": True,
        },
    }


_LABELED_BULLET_RE = re.compile(r"^(\s*[-*]\s+)([^:]+):\s*(.*)$")
_EMPTY_SECTION_VALUES = {"", "none", "n/a", "not applicable"}


def _semantic_value(value: str) -> str:
    normalized = str(value or "").strip()
    for _ in range(2):
        normalized = normalized.strip("`").strip().rstrip(".").strip()
    return normalized.strip("`").strip().casefold()


def _clean_section_line(line: str) -> str | None:
    match = _LABELED_BULLET_RE.match(line)
    if not match:
        stripped = re.sub(r"^\s*[-*]\s+", "", line).strip()
        if _semantic_value(stripped) in _EMPTY_SECTION_VALUES:
            return None
        return re.sub(r"\.{2,}$", ".", line.replace("`", "").rstrip())
    prefix, label, raw_value = match.groups()
    if _semantic_value(raw_value) in _EMPTY_SECTION_VALUES:
        return None
    value = raw_value.strip().replace("`", "")
    value = re.sub(r"\.{2,}$", ".", value)
    return f"{prefix}{label.strip()}: {value}"


def _normalize_section_text(text: str) -> str:
    lines = [_clean_section_line(line) for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line is not None).strip()


def _labeled_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in str(text or "").splitlines():
        match = _LABELED_BULLET_RE.match(line)
        if match:
            values[match.group(2).strip().casefold()] = match.group(3).strip()
    return values


def _filter_section_lines(text: str, keep) -> str:
    return "\n".join(line for line in text.splitlines() if keep(line)).strip()


def _is_generic_no_equipment_view_line(line: str) -> bool:
    value = _semantic_value(_LABELED_BULLET_RE.match(line).group(3)) if _LABELED_BULLET_RE.match(line) else _semantic_value(line)
    return "no equipment" in value and ("jewelry only" in value or "no jewelry" in value)


def normalize_costume_dressing_sections(
    sections: dict[str, str],
    sources: dict[str, dict],
    body_view_token: str,
) -> tuple[dict[str, str], dict[str, dict], dict[str, str]]:
    """Compact costume prompt sections without modifying their source files."""
    normalized = dict(sections)
    normalized_sources = dict(sources)
    suppressed: dict[str, str] = {}

    for name, text in list(normalized.items()):
        if name.startswith("COSTUME_") or name.startswith("EQUIPMENT_"):
            compacted = _normalize_section_text(text)
            if compacted:
                normalized[name] = compacted
            else:
                normalized.pop(name, None)
                normalized_sources.pop(name, None)
                suppressed[name] = "normalized to empty"

    costume_facts = normalized.get("COSTUME_DESCRIPTION_FACTS", "")
    costume_values = _labeled_values(costume_facts)
    costume_facts = _filter_section_lines(
        costume_facts,
        lambda line: not (
            (match := _LABELED_BULLET_RE.match(line))
            and match.group(2).strip().casefold() == "costume name"
        ),
    )
    normalized["COSTUME_DESCRIPTION_FACTS"] = costume_facts

    equipment_facts_name = "EQUIPMENT_DESCRIPTION_FACTS"
    equipment_facts = normalized.get(equipment_facts_name, "")
    equipment_values = _labeled_values(equipment_facts)
    equipment_labels = {
        "equipment",
        "primary weapon/tool",
        "secondary weapon/tool",
        "containers",
        "magical objects",
    }
    has_sided_equipment = any(
        (label.startswith("right side") or label.startswith("left side")) and _semantic_value(value) not in _EMPTY_SECTION_VALUES
        for label, value in equipment_values.items()
    )
    combined_values = [*costume_values.items(), *equipment_values.items()]
    has_equipment = has_sided_equipment or any(
        _semantic_value(value) not in _EMPTY_SECTION_VALUES
        for label, value in combined_values
        if label in equipment_labels
    )
    has_jewelry = any(
        _semantic_value(value) not in _EMPTY_SECTION_VALUES
        for label, value in combined_values
        if label == "jewelry"
    )

    if not has_equipment and not has_jewelry:
        for name in list(normalized):
            if name.startswith("EQUIPMENT_DESCRIPTION_"):
                normalized.pop(name, None)
                normalized_sources.pop(name, None)
                suppressed[name] = "no jewelry or equipment"
    elif equipment_facts:
        if not has_sided_equipment:
            equipment_facts = re.sub(r",?\s*swapped left/right placement,?", ",", equipment_facts, flags=re.IGNORECASE)
            equipment_facts = equipment_facts.replace("drift: no ,", "drift: no").replace(",,", ",")

        def keep_equipment_line(line: str) -> bool:
            match = _LABELED_BULLET_RE.match(line)
            lower = line.casefold()
            if not has_sided_equipment and (
                "use anatomical left and right" in lower
                or "anatomical right appears" in lower
                or "anatomical left appears" in lower
                or (match and (match.group(2).strip().casefold().startswith("right side") or match.group(2).strip().casefold().startswith("left side")))
            ):
                return False
            if body_view_token != "FRONT" and "front-view reminder" in lower:
                return False
            return True

        equipment_facts = _filter_section_lines(equipment_facts, keep_equipment_line)
        normalized[equipment_facts_name] = equipment_facts

    general_values = {
        _semantic_value(value)
        for value in [*_labeled_values(normalized.get("COSTUME_DESCRIPTION_FACTS", "")).values(), *_labeled_values(normalized.get(equipment_facts_name, "")).values()]
        if _semantic_value(value)
    }
    selected_view_names = {
        f"COSTUME_DESCRIPTION_VIEW_{body_view_token}",
        f"EQUIPMENT_DESCRIPTION_VIEW_{body_view_token}",
    }
    for name in selected_view_names:
        text = normalized.get(name, "")
        if not text:
            continue

        def keep_view_line(line: str) -> bool:
            lower = line.casefold()
            if not has_sided_equipment and ("anatomical right" in lower or "anatomical left" in lower):
                return False
            if _is_generic_no_equipment_view_line(line):
                return False
            match = _LABELED_BULLET_RE.match(line)
            return not (match and _semantic_value(match.group(3)) in general_values)

        compacted = _filter_section_lines(text, keep_view_line)
        if compacted:
            normalized[name] = compacted
        else:
            normalized.pop(name, None)
            normalized_sources.pop(name, None)
            suppressed[name] = "empty or redundant view stub"

    return normalized, normalized_sources, suppressed


def costume_dressing_orientation_metadata(
    body_view_token: str,
    head_view_token: str,
    body_view_data: dict,
    head_view_data: dict,
) -> dict[str, str]:
    body_lock = str(body_view_data.get("costume_dressing_orientation_lock") or "").strip()
    head_lock = str(head_view_data.get("costume_dressing_orientation_lock") or "").strip()
    if not body_lock or not head_lock:
        raise TemplateCompileError("MISSING_VIEW_INSTRUCTION", "Missing configured costume-dressing orientation lock.")
    if body_view_token == head_view_token:
        alignment = (
            "Head, neck, shoulders, torso, hips, knees, and feet remain aligned to the same requested direction.\n"
            "Do not introduce a separate head turn or sidelong eye contact."
        )
        head_lock = ""
    else:
        alignment = (
            "Preserve the supplied relationship between body orientation and head orientation exactly.\n"
            "Do not increase, reduce, reverse, or otherwise reinterpret the existing head turn."
        )
        head_lock = f"For the head: {head_lock}"
        body_lock = f"For the body: {body_lock}"
    return {
        "BODY_ORIENTATION_LOCK": body_lock,
        "HEAD_ORIENTATION_LOCK": head_lock,
        "BODY_HEAD_ALIGNMENT_LOCK": alignment,
    }


def load_costume_dressing_section_data(
    project_root: Path,
    character_template_path: Path,
    costume_path: Path,
) -> tuple[dict[str, str], dict[str, dict]]:
    sections, sources = load_body_reference_section_data(project_root, character_template_path)
    for name in list(sections):
        if name.startswith("COSTUME_") or name.startswith("EQUIPMENT_") or name == "IDENTITY_PRESERVATION_COSTUME":
            sections.pop(name, None)
            sources.pop(name, None)
    costume_sections, costume_sources = load_template_sections_with_sources(
        costume_path,
        source_kind="costume_template_section",
        source_label=f"Costume template: {costume_path.name}",
    )
    for name, text in costume_sections.items():
        if name.startswith("COSTUME_") or name.startswith("EQUIPMENT_") or name == "IDENTITY_PRESERVATION_COSTUME":
            sections[name] = text
            sources[name] = costume_sources.get(name, {})
    return sections, sources


def write_dependency_manifest(
    path: Path,
    job_id: str,
    character: str,
    phase: str,
    body_view_token: str,
    head_view_token: str,
    costume_name: str,
    costume_path: Path,
    reference_files: list[dict],
) -> None:
    manifest = {
        "job_id": job_id,
        "task": "costume-dressing",
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "costume_name": costume_name,
        "costume_path": str(costume_path),
        "resources_allowed": True,
        "resources": reference_files,
        "required_reference_roles": ["character_assembly"],
        "notes": [
            "Costume-dressing uses a locked Character-Assembly asset selected by matching body/head view.",
            "Costume and equipment sections are loaded from the selected costume markdown file.",
        ],
    }
    write_json_file(path, manifest)


def write_prompt_review(path: Path, metadata: dict[str, str]) -> None:
    path.write_text(
        f"""# Prompt Review

Job ID: {metadata['job_id']}
Task: {metadata['task']}
Character: {metadata['character']}
Phase: {metadata['phase']}
Body View: {metadata['body_view_token']}
Head View: {metadata['head_view_token']}
Costume: {metadata['costume_name']}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] The opening identifies one full-body technical costume-dressing image.
- [ ] The Character-Assembly source is explicitly locked.
- [ ] Body and head orientation are stated early and match the requested views.
- [ ] The prompt forbids independent head turn, body twist, mirroring, and camera change.
- [ ] Pose, stance, and full-body framing are preserved.
- [ ] Costume, jewelry, and equipment details come from the costume file.
- [ ] Empty `None` equipment fields and redundant sections are suppressed.
- [ ] Sided equipment rules appear only when needed and use anatomical left/right.
- [ ] The prompt contains no duplicated Good Output/Bad Output boilerplate.

## Notes
""",
        encoding="utf-8",
    )


def write_image_review(path: Path, metadata: dict[str, str], expected_output: str) -> None:
    path.write_text(
        f"""# Image Review

Job ID: {metadata['job_id']}
Task: {metadata['task']}
Character: {metadata['character']}
Phase: {metadata['phase']}
Body View: {metadata['body_view_token']}
Head View: {metadata['head_view_token']}
Costume: {metadata['costume_name']}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Character identity matches the assembled character source.
- [ ] Body view matches the Character-Assembly source exactly.
- [ ] Head view and relative head-to-body angle match the Character-Assembly source exactly.
- [ ] The character did not turn toward the viewer.
- [ ] Pose, stance, weight distribution, camera, and framing are unchanged.
- [ ] Only costume-related elements changed.
- [ ] Full body is visible, including feet.
- [ ] Costume design matches the costume file.
- [ ] Jewelry and equipment match the costume file.
- [ ] Left/right equipment placement is correct.
- [ ] Fitment clothing is gone.
- [ ] No narrative scene, prop drift, or dramatic lighting was introduced.

## Notes
""",
        encoding="utf-8",
    )


def compile_costume_dressing_job(job: dict, project_root: Path = PROJECT_ROOT) -> dict:
    job_id = require_job_field(job, "Job", "job_id", "Job ID")
    task = require_job_field(job, "Task", "task")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    raw_body_view = require_job_field(job, "Body View", "body_view", "View", "view")
    raw_head_view = require_job_field(job, "Head View", "head_view")
    costume_name = job_get(job, "Costume", "costume") or "Canonical Adventure Gear"

    if task != "costume-dressing":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported task for costume-dressing runner: {task}")

    bundle = load_bundle(project_root, "costume-dressing")
    body_view_token = normalize_view(project_root, raw_body_view)
    head_view_token = normalize_view(project_root, raw_head_view)
    body_view_data = load_view_data(project_root, body_view_token)
    head_view_data = load_view_data(project_root, head_view_token)
    character_template_path = character_root(project_root) / character / phase / "Character_Image_Template.md"
    costume_path = costume_path_for_job(project_root, job, character, phase)
    if not costume_path.exists():
        raise TemplateCompileError("MISSING_TEMPLATE", f"Costume template not found: {costume_path}")
    output_dir = output_dir_for_job(project_root, job, character, phase, body_view_token, head_view_token)
    expected_output = job_get(job, "Expected Output", "expected_output") or expected_output_for_job(job, body_view_data)

    references = reference_files_for_job(job)
    character_assembly = reference_by_role(references, "character_assembly")
    validate_reference(character_assembly, "character_assembly")

    all_sections, section_sources = load_costume_dressing_section_data(project_root, character_template_path, costume_path)
    all_sections, section_sources, suppressed_sections = normalize_costume_dressing_sections(
        all_sections,
        section_sources,
        body_view_token,
    )
    selection = select_sections(all_sections, bundle, body_view_token, section_sources)
    if selection.missing_required:
        raise TemplateCompileError("MISSING_REQUIRED_SECTION", "Missing required sections: " + ", ".join(selection.missing_required))
    if selection.forbidden_matches:
        raise TemplateCompileError("FORBIDDEN_SECTION_INCLUDED", "Forbidden sections selected: " + ", ".join(selection.forbidden_matches))

    paths = bundle_output_paths(output_dir, output_files(bundle), {
        "final_prompt": "Final_Image_Prompt.md",
        "compiled_sections": "Compiled_Sections.md",
        "source_map": "Prompt_Source_Map.json",
        "dependency_manifest": "dependency_manifest.json",
        "prompt_review": "Prompt_Review.md",
        "image_review": "Image_Review.md",
    })
    final_prompt_path = paths["final_prompt"]
    compiled_sections_path = paths["compiled_sections"]
    source_map_path = paths["source_map"]
    manifest_path = paths["dependency_manifest"]
    prompt_review_path = paths["prompt_review"]
    image_review_path = paths["image_review"]

    metadata = {
        "job_id": job_id,
        "task": task,
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "costume_name": costume_name,
        "suppressed_sections": suppressed_sections,
    }
    orientation_metadata = costume_dressing_orientation_metadata(
        body_view_token,
        head_view_token,
        body_view_data,
        head_view_data,
    )
    body_view_display = re.sub(r"\s+VIEW$", "", str(body_view_data["label"]).upper())
    head_view_display = re.sub(r"\s+VIEW$", "", str(head_view_data["label"]).upper())
    equipment_facts_selected = "EQUIPMENT_DESCRIPTION_FACTS" in selection.sections
    equipment_view_selected = f"EQUIPMENT_DESCRIPTION_VIEW_{body_view_token}" in selection.sections
    equipment_heading = ""
    if equipment_facts_selected:
        equipment_heading = "# Equipment and Jewelry" if any(
            label != "jewelry" and _semantic_value(value) not in _EMPTY_SECTION_VALUES
            for label, value in _labeled_values(selection.sections["EQUIPMENT_DESCRIPTION_FACTS"]).items()
            if label in {"primary weapon/tool", "secondary weapon/tool", "containers", "magical objects"}
            or label.startswith("right side")
            or label.startswith("left side")
        ) else "# Jewelry"
    metadata_values = {
        "CHARACTER_NAME": character,
        "CHARACTER_PHASE": phase,
        "BODY_VIEW_TOKEN": body_view_token,
        "BODY_VIEW_LABEL": str(body_view_data["label"]),
        "BODY_VIEW_DISPLAY": body_view_display,
        "BODY_VIEW_INSTRUCTION": view_instruction(body_view_data, "body", task, include_intro=True),
        "HEAD_VIEW_TOKEN": head_view_token,
        "HEAD_VIEW_LABEL": str(head_view_data["label"]),
        "HEAD_VIEW_DISPLAY": head_view_display,
        "HEAD_VIEW_INSTRUCTION": view_instruction(head_view_data, "head", task),
        "VIEW_TOKEN": body_view_token,
        "VIEW_LABEL": str(body_view_data["label"]),
        "VIEW_INSTRUCTION": view_instruction(body_view_data, "body", task, include_intro=True),
        "BACKGROUND_TREATMENT": load_background_treatment(project_root),
        "COSTUME_VIEW_HEADING": "# View-Specific Costume Details" if f"COSTUME_DESCRIPTION_VIEW_{body_view_token}" in selection.sections else "",
        "EQUIPMENT_HEADING": equipment_heading,
        "EQUIPMENT_VIEW_HEADING": "# View-Specific Equipment Details" if equipment_view_selected else "",
        **orientation_metadata,
        **template_metadata(character_template_path),
        **costume_metadata(costume_path),
    }
    metadata_sources = {
        **metadata_source_map(project_root, character_template_path, body_view_token, task, "body"),
        **background_treatment_source_map(project_root),
        **costume_metadata_sources(costume_path),
        "BODY_VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Body view token", "editable": False},
        "BODY_VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Body view label", "json_pointer": f"/views/{body_view_token}/label", "editable": True},
        "BODY_VIEW_DISPLAY": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Normalized body view display", "editable": False},
        "BODY_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "costume-dressing body view instruction", "json_pointer": f"/views/{body_view_token}/body_instructions/{task}", "editable": True},
        "HEAD_VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Head view token", "editable": False},
        "HEAD_VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Head view label", "json_pointer": f"/views/{head_view_token}/label", "editable": True},
        "HEAD_VIEW_DISPLAY": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Normalized head view display", "editable": False},
        "HEAD_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "costume-dressing head view instruction", "json_pointer": f"/views/{head_view_token}/head_instructions/{task}", "editable": True},
        "BODY_ORIENTATION_LOCK": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Costume-dressing body orientation lock", "json_pointer": f"/views/{body_view_token}/costume_dressing_orientation_lock", "editable": True},
        "HEAD_ORIENTATION_LOCK": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Costume-dressing head orientation lock", "json_pointer": f"/views/{head_view_token}/costume_dressing_orientation_lock", "editable": True},
        "BODY_HEAD_ALIGNMENT_LOCK": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Body/head alignment lock", "editable": False},
        "COSTUME_VIEW_HEADING": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Optional costume view heading", "editable": False},
        "EQUIPMENT_HEADING": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Optional equipment heading", "editable": False},
        "EQUIPMENT_VIEW_HEADING": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Optional equipment view heading", "editable": False},
    }
    prompt_text = render_static_prompt_artifacts(
        project_root=project_root,
        bundle=bundle,
        final_prompt_path=final_prompt_path,
        source_map_path=source_map_path,
        compiled_sections_path=compiled_sections_path,
        metadata=metadata,
        metadata_values=metadata_values,
        metadata_sources=metadata_sources,
        selection=selection,
        required_section_names=list(bundle.get("required_sections", [])),
        view_token=body_view_token,
    )
    references = auxiliary_references_for_texts(
        project_root,
        [compiled_sections_path.read_text(encoding="utf-8"), source_map_path.read_text(encoding="utf-8")],
        references,
    )
    write_dependency_manifest(
        manifest_path,
        job_id,
        character,
        phase,
        body_view_token,
        head_view_token,
        costume_name,
        costume_path,
        references,
    )
    write_prompt_review(prompt_review_path, metadata)
    write_image_review(image_review_path, metadata, expected_output)

    return {
        "status": str(bundle.get("next_status", "READY_FOR_RENDER")),
        "next_actor": str(bundle.get("next_actor", "AI_AGENT")),
        "final_prompt": str(final_prompt_path),
        "compiled_sections": str(compiled_sections_path),
        "dependency_manifest": str(manifest_path),
        "prompt_review": str(prompt_review_path),
        "image_review": str(image_review_path),
        "expected_output": str(output_dir / expected_output),
        "output_dir": str(output_dir),
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "reference_files": references,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a costume-dressing job without AI prompt finalization.")
    parser.add_argument("--job", required=True, help="Path to a single costume-dressing job JSON file.")
    args = parser.parse_args(argv)
    job_path = Path(args.job).expanduser()
    result = compile_costume_dressing_job(json.loads(job_path.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
