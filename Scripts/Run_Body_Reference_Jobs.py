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
from Compile_Character_Template import TemplateCompileError, load_template_sections, load_template_sections_with_sources, select_sections
from Review_Prompt_Static import format_static_findings, load_checklist, review_prompt_text


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_json(path: Path) -> dict:
    if not path.exists():
        raise TemplateCompileError("MISSING_CONFIG", f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle(project_root: Path, task: str) -> dict:
    data = load_json(project_root / "Config" / "Prompt_Task_Bundles.json")
    bundles = data.get("bundles", data)
    bundle = bundles.get(task) if isinstance(bundles, dict) else None
    if not isinstance(bundle, dict):
        raise TemplateCompileError("MISSING_CONFIG", f"No prompt bundle configured for task: {task}")
    return bundle


def normalize_view(project_root: Path, raw_view: str) -> str:
    value = str(raw_view or "").strip()
    if not value:
        raise TemplateCompileError("MISSING_JOB_FIELD", "Missing body view.")
    aliases_data = load_json(project_root / "Config" / "Prompt_View_Aliases.json")
    aliases = aliases_data.get("aliases", aliases_data)
    normalized = re.sub(r"\s+", " ", value).strip().lower()
    candidates = [
        value,
        value.lower(),
        normalized,
        normalized.replace("_", "-"),
        normalized.replace(" ", "-"),
    ]
    for candidate in candidates:
        token = aliases.get(candidate) if isinstance(aliases, dict) else None
        if isinstance(token, str) and token.strip():
            return token.strip()
    raise TemplateCompileError("UNKNOWN_VIEW", f"Unknown view: {value}")


def load_view_data(project_root: Path, view_token: str) -> dict:
    data = load_json(project_root / "Config" / "Prompt_View_Text.json")
    views = data.get("views", data)
    view = views.get(view_token) if isinstance(views, dict) else None
    if not isinstance(view, dict):
        raise TemplateCompileError("UNKNOWN_VIEW", f"No view text configured for token: {view_token}")
    return view


def view_instruction(view_data: dict, role: str, task: str) -> str:
    role_key = f"{role}_instructions"
    task_key = str(task or "").strip()
    role_instructions = view_data.get(role_key)
    if isinstance(role_instructions, dict):
        value = role_instructions.get(task_key)
        if isinstance(value, str) and value.strip():
            return value

    task_instructions = view_data.get("instructions_by_task")
    if isinstance(task_instructions, dict):
        value = task_instructions.get(task_key)
        if isinstance(value, str) and value.strip():
            return value

    value = view_data.get("instruction")
    if isinstance(value, str) and value.strip():
        return value

    raise TemplateCompileError(
        "MISSING_VIEW_INSTRUCTION",
        f"No {role} view instruction configured for task {task_key} and view {view_data.get('label', '')}.",
    )


def _clean_template_field(value: str) -> str:
    return str(value or "").strip().strip("`").strip().strip("[]").strip()


def extract_template_field(template_path: Path, labels: list[str]) -> str:
    text = template_path.read_text(encoding="utf-8")
    for label in labels:
        escaped = re.escape(label).replace(r"\ ", r"\s+")
        match = re.search(rf"(?im)^\s*{escaped}\s*:\s*(.+?)\s*$", text)
        if match:
            return _clean_template_field(match.group(1))
    return ""


def _race_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def extract_character_race(template_path: Path) -> str:
    return extract_template_field(template_path, ["Character Race", "Race", "Species / Ancestry", "Species", "Ancestry"])


def character_gender(template_path: Path) -> str:
    value = extract_template_field(template_path, ["Character Gender", "Gender Presentation", "Gender"])
    key = _race_key(value)
    terms = set(key.split())
    if terms.intersection({"female", "feminine", "woman", "girl"}):
        return "female"
    if terms.intersection({"male", "masculine", "man", "boy"}):
        return "male"
    return value


def template_metadata(template_path: Path) -> dict[str, str]:
    """Extract reusable metadata values from a character template."""
    return {
        "CANONICAL_ART_STYLE": extract_template_field(template_path, ["Canonical Art Style"]),
        "CHARACTER_GENDER": character_gender(template_path),
        "FOOTWEAR": extract_template_field(template_path, ["Footwear"]),
        "FOOTWEAR_CONTACT": extract_template_field(template_path, ["Footwear Contact", "Footwear Contact Rule"]),
        "FOOTWEAR_GROUNDING": extract_template_field(template_path, ["Footwear Grounding", "Footwear Grounding Rule"]),
    }


def metadata_source_map(project_root: Path, template_path: Path, view_token: str, task: str, view_role: str) -> dict[str, dict]:
    view_pointer = f"/views/{view_token}/{view_role}_instructions/{task}"
    view_config_path = project_root / "Config" / "Prompt_View_Text.json"
    race_config_path = project_root / "Config" / "Race_Render_Rules.json"
    return {
        "CHARACTER_NAME": {
            "source_kind": "runtime_generated",
            "source_path": "",
            "source_label": "Asset character",
            "editable": False,
        },
        "CHARACTER_PHASE": {
            "source_kind": "runtime_generated",
            "source_path": "",
            "source_label": "Asset phase",
            "editable": False,
        },
        "VIEW_TOKEN": {
            "source_kind": "runtime_generated",
            "source_path": "",
            "source_label": "Normalized view token",
            "editable": False,
        },
        "VIEW_LABEL": {
            "source_kind": "config_view_instruction",
            "source_path": str(view_config_path),
            "source_label": "View label",
            "json_pointer": f"/views/{view_token}/label",
            "editable": True,
        },
        "VIEW_INSTRUCTION": {
            "source_kind": "config_view_instruction",
            "source_path": str(view_config_path),
            "source_label": f"{task} {view_role} view instruction",
            "json_pointer": view_pointer,
            "editable": True,
        },
        "CANONICAL_ART_STYLE": {
            "source_kind": "template_metadata_field",
            "source_path": str(template_path),
            "source_label": "Canonical Art Style",
            "metadata_key": "CANONICAL_ART_STYLE",
            "editable": True,
        },
        "CHARACTER_GENDER": {
            "source_kind": "template_metadata_field",
            "source_path": str(template_path),
            "source_label": "Gender Presentation",
            "metadata_key": "CHARACTER_GENDER",
            "editable": True,
        },
        "CHARACTER_RACE": {
            "source_kind": "config_rule",
            "source_path": str(race_config_path),
            "source_label": "Race label",
            "editable": True,
        },
        "RACE_BODY_REFERENCE_POSITIVE": {
            "source_kind": "config_rule",
            "source_path": str(race_config_path),
            "source_label": "Race body-reference positive rules",
            "editable": True,
        },
        "RACE_BODY_REFERENCE_NEGATIVE": {
            "source_kind": "config_rule",
            "source_path": str(race_config_path),
            "source_label": "Race body-reference negative rules",
            "editable": True,
        },
    }


def _format_rule_lines(values: object) -> str:
    if isinstance(values, str):
        return values.strip()
    if isinstance(values, list):
        return "\n".join(f"* {str(value).strip()}" for value in values if str(value).strip())
    return ""


def load_race_render_rules(project_root: Path, template_path: Path) -> dict[str, str]:
    data = load_json(project_root / "Config" / "Race_Render_Rules.json")
    races = data.get("races", {})
    if not isinstance(races, dict) or not races:
        raise TemplateCompileError("MISSING_CONFIG", "Race_Render_Rules.json must define at least one race.")

    raw_race = extract_character_race(template_path)
    default_race = str(data.get("default_race", "")).strip()
    requested_key = _race_key(raw_race or default_race)
    alias_map: dict[str, str] = {}

    for canonical, config in races.items():
        canonical_key = _race_key(canonical)
        alias_map[canonical_key] = canonical
        if isinstance(config, dict):
            label = str(config.get("label", "")).strip()
            if label:
                alias_map[_race_key(label)] = canonical
            for alias in config.get("aliases", []):
                alias_map[_race_key(str(alias))] = canonical

    canonical = alias_map.get(requested_key)
    if not canonical:
        source = raw_race or default_race or "(missing)"
        raise TemplateCompileError("UNKNOWN_RACE", f"Unknown character race/species for render rules: {source}")

    config = races.get(canonical, {})
    body_reference = config.get("body_reference", {}) if isinstance(config, dict) else {}
    if not isinstance(body_reference, dict):
        body_reference = {}

    label = str(config.get("label", canonical)).strip() if isinstance(config, dict) else canonical
    return {
        "CHARACTER_RACE": label,
        "RACE_BODY_REFERENCE_POSITIVE": _format_rule_lines(body_reference.get("positive", [])),
        "RACE_BODY_REFERENCE_NEGATIVE": _format_rule_lines(body_reference.get("negative", [])),
    }


def _technical_modesty_variant_for_gender(gender_presentation: str) -> str:
    value = _race_key(gender_presentation)
    if "youth" in value.split():
        return "TECHNICAL_MODESTY_LAYER_YOUTH"
    if any(term in value.split() for term in ("female", "feminine", "woman", "girl")):
        return "TECHNICAL_MODESTY_LAYER_FEMININE"
    if any(term in value.split() for term in ("male", "masculine", "man", "boy")):
        return "TECHNICAL_MODESTY_LAYER_MASCULINE"
    return ""


def load_body_reference_sections(project_root: Path, template_path: Path) -> dict[str, str]:
    return load_body_reference_section_data(project_root, template_path)[0]


def load_body_reference_section_data(project_root: Path, template_path: Path) -> tuple[dict[str, str], dict[str, dict]]:
    shared_path = project_root / "_Lib" / "Characters" / "_Shared" / "Character_Template.md"
    sections, sources = load_template_sections_with_sources(
        template_path,
        source_kind="character_template_section",
        source_label=f"Character template: {template_path.name}",
    )
    if shared_path.exists():
        shared_sections, shared_sources = load_template_sections_with_sources(
            shared_path,
            source_kind="shared_template_section",
            source_label="Shared character template",
        )
    else:
        shared_sections, shared_sources = {}, {}

    shared_section_names = [
        "TECHNICAL_MODESTY_LAYER",
        "TECHNICAL_MODESTY_LAYER_FEMININE",
        "TECHNICAL_MODESTY_LAYER_MASCULINE",
        "TECHNICAL_MODESTY_LAYER_YOUTH",]
    shared_section_names.extend(
        name for name in shared_sections
        if name == "NEUTRAL_POSE_STANCE" or name.startswith("NEUTRAL_POSE_STANCE_VIEW_")
    )
    for name in shared_section_names:
        if name in shared_sections:
            sections[name] = shared_sections[name]
            sources[name] = shared_sources.get(name, {})

    gender_presentation = extract_template_field(template_path, ["Gender Presentation", "Gender"])
    variant_name = _technical_modesty_variant_for_gender(gender_presentation)
    if variant_name and variant_name in sections:
        sections["TECHNICAL_MODESTY_LAYER"] = sections[variant_name]
        if variant_name in sources:
            sources["TECHNICAL_MODESTY_LAYER"] = dict(sources[variant_name], section_name="TECHNICAL_MODESTY_LAYER")
    return sections, sources


def job_get(job: dict, *keys: str) -> str:
    for key in keys:
        value = job.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def resolve_project_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return project_root / path


def require_job_field(job: dict, canonical: str, *keys: str) -> str:
    value = job_get(job, canonical, *keys)
    if not value:
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Missing required job field: {canonical}")
    return value


def template_path_for_job(project_root: Path, job: dict, character: str, phase: str) -> Path:
    explicit = job_get(job, "Template Path", "template_path", "character_image_template")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return project_root / "_Lib" / "Characters" / character / phase / "Character_Image_Template.md"


def output_dir_for_job(project_root: Path, job: dict, character: str, phase: str, view_data: dict) -> Path:
    explicit = job_get(job, "Output Directory", "output_directory", "Folder", "folder")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return project_root / "_Lib" / "Characters" / character / phase / "Body_Reference" / str(view_data["folder_name"])


def expected_output_for_job(job: dict, view_data: dict) -> str:
    explicit = job_get(job, "Expected Output", "expected_output")
    if explicit and explicit.lower() not in {"none", "n/a", "human review"}:
        return explicit
    return f"Body-{view_data['output_name_fragment']}.png"


def output_files(bundle: dict) -> dict:
    value = bundle.get("output_files") or bundle.get("output_filenames") or {}
    return value if isinstance(value, dict) else {}


def resource_policy(bundle: dict) -> dict:
    value = bundle.get("resources") or bundle.get("resource_policy") or {}
    return value if isinstance(value, dict) else {}


def write_dependency_manifest(path: Path, job_id: str, character: str, phase: str, view_token: str, bundle: dict) -> None:
    manifest = {
        "job_id": job_id,
        "task": "body-reference",
        "character": character,
        "phase": phase,
        "view_token": view_token,
        "resources_allowed": False,
        "resources": [],
        "resource_policy": resource_policy(bundle),
        "notes": [
            "Body-reference uses no external, cached, discovered, or prior-rendered image resources unless explicitly allowed by future task configuration."
        ],
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_prompt_review(path: Path, metadata: dict[str, str], prompt_path: Path, findings: list[str]) -> None:
    path.write_text(
        f"""# Prompt Review

Job ID: {metadata['job_id']}
Task: {metadata['task']}
Character: {metadata['character']}
Phase: {metadata['phase']}
View: {metadata['view_token']}
Prompt File: {prompt_path}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Prompt specifies full-body technical body-reference.
- [ ] Prompt includes requested view token and plain-language view instruction.
- [ ] Prompt includes body facts.
- [ ] Prompt includes identity/body preservation rules.
- [ ] Prompt includes plain tank top and shorts fitment clothing.
- [ ] Prompt avoids costume sections.
- [ ] Prompt avoids picaresque/flavor sections.
- [ ] Prompt avoids narrative scene instructions.
- [ ] Prompt avoids emotional acting.
- [ ] Prompt avoids props/weapons/equipment.
- [ ] Prompt contains no unresolved placeholders.
- [ ] Prompt contains no ZET markers.

## Static Review Findings

{format_static_findings(findings)}

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
View: {metadata['view_token']}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Full body visible from head to feet.
- [ ] Requested view is correct.
- [ ] Body proportions match the template.
- [ ] Fitment shell is correct.
- [ ] No costume details were added.
- [ ] No props or weapons were added.
- [ ] No narrative scene was added.
- [ ] Lighting/background are neutral.
- [ ] Image is useful for later head/costume fitment.

## Notes
""",
        encoding="utf-8",
    )


def compile_body_reference_job(job: dict, project_root: Path = PROJECT_ROOT) -> dict:
    job_id = require_job_field(job, "Job", "job_id", "Job ID")
    task = require_job_field(job, "Task", "task")
    character = require_job_field(job, "Character", "character")
    phase = require_job_field(job, "Phase", "phase")
    raw_view = require_job_field(job, "Body View", "body_view", "View", "view")

    if task != "body-reference":
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Unsupported task for body-reference runner: {task}")

    bundle = load_bundle(project_root, "body-reference")
    view_token = normalize_view(project_root, raw_view)
    view_data = load_view_data(project_root, view_token)
    template_path = template_path_for_job(project_root, job, character, phase)
    output_dir = output_dir_for_job(project_root, job, character, phase, view_data)
    expected_output = expected_output_for_job(job, view_data)

    all_sections, section_sources = load_body_reference_section_data(project_root, template_path)
    selection = select_sections(all_sections, bundle, view_token, section_sources)
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
    prompt_review_path = output_dir / files.get("prompt_review", "Prompt_Review.md")
    image_review_path = output_dir / files.get("image_review", "Image_Review.md")

    metadata = {
        "job_id": job_id,
        "task": task,
        "character": character,
        "phase": phase,
        "view_token": view_token,
    }
    template_file = prompt_template_path(project_root, str(bundle.get("static_prompt_template", "")))
    metadata_values = {
        "CHARACTER_NAME": character,
        "CHARACTER_PHASE": phase,
        "VIEW_TOKEN": view_token,
        "VIEW_LABEL": str(view_data["label"]),
        "VIEW_INSTRUCTION": view_instruction(view_data, "body", task),
        **template_metadata(template_path),
        **load_race_render_rules(project_root, template_path),
    }
    prompt_text, source_map = render_static_prompt_with_source_map(
        template_file.read_text(encoding="utf-8"),
        template_path=template_file,
        metadata=metadata_values,
        metadata_sources=metadata_source_map(project_root, template_path, view_token, task, "body"),
        selection=selection,
        required_section_names=list(bundle.get("required_sections", [])),
        view_token=view_token,
        final_prompt_name=final_prompt_path.name,
    )
    final_prompt_path.write_text(prompt_text, encoding="utf-8")
    source_map_path.write_text(json.dumps({**source_map, **metadata}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_compiled_sections(compiled_sections_path, job_metadata=metadata, view_token=view_token, selection=selection)
    write_dependency_manifest(manifest_path, job_id, character, phase, view_token, bundle)

    checklist = load_checklist(project_root, str(bundle.get("review_checklist", "")))
    findings = review_prompt_text(prompt_text, checklist)
    write_prompt_review(prompt_review_path, metadata, final_prompt_path, findings)
    write_image_review(image_review_path, metadata, expected_output)

    return {
        "status": str(bundle.get("next_status", "READY_FOR_PROMPT_REVIEW")),
        "next_actor": str(bundle.get("next_actor", "HUMAN")),
        "final_prompt": str(final_prompt_path),
        "compiled_sections": str(compiled_sections_path),
        "dependency_manifest": str(manifest_path),
        "prompt_review": str(prompt_review_path),
        "image_review": str(image_review_path),
        "expected_output": str(output_dir / expected_output),
        "output_dir": str(output_dir),
        "view_token": view_token,
    }


def load_job_list(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "jobs": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data.setdefault("jobs", [])
        return data
    if isinstance(data, list):
        return {"version": 1, "jobs": data}
    raise TemplateCompileError("MISSING_CONFIG", f"Job list must be a JSON object or array: {path}")


def row_matches(job: dict, only_job: str | None = None) -> bool:
    if only_job and job_get(job, "Job", "Job ID", "job_id") != only_job:
        return False
    return (
        job_get(job, "Task", "task") == "body-reference"
        and job_get(job, "Status", "status").upper() == "READY_FOR_COMPILE"
        and job_get(job, "Next Actor", "next_actor").upper() == "PYTHON"
    )


def update_job_success(job: dict, result: dict) -> None:
    timestamp = now_iso()
    job["Status"] = result["status"]
    job["Next Actor"] = result["next_actor"]
    job["Final Prompt"] = result["final_prompt"]
    job["Compiled Sections"] = result["compiled_sections"]
    job["Dependency Manifest"] = result["dependency_manifest"]
    job["Prompt Review"] = result["prompt_review"]
    job["Image Review"] = result["image_review"]
    job["Expected Output"] = result["expected_output"]
    job["Last Updated"] = timestamp
    job["Error Code"] = ""
    job["Error Message"] = ""
    job["status"] = result["status"]
    job["next_actor"] = result["next_actor"]
    job["final_prompt"] = result["final_prompt"]
    job["compiled_sections"] = result["compiled_sections"]
    job["dependency_manifest"] = result["dependency_manifest"]
    job["prompt_review"] = result["prompt_review"]
    job["image_review"] = result["image_review"]
    job["expected_output"] = result["expected_output"]
    job["last_updated"] = timestamp
    job["error"] = {"state": "NONE", "code": "", "message": "", "time": ""}


def update_job_error(job: dict, exc: Exception) -> None:
    code = exc.code if isinstance(exc, TemplateCompileError) else type(exc).__name__
    timestamp = now_iso()
    job["Status"] = "ERROR"
    job["Last Updated"] = timestamp
    job["Error Code"] = code
    job["Error Message"] = str(exc)
    job["status"] = "ERROR"
    job["last_updated"] = timestamp
    job["error"] = {
        "state": "ERROR",
        "code": code,
        "message": str(exc),
        "time": timestamp,
    }


def run_job_list(job_list_path: Path, only_job: str | None = None, dry_run: bool = False) -> int:
    data = load_job_list(job_list_path)
    count = 0
    for job in data.get("jobs", []):
        if not isinstance(job, dict) or not row_matches(job, only_job):
            continue
        count += 1
        if dry_run:
            continue
        try:
            update_job_success(job, compile_body_reference_job(job))
        except Exception as exc:
            update_job_error(job, exc)
    if not dry_run:
        job_list_path.parent.mkdir(parents=True, exist_ok=True)
        job_list_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile body-reference jobs without AI or rendering.")
    parser.add_argument("--job-list", required=True, help="Path to Job_List.json.")
    parser.add_argument("--only-job", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    count = run_job_list(Path(args.job_list).expanduser(), only_job=args.only_job, dry_run=args.dry_run)
    print(f"Body-reference jobs matched: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

