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

from Build_Static_Final_Prompt import prompt_template_path, render_static_prompt, write_compiled_sections
from Compile_Character_Template import TemplateCompileError, load_template_sections, select_sections
from Run_Body_Reference_Jobs import (
    expected_output_for_job,
    job_get,
    load_bundle,
    load_view_data,
    normalize_view,
    output_files,
    require_job_field,
    resolve_project_path,
    template_path_for_job,
)
from Run_Head_Fitment_Jobs import reference_by_role, reference_files_for_job, validate_reference


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
    reference_files: list[dict],
) -> None:
    manifest = {
        "job_id": job_id,
        "task": "character-assembly",
        "character": character,
        "phase": phase,
        "body_view_token": body_view_token,
        "head_view_token": head_view_token,
        "resources_allowed": True,
        "resources": reference_files,
        "required_reference_roles": ["body_reference", "head_fitment"],
        "notes": [
            "Character-assembly uses locked Body-Reference and Head-Fitment assets selected by matching body/head view.",
            "Prompt text describes reference usage; image file selection is stored in asset.reference_files and ask manifest.",
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

- [ ] Full body is visible, including feet.
- [ ] Body proportions and stance match the body-reference source.
- [ ] Head, hair, ears, face, and neck match the head-fitment source.
- [ ] Head and body join cleanly at the neck.
- [ ] Costume and equipment match the character template.
- [ ] No mannequin, fitment shell, tank top, or compression shorts remain.
- [ ] Requested body/head view is preserved.
- [ ] No narrative scene, extra props, or dramatic lighting was introduced.

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

    all_sections = load_template_sections(template_path)
    selection = select_sections(all_sections, bundle, body_view_token)
    if selection.missing_required:
        raise TemplateCompileError("MISSING_REQUIRED_SECTION", "Missing required sections: " + ", ".join(selection.missing_required))
    if selection.forbidden_matches:
        raise TemplateCompileError("FORBIDDEN_SECTION_INCLUDED", "Forbidden sections selected: " + ", ".join(selection.forbidden_matches))

    output_dir.mkdir(parents=True, exist_ok=True)
    files = output_files(bundle)
    final_prompt_path = output_dir / files.get("final_prompt", "Final_Image_Prompt.md")
    compiled_sections_path = output_dir / files.get("compiled_sections", "Compiled_Sections.md")
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
    prompt_text = render_static_prompt(
        prompt_template_path(project_root, str(bundle.get("static_prompt_template", ""))).read_text(encoding="utf-8"),
        {
            "CHARACTER_NAME": character,
            "CHARACTER_PHASE": phase,
            "BODY_VIEW_TOKEN": body_view_token,
            "BODY_VIEW_LABEL": str(body_view_data["label"]),
            "BODY_VIEW_INSTRUCTION": str(body_view_data["instruction"]),
            "HEAD_VIEW_TOKEN": head_view_token,
            "HEAD_VIEW_LABEL": str(head_view_data["label"]),
            "HEAD_VIEW_INSTRUCTION": str(head_view_data["instruction"]),
            "VIEW_TOKEN": body_view_token,
            "VIEW_LABEL": str(body_view_data["label"]),
            "VIEW_INSTRUCTION": str(body_view_data["instruction"]),
        },
        selection,
        list(bundle.get("required_sections", [])),
        body_view_token,
    )
    final_prompt_path.write_text(prompt_text, encoding="utf-8")
    write_compiled_sections(compiled_sections_path, job_metadata=metadata, view_token=body_view_token, selection=selection)
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
