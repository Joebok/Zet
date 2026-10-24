"""Compile independent FRONT-anchored Head-Image Edit recipes."""
from pathlib import Path
import re

from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections, load_template_sections_with_sources
from Scripts.Job_File_Utils import (
    bundle_output_paths, finalize_chatgpt_prompt, prepare_chatgpt_prompt_contract,
    render_static_prompt_artifacts, select_prompt_sections, write_json_file,
)
from zet.services.pipeline_compiler_support import (
    load_body_reference_section_data, load_bundle, normalize_view, output_files,
    prompt_preview_compiler, reference_files_for_job, require_job_field,
    template_metadata, template_path_for_job, universe_art_style, validate_reference,
)
from zet.services.view_conditioning_service import ViewContext, condition_section

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SECTIONS = (
    "HEAD_EDIT_FRONT_DESCRIPTION", "HEAD_EDIT_PRESERVE", "HEAD_EDIT_VIEW_OVERRIDES",
    "HEAD_EDIT_REFERENCE_GUIDANCE", "HEAD_EDIT_EXPRESSION_GUIDANCE", "HEAD_EDIT_PHASE_CHANGES",
    "HEAD_EDIT_REVIEW_CRITERIA",
)
REQUIRED = (SECTIONS[0], SECTIONS[1], SECTIONS[2], SECTIONS[-1])
RECIPE_VERSION = 1


def validate_authoring(path):
    sections = load_template_sections(path)
    visible = {name: re.sub(r"<!--.*?-->", "", sections.get(name, ""), flags=re.S).strip() for name in REQUIRED}
    missing = [name for name in REQUIRED if not visible[name] or visible[name].startswith("[Describe")]
    if missing:
        raise TemplateCompileError("MISSING_HEAD_EDIT_AUTHORING", "Head-Image Edit requires its separate authoring sections: " + ", ".join(missing))
    return sections


@prompt_preview_compiler
def compile_head_image_edit_job(job, project_root=PROJECT_ROOT, *, prompt_variant="generation",
                                pipeline_mode="local", universe_root=None):
    if pipeline_mode != "local" or require_job_field(job, "Task", "task") != "head-image-edit":
        raise TemplateCompileError("INVALID_PIPELINE_MODE", "Head-Image Edit is a separate local pipeline.")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    view = normalize_view(project_root, require_job_field(job, "Head View", "head_view"))
    path = template_path_for_job(project_root, job, character, phase, universe_root=universe_root)
    validate_authoring(path)
    sections, sources = load_body_reference_section_data(project_root, path)
    # Never merge legacy head/hair/expression sections into this compiler.
    sections = {key: value for key, value in sections.items() if key in SECTIONS}
    sources = {key: value for key, value in sources.items() if key in SECTIONS}
    refs = [dict(ref) for ref in reference_files_for_job(job)]
    bases = [ref for ref in refs if ref.get("role") == "head_image_source"]
    if len(bases) > 1 or (view != "FRONT" and len(bases) != 1):
        raise TemplateCompileError("MISSING_REFERENCE", "Head-Image Edit requires one selected FRONT edit base for non-front views.")
    if bases and refs[0] is not bases[0]:
        raise TemplateCompileError("INVALID_REFERENCE", "The edit base must be Image 1.")
    for ref in refs:
        validate_reference(ref, str(ref.get("role") or "supporting reference"), project_root)
    apply_phase = view == "FRONT" and bool(bases) and job.get("Apply Phase Change") is True
    if job.get("Apply Phase Change") is True and view == "FRONT" and not bases:
        raise TemplateCompileError("MISSING_REFERENCE", "Phase change requires a FRONT source image.")
    if apply_phase and not re.sub(r"<!--.*?-->", "", sections.get("HEAD_EDIT_PHASE_CHANGES", ""), flags=re.S).strip():
        raise TemplateCompileError("MISSING_PHASE_CHANGES", "Author one Head-Image Edit phase-change section before applying it.")
    if view != "FRONT" or bases:
        sections["HEAD_EDIT_FRONT_DESCRIPTION"] = ""
    if view == "FRONT" and (not bases or apply_phase):
        sections["HEAD_EDIT_PRESERVE"] = ""
    if not apply_phase:
        sections["HEAD_EDIT_PHASE_CHANGES"] = ""
    bundle = {**load_bundle(project_root, "head-image-edit"), "legacy_static_prompt_template": ""}
    selection = select_prompt_sections(project_root, bundle, sections, sources, view,
                                      prompt_variant=prompt_variant, pipeline_mode="local")
    refs = auxiliary_references_for_texts(project_root, list(selection.sections.values()), refs, universe_root=universe_root)
    mode = "edit" if bases else "generate"
    refs, inputs, contract, manifest = prepare_chatgpt_prompt_contract(refs, render_mode=mode)
    style, style_sources = universe_art_style(universe_root)
    operation_path = project_root / "Config/Prompt_Templates/head_image_edit_operations.md"
    operations, operation_sources = load_template_sections_with_sources(operation_path, source_kind="task_template_section")
    operation_name = "HEAD_EDIT_OPERATION_" + (
        "FRONT_PHASE_CHANGE" if apply_phase else "FRONT_SOURCE" if bases and view == "FRONT" else view)
    operation = operations.get(operation_name, "").strip()
    if not operation:
        raise TemplateCompileError("MISSING_OPERATION", f"Missing Head-Image Edit operation: {operation_name}")
    guidance = ("Image 1 is the character and edit canvas. Preserve identity, skin, style, background and framing while applying the authored phase changes. Keep anatomical attachments fixed on the head; never mirror the image."
                if apply_phase else
                "Image 1 is the character and edit canvas. Preserve identity, expression, hair asymmetry, skin, style, background and framing while reprojecting the whole head into the requested view. Keep anatomical attachments fixed on the head; never mirror the image."
                if bases else "Establish the character identity from the complete description below.")
    guidance += " Supporting images govern only the explicitly assigned features; exclude their material, identity, hairstyle, neck, shoulders, framing and background. They do not override the target camera."
    output = Path(require_job_field(job, "Output Directory", "output_directory"))
    paths = bundle_output_paths(output, output_files(bundle), {
        "final_prompt": "Final_Image_Prompt.md", "compiled_sections": "Compiled_Sections.md",
        "source_map": "Prompt_Source_Map.json", "dependency_manifest": "dependency_manifest.json",
        "image_review": "Image_Review.md", "diagnostics": "Prompt_Compile_Diagnostics.json",
    })
    metadata = {"job_id": require_job_field(job, "Job", "job_id"), "task": "head-image-edit",
                "character": character, "phase": phase, "view_token": view, "recipe_version": RECIPE_VERSION}
    values = {**template_metadata(path), **contract, "HEAD_EDIT_OPERATION": operation,
              "HEAD_EDIT_INPUT_GUIDANCE": guidance,
              "HEAD_EDIT_STYLE": (style or template_metadata(path).get("CANONICAL_ART_STYLE", "")) if not bases else ""}
    prompt = render_static_prompt_artifacts(project_root=project_root, bundle=bundle,
        final_prompt_path=paths["final_prompt"], source_map_path=paths["source_map"],
        compiled_sections_path=paths["compiled_sections"], metadata=metadata, metadata_values=values,
        metadata_sources={"HEAD_EDIT_STYLE": style_sources.get("CANONICAL_ART_STYLE", {}),
                          "HEAD_EDIT_OPERATION": operation_sources[operation_name]},
        selection=selection, required_section_names=[], view_token=view, prompt_variant=prompt_variant,
        pipeline_mode="local", image_inputs=inputs)
    write_json_file(paths["dependency_manifest"], {**metadata, **manifest, "resources_allowed": True,
        "resources": refs, "pipeline_mode": "local", "required_reference_roles": ["head_image_source"] if bases else []})
    if prompt_variant == "generation":
        finalize_chatgpt_prompt(paths["diagnostics"], prompt, inputs, mode)
    review, _, _ = condition_section(sections.get("HEAD_EDIT_REVIEW_CRITERIA", ""),
        "HEAD_EDIT_REVIEW_CRITERIA", sources.get("HEAD_EDIT_REVIEW_CRITERIA", {}), ViewContext(head_view=view))
    paths["image_review"].write_text("# Head-Image Edit review\n\n" + review, encoding="utf-8")
    return {"status": "READY_FOR_RENDER", "next_actor": "AI_AGENT", "view_token": view,
            "output_dir": str(output), "reference_files": refs, "recipe_version": RECIPE_VERSION,
            "packet_facts": {"selected_sections": dict(selection.sections), "operation": operation,
                             "input_guidance": guidance, "review_criteria": review,
                             "style": values.get("HEAD_EDIT_STYLE", "")},
            **{key: str(value) for key, value in paths.items()}}
