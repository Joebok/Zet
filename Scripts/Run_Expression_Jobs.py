#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from Build_Static_Final_Prompt import prompt_template_path, render_static_prompt_with_source_map, write_compiled_sections
from Compile_Character_Template import TemplateCompileError, select_sections
from Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Run_Body_Reference_Jobs import (
    job_get,
    load_bundle,
    load_body_reference_section_data,
    output_files,
    require_job_field,
    resolve_project_path,
    template_metadata,
    template_path_for_job,
)
from Run_Head_Fitment_Jobs import reference_by_role, reference_files_for_job, validate_reference

PROMPT_INSERT_RE = re.compile(r"\{\{PROMPT_INSERT\}\}(.*?)\{\{/PROMPT_INSERT\}\}", re.DOTALL)
SECTION_MARKER_RE = re.compile(r"^~?\{\{SECTION:([A-Z0-9_{}]+)\}\}$")
PROMPT_INSERT_SECTIONS = [
    "EXPRESSION_DESCRIPTION_FACTS",
    "IDENTITY_PRESERVATION_CORE",
    "IDENTITY_PRESERVATION_FACE",
    "IDENTITY_PRESERVATION_HAIR",
    "IDENTITY_PRESERVATION_EARS",
    "IDENTITY_PRESERVATION_COSTUME",
    "NEGATIVE_GUIDANCE_GENERAL",
    "NEGATIVE_GUIDANCE_JOB_SPECIFIC",
]


def now_iso() -> str:
    """Return an ISO timestamp for generated review artifacts."""
    return datetime.now().isoformat(timespec="seconds")


def safe_name(value: str) -> str:
    """Return a filesystem-safe name fragment."""
    text = str(value or "").strip()
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text).strip("-") or "Expression"


def expression_definition_path_for_job(project_root: Path, job: dict, character: str, phase: str) -> Path:
    """Return the expression definition path for a job."""
    explicit = job_get(job, "Expression Definition Path", "expression_definition_path")
    if explicit:
        return resolve_project_path(project_root, explicit)
    expression_label = job_get(job, "Expression Label", "Expression", "expression") or "Expression"
    return project_root / "_Lib" / "Characters" / character / phase / "Expressions" / f"{safe_name(expression_label)}.md"


def output_dir_for_job(project_root: Path, job: dict, character: str, phase: str, expression_label: str) -> Path:
    """Return the output directory for an expression job."""
    explicit = job_get(job, "Output Directory", "output_directory", "Folder", "folder")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return project_root / "_Lib" / "Pipelines" / character / phase / "Expression" / safe_name(expression_label)


def expression_definition_text(path: Path) -> str:
    """Read the expression definition body."""
    if not path.exists() or not path.is_file():
        raise TemplateCompileError("MISSING_TEMPLATE", f"Expression definition not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise TemplateCompileError("EMPTY_TEMPLATE", f"Expression definition is empty: {path}")
    target = expression_target_text(text)
    if target:
        return target
    return text


def expression_target_text(text: str) -> str:
    """Extract the expression-specific target block from a full structured expression prompt."""
    start = None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().upper() == "EXPRESSION TARGET":
            start = index + 1
            break
    if start is None:
        return ""

    stop_headings = {
        "GENERAL EXPRESSION RULES",
        "IDENTITY PRESERVATION",
        "GOOD OUTPUT",
        "BAD OUTPUT",
        "NEGATIVE CONSTRAINTS",
        "FINAL OUTPUT SUMMARY",
    }
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].strip().upper() in stop_headings:
            end = index
            break
    return strip_prompt_insert_markers("\n".join(lines[start:end])).strip()


def strip_prompt_insert_markers(text: str) -> str:
    """Return prompt-insert block contents without their wrapper markers."""
    return PROMPT_INSERT_RE.sub(lambda match: match.group(1).strip(), text)


def prompt_inserts_by_section(text: str) -> dict[str, str]:
    """Map prompt insert blocks to the nearest previous compiler section marker."""
    lines = text.splitlines()
    line_starts = []
    cursor = 0
    for line in lines:
        line_starts.append(cursor)
        cursor += len(line) + 1

    sections_by_line: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        marker = SECTION_MARKER_RE.match(line.strip())
        if marker:
            sections_by_line.append((index, marker.group(1)))

    inserts: dict[str, list[str]] = {section: [] for section in PROMPT_INSERT_SECTIONS}
    for match in PROMPT_INSERT_RE.finditer(text):
        start_line = 0
        for index, offset in enumerate(line_starts):
            if offset <= match.start():
                start_line = index
            else:
                break
        previous_section = ""
        for line_index, section in sections_by_line:
            if line_index < start_line:
                previous_section = section
            else:
                break
        if previous_section in inserts:
            body = match.group(1).strip()
            if body:
                inserts[previous_section].append(body)
    return {section: "\n\n".join(parts) for section, parts in inserts.items() if parts}


def write_dependency_manifest(path: Path, metadata: dict, reference_files: list[dict]) -> None:
    """Write the expression dependency manifest."""
    manifest = {
        "job_id": metadata["job_id"],
        "task": "expression",
        "character": metadata["character"],
        "phase": metadata["phase"],
        "expression_label": metadata["expression_label"],
        "identity_key_label": metadata["identity_key_label"],
        "expression_definition_path": metadata["expression_definition_path"],
        "resources_allowed": True,
        "resources": reference_files,
        "required_reference_roles": ["identity_key"],
        "notes": [
            "Expression jobs use an explicit Identity Key image reference.",
            "The Identity Key controls identity, framing, view angle, visible costume, lighting, and style.",
        ],
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_prompt_review(path: Path, metadata: dict, prompt_path: Path) -> None:
    """Write a prompt-review checklist for an expression asset."""
    path.write_text(
        f"""# Prompt Review

Job ID: {metadata['job_id']}
Task: expression
Character: {metadata['character']}
Phase: {metadata['phase']}
Expression: {metadata['expression_label']}
Identity Key: {metadata['identity_key_label']}
Prompt File: {prompt_path}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Prompt follows the selected Identity Key framing.
- [ ] Prompt changes expression without redesigning identity, costume, hair, ears, age, or species.
- [ ] Expression definition is clear and not contradicted by generic expression rules.
- [ ] No sheet, collage, label, caption, or narrative scene is requested.

## Notes
""",
        encoding="utf-8",
    )


def write_image_review(path: Path, metadata: dict, expected_output: str) -> None:
    """Write an image-review checklist for an expression asset."""
    path.write_text(
        f"""# Image Review

Job ID: {metadata['job_id']}
Task: expression
Character: {metadata['character']}
Phase: {metadata['phase']}
Expression: {metadata['expression_label']}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Image matches the Identity Key framing and visible body extent.
- [ ] Character identity, hair, ears, age, species, and costume cues are preserved.
- [ ] Requested expression is clear without caricature or identity distortion.
- [ ] No text label, caption, sheet, collage, or narrative scene was generated.

## Notes
""",
        encoding="utf-8",
    )


def compile_expression_job(job: dict, project_root: Path = PROJECT_ROOT) -> dict:
    """Compile a standalone expression prompt from an Identity Key and definition file."""
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    task = (job_get(job, "Task", "task") or "expression").lower()
    if task != "expression":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported task for expression runner: {task}")
    expression_label = require_job_field(job, "Expression Label", "Expression", "expression", "expression_label")
    identity_key_label = job_get(job, "Identity Key Label", "identity_key_label") or "Identity Key"
    expected_output = job_get(job, "Expected Output", "expected_output") or f"Expression_{safe_name(expression_label)}.png"
    template_path = template_path_for_job(project_root, job, character, phase)
    definition_path = expression_definition_path_for_job(project_root, job, character, phase)
    definition_source_text = definition_path.read_text(encoding="utf-8") if definition_path.exists() else ""
    definition_text = expression_definition_text(definition_path)
    prompt_inserts = prompt_inserts_by_section(definition_source_text)
    bundle = load_bundle(project_root, "expression")
    references = reference_files_for_job(job)
    identity_key = reference_by_role(references, "identity_key")
    validate_reference(identity_key, "identity_key")
    output_dir = output_dir_for_job(project_root, job, character, phase, expression_label)
    output_dir.mkdir(parents=True, exist_ok=True)

    sections, section_sources = load_body_reference_section_data(project_root, template_path)
    selection = select_sections(sections, bundle, "EXPRESSION", section_sources)
    files = output_files(bundle)
    prompt_path = output_dir / files.get("final_prompt", "Final_Image_Prompt.md")
    compiled_sections_path = output_dir / files.get("compiled_sections", "Compiled_Sections.md")
    manifest_path = output_dir / files.get("dependency_manifest", "dependency_manifest.json")
    prompt_review_path = output_dir / files.get("prompt_review", "Prompt_Review.md")
    image_review_path = output_dir / files.get("image_review", "Image_Review.md")
    source_map_path = output_dir / files.get("source_map", "Prompt_Source_Map.json")

    metadata = {
        "job_id": job_get(job, "Job", "job") or f"Expression_{safe_name(expression_label)}",
        "task": "expression",
        "character": character,
        "phase": phase,
        "expression_label": expression_label,
        "identity_key_label": identity_key_label,
        "expression_definition_path": str(definition_path),
        "expected_output": expected_output,
    }
    metadata_values = {
        "CHARACTER_NAME": character,
        "CHARACTER_PHASE": phase,
        "EXPRESSION_LABEL": expression_label,
        "IDENTITY_KEY_LABEL": identity_key_label,
        "EXPRESSION_DEFINITION_PATH": str(definition_path),
        "EXPRESSION_DEFINITION": definition_text,
        **template_metadata(template_path),
    }
    for section in PROMPT_INSERT_SECTIONS:
        metadata_values[f"EXPRESSION_PROMPT_INSERT_AFTER_{section}"] = prompt_inserts.get(section, "")
    metadata_sources = {
        "EXPRESSION_LABEL": {"source_kind": "runtime_generated", "source_label": "Expression label", "editable": False},
        "IDENTITY_KEY_LABEL": {"source_kind": "runtime_generated", "source_label": "Identity Key label", "editable": False},
        "EXPRESSION_DEFINITION_PATH": {"source_kind": "runtime_generated", "source_label": "Expression definition path", "editable": False},
        "EXPRESSION_DEFINITION": {
            "source_kind": "expression_definition",
            "source_path": str(definition_path),
            "source_label": "Expression Definition",
            "editable": True,
        },
    }
    for section in PROMPT_INSERT_SECTIONS:
        metadata_sources[f"EXPRESSION_PROMPT_INSERT_AFTER_{section}"] = {
            "source_kind": "expression_definition",
            "source_path": str(definition_path),
            "source_label": f"Expression prompt insert after {section}",
            "editable": True,
        }
    template_file = prompt_template_path(project_root, str(bundle.get("static_prompt_template", "")))
    prompt_text, source_map = render_static_prompt_with_source_map(
        template_file.read_text(encoding="utf-8"),
        template_path=template_file,
        metadata=metadata_values,
        metadata_sources=metadata_sources,
        selection=selection,
        required_section_names=list(bundle.get("required_sections", [])),
        view_token="EXPRESSION",
        final_prompt_name=prompt_path.name,
    )
    references = auxiliary_references_for_texts(
        project_root,
        [prompt_text],
        references,
    )
    prompt_path.write_text(prompt_text, encoding="utf-8")
    source_map_path.write_text(json.dumps({**source_map, **metadata}, indent=2) + "\n", encoding="utf-8")
    write_compiled_sections(compiled_sections_path, job_metadata=metadata, view_token="EXPRESSION", selection=selection)
    write_dependency_manifest(manifest_path, metadata, references)
    write_prompt_review(prompt_review_path, metadata, prompt_path)
    write_image_review(image_review_path, metadata, expected_output)
    return {
        "final_prompt": str(prompt_path),
        "compiled_sections": str(compiled_sections_path),
        "dependency_manifest": str(manifest_path),
        "prompt_review": str(prompt_review_path),
        "image_review": str(image_review_path),
        "source_map": str(source_map_path),
        "expected_output": expected_output,
        "status": str(bundle.get("next_status", "READY_FOR_PROMPT_REVIEW")),
        "next_actor": str(bundle.get("next_actor", "HUMAN_AGENT")),
        "reference_files": references,
    }


def main() -> None:
    """Compile one expression job from a JSON file."""
    parser = argparse.ArgumentParser(description="Compile a standalone expression prompt.")
    parser.add_argument("--job", required=True, help="Path to a single expression job JSON file.")
    args = parser.parse_args()
    job_path = Path(args.job)
    result = compile_expression_job(json.loads(job_path.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
