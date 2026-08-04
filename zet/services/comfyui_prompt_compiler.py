from __future__ import annotations

import re
from typing import Any

from zet.services.scene_render_compiler import (
    collect_primary_characters,
    get_element_display_name,
    local_render_brief,
    resolve_character_order,
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" ,.;")


def _dedupe_join(parts: list[str]) -> str:
    result = []
    seen = set()
    for part in parts:
        cleaned = _clean(part)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return ", ".join(result)


def _first_sentences(value: str, limit: int) -> str:
    parts = [
        part.strip(" ,.;")
        for part in re.split(r"[.;]\s+", value)
        if part.strip(" ,.;")
    ]
    return ". ".join(parts[:limit])


def append_prompt_globals(prompt: str, additions: str) -> str:
    parts = [_clean(prompt)]
    parts.extend(item for item in re.split(r"[,\n]+", additions) if _clean(item))
    return _dedupe_join(parts)


def _identity(element: dict[str, Any]) -> str:
    sections = element.get("resolved_source_sections")
    sections = sections if isinstance(sections, dict) else {}
    value = _clean(
        sections.get("identity_preservation_core")
        or element.get("local_render_visual_override")
        or element.get("fallback_visual_description")
        or element.get("element_visual_override")
    )
    for name in (
        element.get("display_name"),
        element.get("character"),
        element.get("aux_resource_id"),
        element.get("id"),
    ):
        if _clean(name):
            value = re.sub(rf"^\s*{re.escape(_clean(name))}(?:\s+\w+)?\s*[—:-]\s*", "", value, flags=re.I)
    return _clean(_first_sentences(value, 3))


def _costume(element: dict[str, Any]) -> str:
    sections = element.get("resolved_source_sections")
    sections = sections if isinstance(sections, dict) else {}
    value = _clean(sections.get("identity_preservation_costume"))
    value = re.sub(r"^\s*[^—:]{1,80}(?:Costume)?\s*[—:]\s*", "", value, flags=re.I)
    return _clean(_first_sentences(value, 2))


def _gaze(ir: dict[str, Any], element_id: str, placement: dict[str, Any]) -> str:
    pose = placement.get("pose") if isinstance(placement.get("pose"), dict) else {}
    target_id = _clean(pose.get("gaze_target_element_id") or placement.get("gaze_target_element_id"))
    if not target_id:
        for interaction in ir.get("interactions", []):
            relationship = _clean(interaction.get("relationship") or interaction.get("type")).casefold()
            if _clean(interaction.get("subject_element_id")) == element_id and relationship in {
                "looking at",
                "looks at",
                "gaze",
                "direct gaze",
            }:
                target_id = _clean(interaction.get("target_element_id"))
                break
    if not target_id:
        return ""
    elements = {
        _clean(item.get("id")): item
        for item in ir.get("elements", [])
        if isinstance(item, dict) and _clean(item.get("id"))
    }
    return f"looking toward {get_element_display_name(target_id, elements)}"


def _action(placement: dict[str, Any]) -> str:
    pose = placement.get("pose") if isinstance(placement.get("pose"), dict) else {}
    motion = placement.get("motion") if isinstance(placement.get("motion"), dict) else {}
    summary = _clean(pose.get("summary") or placement.get("pose"))
    direction = _clean(motion.get("direction_screen"))
    if _clean(motion.get("state")).casefold() == "moving":
        if "walk" in summary.casefold():
            return _dedupe_join([summary, direction])
        return _clean(f"moving {direction}")
    return summary


def _expression(placement: dict[str, Any]) -> str:
    pose = placement.get("pose") if isinstance(placement.get("pose"), dict) else {}
    value = _clean(pose.get("expression") or placement.get("expression"))
    if not value:
        return ""
    return value if "expression" in value.casefold() else f"{value.lower()} expression"


def _negative_prompt(ir: dict[str, Any], globals_text: str) -> str:
    brief = local_render_brief(ir)
    plain = brief.get("plain_txt2img") if isinstance(brief.get("plain_txt2img"), dict) else {}
    terms = [_clean(item) for item in str(plain.get("negative_prompt") or "").split(",")]
    terms.extend(_clean(item) for item in re.split(r"[,\n]+", globals_text))
    toward_camera = any(
        "toward camera" in _clean(
            (placement.get("motion") if isinstance(placement.get("motion"), dict) else {}).get("direction_screen")
        ).casefold()
        for placement in ir.get("placements", [])
    )
    contradictory = {"front-facing body", "looking at viewer"} if toward_camera else set()
    horizontal_slots = [
        _clean(placement.get("position_within_cell")).casefold()
        for placement in ir.get("placements", [])
        if _clean(placement.get("position_within_cell"))
    ]
    if len(horizontal_slots) != len(set(horizontal_slots)):
        contradictory.add("both characters on the same side")
    terms = [term for term in terms if term and term.casefold() not in contradictory]
    return _dedupe_join(terms)


def compile_scene_prompts(
    ir: dict[str, Any],
    *,
    positive_prompt_globals: str = "",
    negative_prompt_globals: str = "",
) -> dict[str, Any]:
    characters, _ = resolve_character_order(ir, collect_primary_characters(ir))
    canvas = ir.get("canvas") if isinstance(ir.get("canvas"), dict) else {}
    environment = ir.get("environment") if isinstance(ir.get("environment"), dict) else {}
    style = ir.get("style") if isinstance(ir.get("style"), dict) else {}
    global_prompt = _dedupe_join(
        [
            f"{_clean(canvas.get('orientation')) or 'landscape'} {_clean(canvas.get('aspect_ratio')) or '16:9'} scene",
            f"{len(characters)} separate primary characters" if characters else "environment scene",
            _clean(ir.get("scene", {}).get("story_beat")),
            _clean(environment.get("location")),
            _clean(environment.get("weather_or_atmosphere")),
            _clean(environment.get("lighting")),
            _clean(style.get("art_style")),
        ]
    )
    region_records = []
    for element, placement in characters:
        element_id = _clean(element.get("id"))
        name = _clean(element.get("display_name")) or element_id
        region_records.append(
            {
                "element_id": element_id,
                "prompt": _dedupe_join(
                    [
                        name,
                        _identity(element),
                        _costume(element),
                        f"{_clean(placement.get('position_within_cell')) or 'center'} {_clean(placement.get('depth')) or 'midground'}",
                        _action(placement),
                        _expression(placement),
                        _gaze(ir, element_id, placement),
                    ]
                ),
            }
        )
    return {
        "global": append_prompt_globals(global_prompt, positive_prompt_globals),
        "negative": _negative_prompt(ir, negative_prompt_globals),
        "regions": [record["prompt"] for record in region_records],
        "region_records": region_records,
    }
