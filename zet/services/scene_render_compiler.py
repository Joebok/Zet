from __future__ import annotations

import re
from typing import Any

from zet.services.scene_prompt_cleanup import cleanup_compiled_scene_prompt


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


def _is_suppressed_placement(placement: dict[str, Any]) -> bool:
    return _clean(placement.get("position_within_cell")).lower() == "none"


def _style_text(story_settings: dict[str, Any]) -> str:
    return _clean(story_settings.get("style_defaults", {}).get("canonical_art_style", {}).get("full_prompt_text"))


def compile_scene_render_ir(scene_data: dict[str, Any], story_settings: dict[str, Any], resolved_sources: dict[str, Any] | None = None) -> dict[str, Any]:
    setup = scene_data.get("setup", {})
    placements = [item for item in _items(scene_data.get("placements")) if not _is_suppressed_placement(item)]
    suppressed_element_ids = {
        _clean(item.get("scene_element_id"))
        for item in _items(scene_data.get("placements"))
        if _is_suppressed_placement(item)
    }
    source_composition = setup.get("composition", {})
    composition = dict(source_composition) if isinstance(source_composition, dict) else {}
    composition["left_to_right"] = [
        element_id for element_id in _lines(composition.get("left_to_right"))
        if element_id not in suppressed_element_ids
    ]
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
        "composition": composition,
        "style": {
            "art_style": _style_text(story_settings),
            "visual_continuity": story_settings.get("style_defaults", {}).get("visual_continuity", {}),
            "profile": story_profile,
        },
        "environment": setup.get("environment", {}),
        "elements": _items(scene_data.get("scene_elements")),
        "placements": placements,
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
    sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
    text = " ".join(_lines([
        element.get("element_visual_override"),
        element.get("fallback_visual_description"),
        sections.get("identity_preservation_core"),
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


def collect_primary_characters(ir: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    elements = _elements_by_id(ir)
    placements = {_placement_element_id(item): item for item in ir.get("placements", [])}
    return [
        (element, placements[_clean(element.get("id"))])
        for element in ir.get("elements", [])
        if _clean(element.get("element_type")) == "Character" and _clean(element.get("id")) in placements
    ]


def collect_backdrops(ir: dict[str, Any]) -> list[dict[str, Any]]:
    return [element for element in ir.get("elements", []) if _clean(element.get("element_type")) == "Backdrop"]


def resolve_character_order(
    ir: dict[str, Any],
    characters: list[tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[str]]:
    by_id = {_clean(element.get("id")): (element, placement) for element, placement in characters}
    ordered: list[tuple[dict[str, Any], dict[str, Any]]] = []
    warnings: list[str] = []
    for element_id in _lines(ir.get("composition", {}).get("left_to_right")):
        item = by_id.get(element_id)
        if item is None:
            warnings.append(f"Ignoring unresolved left-to-right character ID: {element_id}")
        elif item not in ordered:
            ordered.append(item)
    horizontal = {"far_left": 0, "left": 1, "center_left": 2, "center": 3, "center_right": 4, "right": 5, "far_right": 6}
    remaining = [item for item in characters if item not in ordered]
    remaining.sort(key=lambda item: (horizontal.get(_clean(item[1].get("position_within_cell")).lower(), 7), characters.index(item)))
    if not ordered and len(remaining) == 2:
        first_key = horizontal.get(_clean(remaining[0][1].get("position_within_cell")).lower(), 7)
        second_key = horizontal.get(_clean(remaining[1][1].get("position_within_cell")).lower(), 7)
        if first_key == second_key:
            first, second = remaining
            first_name = (_clean(first[0].get("display_name")) or humanize_identifier(_clean(first[0].get("id")))).lower()
            second_name = (_clean(second[0].get("display_name")) or humanize_identifier(_clean(second[0].get("id")))).lower()
            first_notes = _clean(first[1].get("placement_notes")).lower()
            second_notes = _clean(second[1].get("placement_notes")).lower()
            if f"right of {second_name}" in first_notes or f"left of {first_name}" in second_notes:
                remaining = [second, first]
            elif f"left of {second_name}" in first_notes or f"right of {first_name}" in second_notes:
                remaining = [first, second]
    return ordered + remaining, warnings


def normalize_horizontal_slots(
    ordered_characters: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, str]:
    if len(ordered_characters) == 2:
        return {
            _clean(ordered_characters[0][0].get("id")): "left",
            _clean(ordered_characters[1][0].get("id")): "right",
        }
    normalized = {"far left": "far_left", "center left": "center_left", "center right": "center_right", "far right": "far_right"}
    result = {}
    for index, (element, placement) in enumerate(ordered_characters):
        raw = _clean(placement.get("position_within_cell")).lower().replace("_", " ")
        result[_clean(element.get("id"))] = normalized.get(raw, raw.replace(" ", "_")) or ("center" if len(ordered_characters) == 1 else f"slot_{index + 1}")
    return result


def _count_word(value: int) -> str:
    return {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four"}.get(value, str(value))


def _normalized_view(element: dict[str, Any], placement: dict[str, Any]) -> str:
    references = " ".join(_clean(item.get("tag")) for item in _items(element.get("reference_images")))
    sources = [element.get("element_visual_override"), placement.get("placement_notes"), references]
    patterns = [
        (r"back[\s_-]*right(?:\s+|[-_/])*(?:3/4|three.quarter)", "back-right three-quarter"),
        (r"back[\s_-]*left(?:\s+|[-_/])*(?:3/4|three.quarter)", "back-left three-quarter"),
        (r"front[\s_-]*right(?:\s+|[-_/])*(?:3/4|three.quarter)", "front-right three-quarter"),
        (r"front[\s_-]*left(?:\s+|[-_/])*(?:3/4|three.quarter)", "front-left three-quarter"),
        (r"(?:rear|back)(?:\s+|[-_/])*(?:3/4|three.quarter)", "rear three-quarter"),
        (r"\bleft\s+profile\b", "left profile"),
        (r"\bright\s+profile\b", "right profile"),
        (r"\bback\b|\brear\b", "back"),
        (r"\bfront\b", "front"),
    ]
    for source in sources:
        text = _clean(source).lower()
        for pattern, value in patterns:
            if re.search(pattern, text):
                return value
    motion = placement.get("motion", {}) if isinstance(placement.get("motion"), dict) else {}
    return "back" if "away from camera" in _clean(motion.get("direction_screen")).lower() else "neutral three-quarter"


def _identity_and_costume(element: dict[str, Any], other_names: list[str]) -> tuple[str, str]:
    sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
    identity = clean_prompt_sentence(sections.get("identity_preservation_core") or element.get("fallback_visual_description"))
    costume = clean_prompt_sentence(sections.get("identity_preservation_costume"))
    if not identity:
        visual_override = clean_prompt_sentence(element.get("element_visual_override"))
        visual_sentences = [
            sentence for sentence in re.split(r"[.;]\s*", visual_override)
            if sentence and not re.search(r"\b(walk|stand|move|view|arm|holding|through the arch)\b", sentence, re.IGNORECASE)
        ]
        identity = clean_prompt_sentence(". ".join(visual_sentences)) or f"adult {_resource_subject_type(element)}"
    for name in [_clean(element.get("id")), _clean(element.get("display_name")), *other_names]:
        if name:
            identity = re.sub(re.escape(name), "", identity, flags=re.IGNORECASE)
            costume = re.sub(re.escape(name), "", costume, flags=re.IGNORECASE)
    identity = re.sub(r"^\s*[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?\s+—\s+", "", identity)
    costume = re.sub(r"^\s*Costume\s+—\s+", "", costume, flags=re.IGNORECASE)
    identity = re.sub(r"\b(?:with a confident, aristocratic bearing|poised, immaculately groomed, fashionable, and subtly condescending)\b,?", "", identity, flags=re.IGNORECASE)
    identity_sentences = [
        sentence.strip(" ,.—") for sentence in re.split(r"[.;]\s*", identity)
        if sentence.strip(" ,.—") and not re.search(r"\b(innocent|thoughtful|determined|sense of wonder|personality|motivation)\b", sentence, re.IGNORECASE)
    ]
    costume_sentences = [
        sentence.strip(" ,.—") for sentence in re.split(r"[.;]\s*", costume)
        if sentence.strip(" ,.—") and not re.search(r"\b(reflecting|wealth|status|upbringing|taste)\b", sentence, re.IGNORECASE)
    ]
    identity = ". ".join(identity_sentences[:3])
    costume = ". ".join(costume_sentences[:2])
    phase = _clean(element.get("phase")).lower()
    if phase in {"youth", "adolescent", "teen"} or re.search(r"\b(adolescent|teen(?:age)?)\b", identity, re.IGNORECASE):
        identity = re.sub(r"\badult\s+(?:character|elf woman|woman)\b,?\s*", "", identity, flags=re.IGNORECASE)
        if not re.search(r"\b(adolescent|teen(?:age)?)\b", identity, re.IGNORECASE):
            identity = f"adolescent {identity}"
    return clean_prompt_sentence(identity).strip(" ,.—"), clean_prompt_sentence(costume).strip(" ,.—")


def _character_prop_text(ir: dict[str, Any], element: dict[str, Any], placement: dict[str, Any]) -> str:
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    element_id = _clean(element.get("id"))
    associated_props = [
        clean_prompt_sentence(prop.get("description") or prop.get("state") or prop.get("display_name"))
        for prop in ir.get("props", [])
        if element_id in {
            _clean(prop.get("scene_element_id")), _clean(prop.get("character_element_id")),
            _clean(prop.get("holder_element_id")), _clean(prop.get("owner_element_id")),
        }
    ]
    source = " ".join(_lines([
        element.get("element_visual_override"), placement.get("placement_notes"), pose.get("summary"),
        pose.get("left_arm_action"), pose.get("right_arm_action"), *associated_props,
    ])).lower()
    if "stack of books" in source:
        return "carrying a stack of books in front"
    if "book" in source:
        if "wrapped around" in source or "holding one" in source:
            return "carrying one book tightly against her torso"
        return "carrying a book"
    return ""


def _character_region_prompt(
    ir: dict[str, Any],
    element: dict[str, Any],
    placement: dict[str, Any],
    slot: str,
    subject_count: int,
) -> tuple[str, dict[str, Any], list[str]]:
    elements = _elements_by_id(ir)
    element_id = _clean(element.get("id"))
    name = get_element_display_name(element_id, elements)
    other_names = [get_element_display_name(key, elements) for key in elements if key != element_id]
    identity, costume = _identity_and_costume(element, other_names)
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    motion = placement.get("motion", {}) if isinstance(placement.get("motion"), dict) else {}
    moving = _clean(motion.get("state")).lower() == "moving" or "walking" in _clean(element.get("element_visual_override")).lower()
    direction = clean_prompt_sentence(motion.get("direction_screen"))
    action = f"walking {direction}".strip() if moving else clean_prompt_sentence(pose.get("summary"))
    corrections = []
    if moving and "stand" in _clean(pose.get("summary")).lower():
        corrections.append(f"{name}: standing -> walking")
    prop = _character_prop_text(ir, element, placement)
    if prop and "wrapped around" in _clean(element.get("element_visual_override")).lower():
        corrections.append(f"{name}: wrapped arms + book -> book held against torso")
    view = _normalized_view(element, placement)
    target_id = _clean(pose.get("gaze_target_element_id") or placement.get("gaze_target_element_id"))
    if not target_id:
        target_id = next((
            _clean(item.get("target_element_id"))
            for item in ir.get("interactions", [])
            if _clean(item.get("subject_element_id")) == element_id
            and _relationship_key(item.get("relationship") or item.get("type")) in {"looking at", "looks at", "gaze", "direct gaze"}
        ), "")
    target = get_element_display_name(target_id, elements) if target_id else ""
    if target:
        gaze = f"glancing sideways toward {target}" if "back" in view or "rear" in view else f"looking toward {target}"
    else:
        gaze = ""
    expression = clean_prompt_sentence(pose.get("expression") or placement.get("expression"))
    depth = _clean(placement.get("depth")) or "midground"
    parts = [
        f"Scene contains exactly {_count_word(subject_count)} separate primary characters",
        f"This region contains {name} only",
        f"in the {slot.replace('_', ' ')} {depth}",
        identity,
        f"seen from the {view} view",
        action,
        costume,
        prop,
        expression,
        gaze,
    ]
    return _prompt_join(parts), {"view": view, "action": action, "prop": prop, "gaze": gaze}, corrections


def _advanced_mapping(canvas: dict[str, Any], index: int, count: int, depth: str, weight: float) -> list[float]:
    portrait = _clean(canvas.get("orientation")).lower() != "landscape"
    if count == 2:
        x1, x2 = ((0.04, 0.47), (0.53, 0.96))[index] if portrait else ((0.02, 0.49), (0.51, 0.98))[index]
    else:
        gap = 0.04
        width = (1.0 - gap * (count + 1)) / max(count, 1)
        x1 = gap + index * (width + gap)
        x2 = x1 + width
    y1, y2 = {"foreground": (0.05, 1.0), "midground": (0.20, 0.98), "background": (0.30, 0.90)}.get(depth, (0.20, 0.98))
    return [round(x1, 2), round(x2, 2), y1, y2, round(max(0.8, min(1.2, weight)), 2)]


def validate_forge_couple_plan(plan: dict[str, Any]) -> bool:
    lines = [plan.get("global_region", {}).get("prompt"), *[item.get("prompt") for item in plan.get("character_regions", [])]]
    mappings = [plan.get("global_region", {}).get("mapping"), *[item.get("mapping") for item in plan.get("character_regions", [])]]
    return bool(lines[0]) and len(lines) == len(mappings) and all(lines) and all(mapping for mapping in mappings)


def build_forge_couple_plan(ir: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or {}
    characters, backdrops = collect_primary_characters(ir), collect_backdrops(ir)
    ordered, warnings = resolve_character_order(ir, characters)
    slots = normalize_horizontal_slots(ordered)
    elements = _elements_by_id(ir)
    focal = _clean(ir.get("composition", {}).get("focal_point")).lower()
    focal_ids = {key for key in elements if focal in {key.lower(), get_element_display_name(key, elements).lower()}}
    regions = []
    corrections = []
    for index, (element, placement) in enumerate(ordered):
        element_id = _clean(element.get("id"))
        is_focal = element_id in focal_ids
        prompt, staging, region_corrections = _character_region_prompt(ir, element, placement, slots[element_id], len(ordered))
        corrections.extend(region_corrections)
        depth = _clean(placement.get("depth")) or "midground"
        regions.append({
            "scene_element_id": element_id,
            "display_name": get_element_display_name(element_id, elements),
            "order_index": index,
            "horizontal_slot": slots[element_id],
            "depth": depth,
            "is_focal": is_focal,
            "staging": staging,
            "prompt": prompt,
            "mapping": _advanced_mapping(ir.get("canvas", {}), index, len(ordered), depth, 1.08 if is_focal else 1.0),
        })
    motions = [placement.get("motion", {}) if isinstance(placement.get("motion"), dict) else {} for _element_item, placement in ordered]
    shared_motion = bool(motions) and len({(_clean(item.get("state")).lower(), _clean(item.get("direction_screen")).lower()) for item in motions}) == 1
    direction = clean_prompt_sentence(motions[0].get("direction_screen")) if shared_motion else ""
    action = f"walking side by side {direction}".strip() if shared_motion and _clean(motions[0].get("state")).lower() == "moving" else f"{_count_word(len(ordered))} separate characters occupying distinct positions"
    names = " and ".join(f"{item['display_name']} on the {item['horizontal_slot'].replace('_', ' ')}" for item in regions)
    subject_types = [_resource_subject_type(element) for element, _placement in ordered]
    shared_subject_summary = ""
    if subject_types and all("elf woman" in subject_type for subject_type in subject_types):
        shared_subject_summary = f"{_count_word(len(ordered))} separate elf women"
    depths = list(dict.fromkeys(item["depth"] for item in regions))
    backdrop_text = _prompt_join([_backdrop_description(item) or get_element_display_name(_clean(item.get("id")), elements) for item in backdrops])
    environment = ir.get("environment", {})
    global_prompt = _prompt_join([
        f"{_clean(ir.get('canvas', {}).get('orientation')) or 'landscape'} {_clean(ir.get('canvas', {}).get('aspect_ratio')) or '16:9'} fantasy scene",
        f"exactly {_count_word(len(ordered))} separate primary characters",
        shared_subject_summary,
        action,
        names,
        f"full-body {' and '.join(depths)} figures" if ordered else "",
        "rear three-quarter views" if direction.lower() == "away from camera" else "",
        "clear space between their bodies" if len(ordered) == 2 else "",
        f"{backdrop_text} spans the background" if backdrop_text else "",
        clean_prompt_sentence(environment.get("location")),
        clean_prompt_sentence(environment.get("lighting")),
        clean_prompt_sentence(ir.get("style", {}).get("art_style")),
    ])
    advanced = bool(backdrops and len(ordered) >= 2)
    plan = {
        "mode": "Advanced" if advanced else "Basic",
        "subject_count": len(ordered),
        "backdrop_count": len(backdrops),
        "strict_primary_subject_count": bool(settings.get("strict_primary_subject_count", True)),
        "forge_couple_debug_base_pass": bool(settings.get("forge_couple_debug_base_pass", True)),
        "global_region": {"prompt": global_prompt, "mapping": [0.0, 1.0, 0.0, 1.0, 0.65]},
        "character_regions": regions,
        "diagnostics": {
            "warnings": warnings,
            "conflict_corrections": corrections,
            "suppressed_incidental_background_subjects": bool(settings.get("strict_primary_subject_count", True)),
        },
    }
    plan["valid"] = validate_forge_couple_plan(plan)
    return plan


def _placement_line(ir: dict[str, Any], placement: dict[str, Any], elements_by_id: dict[str, dict[str, Any]]) -> str:
    element_id = _clean(placement.get("scene_element_id"))
    element = _element(ir, element_id)
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    pose_summary = clean_prompt_sentence(pose.get("summary") if pose else placement.get("pose"))
    world_position = clean_prompt_sentence(placement.get("world_position"))
    if world_position:
        name = get_element_display_name(element_id, elements_by_id)
        world_sentence = _sentence(world_position)
        world_sentence = world_sentence[:1].upper() + world_sentence[1:]
        normalized_world = world_position.rstrip(".!?").lower()
        pose_lower = pose_summary.lower()
        prefix_boundary = pose_lower[len(normalized_world):len(normalized_world) + 1]
        if pose_lower.startswith(normalized_world) and (not prefix_boundary or prefix_boundary in " ,.;:!?"):
            pose_summary = pose_summary[len(normalized_world):].lstrip(" ,.;:!?")
            pose_summary = pose_summary[:1].upper() + pose_summary[1:]
        sentences = [world_sentence, _sentence(pose_summary)]
        actions = _lines([pose.get("left_arm_action"), pose.get("right_arm_action")])
        if actions:
            sentences.append(_sentence(", ".join(actions)))
        target_id = _clean(pose.get("gaze_target_element_id") or placement.get("gaze_target_element_id"))
        target = get_element_display_name(target_id, elements_by_id) if target_id else ""
        if target:
            sentences.append(_sentence(f"Looks directly at {target}"))
        expression = clean_prompt_sentence(pose.get("expression") or placement.get("expression"))
        if expression:
            sentences.append(_sentence(f"Expression: {expression}"))
        notes = clean_prompt_sentence(placement.get("placement_notes"))
        if notes:
            sentences.append(_sentence(notes))
        position = clean_prompt_sentence(placement.get("position_within_cell"))
        depth = clean_prompt_sentence(placement.get("depth"))
        camera_region = " ".join(item for item in (position, depth) if item)
        if camera_region:
            sentences.append(_sentence(f"Place {name} in the {camera_region} region"))
        return " ".join(item for item in sentences if item)
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
        composition_lines.append(f"- From left to right the viewer sees: {', then '.join(read_order)}.")
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


def local_render_brief(ir: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "solo",
        "one person",
        "single person",
        "extra people",
        "extra primary character",
        "third foreground person",
        "crowd",
        "duplicate character",
        "same character twice",
        "merged characters",
        "fused bodies",
        "blended faces",
        "hybrid character",
        "overlapping characters",
        "overlapping bodies",
        "characters touching",
        "both characters on the same side",
        "person in the center foreground",
        "centered foreground character",
        "cropped body",
        "cropped feet",
        "looking at viewer",
        "front-facing body",
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
    basic_prompt_lines = [line for line in [_prompt_join(global_parts), *[item[1] for item in subject_prompt_lines]] if line]
    forge_plan = build_forge_couple_plan(ir, settings)
    if forge_plan["subject_count"] < 2:
        negative = [term for term in negative if term not in {"solo", "one person", "single person", "third foreground person"}]
    if not forge_plan["strict_primary_subject_count"]:
        negative = [term for term in negative if term not in {"extra people", "crowd"}]
    prompt_lines = [
        forge_plan.get("global_region", {}).get("prompt", ""),
        *[region.get("prompt", "") for region in forge_plan.get("character_regions", [])],
    ]
    if not forge_plan.get("valid"):
        forge_plan["mode"] = "Basic"
        forge_plan.setdefault("diagnostics", {}).setdefault("warnings", []).append(
            "Advanced prompt/mapping count mismatch; using safe Basic mode."
        )
        prompt_lines = basic_prompt_lines
    return {
        "schema_version": 3,
        "purpose": "composition_preview",
        "include_dialogue": False,
        "subject_count": forge_plan["subject_count"],
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
        "forge_couple_plan": forge_plan,
    }


def local_render_prompt_text(brief: dict[str, Any]) -> str:
    plain = brief.get("plain_txt2img", {}) if isinstance(brief.get("plain_txt2img"), dict) else {}
    return f"prompt: {plain.get('prompt', '')}\nnegative: {plain.get('negative_prompt', '')}\n"


def local_render_forge_couple_prompt_text(brief: dict[str, Any]) -> str:
    forge = brief.get("forge_couple_basic", {}) if isinstance(brief.get("forge_couple_basic"), dict) else {}
    plan = brief.get("forge_couple_plan", {}) if isinstance(brief.get("forge_couple_plan"), dict) else {}
    plain = brief.get("plain_txt2img", {}) if isinstance(brief.get("plain_txt2img"), dict) else {}
    mode = str(plan.get("mode") or "Basic")
    lines = [
        f"mode: {mode}",
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
    diagnostics = plan.get("diagnostics", {}) if isinstance(plan.get("diagnostics"), dict) else {}
    if plan:
        lines.extend([
            "",
            "diagnostics:",
            f"Forge Couple mode: {mode}",
            f"Primary subjects: {plan.get('subject_count', 0)}",
            f"Backdrop regions: {plan.get('backdrop_count', 0)}",
            "Character order:",
            *[
                f"  {index}. {region.get('scene_element_id')} -> {region.get('horizontal_slot')}"
                for index, region in enumerate(plan.get("character_regions", []), start=1)
            ],
            f"Focal region: {next((region.get('display_name') for region in plan.get('character_regions', []) if region.get('is_focal')), 'none')}",
            f"Suppressed incidental background subjects: {'yes' if diagnostics.get('suppressed_incidental_background_subjects') else 'no'}",
            *[f"Warning: {warning}" for warning in diagnostics.get("warnings", [])],
            *[f"Conflict correction: {correction}" for correction in diagnostics.get("conflict_corrections", [])],
        ])
    return "\n".join(lines).rstrip() + "\n"
