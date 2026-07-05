#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from Build_Static_Final_Prompt import prompt_template_path, render_static_prompt_with_source_map, write_compiled_sections
from Compile_Character_Template import TemplateCompileError, select_sections
from Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Run_Body_Reference_Jobs import (
    expected_output_for_job,
    job_get,
    load_bundle,
    load_body_reference_sections,
    load_body_reference_section_data,
    load_view_data,
    normalize_view,
    output_files,
    require_job_field,
    resolve_project_path,
    template_metadata,
    template_path_for_job,
    metadata_source_map,
    view_instruction,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def output_dir_for_job(project_root: Path, job: dict, character: str, phase: str, body_view_token: str, head_view_token: str) -> Path:
    explicit = job_get(job, "Output Directory", "output_directory", "Folder", "folder")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return (
        project_root
        / "_Lib"
        / "Pipelines"
        / character
        / phase
        / "Head-Fitment"
        / body_view_token
        / head_view_token
    )


def reference_files_for_job(job: dict) -> list[dict]:
    value = job.get("Reference Files") or job.get("reference_files") or []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def reference_by_role(reference_files: list[dict], role: str) -> dict:
    for reference in reference_files:
        if reference.get("role") == role:
            return reference
    raise TemplateCompileError("MISSING_REFERENCE", f"Missing required reference slot: {role}")


def validate_reference(reference: dict, role: str) -> Path:
    raw_path = str(reference.get("path") or "").strip()
    if not raw_path:
        raise TemplateCompileError("MISSING_REFERENCE", f"Reference slot {role} has no path.")
    path = Path(raw_path)
    if not path.exists() or not path.is_file():
        raise TemplateCompileError("MISSING_REFERENCE", f"Reference image for {role} was not found: {path}")
    return path


def write_dependency_manifest(
    path: Path,
    job_id: str,
    character: str,
    phase: str,
    body_view_token: str,
    head_view_token: str,
    reference_files: list[dict],
) -> None:
    manifest = {
        "job_id": job_id,
        "task": "head-fitment",
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "resources_allowed": True,
        "resources": reference_files,
        "required_reference_roles": ["body_reference", "headshot"],
        "notes": [
            "Head-fitment uses explicit structured reference slots from asset.reference_files.",
            "Prompt text describes reference usage; image file selection is stored in the asset and ask manifest.",
        ],
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_image_review(path: Path, metadata: dict[str, str], expected_output: str) -> None:
    path.write_text(
        f"""# Image Review

Job ID: {metadata['job_id']}
Task: {metadata['task']}
Character: {metadata['character']}
Phase: {metadata['phase']}
Body View: {metadata['body_view_token']}
Head View: {metadata['head_view_token']}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Body/reference pose and costume are preserved from the body-reference image.
- [ ] Head, face, hair, ears, and identity match the headshot reference.
- [ ] Head scale, neck alignment, and perspective fit the body.
- [ ] Facial identity is not generic.
- [ ] Hair silhouette and elf ears remain visible and correct.
- [ ] No costume redesign was introduced.
- [ ] No narrative scene, prop, or dramatic lighting was introduced.

## Notes
""",
        encoding="utf-8",
    )


def compile_head_fitment_job(job: dict, project_root: Path = PROJECT_ROOT) -> dict:
    job_id = require_job_field(job, "Job", "job_id", "Job ID")
    task = require_job_field(job, "Task", "task")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    raw_body_view = require_job_field(job, "Body View", "body_view", "View", "view")
    raw_head_view = require_job_field(job, "Head View", "head_view")

    if task != "head-fitment":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported task for head-fitment runner: {task}")

    bundle = load_bundle(project_root, "head-fitment")
    body_view_token = normalize_view(project_root, raw_body_view)
    head_view_token = normalize_view(project_root, raw_head_view)
    body_view_data = load_view_data(project_root, body_view_token)
    head_view_data = load_view_data(project_root, head_view_token)
    template_path = template_path_for_job(project_root, job, character, phase)
    output_dir = output_dir_for_job(project_root, job, character, phase, body_view_token, head_view_token)
    expected_output = job_get(job, "Expected Output", "expected_output") or expected_output_for_job(job, body_view_data)

    references = reference_files_for_job(job)
    body_reference = reference_by_role(references, "body_reference")
    headshot = reference_by_role(references, "headshot")
    validate_reference(body_reference, "body_reference")
    validate_reference(headshot, "headshot")

    all_sections, section_sources = load_body_reference_section_data(project_root, template_path)
    selection = select_sections(all_sections, bundle, head_view_token, section_sources)
    if selection.missing_required:
        raise TemplateCompileError("MISSING_REQUIRED_SECTION", "Missing required sections: " + ", ".join(selection.missing_required))
    if selection.forbidden_matches:
        raise TemplateCompileError("FORBIDDEN_SECTION_INCLUDED", "Forbidden sections selected: " + ", ".join(selection.forbidden_matches))

    output_dir.mkdir(parents=True, exist_ok=True)
    files = output_files(bundle)
    final_prompt_path = output_dir / files.get("final_prompt", "Final_Image_Prompt.md")
    compiled_sections_path = output_dir / files.get("compiled_sections", "Compiled_Sections.md")
    source_map_path = output_dir / files.get("source_map", "Prompt_Source_Map.json")
    manifest_path = output_dir / files.get("dependency_manifest", "dependency_manifest.json")
    image_review_path = output_dir / files.get("image_review", "Image_Review.md")

    metadata = {
        "job_id": job_id,
        "task": task,
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
    }
    template_file = prompt_template_path(project_root, str(bundle.get("static_prompt_template", "")))
    metadata_values = {
            "CHARACTER_NAME": character,
            "CHARACTER_PHASE": phase,
            "BODY_VIEW_TOKEN": body_view_token,
            "BODY_VIEW_LABEL": str(body_view_data["label"]),
            "BODY_VIEW_INSTRUCTION": view_instruction(body_view_data, "body", task),
            "HEAD_VIEW_TOKEN": head_view_token,
            "HEAD_VIEW_LABEL": str(head_view_data["label"]),
            "HEAD_VIEW_INSTRUCTION": view_instruction(head_view_data, "head", task, include_intro=True),
            "VIEW_TOKEN": head_view_token,
            "VIEW_LABEL": str(head_view_data["label"]),
            "VIEW_INSTRUCTION": view_instruction(head_view_data, "head", task, include_intro=True),
            **template_metadata(template_path),
        }
    metadata_sources = {
        **metadata_source_map(project_root, template_path, body_view_token, task, "body"),
        "BODY_VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Body view token", "editable": False},
        "BODY_VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Body view label", "json_pointer": f"/views/{body_view_token}/label", "editable": True},
        "BODY_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "head-fitment body view instruction", "json_pointer": f"/views/{body_view_token}/body_instructions/{task}", "editable": True},
        "HEAD_VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Head view token", "editable": False},
        "HEAD_VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "Head view label", "json_pointer": f"/views/{head_view_token}/label", "editable": True},
        "HEAD_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(project_root / "Config" / "Prompt_View_Text.json"), "source_label": "head-fitment head view instruction", "json_pointer": f"/views/{head_view_token}/head_instructions/{task}", "editable": True},
    }
    prompt_text, source_map = render_static_prompt_with_source_map(
        template_file.read_text(encoding="utf-8"),
        template_path=template_file,
        metadata=metadata_values,
        metadata_sources=metadata_sources,
        selection=selection,
        required_section_names=list(bundle.get("required_sections", [])),
        view_token=head_view_token,
        final_prompt_name=final_prompt_path.name,
    )
    references = auxiliary_references_for_texts(
        project_root,
        [prompt_text],
        references,
    )
    final_prompt_path.write_text(prompt_text, encoding="utf-8")
    source_map_path.write_text(json.dumps({**source_map, **metadata}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_compiled_sections(compiled_sections_path, job_metadata=metadata, view_token=head_view_token, selection=selection)
    write_dependency_manifest(
        manifest_path,
        job_id,
        character,
        phase,
        body_view_token,
        head_view_token,
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
        "reference_files": references,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a head-fitment job without AI prompt finalization.")
    parser.add_argument("--job", required=True, help="Path to a single head-fitment job JSON file.")
    args = parser.parse_args(argv)
    job_path = Path(args.job).expanduser()
    result = compile_head_fitment_job(json.loads(job_path.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
