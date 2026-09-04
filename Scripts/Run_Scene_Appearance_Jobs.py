#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from Scripts.Compile_Character_Template import TemplateCompileError
from zet.services.pipeline_compiler_support import (
    job_get,
    load_bundle,
    load_view_data,
    normalize_view,
    reference_by_role,
    reference_files_for_job,
    require_job_field,
    resolve_project_path,
    validate_reference,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def compile_scene_appearance_job(job: dict, project_root: Path = PROJECT_ROOT) -> dict:
    job_id = require_job_field(job, "Job", "job_id")
    task = require_job_field(job, "Task", "task")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    body_view = require_job_field(job, "Body View", "body_view")
    appearance_id = require_job_field(job, "Scene Appearance ID", "scene_appearance_id")
    definition_path = resolve_project_path(
        project_root,
        require_job_field(job, "Definition Path", "definition_path"),
    )
    if task != "scene-appearance":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported Scene Appearance task: {task}")
    if not definition_path.is_file():
        raise TemplateCompileError("MISSING_TEMPLATE", f"Scene Appearance definition not found: {definition_path}")
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    if definition.get("appearance_id") != appearance_id:
        raise TemplateCompileError("DEFINITION_MISMATCH", "Scene Appearance definition ID does not match the asset.")
    if definition.get("character") != character or definition.get("phase") != phase:
        raise TemplateCompileError("DEFINITION_MISMATCH", "Scene Appearance character or phase does not match the asset.")

    bundle = load_bundle(project_root, "scene-appearance")
    view_token = normalize_view(project_root, body_view)
    view_data = load_view_data(project_root, view_token)
    references = reference_files_for_job(job)
    source = reference_by_role(references, "scene_appearance_source")
    validate_reference(source, "scene_appearance_source", project_root)
    configured = definition.get("supporting_references") or []
    expected_roles = [str(item.get("role") or "") for item in configured]
    if [str(item.get("role") or "") for item in references[1:]] != expected_roles:
        raise TemplateCompileError("REFERENCE_ORDER_MISMATCH", "Supporting references do not match the configured order.")
    for role in expected_roles:
        validate_reference(reference_by_role(references, role), role, project_root)

    output_dir = resolve_project_path(project_root, require_job_field(job, "Output Directory", "output_directory"))
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_output = job_get(job, "Expected Output", "expected_output") or f"Scene-Appearance_{body_view}_{appearance_id}.png"
    paths = {
        "final_prompt": output_dir / "Final_Image_Prompt.md",
        "compiled_sections": output_dir / "Compiled_Sections.md",
        "source_map": output_dir / "Prompt_Source_Map.json",
        "dependency_manifest": output_dir / "dependency_manifest.json",
        "prompt_review": output_dir / "Prompt_Review.md",
        "image_review": output_dir / "Image_Review.md",
    }
    guide_lines = [f"- Image 1: locked {definition.get('costume')} Costume-Dressing source for this exact view."]
    for index, item in enumerate(configured, start=2):
        guide_lines.append(f"- Image {index}: {str(item.get('label') or item.get('role')).strip()} visual reference only.")
    values = {
        "CHARACTER_NAME": character,
        "SCENE_APPEARANCE_NAME": str(definition.get("name") or appearance_id),
        "BODY_VIEW_DISPLAY": re.sub(r"\s+VIEW$", "", str(view_data.get("label") or view_token).upper()),
        "REFERENCE_GUIDE": "\n".join(guide_lines),
        "ARRANGEMENT_INSTRUCTIONS": str(definition.get("instructions") or "").strip(),
    }
    template_name = str(bundle.get("static_prompt_template") or "scene_appearance_v1")
    if not Path(template_name).suffix:
        template_name = f"{template_name}.md"
    template_path = project_root / "Config" / "Prompt_Templates" / template_name
    prompt = template_path.read_text(encoding="utf-8")
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", prompt)
    if unresolved:
        raise TemplateCompileError("UNRESOLVED_PLACEHOLDER", f"Unresolved Scene Appearance placeholders: {', '.join(unresolved)}")
    _write(paths["final_prompt"], prompt)
    _write(paths["compiled_sections"], f"# Scene Appearance\n\n{values['ARRANGEMENT_INSTRUCTIONS']}")
    paths["source_map"].write_text(json.dumps({
        "job_id": job_id,
        "task": task,
        "definition_path": str(definition_path),
        "template_path": str(template_path),
        "view_token": view_token,
        "metadata": values,
    }, indent=2) + "\n", encoding="utf-8")
    paths["dependency_manifest"].write_text(json.dumps({
        "job_id": job_id,
        "task": task,
        "character": character,
        "phase": phase,
        "scene_appearance_id": appearance_id,
        "definition_path": str(definition_path),
        "body_view_token": view_token,
        "required_reference_roles": ["scene_appearance_source", *expected_roles],
        "resources": references,
    }, indent=2) + "\n", encoding="utf-8")
    _write(paths["prompt_review"], f"""# Prompt Review

Job ID: {job_id}
Scene Appearance: {definition.get('name')}
View: {view_token}

- [ ] The prompt is concise and assigns every image exactly once.
- [ ] Image 1 is authoritative for identity, costume, view, framing, and style.
- [ ] Arrangement instructions use anatomical left and right.
- [ ] Only the minimum required arm and hand changes are allowed.
""")
    _write(paths["image_review"], f"""# Image Review

Job ID: {job_id}
Scene Appearance: {definition.get('name')}
View: {view_token}
Image File: {expected_output}

- [ ] Tsaeytte and Canonical Adventure Gear match Image 1.
- [ ] Body and head direction match the requested view and are not mirrored.
- [ ] Morrow is the only raven and is perched on Tsaeytte's anatomical left shoulder.
- [ ] The utility tusk is in Tsaeytte's anatomical right hand.
- [ ] The tusk is vertical with its pointed end on the ground and broken thick base upward.
- [ ] Tusk length, material, ridges, and proportions match its reference.
- [ ] Full body and tusk contact point are visible in neutral reference framing.
- [ ] There are no duplicate subjects, duplicate props, scenery, or unlisted objects.
""")
    return {
        "status": str(bundle.get("next_status") or "READY_FOR_RENDER"),
        "next_actor": str(bundle.get("next_actor") or "AI_AGENT"),
        **{key: str(path) for key, path in paths.items()},
        "expected_output": str(output_dir / expected_output),
        "output_dir": str(output_dir),
        "reference_files": references,
    }
