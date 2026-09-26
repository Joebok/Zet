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

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Scripts.Job_File_Utils import (
    bundle_output_paths,
    finalize_chatgpt_prompt,
    prepare_chatgpt_prompt_contract,
    render_static_prompt_artifacts,
    select_prompt_sections,
    write_json_file,
)
from Scripts.Library_Paths import pipeline_root
from zet.services.pipeline_compiler_support import (
    job_get,
    load_body_reference_section_data,
    load_bundle,
    load_view_data,
    normalize_view,
    output_files,
    reference_files_for_job,
    require_job_field,
    resolve_project_path,
    template_metadata,
    template_path_for_job,
    validate_reference,
    view_instruction,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def output_dir_for_job(project_root: Path, job: dict, character: str, phase: str, view_token: str) -> Path:
    explicit = job_get(job, "Output Directory", "output_directory", "Folder", "folder")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return pipeline_root(project_root) / character / phase / "Head-Image" / view_token / view_token


def _source_reference(references: list[dict]) -> dict | None:
    sources = [item for item in references if item.get("role") == "head_image_source"]
    if len(sources) > 1:
        raise TemplateCompileError("INVALID_REFERENCE", "Head-Image accepts at most one head_image_source reference.")
    if not sources:
        raise TemplateCompileError("MISSING_REFERENCE", "Head-Image requires one head_image_source reference.")
    return sources[0]


def _local_source_rules(rules: str) -> str:
    """Make legacy optional-source wording direct when a source is present."""
    lines = []
    for line in rules.splitlines():
        if line.lstrip().startswith(("* Without a source image", "- Without a source image")):
            continue
        line = line.replace("Optional source-image contract:", "Source-image contract:")
        line = line.replace("When a source image is supplied, use it as", "Use the source image as")
        lines.append(line)
    return "\n".join(lines)


def compile_head_image_job(
    job: dict, project_root: Path = PROJECT_ROOT, *, prompt_variant: str = "generation",
    pipeline_mode: str = "traditional",
) -> dict:
    job_id = require_job_field(job, "Job", "job_id", "Job ID")
    task = require_job_field(job, "Task", "task")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    raw_view = require_job_field(job, "Head View", "head_view", "View", "view", "Body View", "body_view")
    if task != "head-image":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported task for head-image runner: {task}")

    bundle = load_bundle(project_root, task)
    if prompt_variant == "analysis" or pipeline_mode == "local":
        bundle = {**bundle, "legacy_static_prompt_template": ""}
    view_token = normalize_view(project_root, raw_view)
    view_data = load_view_data(project_root, view_token)
    template_path = template_path_for_job(project_root, job, character, phase)
    output_dir = output_dir_for_job(project_root, job, character, phase, view_token)
    expected_output = job_get(job, "Expected Output", "expected_output") or f"Head-Image_{view_data['output_name_fragment']}.png"

    if pipeline_mode not in {"traditional", "local"}:
        raise TemplateCompileError("INVALID_PIPELINE_MODE", f"Unsupported Head-Image pipeline mode: {pipeline_mode}")
    references = reference_files_for_job(job)
    source_references = [item for item in references if item.get("role") == "head_image_source"]
    if pipeline_mode == "traditional":
        source_reference = _source_reference(references)
        validate_reference(source_reference, "head_image_source", project_root)
    else:
        if len(source_references) > 1:
            raise TemplateCompileError("INVALID_REFERENCE", "Local Head-Image accepts at most one source image.")
        if view_token != "FRONT" and not source_references:
            raise TemplateCompileError("MISSING_REFERENCE", "Local non-front Head-Image views require the selected FRONT anchor.")
        for source_reference in source_references:
            validate_reference(source_reference, "head_image_source", project_root)
    sections, section_sources = load_body_reference_section_data(project_root, template_path)
    if pipeline_mode == "local" and not source_references:
        for name in ("HEAD_IMAGE_TRANSFORM_INSTRUCTIONS", "HEAD_IMAGE_SOURCE_INSTRUCTIONS", "HEAD_IMAGE_SOURCE_RULES"):
            sections[name] = ""
    elif pipeline_mode == "local":
        sections["HEAD_IMAGE_SOURCE_RULES"] = _local_source_rules(sections.get("HEAD_IMAGE_SOURCE_RULES", ""))
    local_phase_changes = ""
    if pipeline_mode == "local":
        local_phase_changes = str(
            sections.get("HEAD_IMAGE_LOCAL_PHASE_CHANGES") or sections.get("HEAD_IMAGE_TRANSFORM_INSTRUCTIONS") or ""
        ).strip()
        if view_token != "FRONT":
            local_phase_changes = ""
        sections["HEAD_IMAGE_TRANSFORM_INSTRUCTIONS"] = ""
        if view_token in {"BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK"}:
            sections["HEAD_DESCRIPTION_FACTS"] = ""
    elif str(sections.get("HEAD_IMAGE_TRANSFORM_INSTRUCTIONS") or "").strip():
        for name in (
            "HEAD_IMAGE_SOURCE_INSTRUCTIONS",
            "HEAD_DESCRIPTION_FACTS",
            f"HEAD_DESCRIPTION_VIEW_{view_token}",
            "HAIR_DESCRIPTION_FACTS",
            f"HAIR_DESCRIPTION_VIEW_{view_token}",
            "HEAD_IMAGE_SOURCE_RULES",
            "HEAD_IMAGE_CHARACTER_REQUIREMENTS",
        ):
            sections[name] = ""
    selection = select_prompt_sections(
        project_root, bundle, sections, section_sources, view_token,
        prompt_variant=prompt_variant, pipeline_mode=pipeline_mode,
    )
    references = auxiliary_references_for_texts(
        project_root, ["\n".join(selection.sections.values())], references
    )
    render_mode = "edit" if source_references else "generate"
    references, image_inputs, contract_values, contract_manifest = prepare_chatgpt_prompt_contract(
        references, render_mode=render_mode
    )
    contract_values["LOCAL_RENDER_MODE"] = render_mode
    local_style = str(template_metadata(template_path).get("CANONICAL_ART_STYLE") or "").rstrip(". ")
    if view_token in {"BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK"}:
        local_style = re.sub(
            r" with anime-influenced facial proportions(?:,\s*(?:and\s+)?|\s+and\s+)large expressive eyes",
            "",
            local_style,
        )
        local_style = local_style.replace(", and refined linework", " with refined linework")
        local_style = local_style.replace(", refined linework, and ", " with refined linework and ")
    if source_references and view_token != "FRONT":
        contract_values["LOCAL_REFERENCE_GUIDANCE"] = (
            "Use Image 1, the selected FRONT render, as the identity and appearance anchor."
        )
    elif source_references:
        contract_values["LOCAL_REFERENCE_GUIDANCE"] = (
            "Use Image 1 as the identity and appearance reference."
        )
    elif pipeline_mode == "local":
        contract_values["LOCAL_REFERENCE_GUIDANCE"] = "Build the character from the identifying details below."
    else:
        contract_values["LOCAL_REFERENCE_GUIDANCE"] = ""

    paths = bundle_output_paths(output_dir, output_files(bundle), {
        "final_prompt": "Final_Image_Prompt.md",
        "compiled_sections": "Compiled_Sections.md",
        "source_map": "Prompt_Source_Map.json",
        "dependency_manifest": "dependency_manifest.json",
        "image_review": "Image_Review.md",
        "diagnostics": "Prompt_Compile_Diagnostics.json",
    })
    metadata = {
        "job_id": job_id,
        "task": task,
        "character": character,
        "phase": phase,
        "view_token": view_token,
    }
    metadata_values = {
        "CHARACTER_NAME": character,
        "CHARACTER_PHASE": phase,
        "VIEW_TOKEN": view_token,
        "VIEW_LABEL": str(view_data["label"]),
        "VIEW_INSTRUCTION": view_instruction(view_data, "head", task, include_intro=True),
        "LOCAL_VIEW_INSTRUCTION": str(view_data.get("local_head_image_instruction") or ""),
        "LOCAL_GAZE_INSTRUCTION": str(view_data.get("local_head_image_gaze") or ""),
        "LOCAL_PHASE_CHANGES": local_phase_changes,
        "LOCAL_VISIBLE_CHARACTER_FACTS": "\n\n".join(
            value for value in (
                sections.get("HEAD_DESCRIPTION_FACTS", "") if view_token == "FRONT" else "",
                sections.get(f"HEAD_DESCRIPTION_VIEW_{view_token}", ""),
                sections.get("HAIR_DESCRIPTION_FACTS", "") if view_token == "FRONT" else "",
                sections.get(f"HAIR_DESCRIPTION_VIEW_{view_token}", ""),
            ) if str(value or "").strip()
        ),
        "LOCAL_STYLE_INSTRUCTION": local_style,
        "HEAD_IMAGE_GAZE_RULE": (
            "Do not preserve the source image's camera-facing gaze; the subject must not look toward the viewer."
            if pipeline_mode == "local" and view_token != "FRONT" else ""
        ),
        **contract_values,
        **template_metadata(template_path),
    }
    config_path = project_root / "Config" / "Prompt_View_Text.json"
    metadata_sources = {
        "VIEW_TOKEN": {"source_kind": "runtime_generated", "source_path": "", "source_label": "Head view token", "editable": False},
        "VIEW_LABEL": {"source_kind": "config_view_instruction", "source_path": str(config_path), "source_label": "Head-Image view label", "json_pointer": f"/views/{view_token}/label", "editable": True},
        "VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(config_path), "source_label": "Head-Image view instruction", "json_pointer": f"/views/{view_token}/head_instructions/{task}", "editable": True},
        "LOCAL_VIEW_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(config_path), "source_label": "Local head-image view instruction", "json_pointer": f"/views/{view_token}/local_head_image_instruction", "editable": True},
        "LOCAL_GAZE_INSTRUCTION": {"source_kind": "config_view_instruction", "source_path": str(config_path), "source_label": "Local head-image gaze instruction", "json_pointer": f"/views/{view_token}/local_head_image_gaze", "editable": True},
    }
    gaze_review_items = {
        "FRONT": "- [ ] The eyes look forward with the face.",
        "FRONT_LEFT_3_4": "- [ ] Any visible eyes follow the turned face and nose direction without looking toward the viewer.",
        "FRONT_RIGHT_3_4": "- [ ] Any visible eyes follow the turned face and nose direction without looking toward the viewer.",
        "LEFT_PROFILE": "- [ ] The visible eye follows the nose direction instead of looking toward the viewer.",
        "RIGHT_PROFILE": "- [ ] The visible eye follows the nose direction instead of looking toward the viewer.",
        "BACK_LEFT_3_4": "- [ ] If an eye is visible, its gaze remains aligned with the away-facing head.",
        "BACK_RIGHT_3_4": "- [ ] If an eye is visible, its gaze remains aligned with the away-facing head.",
    }.get(view_token, "")
    prompt_text = render_static_prompt_artifacts(
        project_root=project_root,
        bundle=bundle,
        final_prompt_path=paths["final_prompt"],
        source_map_path=paths["source_map"],
        compiled_sections_path=paths["compiled_sections"],
        metadata=metadata,
        metadata_values=metadata_values,
        metadata_sources=metadata_sources,
        selection=selection,
        required_section_names=[],
        view_token=view_token,
        prompt_variant=prompt_variant,
        pipeline_mode=pipeline_mode,
        image_inputs=image_inputs,
    )
    write_json_file(paths["dependency_manifest"], {
        **metadata,
        "resources_allowed": True,
        "resources": references,
        "required_reference_roles": (["head_image_source"] if pipeline_mode == "traditional" or view_token != "FRONT" else []),
        "pipeline_mode": pipeline_mode,
        **contract_manifest,
        "head_image_prompt_contract": {
            "version": 4,
            "primary_focus": "phase_transformation_identity_and_view",
            "geometry_regularization": "deferred",
            "background": "transparent",
        },
    })
    if prompt_variant == "generation":
        finalize_chatgpt_prompt(paths["diagnostics"], prompt_text, image_inputs, render_mode)
    paths["image_review"].write_text(
        f"""# Image Review

Job ID: {job_id}
Task: head-image
Character: {character}
Phase: {phase}
Head View: {view_token}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] The requested head view is exact and not mirrored.
{gaze_review_items}
- [ ] The result is recognizably the same character as the required supplied source.
- [ ] Explicit target-phase changes are clearly visible rather than being suppressed by the source appearance.
- [ ] If the target phase changes apparent age, the face itself communicates that age change without relying only on hair color.
- [ ] Head and hair appearance match the Character.md factual and view-specific rules.
- [ ] The complete head and hairstyle silhouette are present and usable.
- [ ] Framing is natural and does not distort the character merely to satisfy technical fitment geometry.
- [ ] The background is transparent and no narrative environment or unrelated character was added.

## Notes
""",
        encoding="utf-8",
    )
    return {
        "status": str(bundle.get("next_status", "READY_FOR_RENDER")),
        "next_actor": str(bundle.get("next_actor", "AI_AGENT")),
        "final_prompt": str(paths["final_prompt"]),
        "compiled_sections": str(paths["compiled_sections"]),
        "dependency_manifest": str(paths["dependency_manifest"]),
        "image_review": str(paths["image_review"]),
        "diagnostics": str(paths["diagnostics"]) if prompt_variant == "generation" else "",
        "expected_output": str(output_dir / expected_output),
        "output_dir": str(output_dir),
        "view_token": view_token,
        "head_image_prompt_contract_version": 4,
        "reference_files": references,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a Head-Image job.")
    parser.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    result = compile_head_image_job(json.loads(Path(args.job).read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
