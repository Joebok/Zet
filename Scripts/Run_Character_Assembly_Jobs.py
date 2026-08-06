#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scripts.Compile_Character_Template import TemplateCompileError, select_sections
from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Scripts.Job_File_Utils import bundle_output_paths, render_static_prompt_artifacts, write_json_file
from Scripts.Library_Paths import pipeline_root
from zet.services.pipeline_compiler_support import (
    expected_output_for_job,
    job_get,
    load_bundle,
    load_body_reference_section_data,
    load_view_data,
    metadata_source_map,
    normalize_view,
    output_files,
    require_job_field,
    resolve_project_path,
    template_metadata,
    template_path_for_job,
    view_instruction,
    reference_by_role,
    reference_files_for_job,
    validate_reference,
    validate_character_assembly_inputs,
    normalize_assembly_style_mode,
    character_assembly_style_instruction,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def output_dir_for_job(project_root: Path, job: dict, character: str, phase: str, body_view_token: str, head_view_token: str) -> Path:
    explicit = job_get(job, "Output Directory", "output_directory", "Folder", "folder")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return (
        pipeline_root(project_root)
        / character
        / phase
        / "Character-Assembly"
        / body_view_token
        / head_view_token
    )


def write_dependency_manifest(
    path: Path,
    job_id: str,
    character: str,
    phase: str,
    body_view_token: str,
    head_view_token: str,
    assembly_style_mode: str,
    reference_files: list[dict],
) -> None:
    manifest = {
        "job_id": job_id,
        "task": "character-assembly",
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "assembly_style_mode": assembly_style_mode,
        "resources_allowed": True,
        "resources": reference_files,
        "required_reference_roles": ["body_reference", "head_fitment"],
        "notes": [
            "Character-assembly uses locked Body-Reference and Head-Fitment assets selected by matching body/head view.",
            "Prompt text describes reference usage; image file selection is stored in asset.reference_files and ask manifest.",
        ],
    }
    write_json_file(path, manifest)


def write_image_review(path: Path, metadata: dict[str, str], expected_output: str) -> None:
    path.write_text(
        f"""# Image Review

Job ID: {metadata['job_id']}
Task: {metadata['task']}
Character: {metadata['character']}
Phase: {metadata['phase']}
Body View: {metadata['body_view_token']}
Head View: {metadata['head_view_token']}
Assembly Style Mode: {metadata['assembly_style_mode']}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Full body is visible, including feet.
- [ ] Everything below the head-replacement boundary matches the Reference Body, including pose, framing, fitment clothing, exposed skin, and background.
- [ ] Head, hair, ears, face, expression, gaze, and upper neck match the Character Head source.
- [ ] Head and body join cleanly at the neck without a visible seam, floating head, or mannequin material.
- [ ] Reference Body, Character Head, and final render preserve the same requested view.
- [ ] Rendering changes comply with the selected assembly style mode.
- [ ] No costume, prop, accessory, scene, or lighting changes were introduced.

## Notes
""",
        encoding="utf-8",
    )


def compile_character_assembly_job(job: dict, project_root: Path = PROJECT_ROOT) -> dict:
    job_id = require_job_field(job, "Job", "job_id", "Job ID")
    task = require_job_field(job, "Task", "task")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    raw_body_view = require_job_field(job, "Body View", "body_view", "View", "view")
    raw_head_view = require_job_field(job, "Head View", "head_view")

    if task != "character-assembly":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported task for character-assembly runner: {task}")

    bundle = load_bundle(project_root, "character-assembly")
    body_view_token = normalize_view(project_root, raw_body_view)
    head_view_token = normalize_view(project_root, raw_head_view)
    assembly_style_mode = normalize_assembly_style_mode(
        job_get(job, "Assembly Style Mode", "assembly_style_mode")
    )
    body_view_data = load_view_data(project_root, body_view_token)
    head_view_data = load_view_data(project_root, head_view_token)
    template_path = template_path_for_job(project_root, job, character, phase)
    output_dir = output_dir_for_job(project_root, job, character, phase, body_view_token, head_view_token)
    expected_output = job_get(job, "Expected Output", "expected_output") or expected_output_for_job(job, body_view_data)

    references = reference_files_for_job(job)
    body_reference = reference_by_role(references, "body_reference")
    head_fitment = reference_by_role(references, "head_fitment")
    validate_reference(body_reference, "body_reference")
    validate_reference(head_fitment, "head_fitment")
    validate_character_assembly_inputs(
        project_root,
        character=character,
        phase=phase,
        body_view_token=body_view_token,
        head_view_token=head_view_token,
        body_reference=body_reference,
        head_fitment=head_fitment,
    )

    all_sections, section_sources = load_body_reference_section_data(project_root, template_path)
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
        "image_review": "Image_Review.md",
    })
    final_prompt_path = paths["final_prompt"]
    compiled_sections_path = paths["compiled_sections"]
    source_map_path = paths["source_map"]
    manifest_path = paths["dependency_manifest"]
    image_review_path = paths["image_review"]

    metadata = {
        "job_id": job_id,
        "task": task,
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "assembly_style_mode": assembly_style_mode,
    }
    metadata_values = {
            "CHARACTER_NAME": character,
            "CHARACTER_PHASE": phase,
            "BODY_VIEW_TOKEN": body_view_token,
            "BODY_VIEW_LABEL": str(body_view_data["label"]),
            "BODY_VIEW_INSTRUCTION": view_instruction(body_view_data, "body", task),
            "HEAD_VIEW_TOKEN": head_view_token,
            "HEAD_VIEW_LABEL": str(head_view_data["label"]),
            "HEAD_VIEW_INSTRUCTION": view_instruction(head_view_data, "head", task),
            "VIEW_TOKEN": body_view_token,
            "VIEW_LABEL": str(body_view_data["label"]),
            "VIEW_INSTRUCTION": view_instruction(body_view_data, "body", task),
            "ASSEMBLY_STYLE_MODE": assembly_style_mode,
            "ASSEMBLY_STYLE_INSTRUCTION": character_assembly_style_instruction(assembly_style_mode),
            **template_metadata(template_path),
        }
    metadata_sources = {
        **metadata_source_map(project_root, template_path, body_view_token, task, "body"),
        "ASSEMBLY_STYLE_MODE": {"source_kind": "asset_metadata", "source_path": "", "source_label": "Assembly style mode", "editable": True},
        "ASSEMBLY_STYLE_INSTRUCTION": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Assembly style instruction", "editable": False},
        "BODY_VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Body view token", "editable": False},
        "BODY_VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Body view label", "json_pointer": f"/views/{body_view_token}/label", "editable": True},
        "BODY_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "character-assembly body view instruction", "json_pointer": f"/views/{body_view_token}/body_instructions/{task}", "editable": True},
        "HEAD_VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Head view token", "editable": False},
        "HEAD_VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Head view label", "json_pointer": f"/views/{head_view_token}/label", "editable": True},
        "HEAD_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "character-assembly head view instruction", "json_pointer": f"/views/{head_view_token}/head_instructions/{task}", "editable": True},
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
        assembly_style_mode,
        references,
    )
    write_image_review(image_review_path, metadata, expected_output)

    return {
        "status": str(bundle.get("next_status", "READY_FOR_RENDER")),
        "next_actor": str(bundle.get("next_actor", "AI_AGENT")),
        "final_prompt": str(final_prompt_path),
        "compiled_sections": str(compiled_sections_path),
        "dependency_manifest": str(manifest_path),
        "image_review": str(image_review_path),
        "expected_output": str(output_dir / expected_output),
        "output_dir": str(output_dir),
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "assembly_style_mode": assembly_style_mode,
        "reference_files": references,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a character-assembly job without AI prompt finalization.")
    parser.add_argument("--job", required=True, help="Path to a single character-assembly job JSON file.")
    args = parser.parse_args(argv)
    job_path = Path(args.job).expanduser()
    result = compile_character_assembly_job(json.loads(job_path.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
