"""Natural-language scene prompts for Qwen Image 2.1 local renders."""

from __future__ import annotations

import re
from typing import Any


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .;,")


def _sentence(value: Any) -> str:
    content = _text(value)
    return f"{content}." if content else ""


def compile_qwen_scene_prompt(ir: dict[str, Any]) -> str:
    """Describe the finished scene while retaining the manual render's image slots."""
    image_inputs = ir.get("image_inputs") or []
    if len(image_inputs) > 10:
        raise ValueError("Qwen Image 2.1 supports at most ten scene reference images.")
    elements = {str(item.get("id")): item for item in ir.get("elements") or [] if isinstance(item, dict)}
    canvas = ir.get("canvas") or {}
    scene = ir.get("scene") or {}
    composition = ir.get("composition") or {}
    environment = ir.get("environment") or {}
    style = ir.get("style") or {}
    orientation = _text(canvas.get("orientation")) or "landscape"
    medium = _text(style.get("canonical_art_style") or style.get("art_style")) or "fantasy illustration"
    subject_names = [
        _text(elements.get(str(item.get("scene_element_id")), {}).get("display_name"))
        for item in ir.get("placements") or []
    ]
    subject_names = list(dict.fromkeys(name for name in subject_names if name))
    subject = ", ".join(subject_names) if subject_names else _text(scene.get("story_beat")) or "the setting"
    parts = [f"Create a {orientation} scene depicting {subject}, in this visual style: {medium}."]
    if image_inputs:
        parts.append("Create a new scene using the supplied images as visual references; the composition and canvas come from this description.")
        for index, item in enumerate(image_inputs, start=1):
            target = str(item.get("applies_to") or "")
            name = _text(elements.get(target, {}).get("display_name") or target or item.get("label")) or f"reference {index}"
            role = _text(item.get("role")).replace("_", " ") or "visual reference"
            preserved = "; ".join(_text(value) for value in item.get("preserve") or [] if _text(value))
            detail = f"<image{index}> supplies the {role} for {name}"
            if preserved:
                detail += f", preserving {preserved}"
            parts.append(_sentence(detail))
            for label, values in (("Change", item.get("change")), ("Ignore", item.get("ignore"))):
                text = "; ".join(_text(value) for value in values or [] if _text(value))
                if text:
                    parts.append(_sentence(f"For <image{index}>, {label.lower()} {text}"))
            if _text(item.get("notes")):
                parts.append(_sentence(f"Reference note for <image{index}>: {item['notes']}"))
            for assignment in (item.get("assignments") or [])[1:]:
                if not isinstance(assignment, dict):
                    continue
                assignment_target = str(assignment.get("applies_to") or "")
                assignment_name = _text(elements.get(assignment_target, {}).get("display_name") or assignment_target or "the scene")
                assignment_role = _text(assignment.get("prompt_role")).replace("_", " ") or role
                parts.append(_sentence(f"For <image{index}>, use as {assignment_role} for {assignment_name}"))
                for label, values in (("Preserve", assignment.get("preserve")), ("Change", assignment.get("change")), ("Ignore", assignment.get("ignore"))):
                    text = "; ".join(_text(value) for value in values or [] if _text(value))
                    if text:
                        parts.append(_sentence(f"{label} for this <image{index}> assignment: {text}"))
                if _text(assignment.get("notes")):
                    parts.append(_sentence(f"Reference note for this <image{index}> assignment: {assignment['notes']}"))
    for value in (scene.get("story_beat"), environment.get("location"), environment.get("general_background_notes")):
        if _text(value):
            parts.append(_sentence(value))
    if _text(composition.get("focal_point")):
        parts.append(_sentence(f"The focal point is {_text(composition['focal_point'])}"))
    if _text(composition.get("left_to_right")):
        order = composition["left_to_right"]
        if isinstance(order, list):
            order = [elements.get(str(key), {}).get("display_name") or key for key in order]
            order = ", then ".join(_text(value) for value in order)
        parts.append(_sentence(f"From left to right: {order}"))
    if _text(composition.get("composition_notes")):
        parts.append(_sentence(composition["composition_notes"]))
    for interaction in ir.get("interactions") or []:
        if not isinstance(interaction, dict):
            continue
        subject = _text(elements.get(str(interaction.get("subject_element_id")), {}).get("display_name"))
        target = _text(elements.get(str(interaction.get("target_element_id")), {}).get("display_name"))
        relationship = _text(interaction.get("relationship") or interaction.get("type"))
        if subject and target and relationship:
            detail = f"{subject} {relationship} {target}"
            if _text(interaction.get("note")):
                detail += f", {_text(interaction['note'])}"
            parts.append(_sentence(detail))
    if _text(ir.get("custom_interactions")):
        parts.append(_sentence(ir["custom_interactions"]))
    for item in ir.get("dialogue") or []:
        speaker = elements.get(str(item.get("speaker_element_id")), {}).get("display_name") or "A character"
        exact = str(item.get("text") or "")
        if exact:
            parts.append(_sentence(f'Include a clearly visible speech panel for {speaker} reading exactly "{exact}"'))
            if item.get("max_lines"):
                parts.append(_sentence(f'The speech panel uses at most {item["max_lines"]} lines'))
            if _text(item.get("pointer_target")):
                parts.append(_sentence(f'The speech panel pointer aims at {item["pointer_target"]}'))
            if _text(item.get("notes")):
                parts.append(_sentence(item["notes"]))
    for placement in ir.get("placements") or []:
        element = elements.get(str(placement.get("scene_element_id")), {})
        name = _text(element.get("display_name"))
        if not name:
            continue
        source = element.get("resolved_source_sections") or {}
        identity = _text(source.get("identity_anchors") or source.get("identity_preservation_core")
                         or element.get("fallback_visual_description"))
        costume = _text(source.get("costume_anchors") or source.get("identity_preservation_costume"))
        appearance = _text(element.get("element_visual_override"))
        pose = placement.get("pose") or {}
        motion = placement.get("motion") or {}
        location = " ".join(filter(None, (_text(placement.get("position_within_cell")), _text(placement.get("depth")))))
        detail = [_sentence(f"{name} appears in the {location}" if location else name)]
        detail.extend(_sentence(value) for value in (identity, costume, appearance, pose.get("summary"),
                                                      placement.get("placement_notes")) if _text(value))
        if _text(pose.get("expression")):
            detail.append(_sentence(f"{name}'s expression is {_text(pose['expression'])}"))
        gaze = elements.get(str(pose.get("gaze_target_element_id")), {}).get("display_name")
        if gaze:
            detail.append(_sentence(f"{name} looks toward {gaze}"))
        if _text(motion.get("state")) == "moving":
            direction = _text(motion.get("direction_screen"))
            if direction:
                detail.append(_sentence(f"{name} moves {direction}"))
            if _text(motion.get("cue")):
                detail.append(_sentence(motion["cue"]))
        parts.append(" ".join(detail))
    for prop in ir.get("props") or []:
        parts.append(_sentence(prop.get("description") or prop.get("state")))
    for label, value in (("Lighting", environment.get("lighting")), ("Atmosphere", environment.get("weather_or_atmosphere")),
                         ("Mood", environment.get("mood"))):
        if _text(value):
            parts.append(_sentence(f"{label}: {_text(value)}"))
    return " ".join(part for part in parts if part)
