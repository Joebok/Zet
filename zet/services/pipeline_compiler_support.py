from __future__ import annotations

import json
from pathlib import Path
import re

from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections_with_sources
from Scripts.Library_Paths import character_root, resolve_library_path
from zet.services.view_service import UnknownViewError, ViewService

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    try:
        return ViewService(project_root).normalize_token(value)
    except FileNotFoundError:
        path = project_root / "Config" / "Prompt_View_Aliases.json"
        raise TemplateCompileError("MISSING_CONFIG", f"Missing JSON file: {path}") from None
    except UnknownViewError as exc:
        raise TemplateCompileError("UNKNOWN_VIEW", str(exc)) from None


def load_view_data(project_root: Path, view_token: str) -> dict:
    """Load one configured view record and attach its token."""
    try:
        return ViewService(project_root).load_view_data(view_token)
    except FileNotFoundError:
        path = project_root / "Config" / "Prompt_View_Text.json"
        raise TemplateCompileError("MISSING_CONFIG", f"Missing JSON file: {path}") from None
    except UnknownViewError as exc:
        raise TemplateCompileError("UNKNOWN_VIEW", str(exc)) from None


def view_orientation_intro(view_data: dict) -> str:
    """Return the shared anatomical side instruction for one view."""
    token = str(view_data.get("_view_token") or "").strip().upper()
    label = str(view_data.get("label") or token.lower().replace("_", " ")).strip()
    viewpoint = re.sub(r"\s+view$", "", label, flags=re.IGNORECASE).strip() or label
    lines = ["Use anatomical left and right."]
    if token in {"FRONT_LEFT_3_4", "BACK_LEFT_3_4"}:
        lines.append(f"The {viewpoint} viewpoint primarily exposes the anatomical left side.")
    elif token in {"FRONT_RIGHT_3_4", "BACK_RIGHT_3_4"}:
        lines.append(f"The {viewpoint} viewpoint primarily exposes the anatomical right side.")
    return "\n".join(lines)


def with_view_orientation_intro(instruction: str, view_data: dict, include_intro: bool) -> str:
    """Prefix view instructions with anatomical side guidance when requested."""
    if not include_intro:
        return instruction
    return f"{view_orientation_intro(view_data)}\n\n{instruction}"


def view_instruction(view_data: dict, role: str, task: str, include_intro: bool = False) -> str:
    """Return task-specific view instruction text with optional shared intro."""
    role_key = f"{role}_instructions"
    task_key = str(task or "").strip()
    role_instructions = view_data.get(role_key)
    if isinstance(role_instructions, dict):
        value = role_instructions.get(task_key)
        if isinstance(value, str) and value.strip():
            return with_view_orientation_intro(value, view_data, include_intro)

    task_instructions = view_data.get("instructions_by_task")
    if isinstance(task_instructions, dict):
        value = task_instructions.get(task_key)
        if isinstance(value, str) and value.strip():
            return with_view_orientation_intro(value, view_data, include_intro)

    value = view_data.get("instruction")
    if isinstance(value, str) and value.strip():
        return with_view_orientation_intro(value, view_data, include_intro)

    raise TemplateCompileError(
        "MISSING_VIEW_INSTRUCTION",
        f"No {role} view instruction configured for task {task_key} and view {view_data.get('label', '')}.",
    )


def load_background_treatment(project_root: Path, key: str = "turnaround_source") -> str:
    """Load globally configured background prompt text."""
    data = load_json(project_root / "Config" / "Prompt_Background_Text.json")
    backgrounds = data.get("backgrounds", data)
    record = backgrounds.get(key) if isinstance(backgrounds, dict) else None
    if isinstance(record, dict):
        value = record.get("text")
    else:
        value = record
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise TemplateCompileError("MISSING_CONFIG", f"No background treatment configured for key: {key}")


def background_treatment_source_map(project_root: Path, key: str = "turnaround_source") -> dict[str, dict]:
    """Return source-map metadata for globally configured background prompt text."""
    return {
        "BACKGROUND_TREATMENT": {
            "source_kind": "config_background_instruction",
            "source_path": str(project_root / "Config" / "Prompt_Background_Text.json"),
            "source_label": "Turnaround source background treatment",
            "json_pointer": f"/backgrounds/{key}/text",
            "editable": True,
        }
    }


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
    shared_path = character_root(project_root) / "_Shared" / "Character_Template.md"
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
    """Resolve a job path with legacy library-path support."""
    return resolve_library_path(project_root, raw_path)


def require_job_field(job: dict, canonical: str, *keys: str) -> str:
    value = job_get(job, canonical, *keys)
    if not value:
        raise TemplateCompileError("MISSING_JOB_FIELD", f"Missing required job field: {canonical}")
    return value


def template_path_for_job(project_root: Path, job: dict, character: str, phase: str) -> Path:
    explicit = job_get(job, "Template Path", "template_path", "character_image_template")
    if explicit:
        return resolve_project_path(project_root, explicit)
    return character_root(project_root) / character / phase / "Character_Image_Template.md"


def expected_output_for_job(job: dict, view_data: dict) -> str:
    explicit = job_get(job, "Expected Output", "expected_output")
    if explicit and explicit.lower() not in {"none", "n/a", "human review"}:
        return explicit
    return f"Body-{view_data['output_name_fragment']}.png"


def output_files(bundle: dict) -> dict:
    value = bundle.get("output_files") or bundle.get("output_filenames") or {}
    return value if isinstance(value, dict) else {}


def reference_files_for_job(job: dict) -> list[dict]:
    value = job.get("Reference Files") or job.get("reference_files") or []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def reference_by_role(reference_files: list[dict], role: str) -> dict:
    for reference in reference_files:
        if reference.get("role") == role:
            return reference
    raise TemplateCompileError("MISSING_REFERENCE", f"Missing required reference slot: {role}")


def validate_reference(reference: dict, role: str, project_root: Path = PROJECT_ROOT) -> Path:
    raw_path = str(reference.get("path") or "").strip()
    if not raw_path:
        raise TemplateCompileError("MISSING_REFERENCE", f"Reference slot {role} has no path.")
    path = resolve_library_path(project_root, raw_path)
    if not path.exists() or not path.is_file():
        raise TemplateCompileError("MISSING_REFERENCE", f"Reference image for {role} was not found: {path}")
    return path
