from __future__ import annotations

from dataclasses import dataclass
import json
import re
import tomllib
from typing import Any


@dataclass(frozen=True)
class SceneRenderCompilation:
    prompt: str
    ir: dict[str, Any]
    validation: dict[str, Any]
    local_brief: dict[str, Any]
    local_prompt: str
    source_map: dict[str, Any]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _is_placeholder(value: Any) -> bool:
    text = _clean(value)
    return bool(re.fullmatch(r"\([^)]*\)|\[[^]]*\]", text))


def _sentence(value: Any) -> str:
    text = _clean(value)
    if not text or _is_placeholder(text):
        return ""
    return text


def _join_terms(values: list[str]) -> str:
    return ", ".join(value for value in values if value)


def _grid_region(cell: dict[str, Any], columns: int) -> str:
    column = int(cell.get("column") or 0)
    if columns <= 1:
        return "center"
    if column == 1:
        return "left"
    if column == columns:
        return "right"
    return "center"


def _region_label(region: str, depth: str) -> str:
    if region == "left":
        return f"left {depth}".strip()
    if region == "right":
        return f"right {depth}".strip()
    return f"center {depth}".strip()


def _reference_roles(reference: dict[str, Any]) -> dict[str, Any]:
    tag = _clean(reference.get("tag"))
    kind = _clean(reference.get("kind"))
    label = _clean(reference.get("label"))
    applies_to = label
    roles = ["visual reference"]
    ignore = ["source pose", "source background", "source framing"]
    if kind == "asset":
        applies_to = _clean(reference.get("source_character")) or (tag.split(":")[1] if tag.startswith("{{ASSET:") else label)
        roles = ["identity", "costume"]
    elif kind == "identity-key":
        applies_to = _clean(reference.get("source_character")) or (tag.split(":")[1] if tag.startswith("{{IDENTITY:") else label)
        roles = ["identity"]
    elif kind.startswith("aux:place"):
        roles = ["architecture", "location design"]
        ignore = ["source camera composition", "source lighting"]
    elif kind.startswith("aux:person"):
        roles = ["identity", "costume", "proportions"]
    return {
        "tag": tag,
        "label": label,
        "kind": kind,
        "applies_to": applies_to,
        "roles": roles,
        "ignore": ignore,
        "path": reference.get("path"),
    }


def _reference_sentence(reference: dict[str, Any]) -> str:
    roles = ", ".join(reference.get("roles") or [])
    ignore = ", ".join(reference.get("ignore") or [])
    label = _clean(reference.get("label")) or _clean(reference.get("tag"))
    applies_to = _clean(reference.get("applies_to"))
    return f"Use **{label}** for {applies_to}: preserve {roles}; ignore {ignore}."


def _dialogue_items(scene_text: str) -> list[dict[str, str]]:
    match = re.search(r"(?is)Dialogue panel:\s*-?\s*Speaker:\s*(.+?)\s*-?\s*Text:\s*\"(.+?)\"", scene_text or "")
    if not match:
        return []
    return [{"speaker": match.group(1).strip(), "text": match.group(2).strip(), "include_in_final": True, "include_in_local": False}]


def _screen_order(characters: list[dict[str, Any]], anchors: list[dict[str, Any]]) -> list[str]:
    items = characters + anchors
    rank = {"left": 0, "center": 1, "right": 2}
    ordered = sorted(items, key=lambda item: (rank.get(item.get("screen_region"), 1), item.get("name", "")))
    return [item["name"] for item in ordered if item.get("name")]


def compile_scene_render(
    *,
    story_sections: dict[str, str],
    scene_sections: dict[str, str],
    scene_builder: dict[str, Any],
    references: list[dict[str, Any]],
    story_file: str,
    scene_file: str,
    scene_builder_file: str,
    final_prompt_file: str,
) -> SceneRenderCompilation:
    setup = scene_builder.get("setup") if isinstance(scene_builder.get("setup"), dict) else {}
    canvas = setup.get("canvas") if isinstance(setup.get("canvas"), dict) else {}
    composition = setup.get("composition") if isinstance(setup.get("composition"), dict) else {}
    grid = composition.get("grid") if isinstance(composition.get("grid"), dict) else {}
    camera = setup.get("camera") if isinstance(setup.get("camera"), dict) else {}
    environment = setup.get("environment") if isinstance(setup.get("environment"), dict) else {}
    columns = int(grid.get("columns") or 3)
    elements = {str(item.get("id")): item for item in scene_builder.get("scene_elements", []) if isinstance(item, dict)}
    validation = {"errors": [], "warnings": [], "auto_resolutions": []}

    for path, value in _walk_values(scene_builder):
        if _is_placeholder(value):
            validation["warnings"].append({"code": "placeholder", "path": path, "value": value})

    aspect_ratio = _sentence(canvas.get("aspect_ratio")) or "16:9"
    orientation = _sentence(canvas.get("orientation")) or ("landscape" if aspect_ratio.startswith("16:9") else "portrait")
    scene_notes = _clean(scene_sections.get("SCENE_RENDERING_NOTES"))
    if re.search(r"portrait|4:5", scene_notes, re.I) and orientation == "landscape":
        validation["warnings"].append({"code": "canvas_conflict", "message": "Scene markdown notes mention portrait/4:5; Scene Builder landscape setting was used."})
        validation["auto_resolutions"].append({"field": "canvas", "resolution": "Scene Builder canvas wins over scene markdown notes."})

    characters: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    placements = scene_builder.get("placements") if isinstance(scene_builder.get("placements"), list) else []
    placed_ids = set()
    for placement in placements:
        if not isinstance(placement, dict):
            continue
        element = elements.get(str(placement.get("scene_element_id")))
        if not element:
            validation["errors"].append({"code": "missing_placement_element", "placement_id": placement.get("id")})
            continue
        placed_ids.add(str(element.get("id")))
        region = _grid_region(placement.get("screen_cell") or {}, columns)
        item = {
            "id": element.get("id"),
            "name": _clean(element.get("display_name")) or _clean(element.get("id")),
            "type": _clean(element.get("element_type")),
            "importance": _clean(element.get("importance")),
            "screen_region": region,
            "placement": _region_label(region, _clean(placement.get("depth")) or "foreground"),
            "depth": _clean(placement.get("depth")),
            "description": _sentence(element.get("default_visual_description")) or _sentence(element.get("identity_prompt")),
            "pose": _sentence(placement.get("pose")),
            "body_facing": _sentence(placement.get("body_facing")),
            "head_facing": _sentence(placement.get("head_facing")),
            "gaze_target": _clean(placement.get("gaze_target_element_id")),
            "gaze_description": _sentence(placement.get("gaze_target_description")),
            "expression": _sentence(placement.get("expression")),
            "image_tag": _clean(element.get("image_tag")),
            "notes": _sentence(placement.get("placement_notes")),
        }
        if item["type"].lower() == "character":
            characters.append(item)
        else:
            anchors.append(item)
        gaze_target = item.get("gaze_target")
        if gaze_target and gaze_target not in elements:
            validation["errors"].append({"code": "invalid_gaze_target", "character": item["name"], "target": gaze_target})

    for element_id, element in elements.items():
        if _clean(element.get("importance")).lower() == "primary" and element_id not in placed_ids:
            validation["errors"].append({"code": "missing_primary_placement", "element": element.get("display_name") or element_id})

    if not characters:
        validation["errors"].append({"code": "missing_primary_characters", "message": "Scene Builder has no placed characters."})

    dialogue = _dialogue_items(scene_sections.get("SCENE_DESCRIPTION", ""))
    if dialogue and re.search(r"do not stamp text|no text|captions", scene_sections.get("SCENE_DESCRIPTION", "") + "\n" + scene_sections.get("SCENE_RENDERING_NOTES", ""), re.I):
        validation["warnings"].append({"code": "dialogue_no_text_conflict", "message": "Dialogue was requested while no-text guidance also appears."})
        validation["auto_resolutions"].append({"field": "dialogue", "resolution": "Final prompt permits only requested dialogue text; local prompt excludes text."})
    local_override_error = _local_override_error(scene_sections.get("_RAW_SCENE_TEXT", ""))
    if local_override_error:
        validation["errors"].append({"code": "invalid_local_overrides", "message": local_override_error})

    reference_assignments = [_reference_roles(reference) for reference in references]
    for character in characters:
        if not character.get("image_tag") and not any(character["name"].lower() in _clean(ref.get("tag")).lower() for ref in reference_assignments):
            validation["warnings"].append({"code": "missing_character_reference", "character": character["name"]})

    story_title = _sentence(story_sections.get("STORY_TITLE"))
    art_style = _sentence(story_sections.get("CANONICAL_ART_STYLE"))
    focal_point = _sentence(composition.get("primary_focal_point")) or "the interaction between the primary characters"
    lighting = _sentence(environment.get("lighting"))
    mood = _sentence(environment.get("mood"))
    location = _sentence(environment.get("location")) or next((anchor["name"] for anchor in anchors), "")
    shot = _sentence(camera.get("shot_type")) or "wide shot"
    camera_line = _join_terms([shot, _sentence(camera.get("camera_height")), _sentence(camera.get("camera_angle")), f"{_sentence(camera.get('lens_feel'))} lens feel" if _sentence(camera.get("lens_feel")) else ""])
    screen_order = _screen_order(characters, anchors)

    ir = {
        "canvas": {
            "orientation": orientation,
            "aspect_ratio": aspect_ratio,
            "width": canvas.get("width"),
            "height": canvas.get("height"),
            "shot_type": shot,
            "camera_height": _sentence(camera.get("camera_height")),
            "camera_angle": _sentence(camera.get("camera_angle")),
            "lens_feel": _sentence(camera.get("lens_feel")),
        },
        "composition": {
            "planning_grid": {"rows": int(grid.get("rows") or 1), "columns": columns},
            "focal_point": focal_point,
            "left_to_right_order": screen_order,
            "draw_grid": False,
        },
        "characters": characters,
        "props": [item for item in scene_builder.get("props", []) if isinstance(item, dict)],
        "interactions": [item for item in scene_builder.get("interactions", []) if isinstance(item, dict)],
        "environment": {
            "location": location,
            "weather_or_atmosphere": _sentence(environment.get("weather_or_atmosphere")),
            "background": _sentence(environment.get("general_background_notes")),
            "foreground": _sentence(environment.get("general_foreground_notes")),
        },
        "lighting": {"description": lighting, "mood": mood},
        "dialogue": dialogue,
        "references": reference_assignments,
        "avoid": _avoid_terms(environment, scene_sections, dialogue),
        "source_lineage": [
            {"source": story_file, "fields": ["story title", "canonical art style", "visual continuity"]},
            {"source": scene_file, "fields": ["narrative intent", "special render instructions", "reference tags"]},
            {"source": scene_builder_file, "fields": ["canvas", "camera", "composition", "environment", "placements"]},
        ],
    }

    local_brief = _local_brief(ir, art_style)
    local_prompt = _local_prompt(local_brief)
    prompt = _final_prompt(ir, story_title, art_style, scene_sections)
    source_map = {
        "story_file": story_file,
        "scene_file": scene_file,
        "scene_builder_file": scene_builder_file,
        "final_prompt": final_prompt_file,
        "compiler": "scene_render_v2",
        "sections": sorted(key for key in (story_sections.keys() | scene_sections.keys()) if not key.startswith("_")),
        "artifacts": ["Scene_Render_IR.json", "Scene_Render_Validation.json", "Final_Image_Prompt.md", "Local_Render_Brief.json", "Local_Render_Prompt.md"],
        "field_lineage": ir["source_lineage"],
    }
    return SceneRenderCompilation(prompt=prompt, ir=ir, validation=validation, local_brief=local_brief, local_prompt=local_prompt, source_map=source_map)


def _walk_values(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _local_override_error(scene_text: str) -> str:
    marker = "LOCAL_IMAGE_GEN_OVERRIDES"
    in_section = False
    lines: list[str] = []
    for line in (scene_text or "").splitlines():
        if f"ZET:BEGIN {marker}" in line:
            in_section = True
            continue
        if f"ZET:END {marker}" in line:
            break
        if in_section:
            lines.append(line)
    if not lines:
        return ""
    try:
        tomllib.loads(_legacy_override_lines_to_toml(lines))
    except tomllib.TOMLDecodeError as exc:
        return str(exc)
    return ""


def _legacy_override_lines_to_toml(lines: list[str]) -> str:
    keys = {
        "prompt",
        "negative_prompt",
        "denoising_strength",
        "steps",
        "cfg_scale",
        "seed",
        "s_noise",
        "sd_model_checkpoint",
        "sampler_name",
        "scheduler",
        "enable_hr",
        "hr_upscaler",
        "hr_second_pass_steps",
        "hr_scale",
        "orientation",
        "aspect_ratio",
        "width",
        "height",
        "restore_faces",
    }
    converted: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("[") or "=" in stripped or ":" not in stripped:
            converted.append(line)
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in keys or not value:
            continue
        if value.endswith(":") and value[:-1] in keys:
            continue
        if re.fullmatch(r"-?\d+(?:\.\d+)?", value) or value.lower() in {"true", "false"}:
            converted.append(f"{key} = {value}")
        else:
            converted.append(f"{key} = {json.dumps(value)}")
    return "\n".join(converted)


def _avoid_terms(environment: dict[str, Any], scene_sections: dict[str, str], dialogue: list[dict[str, str]]) -> list[str]:
    terms = [
        "extra characters",
        "visible grid",
        "split panels",
        "merged bodies",
        "duplicated characters",
        "swapped positions",
        "incorrect gaze",
        "cropped primary figures",
        "malformed hands",
        "extra limbs",
        "floating props",
        "watermark",
    ]
    for value in environment.get("important_exclusions") or []:
        if _sentence(value):
            terms.append(_sentence(value))
    if dialogue:
        terms.append("text other than the requested dialogue")
    else:
        terms.extend(["text", "letters", "caption", "speech bubble"])
    notes = _clean(scene_sections.get("SCENE_RENDERING_NOTES"))
    avoid_match = re.search(r"(?ims)Avoid:\s*(.+)$", notes)
    if avoid_match:
        terms.extend([part.strip(" -*") for part in avoid_match.group(1).splitlines() if part.strip(" -*")])
    return list(dict.fromkeys(terms))


def _character_lines(character: dict[str, Any]) -> list[str]:
    lines = [f"## {character['name']} - {character['placement']}"]
    details = [
        character.get("description"),
        f"Pose: {character.get('pose')}." if character.get("pose") else "",
        f"Body facing: {character.get('body_facing')}." if character.get("body_facing") else "",
        f"Head facing: {character.get('head_facing')}." if character.get("head_facing") else "",
        f"Gaze: {character.get('gaze_description') or character.get('gaze_target')}." if character.get("gaze_description") or character.get("gaze_target") else "",
        f"Expression: {character.get('expression')}." if character.get("expression") else "",
        character.get("notes"),
    ]
    lines.extend(f"- {detail}" for detail in details if detail)
    return lines


def _final_prompt(ir: dict[str, Any], story_title: str, art_style: str, scene_sections: dict[str, str]) -> str:
    canvas = ir["canvas"]
    lines = [
        "# Render Task",
        "",
        f"Create one finished {canvas['orientation']} {canvas['aspect_ratio']} narrative fantasy illustration. This is a single continuous scene, not a comic-panel grid or reference sheet. The planning grid is invisible and must not appear in the image.",
        "",
        "# Reference Image Assignment",
        "",
    ]
    if ir["references"]:
        lines.extend(f"{index}. {_reference_sentence(reference)}" for index, reference in enumerate(ir["references"], start=1))
    else:
        lines.append("No attached reference images are assigned for this scene.")
    lines.extend([
        "",
        "# Camera and Composition",
        "",
        f"- {canvas['orientation'].capitalize()} {canvas['aspect_ratio']}.",
        f"- {canvas.get('shot_type') or 'Wide shot'} at {canvas.get('camera_height') or 'eye level'}, {canvas.get('camera_angle') or 'straight-on'}.",
        f"- Focal point: {ir['composition']['focal_point']}.",
        f"- Left-to-right order: {' -> '.join(ir['composition']['left_to_right_order'])}.",
        "- Do not draw grid lines or divide the scene into panels.",
        "",
        "# Character Staging",
        "",
    ])
    for character in ir["characters"]:
        lines.extend(_character_lines(character))
        lines.append("")
    lines.extend([
        "# Props and Interactions",
        "",
    ])
    if ir["interactions"]:
        lines.extend(f"- {item}" for item in ir["interactions"])
    else:
        lines.append("- Preserve any prop and interaction facts from the scene description; keep held items, gaze, and distances anatomically readable.")
    lines.extend([
        "",
        "# Environment and Depth",
        "",
        f"- Location: {ir['environment'].get('location') or 'scene location'}.",
    ])
    for key in ("foreground", "background", "weather_or_atmosphere"):
        if ir["environment"].get(key):
            lines.append(f"- {key.replace('_', ' ').capitalize()}: {ir['environment'][key]}.")
    lines.extend([
        "",
        "# Lighting, Mood, and Story Beat",
        "",
    ])
    if ir["lighting"].get("description"):
        lines.append(f"- Lighting: {ir['lighting']['description']}.")
    if ir["lighting"].get("mood"):
        lines.append(f"- Mood: {ir['lighting']['mood']}.")
    if art_style:
        lines.append(f"- Art style: {art_style}.")
    scene_description = _clean(scene_sections.get("SCENE_DESCRIPTION"))
    if scene_description:
        lines.append(f"- Story beat: {_first_sentence(scene_description)}")
    if ir["dialogue"]:
        lines.extend(["", "# Dialogue Panel", ""])
        for item in ir["dialogue"]:
            lines.append(f"Include exactly one compact parchment dialogue panel for {item['speaker']} with the text: \"{item['text']}\".")
        lines.append("Place dialogue so it does not cover faces, hands, required props, or the focal background element.")
    lines.extend([
        "",
        "# Must Preserve",
        "",
        f"- Exactly {len(ir['characters'])} primary characters.",
        f"- Character order: {' -> '.join(ir['composition']['left_to_right_order'])}.",
        f"- The {ir['environment'].get('location') or 'specified scene location'}.",
    ])
    if story_title:
        lines.append(f"- Continuity for {story_title}.")
    lines.extend(["", "# Avoid", "", "No " + ", ".join(ir["avoid"]) + ".", "", "# Final Verification", ""])
    lines.append("Before completing the image, verify character count, left/right placement, gaze, required props/interactions, readable hands, readable faces, correct setting, and that only requested dialogue text appears.")
    return "\n".join(lines).strip() + "\n"


def _first_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", re.sub(r"\[Use:.*?\]", "", text, flags=re.S)).strip()
    match = re.match(r"(.+?[.!?])\s", cleaned)
    return match.group(1) if match else cleaned[:240]


def _local_brief(ir: dict[str, Any], art_style: str) -> dict[str, Any]:
    canvas = ir["canvas"]
    character_facts = []
    for character in ir["characters"]:
        character_facts.append(_join_terms([
            f"{character['name']} in the {character['screen_region']} foreground",
            character.get("description"),
            character.get("pose"),
            f"facing {character.get('body_facing')}" if character.get("body_facing") else "",
        ]))
    positive = [
        f"{len(ir['characters'])} characters",
        art_style,
        f"{canvas['orientation']} {canvas['aspect_ratio']} {canvas.get('shot_type') or 'wide shot'}",
        f"{canvas.get('camera_height') or 'eye-level'} {canvas.get('camera_angle') or 'straight-on'} camera",
        ir["environment"].get("location"),
        *character_facts,
        "mutual or directed gaze between characters" if any(character.get("gaze_target") for character in ir["characters"]) else "",
        ir["lighting"].get("description"),
        ir["lighting"].get("mood"),
        "clear separated silhouettes",
    ]
    return {
        "purpose": "composition preview only",
        "include_dialogue": False,
        "protected_facts": {
            "subject_count": len(ir["characters"]),
            "canvas": f"{canvas['orientation']} {canvas['aspect_ratio']}",
            "shot": canvas.get("shot_type"),
            "left_to_right_order": ir["composition"]["left_to_right_order"],
            "location": ir["environment"].get("location"),
        },
        "positive_facts": [value for value in positive if value],
        "negative_facts": [term for term in ir["avoid"] if "dialogue" not in term] + ["text", "letters", "caption", "speech bubble", "watermark"],
    }


def _local_prompt(local_brief: dict[str, Any]) -> str:
    positive = ", ".join(local_brief.get("positive_facts") or [])
    negative = ", ".join(dict.fromkeys(local_brief.get("negative_facts") or []))
    return f"prompt: {positive}\nnegative: {negative}\n"
