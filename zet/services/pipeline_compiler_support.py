from __future__ import annotations

import json
from pathlib import Path
import re

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Library_Paths import character_root, resolve_library_path
from zet.services.prompt_template_service import PromptTemplateService
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


def view_orientation_intro(view_data: dict, include_orientation_details: bool = False) -> str:
    """Return the shared anatomical side instruction for one view."""
    token = str(view_data.get("_view_token") or "").strip().upper()
    label = str(view_data.get("label") or token.lower().replace("_", " ")).strip()
    viewpoint = re.sub(r"\s+view$", "", label, flags=re.IGNORECASE).strip() or label
    lines = ["Use anatomical left and right."]
    if token in {"FRONT_LEFT_3_4", "BACK_LEFT_3_4"}:
        lines.append(f"The {viewpoint} viewpoint primarily exposes the anatomical left side.")
    elif token in {"FRONT_RIGHT_3_4", "BACK_RIGHT_3_4"}:
        lines.append(f"The {viewpoint} viewpoint primarily exposes the anatomical right side.")
    if include_orientation_details:
        orientation = str(view_data.get("orientation_sentence") or "").strip()
        camera_position = str(view_data.get("camera_position") or "").strip()
        details = [value for value in (orientation, "Do not rotate the head independently of the body.", camera_position) if value]
        if orientation:
            if len(lines) > 1:
                lines[-1] = f"{lines[-1]} {' '.join(details)}"
            else:
                lines.append(" ".join(details))
    return "\n".join(lines)


def with_view_orientation_intro(
    instruction: str,
    view_data: dict,
    include_intro: bool,
    include_orientation_details: bool = False,
) -> str:
    """Prefix view instructions with anatomical side guidance when requested."""
    if not include_intro:
        return instruction
    return f"{view_orientation_intro(view_data, include_orientation_details)}\n\n{instruction}"


def body_reference_head_facing_rule(view_data: dict) -> str:
    """Return a mannequin head/body orientation lock for one body-reference view."""
    label = str(view_data.get("label") or view_data.get("_view_token") or "").strip()
    direction = re.sub(r"\s+view$", "", label, flags=re.IGNORECASE).strip().upper()
    qualifier = "" if "three-quarter" in label.lower() else "direct "
    if qualifier:
        direction = re.sub(r"^DIRECT\s+", "", direction)
    return f"The mannequin head must face the same {qualifier}{direction} view as the body."


def view_instruction(view_data: dict, role: str, task: str, include_intro: bool = False) -> str:
    """Return task-specific view instruction text with optional shared intro."""
    role_key = f"{role}_instructions"
    task_key = str(task or "").strip()

    def finalize(value: str) -> str:
        instruction = value
        if role == "body" and task_key == "body-reference":
            instruction = f"{instruction}\n\n{body_reference_head_facing_rule(view_data)}"
        return with_view_orientation_intro(
            instruction,
            view_data,
            include_intro,
            include_orientation_details=role == "body" and (task_key == "body-reference" or task_key == "character-assembly"),
        )

    role_instructions = view_data.get(role_key)
    if isinstance(role_instructions, dict):
        value = role_instructions.get(task_key)
        if isinstance(value, str) and value.strip():
            return finalize(value)

    task_instructions = view_data.get("instructions_by_task")
    if isinstance(task_instructions, dict):
        value = task_instructions.get(task_key)
        if isinstance(value, str) and value.strip():
            return finalize(value)

    value = view_data.get("instruction")
    if isinstance(value, str) and value.strip():
        return finalize(value)

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


def load_race_render_rules(project_root: Path, template_path: Path, view_token: str = "") -> dict[str, str]:
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
    view_instructions = body_reference.get("view_instructions", {})
    if not isinstance(view_instructions, dict):
        view_instructions = {}

    positive_rules = _format_rule_lines(body_reference.get("positive", []))
    view_rules = _format_rule_lines(view_instructions.get(view_token, []))
    if view_rules:
        positive_rules = "\n".join(value for value in (positive_rules, view_rules) if value)

    label = str(config.get("label", canonical)).strip() if isinstance(config, dict) else canonical
    return {
        "CHARACTER_RACE": label,
        "RACE_BODY_REFERENCE_POSITIVE": positive_rules,
        "RACE_BODY_REFERENCE_NEGATIVE": _format_rule_lines(body_reference.get("negative", [])),
    }


def technical_modesty_variant(character_phase: str, gender_presentation: str) -> str:
    phase_terms = set(_race_key(character_phase).split())
    gender_terms = set(_race_key(gender_presentation).split())
    if "youth" in phase_terms:
        return "TECHNICAL_MODESTY_LAYER_YOUTH"
    if "adult" in phase_terms and gender_terms.intersection({"female", "feminine", "woman", "girl"}):
        return "TECHNICAL_MODESTY_LAYER_ADULT_FEMININE"
    if "adult" in phase_terms and gender_terms.intersection({"male", "masculine", "man", "boy"}):
        return "TECHNICAL_MODESTY_LAYER_ADULT_MASCULINE"
    return "TECHNICAL_MODESTY_LAYER_DEFAULT"


def load_body_reference_sections(project_root: Path, template_path: Path) -> dict[str, str]:
    return load_body_reference_section_data(project_root, template_path)[0]


def load_body_reference_section_data(project_root: Path, template_path: Path) -> tuple[dict[str, str], dict[str, dict]]:
    global_path = project_root / "Config" / "Prompt_Global_Sections.md"
    prompt_templates = PromptTemplateService(project_root)
    sections, sources = prompt_templates.load_marked_sections([
        (template_path, "character_template_section", f"Character template: {template_path.name}"),
    ])
    if global_path.exists():
        global_sections, global_sources = prompt_templates.load_marked_sections([
            (global_path, "global_prompt_section", "Global prompt sections"),
        ])
    else:
        global_sections, global_sources = {}, {}

    global_section_names = list(
        name for name in global_sections
        if name == "NEUTRAL_POSE_STANCE" or name.startswith("NEUTRAL_POSE_STANCE_VIEW_")
    )
    for name in global_section_names:
        sections[name] = global_sections[name]
        sources[name] = global_sources.get(name, {})

    character_phase = extract_template_field(template_path, ["Character Phase", "Phase"])
    gender_presentation = extract_template_field(template_path, ["Gender Presentation", "Gender"])
    variant_name = technical_modesty_variant(character_phase, gender_presentation)
    if variant_name in global_sections:
        sections["TECHNICAL_MODESTY_LAYER"] = global_sections[variant_name]
        if variant_name in global_sources:
            sources["TECHNICAL_MODESTY_LAYER"] = dict(
                global_sources[variant_name],
                section_name="TECHNICAL_MODESTY_LAYER",
                selected_variant=variant_name,
            )
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
    return character_root(project_root) / character / phase / "Character.md"


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


ASSEMBLY_STYLE_MODES = {"MATCHED_STYLE", "HARMONIZE_STYLE"}


def normalize_assembly_style_mode(raw_mode: str | None) -> str:
    mode = re.sub(r"[^A-Z0-9]+", "_", str(raw_mode or "MATCHED_STYLE").strip().upper()).strip("_")
    if mode not in ASSEMBLY_STYLE_MODES:
        raise TemplateCompileError(
            "INVALID_ASSEMBLY_STYLE_MODE",
            f"Unsupported character-assembly style mode: {raw_mode}",
        )
    return mode


def character_assembly_style_instruction(mode: str) -> str:
    if mode == "HARMONIZE_STYLE":
        return (
            "Harmonize the Character Head's line quality, shading, and surface finish only as needed to match the "
            "locked Reference Body. Do not repaint the Reference Body or change head identity, geometry, pose, "
            "orientation, clothing, or background."
        )
    return (
        "The supplied sources are already rendered in the same intended style. Preserve that style throughout "
        "the image. Allow localized blending, antialiasing, shading adjustment, skin-transition harmonization, edge cleanup, and limited reconstruction only at the neck and immediate hair/neck/shoulder junction. "
        "Do not broadly repaint or reinterpret the character."
    )


def validate_character_assembly_inputs(
    project_root: Path,
    *,
    character: str,
    phase: str,
    body_view_token: str,
    head_view_token: str,
    body_reference: dict,
    head_image: dict,
) -> None:
    if body_view_token != head_view_token:
        raise TemplateCompileError(
            "CHARACTER_ASSEMBLY_VIEW_MISMATCH",
            f"Character-assembly body view {body_view_token} does not match head view {head_view_token}.",
        )

    expected_views = (
        (body_reference, "body_reference", "body_view"),
        (head_image, "head_image", "body_view"),
        (head_image, "head_image", "head_view"),
    )
    for reference, role, field in expected_views:
        raw_view = str(reference.get(field) or "").strip()
        if not raw_view:
            raise TemplateCompileError(
                "MISSING_REFERENCE_VIEW",
                f"Reference slot {role} is missing required {field} metadata.",
            )
        reference_view = normalize_view(project_root, raw_view)
        if reference_view != body_view_token:
            raise TemplateCompileError(
                "CHARACTER_ASSEMBLY_VIEW_MISMATCH",
                f"Reference slot {role} {field} {reference_view} does not match requested view {body_view_token}.",
            )

    for reference, role in ((body_reference, "body_reference"), (head_image, "head_image")):
        for field, expected in (("character", character), ("phase", phase)):
            value = str(reference.get(field) or "").strip()
            if value and value != expected:
                raise TemplateCompileError(
                    "CHARACTER_ASSEMBLY_REFERENCE_MISMATCH",
                    f"Reference slot {role} {field} {value} does not match requested {field} {expected}.",
                )
