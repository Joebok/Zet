from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
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


def clean_prompt_sentence(value: Any) -> str:
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    if not text:
        return ""
    return re.sub(r"(?<!\.)[.]{2,}$", ".", text)


def _sentence(value: Any) -> str:
    text = clean_prompt_sentence(value)
    if not text:
        return ""
    if text.endswith((".", "!", "?")):
        return text
    return text + "."


def humanize_identifier(value: str) -> str:
    text = re.sub(r"_[0-9a-f]{6,}$", "", _clean(value), flags=re.IGNORECASE)
    text = re.sub(r"_\d{8,}$", "", text)
    return re.sub(r"[_-]+", " ", text).strip()


def _items(values: Any) -> list[dict[str, Any]]:
    return [item for item in values or [] if isinstance(item, dict)]


def _lines(values: Any) -> list[str]:
    return [_clean(item) for item in values or [] if _clean(item)]


def _style_text(story_settings: dict[str, Any], scene_data: dict[str, Any]) -> str:
    style = scene_data.get("setup", {}).get("style", {})
    if _clean(style.get("art_style_override")):
        return _clean(style.get("art_style_override"))
    return _clean(story_settings.get("style_defaults", {}).get("canonical_art_style", {}).get("full_prompt_text"))


def _dialogue_style(story_settings: dict[str, Any], style_id: str) -> dict[str, Any] | None:
    for style in _items(story_settings.get("dialogue_styles")):
        if _clean(style.get("id")) == style_id:
            return style
    return None


def compile_scene_render_ir(scene_data: dict[str, Any], story_settings: dict[str, Any], resolved_sources: dict[str, Any] | None = None) -> dict[str, Any]:
    setup = scene_data.get("setup", {})
    style = setup.get("style", {})
    story_profile = story_settings.get("compiler_profiles", {}).get("final_image_prompt", {})
    references = list(_items(scene_data.get("reference_assignments")))
    for element in _items(scene_data.get("scene_elements")):
        for reference in _items(element.get("reference_images")):
            references.append({
                "id": f"ref_{element.get('id')}_{reference.get('tag')}",
                "tag": reference.get("tag", ""),
                "applies_to_element_id": element.get("id", ""),
                "roles": reference.get("roles", []),
                "ignore": reference.get("ignore", []),
                "notes": reference.get("notes", ""),
            })
    dialogue = [
        item for item in _items(scene_data.get("dialogue"))
        if item.get("include_in_final_image_prompt", True)
    ]
    avoid = []
    avoid.extend(_lines(story_settings.get("style_defaults", {}).get("default_avoid")))
    avoid.extend(_lines(scene_data.get("avoid", {}).get("scene_specific")))
    avoid.extend(_lines(setup.get("environment", {}).get("important_exclusions")))
    verification = [
        "character count and identities match the scene JSON",
        "left/right placement and depth match placements",
        "hands, props, gaze, and interactions are readable",
        "setting, lighting, mood, and art style match the source data",
    ]
    return {
        "source": {
            "scene_json_path": scene_data.get("scene", {}).get("source_path", ""),
            "story_settings_path": scene_data.get("scene", {}).get("story_settings_path", ""),
            "source_hashes": {},
        },
        "canvas": setup.get("canvas", {}),
        "style": {
            "art_style": _style_text(story_settings, scene_data),
            "visual_continuity": story_settings.get("style_defaults", {}).get("visual_continuity", {}),
            "profile": story_profile,
        },
        "composition": setup.get("composition", {}),
        "camera": setup.get("camera", {}),
        "environment": setup.get("environment", {}),
        "elements": _items(scene_data.get("scene_elements")),
        "placements": _items(scene_data.get("placements")),
        "props": _items(scene_data.get("props_and_states")),
        "interactions": _items(scene_data.get("interactions")),
        "dialogue": dialogue,
        "dialogue_styles": story_settings.get("dialogue_styles", []),
        "references": references,
        "avoid": list(dict.fromkeys(avoid)),
        "final_verification": verification,
        "resolved_sources": resolved_sources or {},
    }


def _element(ir: dict[str, Any], element_id: str) -> dict[str, Any]:
    return next((item for item in ir.get("elements", []) if _clean(item.get("id")) == element_id), {})


def _elements_by_id(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_clean(item.get("id")): item for item in ir.get("elements", []) if _clean(item.get("id"))}


def get_element_display_name(element_id: str, elements_by_id: dict[str, dict[str, Any]]) -> str:
    element = elements_by_id.get(_clean(element_id))
    if element is None:
        return humanize_identifier(element_id)
    return (
        clean_prompt_sentence(element.get("display_name"))
        or clean_prompt_sentence(element.get("character"))
        or clean_prompt_sentence(element.get("aux_resource_id"))
        or humanize_identifier(_clean(element.get("id")))
    )


def _semantic_region(ir: dict[str, Any], placement: dict[str, Any]) -> str:
    explicit = clean_prompt_sentence(placement.get("semantic_screen_region"))
    depth = clean_prompt_sentence(placement.get("depth"))
    cell = placement.get("screen_cell", {}) if isinstance(placement.get("screen_cell"), dict) else {}
    grid = ir.get("composition", {}).get("grid", {}) if isinstance(ir.get("composition", {}).get("grid"), dict) else {}
    columns = int(grid.get("columns") or 0)
    rows = int(grid.get("rows") or 0)
    column = int(cell.get("column") or 0)
    row = int(cell.get("row") or 0)
    horizontal = ""
    if columns == 2:
        horizontal = {1: "left", 2: "right"}.get(column, "")
    elif columns == 3:
        horizontal = {1: "left", 2: "center", 3: "right"}.get(column, "")
    elif columns >= 4 and column:
        horizontal = "far left" if column == 1 else "far right" if column == columns else "left of center" if column <= columns / 2 else "right of center"
    vertical = ""
    if rows == 2:
        vertical = {1: "upper", 2: "lower"}.get(row, "")
    elif rows == 3:
        vertical = {1: "upper", 2: "middle", 3: "lower"}.get(row, "")
    region = "-".join(part for part in [vertical, horizontal] if part)
    if not region:
        region = explicit
    if not region:
        region = clean_prompt_sentence(cell.get("name"))
    if depth and depth not in region:
        return f"{region} {depth}".strip()
    return region


def _placement_sort_key(placement: dict[str, Any]) -> tuple[int, str, int]:
    cell = placement.get("screen_cell", {}) if isinstance(placement.get("screen_cell"), dict) else {}
    return (int(cell.get("column") or 9999), _clean(placement.get("position_within_cell")), int(placement.get("z_order") or 9999))


def _left_to_right_order(ir: dict[str, Any], elements_by_id: dict[str, dict[str, Any]]) -> list[str]:
    explicit = _lines(ir.get("composition", {}).get("left_to_right_order"))
    if explicit:
        return [get_element_display_name(item, elements_by_id) if item in elements_by_id else clean_prompt_sentence(item) for item in explicit]
    ordered = []
    for placement in sorted(ir.get("placements", []), key=_placement_sort_key):
        cell = placement.get("screen_cell", {}) if isinstance(placement.get("screen_cell"), dict) else {}
        if cell.get("column"):
            ordered.append(get_element_display_name(_clean(placement.get("scene_element_id")), elements_by_id))
    return list(dict.fromkeys(item for item in ordered if item))


def _view_text(value: Any) -> str:
    return clean_prompt_sentence(value).replace("3/4", "three-quarter")


def _dialogue_tones(ir: dict[str, Any]) -> dict[str, str]:
    visible = {"worried", "angry", "sad", "happy", "afraid", "fearful", "surprised", "amused", "stern", "confused", "concerned"}
    tones = {}
    for item in ir.get("dialogue", []):
        tone = clean_prompt_sentence(item.get("tone")).lower()
        if tone in visible:
            tones[_clean(item.get("speaker_element_id"))] = tone
    return tones


def _placement_line(ir: dict[str, Any], placement: dict[str, Any], elements_by_id: dict[str, dict[str, Any]], tones: dict[str, str]) -> str:
    element_id = _clean(placement.get("scene_element_id"))
    element = _element(ir, element_id)
    name = get_element_display_name(element_id, elements_by_id)
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    pose_summary = clean_prompt_sentence(pose.get("summary") if pose else placement.get("pose"))
    region = _semantic_region(ir, placement)
    element_type = _clean(element.get("element_type"))
    verb = "occupies" if element_type in {"Place", "Anchor"} or _clean(element.get("resource_type")) == "Place" else "stands"
    first = f"{name} {verb}"
    if pose_summary and pose_summary.lower() not in {"standing", "stands"} and verb == "stands":
        first = f"{name} {pose_summary}"
    if region:
        first += f" in the {region}" if verb == "stands" else f" the {region}"
    sentences = [_sentence(first)]
    body = _view_text(pose.get("body_view") or placement.get("body_view"))
    head = _view_text(pose.get("head_view") or placement.get("head_view"))
    target_id = _clean(pose.get("gaze_target_element_id") or placement.get("gaze_target_element_id"))
    target = get_element_display_name(target_id, elements_by_id) if target_id else ""
    if body and head and body == head:
        sentences.append(_sentence(f"Body and head are shown in {body}"))
    else:
        if body:
            sentences.append(_sentence(f"Body is shown in {body}"))
        if head:
            detail = f"Head is turned into {head}"
            if target:
                detail += f" toward {target}"
            sentences.append(_sentence(detail))
    actions = _lines([
        pose.get("left_arm_action"),
        pose.get("right_arm_action"),
        pose.get("left_hand_detail"),
        pose.get("right_hand_detail"),
    ])
    if actions:
        sentences.append(_sentence(", ".join(actions)))
    gaze_description = clean_prompt_sentence(pose.get("gaze_description") or placement.get("gaze_description"))
    if target:
        sentences.append(_sentence(f"{name} looks directly at {target}"))
    elif gaze_description:
        sentences.append(_sentence(gaze_description))
    expression = clean_prompt_sentence(pose.get("expression") or placement.get("expression") or tones.get(element_id))
    if expression:
        sentences.append(_sentence(f"{name} appears {expression}"))
    notes = clean_prompt_sentence(placement.get("placement_notes"))
    if notes:
        sentences.append(_sentence(notes))
    return " ".join(item for item in sentences if item)


def _reference_defaults(element: dict[str, Any], ref: dict[str, Any]) -> tuple[str, str]:
    resource_type = _clean(element.get("resource_type")) or _clean(element.get("element_type"))
    roles = {item.lower() for item in _lines(ref.get("roles"))}
    tag = _clean(ref.get("tag")).lower()
    if resource_type in {"Place", "Anchor"}:
        return (
            "architecture, structural design, identifying materials, and location-defining features",
            "source camera composition, framing, people, lighting, weather, and temporary objects",
        )
    if resource_type in {"Object", "Prop"}:
        return (
            "shape, construction, materials, colors, scale, and identifying details",
            "source position, orientation, hand placement, framing, background, and lighting",
        )
    if "costume" in roles or "costume" in tag:
        return (
            "identity, facial features, hair, ears when applicable, body proportions, costume design, costume colors, and signature worn items",
            "source pose, expression, action, camera angle, framing, background, and lighting",
        )
    return (
        "identity, facial features, hair, ears when applicable, and body proportions",
        "source costume unless explicitly assigned, pose, expression, action, camera angle, framing, background, and lighting",
    )


def _relationship_key(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean(value).lower()).strip()


def _interaction_lines(ir: dict[str, Any], elements_by_id: dict[str, dict[str, Any]]) -> list[str]:
    records = []
    seen = set()
    for item in ir.get("interactions", []):
        subject = _clean(item.get("subject_element_id"))
        target = _clean(item.get("target_element_id"))
        relationship = _relationship_key(item.get("relationship") or item.get("type"))
        key = (subject, relationship, target)
        if subject and relationship and target and key not in seen:
            seen.add(key)
            records.append(key)
    lines = []
    used = set()
    for subject, relationship, target in records:
        reverse = (target, relationship, subject)
        if relationship in {"looking at", "looks at", "gaze", "direct gaze"} and reverse in seen and reverse not in used:
            lines.append(f"{get_element_display_name(subject, elements_by_id)} and {get_element_display_name(target, elements_by_id)} hold direct eye contact.")
            used.add((subject, relationship, target))
            used.add(reverse)
    for subject, relationship, target in records:
        if (subject, relationship, target) in used:
            continue
        lines.append(_sentence(f"{get_element_display_name(subject, elements_by_id)} {relationship} {get_element_display_name(target, elements_by_id)}"))
    return lines


def final_image_prompt_text(ir: dict[str, Any]) -> str:
    canvas = ir.get("canvas", {})
    camera = ir.get("camera", {})
    composition = ir.get("composition", {})
    environment = ir.get("environment", {})
    elements_by_id = _elements_by_id(ir)
    tones = _dialogue_tones(ir)
    lines = [
        "# Render Task",
        "",
        f"Create one finished {clean_prompt_sentence(canvas.get('orientation')) or 'landscape'} {clean_prompt_sentence(canvas.get('aspect_ratio')) or '16:9'} scene image. Do not show the planning grid or split the image into comic panels.",
        "",
    ]
    if ir.get("references"):
        lines.extend(["# Reference Image Assignment", ""])
        for ref in ir["references"]:
            element_id = _clean(ref.get("applies_to_element_id"))
            element = elements_by_id.get(element_id, {})
            name = get_element_display_name(element_id, elements_by_id)
            preserve, ignore = _reference_defaults(element, ref)
            tag = clean_prompt_sentence(ref.get("tag"))
            roles = ", ".join(_lines(ref.get("roles")))
            lines.append(f"- {name} - {tag}")
            if roles:
                lines.append(f"  Use for {name}'s {roles}.")
            lines.append(f"  Preserve {preserve}.")
            lines.append(f"  Ignore {ignore}.")
        lines.append("")
    lines.extend(["# Camera and Composition", ""])
    lines.append(f"- {clean_prompt_sentence(canvas.get('orientation')) or 'Landscape'} {clean_prompt_sentence(canvas.get('aspect_ratio')) or '16:9'}.")
    camera_parts = [
        clean_prompt_sentence(camera.get("shot_type")) or "wide shot",
        clean_prompt_sentence(camera.get("camera_height")) or "eye level",
        clean_prompt_sentence(camera.get("camera_angle")) or "straight-on",
    ]
    lens = clean_prompt_sentence(camera.get("lens_feel")) or "normal"
    lines.append(f"- {', '.join(camera_parts)}, with a {lens} lens feel.")
    focal = clean_prompt_sentence(composition.get("primary_focal_point"))
    if focal:
        lines.append(f"- Primary focal point: {get_element_display_name(focal, elements_by_id) if focal in elements_by_id else focal}.")
    order = _left_to_right_order(ir, elements_by_id)
    if order:
        lines.append(f"- Left-to-right order: {' -> '.join(order)}.")
    lines.append("- Render one continuous scene. Do not show the planning grid or divide the image into panels.")
    lines.extend(["", "# Character and Location Staging", ""])
    for placement in ir.get("placements", []):
        element = _element(ir, _clean(placement.get("scene_element_id")))
        if _clean(element.get("element_type")) in {"Character", "Monster", "Place", "Anchor", "Prop", "Effect", "Vehicle"}:
            lines.append(f"- {_placement_line(ir, placement, elements_by_id, tones)}")
    if lines[-1] == "":
        lines.extend(["- No staging specified."])
    lines.extend(["", "# Props and Interactions", ""])
    for prop in ir.get("props", []):
        text = clean_prompt_sentence(prop.get("description") or prop.get("state") or prop.get("display_name"))
        if text:
            lines.append(f"- {_sentence(text)}")
    lines.extend(f"- {line}" for line in _interaction_lines(ir, elements_by_id))
    if lines[-1] == "":
        lines.append("- Preserve structured prop and interaction facts from the scene JSON.")
    environment_lines = [
        _sentence(environment.get("location")),
        _sentence(environment.get("general_foreground_notes")),
        _sentence(environment.get("general_background_notes")),
    ]
    environment_lines = [item for item in environment_lines if item]
    if environment_lines:
        lines.extend(["", "# Environment and Depth", "", *environment_lines])
    mood_lines = [
        f"- Lighting: {clean_prompt_sentence(environment.get('lighting'))}." if clean_prompt_sentence(environment.get("lighting")) else "",
        f"- Mood: {clean_prompt_sentence(environment.get('mood'))}." if clean_prompt_sentence(environment.get("mood")) else "",
        f"- Atmosphere: {clean_prompt_sentence(environment.get('weather_or_atmosphere'))}." if clean_prompt_sentence(environment.get("weather_or_atmosphere")) else "",
        f"- Art style: {clean_prompt_sentence(ir.get('style', {}).get('art_style'))}." if clean_prompt_sentence(ir.get("style", {}).get("art_style")) else "",
    ]
    if any(mood_lines):
        lines.extend(["", "# Lighting and Mood", "", *[line for line in mood_lines if line]])
    if ir.get("dialogue"):
        lines.extend(["", "# Dialogue Panel", ""])
        for item in ir["dialogue"]:
            style = next((s for s in ir.get("dialogue_styles", []) if s.get("id") == item.get("panel_style_id")), {})
            speaker = get_element_display_name(_clean(item.get("speaker_element_id")), elements_by_id)
            lines.append(f"{speaker} says exactly: \"{item.get('text', '')}\"")
            style_text = " ".join(_lines([style.get("panel_prompt"), style.get("pointer_prompt"), style.get("lettering_prompt")]))
            if style_text:
                lines.append("")
                lines.append(_sentence(style_text))
            target = get_element_display_name(_clean(item.get("target_element_id")), elements_by_id) if _clean(item.get("target_element_id")) else ""
            if target:
                lines.append(f"Place the panel so the dialogue reads as directed toward {target}.")
            for rule in _lines(style.get("layout_rules")):
                lines.append(f"  - {rule}")
    preserve_lines = []
    continuity = ir.get("style", {}).get("visual_continuity", {})
    for rule in _lines(continuity.get("rules")):
        preserve_lines.append(f"- {rule}")
    for element in ir.get("elements", []):
        sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
        identity = clean_prompt_sentence(sections.get("identity_preservation_core"))
        costume = clean_prompt_sentence(sections.get("identity_preservation_costume"))
        if identity or costume:
            preserve_lines.extend(["", f"## {get_element_display_name(_clean(element.get('id')), elements_by_id)}", ""])
            resource_type = _clean(element.get("resource_type")) or _clean(element.get("element_type"))
            if identity:
                label = "Location design" if resource_type in {"Place", "Anchor"} else "Identity"
                preserve_lines.append(f"**{label}:** {identity}")
            if costume and resource_type not in {"Place", "Object", "Anchor", "Prop"}:
                costume_name = clean_prompt_sentence(element.get("costume"))
                label = f"Costume - {costume_name}" if costume_name else "Costume"
                preserve_lines.extend(["", f"**{label}:** {costume}"])
    if preserve_lines:
        lines.extend(["", "# Scene Element Preservation", "", *preserve_lines])
    avoid = ", ".join(_lines(ir.get("avoid")) or ["unrequested text", "malformed hands"])
    lines.extend(["", "# Avoid", "", f"No {avoid}.", "", "# Final Verification", ""])
    for item in ir.get("final_verification", []):
        lines.append(f"- {_sentence(item)}")
    return "\n".join(lines).strip() + "\n"


def local_render_brief(ir: dict[str, Any]) -> dict[str, Any]:
    canvas = ir.get("canvas", {})
    elements_by_id = _elements_by_id(ir)
    tones = _dialogue_tones(ir)
    positive = [
        _clean(ir.get("style", {}).get("art_style")),
        f"{_clean(canvas.get('orientation')) or 'landscape'} {_clean(canvas.get('aspect_ratio')) or '16:9'}",
        _clean(ir.get("camera", {}).get("shot_type")),
        _clean(ir.get("environment", {}).get("location")),
        _clean(ir.get("composition", {}).get("primary_focal_point")),
    ]
    positive.extend(_placement_line(ir, placement, elements_by_id, tones) for placement in ir.get("placements", []))
    negative = list(dict.fromkeys([term for term in ir.get("avoid", []) if "dialogue" not in term] + ["text", "letters", "caption", "speech bubble", "watermark"]))
    return {
        "purpose": "composition preview only",
        "include_dialogue": False,
        "protected_facts": {
            "canvas": f"{_clean(canvas.get('orientation')) or 'landscape'} {_clean(canvas.get('aspect_ratio')) or '16:9'}",
            "left_to_right_order": ir.get("composition", {}).get("left_to_right_order", []),
            "location": ir.get("environment", {}).get("location", ""),
        },
        "positive_facts": [item for item in positive if item],
        "negative_facts": negative,
    }


def local_render_prompt_text(brief: dict[str, Any]) -> str:
    return f"prompt: {', '.join(brief.get('positive_facts') or [])}\nnegative: {', '.join(brief.get('negative_facts') or [])}\n"


def write_final_image_prompt(ir: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_image_prompt_text(ir), encoding="utf-8")


def write_local_render_brief(ir: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(local_render_brief(ir), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_local_render_prompt(local_brief: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(local_render_prompt_text(local_brief), encoding="utf-8")


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
    story_settings = {
        "style_defaults": {
            "canonical_art_style": {"full_prompt_text": story_sections.get("CANONICAL_ART_STYLE", "")},
            "visual_continuity": {"rules": [story_sections.get("STORY_VISUAL_CONTINUITY", "")]},
            "default_avoid": [],
        },
        "dialogue_styles": [],
        "compiler_profiles": {"final_image_prompt": {}},
    }
    ir = compile_scene_render_ir(scene_builder, story_settings, {"legacy_references": references})
    prompt = final_image_prompt_text(ir)
    brief = local_render_brief(ir)
    return SceneRenderCompilation(
        prompt=prompt,
        ir=ir,
        validation={"errors": [], "warnings": []},
        local_brief=brief,
        local_prompt=local_render_prompt_text(brief),
        source_map={
            "story_file": story_file,
            "scene_file": scene_file,
            "scene_builder_file": scene_builder_file,
            "final_prompt": final_prompt_file,
            "compiler": "scene_render_v3",
            "artifacts": ["Scene_Render_IR.json", "Final_Image_Prompt.md", "Local_Render_Brief.json", "Local_Render_Prompt.md"],
        },
    )
