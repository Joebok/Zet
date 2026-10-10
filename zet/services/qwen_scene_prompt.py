"""Natural-language scene prompts for Qwen Image 2.1 local renders."""

from __future__ import annotations

import re
from typing import Any

from zet.services.scene_spatial_contract import (
    gaze_is_consistent,
    frame_extension_contract,
    has_measured_layout,
    group_reference_contract,
    layout_reference_contract,
    projected_subject_text,
    projection_for_element,
    suppress_spatial_clauses,
)


_ARRIVAL_LANGUAGE = re.compile(
    r"\b(?:approach(?:ing|es)?|enter(?:ing|s)?|arriv(?:e|es|ing)|"
    r"come|comes|coming|walk(?:ing)? in|move(?:s|d|ing)? from|"
    r"entering the scene|from the background)\b",
    re.IGNORECASE,
)
_SPATIAL_WORDS = {
    "left": {"left", "screen-left", "left side"},
    "center": {"center", "centre", "middle", "screen-center"},
    "right": {"right", "screen-right", "right side"},
}
_VISIBLE_TYPES = {"character", "monster"}
_POSE_OR_ACTION = re.compile(
    r"\b(?:push(?:es|ed|ing)?|shov(?:e|es|ed|ing)|point(?:s|ed|ing)?|grinn?(?:s|ed|ing)?|"
    r"smil(?:e|es|ed|ing)|laugh(?:s|ed|ing)?|lean(?:s|ed|ing)?|stand(?:s|ing)?|sit(?:s|ting)?|"
    r"walk(?:s|ed|ing)?|mov(?:e|es|ed|ing)|approach(?:es|ed|ing)?|enter(?:s|ed|ing) the scene)\b",
    re.IGNORECASE,
)
_NONVISUAL_MOTION = re.compile(r"\b(?:horseplay|antics|harmless|moving along|entering the scene)\b", re.IGNORECASE)
_APPEARANCE_WORD = re.compile(
    r"\b(?:hair|skin|eyes?|face|ears?|shirt|coat|vest|waistcoat|dress|trousers|boots|belt|"
    r"armor|jacket|cloak|pendant|crest|freckles|scar|jewelry|fabric|cloth|colored|coloured)\b",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .;,")


def _sentence(value: Any) -> str:
    content = _text(value)
    return f"{content}." if content else ""


def _items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _elements(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in _items(ir.get("elements")) if item.get("id")}


def _placements(ir: dict[str, Any], elements: dict[str, dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    visible = []
    seen: set[str] = set()
    for placement in _items(ir.get("placements")):
        element_id = str(placement.get("scene_element_id") or "")
        element = elements.get(element_id)
        if not element or _text(placement.get("position_within_cell")).casefold() == "none":
            continue
        if element_id in seen:
            continue
        seen.add(element_id)
        visible.append((element, placement))
    return visible


def _reference_lines(
    image_inputs: list[dict[str, Any]], elements: dict[str, dict[str, Any]], *, measured_layout: bool = False
) -> list[str]:
    lines: list[str] = []
    for index, item in enumerate(image_inputs, start=1):
        tag = f"<image{index}>"
        assignments = _items(item.get("assignments"))
        if assignments:
            roles = []
            for assignment in assignments:
                target_id = str(assignment.get("applies_to") or "")
                name = _text(elements.get(target_id, {}).get("display_name") or target_id)
                role = _text(assignment.get("prompt_role")).replace("_", " ")
                phrase = " ".join(part for part in (role, f"for {name}" if name else "") if part)
                preserved_assignment = list(dict.fromkeys(
                    _text(value) for value in assignment.get("preserve") or [] if _text(value)
                ))
                if preserved_assignment:
                    phrase += f", preserving {', '.join(preserved_assignment)}"
                changed_assignment = list(dict.fromkeys(
                    _text(value) for value in assignment.get("change") or [] if _text(value)
                ))
                if changed_assignment:
                    phrase += f", changing only {', '.join(changed_assignment)}"
                ignored_assignment = list(dict.fromkeys(
                    _text(value) for value in assignment.get("ignore") or [] if _text(value)
                ))
                if ignored_assignment:
                    phrase += f", ignoring {', '.join(ignored_assignment)}"
                assignment_note = _text(assignment.get("notes"))
                if assignment_note:
                    phrase += f", note: {assignment_note}"
                roles.append(phrase)
            roles = list(dict.fromkeys(role for role in roles if role))
        else:
            target_id = str(item.get("applies_to") or "")
            name = _text(elements.get(target_id, {}).get("display_name") or target_id or item.get("label"))
            role = _text(item.get("role")).replace("_", " ") or "visual reference"
            roles = [" ".join(part for part in (role, f"for {name}" if name else "") if part)]

        detail = f"{tag} supplies {' and '.join(roles)}"
        if item.get("role") == "layout_reference":
            detail = (f"{tag} is the measured camera-view layout guide; preserve its framing, subject count, "
                      "projected positions, relative heights, and overlaps while replacing the gray pawns "
                      "with their assigned scene elements")
        elif measured_layout and any(
            elements.get(target_id, {}).get("resource_type") == "Scene-Only"
            for target_id in ([str(assignment.get("applies_to") or "") for assignment in assignments]
                              or [str(item.get("applies_to") or "")])
        ):
            group_ids = [target_id for target_id in (
                [str(assignment.get("applies_to") or "") for assignment in assignments]
                or [str(item.get("applies_to") or "")]
            ) if elements.get(target_id, {}).get("resource_type") == "Scene-Only"]
            group_names = [
                _text(elements.get(target_id, {}).get("display_name")) for target_id in group_ids
            ]
            detail = f"{tag} is a member identity, costume, and action reference for {', '.join(name for name in group_names if name)}; {group_reference_contract()}"
        assigned_preserve = {
            _text(value).casefold()
            for assignment in assignments
            for value in assignment.get("preserve") or []
            if _text(value)
        }
        preserved = list(dict.fromkeys(
            _text(value) for value in item.get("preserve") or []
            if _text(value) and _text(value).casefold() not in assigned_preserve
        ))
        if preserved:
            detail += f"; retain {', '.join(preserved)}"
        changes = list(dict.fromkeys(_text(value) for value in item.get("change") or [] if _text(value)))
        if changes:
            detail += f"; change only {', '.join(changes)}"
        ignored = list(dict.fromkeys(_text(value) for value in item.get("ignore") or [] if _text(value)))
        assigned_ignore = {
            _text(value).casefold()
            for assignment in assignments
            for value in assignment.get("ignore") or []
            if _text(value)
        }
        ignored = [value for value in ignored if value.casefold() not in assigned_ignore]
        if ignored:
            detail += f"; disregard {', '.join(ignored)}"
        note = _text(item.get("notes"))
        if note:
            detail += f"; reference note: {note}"
        lines.append(_sentence(detail))
    return lines


def _interaction_map(ir: dict[str, Any], elements: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    by_subject: dict[str, list[str]] = {}
    for interaction in _items(ir.get("interactions")):
        subject_id = str(interaction.get("subject_element_id") or "")
        target_id = str(interaction.get("target_element_id") or "")
        relationship = _text(interaction.get("relationship") or interaction.get("type"))
        subject_name = _text(elements.get(subject_id, {}).get("display_name"))
        target_name = _text(elements.get(target_id, {}).get("display_name"))
        if not subject_name or not target_name or not relationship:
            continue
        clause = f"{relationship} {target_name}"
        note = _text(interaction.get("note"))
        if note:
            participant_names = (subject_name, target_name)
            note_parts = [
                part for part in _note_sentences(note)
                if not any(name.casefold() in part.casefold() for name in participant_names)
            ]
            if note_parts:
                clause += ", " + ", ".join(note_parts)
        by_subject.setdefault(subject_id, []).append(clause)
    return by_subject


def _appearance_parts(value: Any, name: str = "") -> tuple[list[str], bool]:
    clauses = [_text(part) for part in re.split(r"[.;]", str(value or "")) if _text(part)]
    def is_action_only(part: str) -> bool:
        candidate = part
        if name:
            candidate = re.sub(rf"^{re.escape(name)}\b[:,]?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"^(?:(?:he|she|they|the subject)\s+)?(?:is\s+)?", "", candidate, flags=re.IGNORECASE)
        return bool(_POSE_OR_ACTION.search(candidate) and not _APPEARANCE_WORD.search(candidate))

    kept = [part for part in clauses if not is_action_only(part)]
    return kept, len(kept) != len(clauses)


def _subject_description(
    element: dict[str, Any], placement: dict[str, Any], interactions: list[str], elements: dict[str, dict[str, Any]],
    ir: dict[str, Any] | None = None,
) -> str:
    name = _text(element.get("display_name")) or "The subject"
    projection = placement.get("layout_projection") if isinstance(placement.get("layout_projection"), dict) else None
    projection = projection or projection_for_element(ir or {"placements": [placement]}, str(element.get("id") or ""))
    if projection:
        identity_source = element.get("resolved_source_sections") or {}
        identity = _text(identity_source.get("identity_preservation_core") or element.get("fallback_visual_description"))
        costume = _text(identity_source.get("identity_preservation_costume"))
        pose = placement.get("pose") if isinstance(placement.get("pose"), dict) else {}
        gaze_id = str(pose.get("gaze_target_element_id") or "")
        if gaze_id and not gaze_is_consistent(ir or {}, projection, gaze_id):
            gaze_id = ""
        gaze = _text(elements.get(gaze_id, {}).get("display_name") or gaze_id)
        expression = _text(pose.get("expression") or placement.get("expression"))
        pose_summary = suppress_spatial_clauses(pose.get("summary"))
        override = suppress_spatial_clauses(element.get("element_visual_override"))
        placement_notes = suppress_spatial_clauses(placement.get("placement_notes"))
        motion = placement.get("motion") if isinstance(placement.get("motion"), dict) else {}
        cue = suppress_spatial_clauses(motion.get("cue")) if _text(motion.get("state")).casefold() == "moving" else ""
        pose_summary = pose_summary.rstrip(" .!?")
        override = override.rstrip(" .!?")
        clauses = [f"{name} appears once", identity, costume,
                   projected_subject_text(projection, display_name=name),
                   pose_summary, override,
                   (f"with an {expression} expression" if expression[:1].casefold() in "aeiou" else f"with a {expression} expression") if expression else "",
                   f"looking toward {gaze}" if gaze else "", placement_notes, cue]
        clauses.extend(suppress_spatial_clauses(value) for value in interactions)
        return _sentence(", ".join(item for item in clauses if item))
    source = element.get("resolved_source_sections") or {}
    source = source if isinstance(source, dict) else {}
    identity = _text(
        source.get("identity_anchors")
        or source.get("identity_preservation_core")
        or element.get("fallback_visual_description")
    )
    costume = _text(source.get("costume_anchors") or source.get("identity_preservation_costume"))
    appearance_parts, _ = _appearance_parts(element.get("element_visual_override"), name)
    pose = placement.get("pose") or {}
    pose = pose if isinstance(pose, dict) else {}
    position = _text(placement.get("position_within_cell"))
    depth = _text(placement.get("depth"))
    location = " ".join(part for part in (position, depth) if part)
    world_position = _text(placement.get("world_position"))
    position_key = position.casefold()
    claimed_sides = {
        side for side, words in _SPATIAL_WORDS.items()
        if any(re.search(rf"\b{re.escape(word)}\b", world_position.casefold()) for word in words)
    }
    if position_key in _SPATIAL_WORDS and claimed_sides and position_key not in claimed_sides:
        world_position = ""
    placement_note = _text(placement.get("placement_notes"))
    if placement_note and (
        _ARRIVAL_LANGUAGE.search(placement_note)
        or any(re.search(rf"\b{re.escape(word)}\b", placement_note.casefold())
               for side, words in _SPATIAL_WORDS.items() if side != position_key for word in words)
        or any(_text(item.get("display_name")).casefold() in placement_note.casefold()
               for item in elements.values() if _text(item.get("display_name")))
    ):
        placement_note = ""
    motion = placement.get("motion") or {}
    motion = motion if isinstance(motion, dict) else {}

    identity_names_subject = bool(re.match(rf"^{re.escape(name)}\b", identity, re.IGNORECASE))
    parts = [identity] if identity_names_subject else [name]
    if identity and not identity_names_subject:
        parts.append(identity)
    if costume:
        parts.append(costume)
    parts.extend(appearance_parts)
    if location:
        parts.append(f"at {location}")
    if world_position:
        parts.append(world_position)
    if placement_note:
        parts.append(placement_note)
    summary = _text(pose.get("summary"))
    summary = re.sub(r"\bstanding at (?:the )?(?:left|center|centre|middle|right),?\s*", "", summary, flags=re.IGNORECASE)
    summary_repeats_interaction = any(
        re.search(r"\b" + re.escape(action) + r"\w*\b", summary, re.IGNORECASE)
        and any(re.search(r"\b" + re.escape(action) + r"\w*\b", clause, re.IGNORECASE) for clause in interactions)
        for action in ("point", "shove", "push", "hold", "carry", "embrace", "kiss", "attack", "offer", "hand", "shoulder")
    )
    if summary and not summary_repeats_interaction:
        parts.append(summary)
    parts.extend(interactions)
    expression = _text(pose.get("expression"))
    if expression:
        parts.append(f"with a {expression} expression")
    gaze_target = str(pose.get("gaze_target_element_id") or "")
    if gaze_target:
        parts.append(f"looking toward {_text(elements.get(gaze_target, {}).get('display_name') or gaze_target)}")
    cue = _text(motion.get("cue")) if _text(motion.get("state")).casefold() == "moving" else ""
    if _ARRIVAL_LANGUAGE.search(cue) or _NONVISUAL_MOTION.search(cue):
        cue = ""
    if cue:
        parts.append(cue)
    return _sentence(", ".join(part for part in parts if part))


def _note_sentences(value: Any) -> list[str]:
    return [
        _text(sentence)
        for sentence in re.split(r"(?<=[.!?])\s+|\s*;\s*", str(value or ""))
        if _text(sentence)
    ]


def _is_redundant_scene_note(sentence: str, names: list[str]) -> bool:
    folded = sentence.casefold()
    if any(name and name.casefold() in folded for name in names):
        return True
    count_words = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    return bool(
        re.search(r"\bfrom left to right\b|\bsingle captured moment\b", folded)
        or re.search(rf"\bexactly {count_words}\b.*\b(?:people|characters|males|females|figures|students)\b", folded)
    )


def _is_parent_placement_note(sentence: str) -> bool:
    folded = sentence.casefold()
    return bool(re.search(r"\b(?:will be placed|to be placed|outer placement|full scene|final scene)\b", folded))


def _dialogue_description(
    item: dict[str, Any], elements: dict[str, dict[str, Any]], placement: dict[str, Any] | None = None
) -> str:
    exact = str(item.get("text") or "")
    if not exact:
        return ""
    speaker_id = str(item.get("speaker_element_id") or "")
    speaker = _text(item.get("speaker_name") or elements.get(speaker_id, {}).get("display_name") or "the speaker")
    placement = placement or {}
    projection = placement.get("layout_projection") if isinstance(placement.get("layout_projection"), dict) else None
    location = projected_subject_text(projection, display_name=speaker) if projection else " ".join(part for part in (
        _text(placement.get("position_within_cell")), _text(placement.get("depth"))
    ) if part)
    panel_placement = _text(item.get("panel_placement"))
    if panel_placement in {"left", "right", "above", "below"}:
        direction = {"left": "to the left", "right": "to the right", "above": "above", "below": "below"}[panel_placement]
        detail = f'A clearly visible speech balloon shaped as a rounded-corner rectangle sits {direction} of {speaker}'
    else:
        detail = f'A clearly visible speech balloon shaped as a rounded-corner rectangle sits just above {speaker}'
    if panel_placement in {"left", "right", "above", "below"}:
        detail += " in this image's screen coordinates"
    if location:
        detail += f" at {location}"
    detail += f'; its border fits closely around the text with minimal padding; it contains only "{exact}"'
    max_lines = item.get("max_lines")
    if max_lines == 1:
        detail += " on one line"
    elif max_lines:
        detail += f" in no more than {max_lines} lines"
    pointer_target = _text(item.get("pointer_target"))
    if pointer_target.casefold() == "speaker mouth":
        detail += f"; its short tail ends at {speaker}'s visible mouth"
    elif pointer_target:
        detail += f"; its short tail points toward {pointer_target}"
    speaker_context = _text(item.get("speaker_context"))
    if speaker_context:
        detail += f"; {speaker} is visible within the referenced {speaker_context} image, so do not add a second copy of the speaker"
    target_id = str(item.get("target_element_id") or "")
    target_name = _text(item.get("target_name") or elements.get(target_id, {}).get("display_name"))
    if target_name:
        detail += f"; the line is addressed to {target_name}"
    target_context = _text(item.get("target_context"))
    if target_context:
        target_name = target_name or "the addressed listener"
        detail += f"; {target_name} is in the separate {target_context} image and is outside this render; retain the listener context without adding them here"
    detail += "; the balloon stays clear of faces and readable background text"
    notes = _text(item.get("notes"))
    if notes:
        detail += f"; {notes}"
    return _sentence(detail)


def analyze_qwen_scene_prompt(ir: dict[str, Any]) -> list[dict[str, str]]:
    """Return advisory, target-local warnings for authored text that can conflict."""
    elements = _elements(ir)
    placements = _placements(ir, elements)
    warnings: list[dict[str, str]] = []
    names = [_text(element.get("display_name")) for element, _ in placements]
    names = [name for name in names if name]
    placement_ids = [str(item.get("scene_element_id") or "") for item in _items(ir.get("placements"))]
    duplicate_ids = {element_id for element_id in placement_ids if element_id and placement_ids.count(element_id) > 1}
    for element_id in sorted(duplicate_ids):
        label = _text(elements.get(element_id, {}).get("display_name") or element_id)
        warnings.append({
            "field": f"placements[{label}]",
            "message": f"{label} has more than one placement; the Qwen prompt uses the first placement only.",
        })

    for element, placement in placements:
        element_id = str(element.get("id") or "")
        label = _text(element.get("display_name")) or element_id
        _, has_action_override = _appearance_parts(element.get("element_visual_override"), _text(element.get("display_name")))
        if has_action_override:
            warnings.append({
                "field": f"scene_elements[{label}].element_visual_override",
                "message": f"{label}: pose or action text is represented by placement and interaction fields; the prompt keeps only non-action appearance clauses.",
            })
        location = _text(placement.get("position_within_cell")).casefold()
        for field_name in ("world_position", "placement_notes"):
            value = _text(placement.get(field_name))
            if not value:
                continue
            if field_name == "placement_notes" and _ARRIVAL_LANGUAGE.search(value):
                warnings.append({
                    "field": f"placements[{label}].placement_notes",
                    "message": f"{label}: describes arriving or moving between locations; Qwen prompt uses the final pose and omits this note.",
                })
                continue
            claimed = {
                side for side, words in _SPATIAL_WORDS.items()
                if any(re.search(rf"\b{re.escape(word)}\b", value.casefold()) for word in words)
            }
            if location in _SPATIAL_WORDS and claimed and location not in claimed:
                warnings.append({
                    "field": f"placements[{label}].{field_name}",
                    "message": f"{label}: this note gives a different screen position than the placement field; the structured position takes precedence.",
                })
            elif field_name == "placement_notes" and any(name.casefold() in value.casefold() for name in names):
                warnings.append({
                    "field": f"placements[{label}].placement_notes",
                    "message": f"{label}: this note repeats a named subject; check that it adds a visual fact beyond the subject and interaction fields.",
                })
        motion = placement.get("motion") or {}
        cue = _text(motion.get("cue")) if isinstance(motion, dict) else ""
        if cue and (_ARRIVAL_LANGUAGE.search(cue) or _NONVISUAL_MOTION.search(cue)):
            warnings.append({
                "field": f"placements[{label}].motion.cue",
                "message": f"{label}: this cue describes narrative action rather than visible motion; use a pose or movement trace in the captured frame.",
            })

    composition = ir.get("composition") or {}
    if isinstance(composition, dict):
        notes = _text(composition.get("composition_notes"))
        if notes and any(_is_redundant_scene_note(item, names) for item in _note_sentences(notes)):
            warnings.append({
                "field": "composition.composition_notes",
                "message": "Composition notes repeat a named subject or structured cast/position detail; keep only framing constraints or details absent from subject fields.",
            })

    environment = ir.get("environment") or {}
    background_notes = _text(environment.get("general_background_notes")) if isinstance(environment, dict) else ""
    if any(_is_parent_placement_note(note) for note in _note_sentences(background_notes)):
        warnings.append({
            "field": "setup.environment.general_background_notes",
            "message": "This note describes placement in a parent scene; that staging belongs to the parent render target and is omitted here.",
        })

    for index, item in enumerate(_items(ir.get("image_inputs")), start=1):
        assignments = _items(item.get("assignments"))
        roles = [
            _text(assignment.get("prompt_role") or assignment.get("role")).casefold().replace("_", " ")
            for assignment in assignments
        ] or [_text(item.get("role")).casefold().replace("_", " ")]
        targets = [str(assignment.get("applies_to") or "") for assignment in assignments] or [str(item.get("applies_to") or "")]
        if not any(targets) or any(not role or role in {"reference", "visual reference"} for role in roles):
            warnings.append({
                "field": f"image_inputs[{index}]",
                "message": f"Image reference {index} has no clear subject assignment or visual role; identify what it contributes.",
            })
    return warnings


def compile_qwen_scene_prompt(ir: dict[str, Any]) -> str:
    """Describe one captured frame while retaining the render's image slots."""
    image_inputs = _items(ir.get("image_inputs"))
    if len(image_inputs) > 10:
        raise ValueError("Qwen Image 2.1 supports at most ten scene reference images.")
    elements = _elements(ir)
    visible = _placements(ir, elements)
    canvas = ir.get("canvas") or {}
    scene = ir.get("scene") or {}
    composition = ir.get("composition") or {}
    environment = ir.get("environment") or {}
    style = ir.get("style") or {}
    if has_measured_layout(ir):
        visible.sort(key=lambda pair: float(
            ((pair[1].get("layout_projection") or {}).get("screen") or {}).get("x", .5)
        ))
    elif isinstance(composition, dict) and isinstance(composition.get("left_to_right"), list):
        order = {str(element_id): index for index, element_id in enumerate(composition["left_to_right"])}
        visible.sort(key=lambda pair: order.get(str(pair[0].get("id") or ""), len(order)))
    else:
        screen_order = {"left": 0, "center": 1, "centre": 1, "right": 2}
        visible.sort(key=lambda pair: screen_order.get(_text(pair[1].get("position_within_cell")).casefold(), 3))
    orientation = _text(canvas.get("orientation")) or "landscape"
    medium = _text(style.get("canonical_art_style") or style.get("art_style")) or "fantasy illustration"

    if visible:
        visible_characters = [
            element for element, _ in visible
            if _text(element.get("element_type")).casefold() in _VISIBLE_TYPES
        ]
        count_text = ""
        if len(visible_characters) == len(visible) and visible_characters \
                and (ir.get("render_target") or {}).get("kind") in {"element_subscene", "subscene"}:
            count_text = (
                "Exactly one visible character appears once. " if len(visible_characters) == 1
                else f"Exactly {len(visible_characters)} visible characters appear once each. "
            )
        opening = f"A single {orientation} image in the style of {medium}. {count_text}"
    else:
        opening = f"A single {orientation} image in the style of {medium}. {_sentence(scene.get('story_beat'))} "

    parts = [opening.strip()]
    parts.extend(_reference_lines(image_inputs, elements, measured_layout=has_measured_layout(ir)))
    if has_measured_layout(ir):
        parts.append(layout_reference_contract())
    if ir.get("layout_projection"):
        if ir["layout_projection"].get("background"):
            parts.append("Preserve the already selected background crop and framing shown in the layout guide and background reference. Integrate the subjects into that setting without zooming, stretching, or reframing the background. The guide's gray subjects are placeholders to replace with their assigned scene elements.")
        parts.extend(frame_extension_contract(ir))
        ground = ir["layout_projection"].get("ground") or {}
        if ground.get("enabled"):
            parts.append(f"Render {ground.get('surface') or 'a ground surface matching the setting'} across the foreground, continuing naturally from the backdrop at the indicated ground join. Replace the flat preview ground color with the scene's actual surface and lighting.")
        camera = (ir.get("layout_projection") or {}).get("camera") or {}
        if camera:
            parts.append(
                f"Use a camera height of {camera.get('height')} above ground, "
                f"a {camera.get('pitch_degrees')} degree pitch and {camera.get('yaw_degrees')} degree yaw, "
                f"with a {camera.get('vertical_fov')} degree vertical field of view."
            )
    for value in (environment.get("location"), environment.get("general_background_notes")):
        if _text(value):
            for note in _note_sentences(suppress_spatial_clauses(value) if has_measured_layout(ir) else value):
                if not _is_parent_placement_note(note):
                    parts.append(_sentence(note))

    if isinstance(composition, dict):
        focal_point = _text(composition.get("focal_point"))
        if focal_point:
            parts.append(_sentence(f"The main visual focus is {focal_point}"))
        order = composition.get("left_to_right")
        if order and not isinstance(order, list) and not has_measured_layout(ir):
            parts.append(_sentence(f"The composition reads {order}"))

        names = [_text(element.get("display_name")) for element, _ in visible]
        names = [name for name in names if name]
        composition_notes = suppress_spatial_clauses(composition.get("composition_notes")) if has_measured_layout(ir) else composition.get("composition_notes")
        for note in _note_sentences(composition_notes):
            if not _is_redundant_scene_note(note, names):
                parts.append(_sentence(note))

    interactions = _interaction_map(ir, elements)
    dialogue = _items(ir.get("dialogue"))
    rendered_subjects: set[str] = set()
    for element, placement in visible:
        element_id = str(element.get("id") or "")
        rendered_subjects.add(element_id)
        clauses = interactions.get(element_id, [])
        description = _subject_description(element, placement, clauses, elements, ir)
        parts.append(description)
        for item in dialogue:
            if str(item.get("speaker_element_id") or "") == element_id:
                balloon = _dialogue_description(item, elements, placement)
                if balloon:
                    parts.append(balloon)
    for element_id, clauses in interactions.items():
        if element_id not in rendered_subjects:
            name = _text(elements.get(element_id, {}).get("display_name"))
            for clause in clauses:
                parts.append(_sentence(f"{name} {clause}"))

    custom = _text(ir.get("custom_interactions"))
    if custom:
        parts.append(_sentence(custom))
    for item in dialogue:
        speaker_id = str(item.get("speaker_element_id") or "")
        if speaker_id not in rendered_subjects:
            parts.append(_dialogue_description(item, elements))

    for prop in _items(ir.get("props")):
        description = prop.get("description") or prop.get("state")
        if _text(description):
            parts.append(_sentence(description))
    for label, value in (("Lighting", environment.get("lighting")), ("Atmosphere", environment.get("weather_or_atmosphere")),
                         ("Mood", environment.get("mood"))):
        if _text(value):
            parts.append(_sentence(f"{label}: {_text(value)}"))
    return " ".join(part for part in parts if part)
