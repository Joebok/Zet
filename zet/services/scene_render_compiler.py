from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from zet.services.scene_prompt_cleanup import cleanup_compiled_scene_prompt


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


def _capitalize_bullet(line: str) -> str:
    if not line.startswith("- "):
        return line
    match = re.search(r"[A-Za-z]", line[2:])
    if match is None:
        return line
    index = match.start() + 2
    return line[:index] + line[index].upper() + line[index + 1:]


def humanize_identifier(value: str) -> str:
    text = re.sub(r"_[0-9a-f]{6,}$", "", _clean(value), flags=re.IGNORECASE)
    text = re.sub(r"_\d{8,}$", "", text)
    return re.sub(r"[_-]+", " ", text).strip()


def _items(values: Any) -> list[dict[str, Any]]:
    return [item for item in values or [] if isinstance(item, dict)]


def _lines(values: Any) -> list[str]:
    return [_clean(item) for item in values or [] if _clean(item)]


def _style_text(story_settings: dict[str, Any]) -> str:
    return _clean(story_settings.get("style_defaults", {}).get("canonical_art_style", {}).get("full_prompt_text"))


def compile_scene_render_ir(scene_data: dict[str, Any], story_settings: dict[str, Any], resolved_sources: dict[str, Any] | None = None) -> dict[str, Any]:
    setup = scene_data.get("setup", {})
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
    dialogue = _items(scene_data.get("dialogue"))
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
        "scene": {
            "id": scene_data.get("scene", {}).get("id", ""),
            "name": scene_data.get("scene", {}).get("name", ""),
            "slug": scene_data.get("scene", {}).get("slug", ""),
            "story_beat": scene_data.get("scene", {}).get("story_beat", ""),
        },
        "source": {
            "scene_json_path": scene_data.get("scene", {}).get("source_path", ""),
            "story_settings_path": scene_data.get("scene", {}).get("story_settings_path", ""),
            "source_hashes": {},
        },
        "canvas": setup.get("canvas", {}),
        "composition": setup.get("composition", {}),
        "style": {
            "art_style": _style_text(story_settings),
            "visual_continuity": story_settings.get("style_defaults", {}).get("visual_continuity", {}),
            "profile": story_profile,
        },
        "environment": setup.get("environment", {}),
        "elements": _items(scene_data.get("scene_elements")),
        "placements": _items(scene_data.get("placements")),
        "props": _items(scene_data.get("props_and_states")),
        "interactions": _items(scene_data.get("interactions")),
        "custom_interactions": _clean(scene_data.get("custom_interactions")),
        "dialogue": dialogue,
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
    region = explicit or clean_prompt_sentence(placement.get("position_within_cell"))
    if depth and depth not in region:
        return f"{region} {depth}".strip()
    return region


def _placement_sort_key(placement: dict[str, Any]) -> tuple[int, str, int]:
    return (0, _clean(placement.get("position_within_cell")), int(placement.get("id", "").rsplit("_", 1)[-1] or 9999) if str(placement.get("id", "")).rsplit("_", 1)[-1].isdigit() else 9999)


def _view_text(value: Any) -> str:
    return clean_prompt_sentence(value).replace("3/4", "three-quarter")


def _placement_element_id(placement: dict[str, Any]) -> str:
    return _clean(placement.get("scene_element_id"))


def _is_visible_subject(element: dict[str, Any], placement: dict[str, Any]) -> bool:
    return _clean(element.get("element_type")) in {"Character", "Monster"}


def _backdrop_element(ir: dict[str, Any]) -> dict[str, Any]:
    return next((element for element in ir.get("elements", []) if _clean(element.get("element_type")) == "Backdrop"), {})


def _backdrop_description(element: dict[str, Any]) -> str:
    sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
    return clean_prompt_sentence(
        sections.get("identity_preservation_core")
        or element.get("element_visual_override")
        or element.get("fallback_visual_description")
    )


def _resource_subject_type(element: dict[str, Any]) -> str:
    text = " ".join(_lines([
        element.get("element_visual_override"),
        element.get("fallback_visual_description"),
        element.get("display_name"),
        element.get("resource_type"),
        element.get("element_type"),
    ])).lower()
    if "half-elf" in text or "half elf" in text:
        return "half-elf woman"
    if "elf" in text:
        return "elf woman"
    if "woman" in text or "female" in text:
        return "woman"
    resource_type = _clean(element.get("resource_type")) or _clean(element.get("element_type"))
    return humanize_identifier(resource_type).lower() or "subject"


def _subject_count_phrase(subjects: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    if not subjects:
        return "no visible people"
    count_word = {1: "one", 2: "two", 3: "three", 4: "four"}.get(len(subjects), str(len(subjects)))
    types = [_resource_subject_type(element) for element, _placement in subjects]
    normalized = ["elf woman" if item == "half-elf woman" else item for item in types]
    if len(set(normalized)) == 1:
        plural = normalized[0].replace("woman", "women")
        return f"exactly {count_word} adult {plural}"
    return f"exactly {count_word} visible subjects"


def _descriptor_source(element: dict[str, Any]) -> str:
    sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
    return " ".join(_lines([
        element.get("local_render_visual_override"),
        element.get("element_visual_override"),
        sections.get("identity_preservation_core"),
        sections.get("identity_preservation_costume"),
        element.get("fallback_visual_description"),
    ]))


def build_local_visual_descriptor(element: dict[str, Any]) -> str:
    """Return a short checkpoint-readable visual descriptor."""
    source = clean_prompt_sentence(_descriptor_source(element))
    generic = _resource_subject_type(element)
    if not source:
        return f"adult {generic}" if "adult" not in generic else generic
    name_terms = _lines([element.get("id"), element.get("display_name"), element.get("character"), element.get("aux_resource_id")])
    for term in name_terms:
        source = re.sub(re.escape(term), "", source, flags=re.IGNORECASE)
    source = re.sub(r"\b(preserve|reference|canonical|identity|exact|must|forbidden|drift|matching)\b[^,.]*(?:,|\.|$)", "", source, flags=re.IGNORECASE)
    sentences = re.split(r"[.;]\s*", source)
    keep = []
    keywords = re.compile(r"\b(elf|woman|adult|petite|tall|short|slender|stocky|hair|bob|black|teal|crimson|red|gold|academy|adventur|outfit|dress|robe|armor|coat|hat|staff|sword)\b", re.IGNORECASE)
    for sentence in sentences:
        sentence = clean_prompt_sentence(sentence)
        if sentence and keywords.search(sentence):
            keep.append(sentence)
    text = ", ".join(keep[:3]) if keep else source
    terms = [term.strip(" ,") for term in re.split(r",|\band\b", text) if term.strip(" ,")]
    descriptor = ", ".join(dict.fromkeys(terms[:8]))
    if generic and generic not in descriptor.lower():
        descriptor = f"adult {generic}, {descriptor}" if "adult" not in generic else f"{generic}, {descriptor}"
    return clean_prompt_sentence(descriptor)


def _anchor_visual_descriptor(element: dict[str, Any]) -> str:
    source = clean_prompt_sentence(_descriptor_source(element))
    for term in _lines([element.get("id"), element.get("display_name"), element.get("aux_resource_id")]):
        source = re.sub(re.escape(term), "", source, flags=re.IGNORECASE)
    if source:
        return source
    return "major background architecture"


def _screen_facing(ir: dict[str, Any], placement: dict[str, Any]) -> tuple[str, str]:
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    target_id = _clean(pose.get("gaze_target_element_id") or placement.get("gaze_target_element_id"))
    if not target_id:
        return "", ""
    return "", "looking toward the subject opposite"


def _broad_pose(placement: dict[str, Any]) -> str:
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    parts = _lines([
        pose.get("summary") if pose else placement.get("pose"),
        pose.get("left_arm_action"),
        pose.get("right_arm_action"),
    ])
    text = ", ".join(parts)
    replacements = {
        "left hand raised": "one hand raised",
        "right hand raised": "one hand raised",
    }
    for old, new in replacements.items():
        text = re.sub(old, new, text, flags=re.IGNORECASE)
    return clean_prompt_sentence(text)


def _prompt_join(parts: list[str]) -> str:
    return ", ".join(dict.fromkeys(item for item in (clean_prompt_sentence(part) for part in parts) if item))


def _placement_line(ir: dict[str, Any], placement: dict[str, Any], elements_by_id: dict[str, dict[str, Any]]) -> str:
    element_id = _clean(placement.get("scene_element_id"))
    element = _element(ir, element_id)
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    pose_summary = clean_prompt_sentence(pose.get("summary") if pose else placement.get("pose"))
    region = _semantic_region(ir, placement)
    element_type = _clean(element.get("element_type"))
    verb = "occupies" if element_type in {"Place", "Backdrop"} or _clean(element.get("resource_type")) == "Place" else "stands"
    first = verb.capitalize()
    trailing_action = ""
    if pose_summary and pose_summary.lower() not in {"standing", "stands"} and verb == "stands":
        pose_match = re.match(r"^(.*?),\s*(.+?)(?:,)?$", pose_summary)
        if pose_match and region:
            first, trailing_action = pose_match.group(1), pose_match.group(2)
        else:
            first = pose_summary
    if region:
        first += f" in the {region}" if verb == "stands" else f" the {region}"
    if trailing_action:
        first += f", {trailing_action}"
    first = first[:1].upper() + first[1:]
    sentences = [_sentence(first)]
    target_id = _clean(pose.get("gaze_target_element_id") or placement.get("gaze_target_element_id"))
    target = get_element_display_name(target_id, elements_by_id) if target_id else ""
    actions = _lines([
        pose.get("left_arm_action"),
        pose.get("right_arm_action"),
    ])
    if actions:
        sentences.append(_sentence(", ".join(actions)))
    if target:
        sentences.append(_sentence(f"Looks directly at {target}"))
    expression = clean_prompt_sentence(pose.get("expression") or placement.get("expression"))
    if expression:
        sentences.append(_sentence(f"Expression: {expression}"))
    notes = clean_prompt_sentence(placement.get("placement_notes"))
    if notes:
        sentences.append(_sentence(notes))
    return " ".join(item for item in sentences if item)


def _reference_defaults(element: dict[str, Any], ref: dict[str, Any]) -> tuple[str, str]:
    resource_type = _clean(element.get("resource_type")) or _clean(element.get("element_type"))
    roles = {item.lower() for item in _lines(ref.get("roles"))}
    tag = _clean(ref.get("tag")).lower()
    if resource_type in {"Place", "Backdrop"}:
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
            "identity, facial features, hair, ears if applicable, body proportions, costume design, costume colors, and signature worn items",
            "source pose, expression, action, camera angle, framing, background, and lighting",
        )
    return (
        "identity, facial features, hair, ears if applicable, and body proportions",
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


def _custom_interaction_lines(ir: dict[str, Any]) -> list[str]:
    return [line if line.startswith("- ") else f"- {line}" for value in str(ir.get("custom_interactions") or "").splitlines() if (line := value.strip())]


def final_image_prompt_text(ir: dict[str, Any]) -> str:
    canvas = ir.get("canvas", {})
    environment = ir.get("environment", {})
    elements_by_id = _elements_by_id(ir)
    composition = ir.get("composition", {}) if isinstance(ir.get("composition"), dict) else {}
    backdrop = _backdrop_element(ir)
    lines = [
        "# Render Task",
        "",
        "Create one finished scene. Do not show the planning grid or split the image into comic panels.",
        "",
    ]
    story_beat = clean_prompt_sentence(ir.get("scene", {}).get("story_beat"))
    if story_beat:
        lines.extend(["# Story Beat", "", f"- {_sentence(story_beat)}", ""])
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
    lines.extend(["# Canvas", ""])
    lines.append(f"- {clean_prompt_sentence(canvas.get('orientation')) or 'Landscape'} {clean_prompt_sentence(canvas.get('aspect_ratio')) or '16:9'}.")
    composition_lines = []
    if clean_prompt_sentence(composition.get("focal_point")):
        composition_lines.append(f"- Primary focal point: {clean_prompt_sentence(composition.get('focal_point'))}.")
    read_order = [get_element_display_name(element_id, elements_by_id) for element_id in _lines(composition.get("left_to_right"))]
    if read_order:
        composition_lines.append(f"- Read the scene from left to right: {', then '.join(read_order)}.")
    if clean_prompt_sentence(composition.get("composition_notes")):
        composition_lines.append(f"- {_sentence(composition.get('composition_notes'))}")
    if composition_lines:
        lines.extend(["", "# Composition", "", *composition_lines])
    backdrop_lines = []
    backdrop_name = get_element_display_name(_clean(backdrop.get("id")), elements_by_id) if backdrop else ""
    backdrop_description = _backdrop_description(backdrop) if backdrop else ""
    location = clean_prompt_sentence(environment.get("location"))
    background_notes = clean_prompt_sentence(environment.get("general_background_notes"))
    if backdrop or location or background_notes:
        if location:
            backdrop_lines.append(f"- The scene takes place {location}.")
        if backdrop_name:
            backdrop_lines.append(f"- {backdrop_name} defines the overall background and surrounding setting.")
        if backdrop_description and backdrop_description.lower() not in {location.lower(), background_notes.lower()}:
            backdrop_lines.append(f"- Show {backdrop_description}.")
        if background_notes and background_notes.lower() not in {location.lower(), backdrop_description.lower()}:
            backdrop_lines.append(f"- {_sentence(background_notes)}")
        if backdrop:
            backdrop_lines.append("- Integrate all characters, props, and action naturally within this setting.")
    if backdrop_lines:
        lines.extend(["", "# Backdrop and Setting", "", *backdrop_lines])
    lines.extend(["", "# Character and Object Staging", ""])
    staging_count = 0
    for placement in ir.get("placements", []):
        element = _element(ir, _clean(placement.get("scene_element_id")))
        if _clean(element.get("element_type")) in {"Character", "Monster", "Place", "Prop", "Effect", "Vehicle"}:
            name = get_element_display_name(_clean(placement.get("scene_element_id")), elements_by_id)
            lines.append(f"- **{name}:** {_placement_line(ir, placement, elements_by_id)}")
            staging_count += 1
    if not staging_count:
        lines.extend(["- No staging specified."])
    motion_lines = []
    for placement in ir.get("placements", []):
        motion = placement.get("motion", {}) if isinstance(placement.get("motion"), dict) else {}
        if _clean(motion.get("state")) == "moving":
            name = get_element_display_name(_clean(placement.get("scene_element_id")), elements_by_id)
            direction = clean_prompt_sentence(motion.get("direction_screen"))
            cue = clean_prompt_sentence(motion.get("cue"))
            details = [f"{name} is visibly moving"]
            if direction:
                details.append(f"{direction} on screen")
            if cue:
                details.append(cue)
            motion_lines.append(f"- {_sentence(', '.join(details))}")
    if motion_lines:
        lines.extend(["", "# Motion Cues", "", *motion_lines])
    prop_lines = []
    for prop in ir.get("props", []):
        text = clean_prompt_sentence(prop.get("description") or prop.get("state") or prop.get("display_name"))
        if text:
            prop_lines.append(f"- {_sentence(text)}")
    if prop_lines:
        lines.extend(["", "# Props and States", "", *prop_lines])
    interaction_lines = _interaction_lines(ir, elements_by_id)
    custom_interaction_lines = _custom_interaction_lines(ir)
    if interaction_lines or custom_interaction_lines:
        lines.extend(["", "# Interactions", "", *[f"- {line}" for line in interaction_lines], *custom_interaction_lines])
    environment_lines = [
        _sentence(environment.get("general_foreground_notes")),
    ]
    environment_lines = [item for item in environment_lines if item]
    if environment_lines:
        lines.extend(["", "# Environment", "", *environment_lines])
    mood_lines = [
        f"- Lighting: {clean_prompt_sentence(environment.get('lighting'))}." if clean_prompt_sentence(environment.get("lighting")) else "",
        f"- Mood: {clean_prompt_sentence(environment.get('mood'))}." if clean_prompt_sentence(environment.get("mood")) else "",
        f"- Atmosphere: {clean_prompt_sentence(environment.get('weather_or_atmosphere'))}." if clean_prompt_sentence(environment.get("weather_or_atmosphere")) else "",
        f"- Art style: {clean_prompt_sentence(ir.get('style', {}).get('art_style'))}." if clean_prompt_sentence(ir.get("style", {}).get("art_style")) else "",
    ]
    if any(mood_lines):
        lines.extend(["", "# Lighting and Mood", "", *[line for line in mood_lines if line]])
    if ir.get("dialogue"):
        dialogue = ir["dialogue"]
        lines.extend(["", "# Dialogue Panel" if len(dialogue) == 1 else "# Dialogue Panels", ""])
        for index, item in enumerate(dialogue, start=1):
            if len(dialogue) > 1:
                lines.extend([f"## Dialogue Panel {index}", ""])
            speaker = get_element_display_name(_clean(item.get("speaker_element_id")), elements_by_id)
            lines.append(f"{speaker} says exactly: \"{item.get('text', '')}\"")
            target = get_element_display_name(_clean(item.get("target_element_id")), elements_by_id) if _clean(item.get("target_element_id")) else ""
            if target:
                lines.append(f"Place the panel so the dialogue reads as directed toward {target}.")
            pointer_target = clean_prompt_sentence(item.get("pointer_target"))
            if pointer_target:
                lines.append(f"Aim the dialogue-panel pointer at {pointer_target}.")
            max_lines = item.get("max_lines")
            if isinstance(max_lines, int) and max_lines > 0:
                line_label = "line" if max_lines == 1 else "lines"
                lines.append(f"Wrap the dialogue in no more than {max_lines} {line_label}.")
            instructions = clean_prompt_sentence(item.get("notes"))
            if instructions:
                lines.append(f"- **Special instructions:** {instructions}")
            if index < len(dialogue):
                lines.append("")
    preserve_lines = []
    referenced_element_ids = {
        _clean(ref.get("applies_to_element_id"))
        for ref in ir.get("references", [])
        if _clean(ref.get("tag")) and _clean(ref.get("applies_to_element_id"))
    }
    continuity = ir.get("style", {}).get("visual_continuity", {})
    for rule in _lines(continuity.get("rules")):
        preserve_lines.append(f"- {rule}")
    for element in ir.get("elements", []):
        element_id = _clean(element.get("id"))
        sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
        identity = clean_prompt_sentence(sections.get("identity_preservation_core"))
        costume = clean_prompt_sentence(sections.get("identity_preservation_costume"))
        override = clean_prompt_sentence(element.get("element_visual_override"))
        fallback = clean_prompt_sentence(element.get("fallback_visual_description")) if element_id not in referenced_element_ids else ""
        if identity or costume or override or fallback:
            preserve_lines.extend(["", f"## {get_element_display_name(element_id, elements_by_id)}", ""])
            resource_type = _clean(element.get("resource_type")) or _clean(element.get("element_type"))
            if identity:
                label = "Location design" if resource_type in {"Place", "Backdrop"} else "Identity"
                preserve_lines.append(f"**{label}:** {identity}")
            if costume and resource_type not in {"Place", "Object", "Backdrop", "Prop"}:
                costume_name = clean_prompt_sentence(element.get("costume"))
                label = f"Costume - {costume_name}" if costume_name else "Costume"
                preserve_lines.extend(["", f"**{label}:** {costume}"])
            if override:
                preserve_lines.extend(["", f"**Element Override:** {override}"])
            if fallback:
                preserve_lines.extend(["", f"**Visual description:** {fallback}"])
    if preserve_lines:
        lines.extend(["", "# Scene Element Preservation", "", *preserve_lines])
    avoid = ", ".join(_lines(ir.get("avoid")) or ["unrequested text", "malformed hands"])
    lines.extend(["", "# Avoid", "", f"No {avoid}.", "", "# Final Verification", ""])
    for item in ir.get("final_verification", []):
        lines.append(f"- {_sentence(item)}")
    markdown = "\n".join(_capitalize_bullet(line) for line in lines).strip() + "\n"
    return cleanup_compiled_scene_prompt(markdown)


def local_render_brief(ir: dict[str, Any]) -> dict[str, Any]:
    canvas = ir.get("canvas", {})
    elements_by_id = _elements_by_id(ir)
    placements = sorted(ir.get("placements", []), key=_placement_sort_key)
    subjects = [(elements_by_id.get(_placement_element_id(item), {}), item) for item in placements]
    subjects = [(element, placement) for element, placement in subjects if _is_visible_subject(element, placement)]
    subject_phrase = _subject_count_phrase(subjects)
    anchor_parts = []
    for placement in placements:
        element = elements_by_id.get(_placement_element_id(placement), {})
        if _clean(element.get("element_type")) not in {"Place", "Backdrop"} and _clean(element.get("resource_type")) != "Place":
            continue
        region = _semantic_region(ir, placement)
        descriptor = _anchor_visual_descriptor(element)
        notes = clean_prompt_sentence(placement.get("placement_notes"))
        anchor_parts.append(_prompt_join([descriptor, f"{region} scenery", notes]))
    global_parts = [
        f"{_clean(canvas.get('orientation')) or 'landscape'} {_clean(canvas.get('aspect_ratio')) or '16:9'}",
        subject_phrase,
        "full bodies visible" if subjects else "",
        *anchor_parts,
        clean_prompt_sentence(ir.get("environment", {}).get("weather_or_atmosphere")),
    ]
    regions = []
    subject_prompt_lines: list[tuple[str, str]] = []
    for placement in placements:
        element_id = _placement_element_id(placement)
        element = elements_by_id.get(element_id, {})
        region = _semantic_region(ir, placement)
        if not region:
            continue
        is_scenery = _clean(element.get("element_type")) in {"Place", "Backdrop"} or _clean(element.get("resource_type")) == "Place"
        if not _is_visible_subject(element, placement) and not is_scenery:
            continue
        prompt_parts = [subject_phrase]
        if _is_visible_subject(element, placement):
            descriptor = build_local_visual_descriptor(element)
            facing, gaze = _screen_facing(ir, placement)
            expression = clean_prompt_sentence((placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}).get("expression") or placement.get("expression"))
            if expression:
                expression = f"Expression: {expression}"
            label = "visible subject"
            prompt_parts.extend([
                f"{label} positioned in the {region}",
                descriptor,
                _broad_pose(placement),
                expression,
                facing,
                gaze,
            ])
        elif is_scenery:
            prompt_parts.extend([_anchor_visual_descriptor(element), f"{region} {_clean(placement.get('depth')) or 'background'} scenery", clean_prompt_sentence(placement.get("placement_notes"))])
        prompt = _prompt_join(prompt_parts)
        if _is_visible_subject(element, placement):
            subject_prompt_lines.append((_clean(placement.get("position_within_cell")), prompt))
        regions.append({
            "region": region,
            "depths": list(dict.fromkeys([_clean(placement.get("depth"))] if _clean(placement.get("depth")) else [])),
            "element_ids": [element_id],
            "prompt": prompt,
        })
    plain_prompt = _prompt_join(global_parts + [region["prompt"] for region in regions])
    negative = list(dict.fromkeys([
        "extra people",
        "third person",
        "crowd",
        "duplicate character",
        "same character twice",
        "merged characters",
        "fused bodies",
        "overlapping characters",
        "characters touching",
        "both characters on the same side",
        "person in the center foreground",
        "centered foreground character",
        "cropped body",
        "cropped feet",
        "back turned toward the other character",
        "looking at viewer",
        "extra limbs",
        "malformed hands",
        "text",
        "letters",
        "caption",
        "speech bubble",
        "watermark",
    ]))
    horizontal_order = {"left": 0, "center": 1, "right": 2}
    subject_prompt_lines.sort(key=lambda item: (horizontal_order.get(item[0], 3), item[0]))
    prompt_lines = [line for line in [_prompt_join(global_parts), *[item[1] for item in subject_prompt_lines]] if line]
    return {
        "schema_version": 2,
        "purpose": "composition_preview",
        "include_dialogue": False,
        "subject_count": len(subjects),
        "canvas": canvas,
        "global_prompt": prompt_lines[0] if prompt_lines else "",
        "regions": regions,
        "plain_txt2img": {
            "prompt": plain_prompt,
            "negative_prompt": ", ".join(negative),
        },
        "forge_couple_basic": {
            "direction": "Horizontal",
            "background": "First Line",
            "background_weight": 0.5,
            "separator": "\n",
            "prompt_lines": prompt_lines,
        },
    }


def local_render_prompt_text(brief: dict[str, Any]) -> str:
    plain = brief.get("plain_txt2img", {}) if isinstance(brief.get("plain_txt2img"), dict) else {}
    return f"prompt: {plain.get('prompt', '')}\nnegative: {plain.get('negative_prompt', '')}\n"


def local_render_forge_couple_prompt_text(brief: dict[str, Any]) -> str:
    forge = brief.get("forge_couple_basic", {}) if isinstance(brief.get("forge_couple_basic"), dict) else {}
    plain = brief.get("plain_txt2img", {}) if isinstance(brief.get("plain_txt2img"), dict) else {}
    lines = [
        "mode: Basic",
        f"direction: {forge.get('direction', 'Horizontal')}",
        f"background: {forge.get('background', 'First Line')}",
        f"background_weight: {forge.get('background_weight', 0.5)}",
        "separator: newline",
        "",
        "prompt:",
        *[line for line in forge.get("prompt_lines", []) if line],
        "",
        "negative:",
        str(plain.get("negative_prompt", "")),
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_final_image_prompt(ir: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_image_prompt_text(ir), encoding="utf-8")


def write_local_render_brief(ir: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(local_render_brief(ir), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_local_render_prompt(local_brief: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(local_render_prompt_text(local_brief), encoding="utf-8")


def write_local_render_forge_couple_prompt(local_brief: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(local_render_forge_couple_prompt_text(local_brief), encoding="utf-8")


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
