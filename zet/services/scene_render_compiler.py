from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
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


def _placement_line(ir: dict[str, Any], placement: dict[str, Any]) -> str:
    element = _element(ir, _clean(placement.get("scene_element_id")))
    pose = placement.get("pose", {}) if isinstance(placement.get("pose"), dict) else {}
    cell = placement.get("screen_cell", {}) if isinstance(placement.get("screen_cell"), dict) else {}
    parts = [
        _clean(element.get("display_name")) or _clean(placement.get("scene_element_id")),
        f"{_clean(element.get('element_type'))} {_clean(element.get('importance'))}".strip(),
        f"cell {cell.get('row', '')},{cell.get('column', '')} {cell.get('name', '')}".strip(),
        _clean(placement.get("semantic_screen_region")),
        _clean(placement.get("depth")),
        _clean(placement.get("frame_coverage")),
        _clean(pose.get("summary")),
        _clean(pose.get("body_view")),
        _clean(pose.get("head_view")),
        _clean(pose.get("gaze_description")) or _clean(pose.get("gaze_target_element_id")),
        _clean(pose.get("expression")),
        _clean(pose.get("left_arm_action")),
        _clean(pose.get("right_arm_action")),
        _clean(pose.get("left_hand_detail")),
        _clean(pose.get("right_hand_detail")),
    ]
    return "; ".join(part for part in parts if part)


def final_image_prompt_text(ir: dict[str, Any]) -> str:
    canvas = ir.get("canvas", {})
    camera = ir.get("camera", {})
    composition = ir.get("composition", {})
    environment = ir.get("environment", {})
    lines = [
        "# Render Task",
        "",
        f"Create one finished {_clean(canvas.get('orientation')) or 'landscape'} {_clean(canvas.get('aspect_ratio')) or '16:9'} scene image. Do not show the planning grid or split the image into comic panels.",
        "",
        "# Reference Image Assignment",
        "",
    ]
    if ir.get("references"):
        for ref in ir["references"]:
            lines.append(f"- {ref.get('tag')}: applies to {ref.get('applies_to_element_id')}; preserve {', '.join(ref.get('roles') or [])}; ignore {', '.join(ref.get('ignore') or [])}.")
    else:
        lines.append("- No reference image assignments.")
    lines.extend([
        "",
        "# Camera and Composition",
        "",
        f"- Camera: {_clean(camera.get('shot_type')) or 'wide shot'}, {_clean(camera.get('camera_height')) or 'eye-level'}, {_clean(camera.get('camera_angle')) or 'straight-on'}, {_clean(camera.get('lens_feel')) or 'normal'} lens feel.",
        f"- Primary focal point: {_clean(composition.get('primary_focal_point'))}.",
        f"- Left-to-right order: {' -> '.join(_lines(composition.get('left_to_right_order')))}.",
        "",
        "# Character and Monster Staging",
        "",
    ])
    staged = False
    for placement in ir.get("placements", []):
        element = _element(ir, _clean(placement.get("scene_element_id")))
        if _clean(element.get("element_type")) in {"Character", "Monster"}:
            staged = True
            lines.append(f"- {_placement_line(ir, placement)}.")
    if not staged:
        lines.append("- No character or monster staging specified.")
    lines.extend(["", "# Props and Interactions", ""])
    for prop in ir.get("props", []):
        lines.append(f"- {prop}.")
    for interaction in ir.get("interactions", []):
        lines.append(f"- {interaction}.")
    if not ir.get("props") and not ir.get("interactions"):
        lines.append("- Preserve structured prop and interaction facts from the scene JSON.")
    lines.extend([
        "",
        "# Environment and Depth",
        "",
        f"- Location: {_clean(environment.get('location'))}.",
        f"- Foreground: {_clean(environment.get('general_foreground_notes'))}.",
        f"- Background: {_clean(environment.get('general_background_notes'))}.",
        "",
        "# Lighting and Mood",
        "",
        f"- Lighting: {_clean(environment.get('lighting'))}.",
        f"- Mood: {_clean(environment.get('mood'))}.",
        f"- Atmosphere: {_clean(environment.get('weather_or_atmosphere'))}.",
        f"- Art style: {_clean(ir.get('style', {}).get('art_style'))}.",
    ])
    if ir.get("dialogue"):
        lines.extend(["", "# Dialogue Panel", ""])
        for item in ir["dialogue"]:
            style = next((s for s in ir.get("dialogue_styles", []) if s.get("id") == item.get("panel_style_id")), {})
            lines.append(f"- {item.get('speaker_element_id')}: render exactly \"{item.get('text')}\". {style.get('panel_prompt', '')} {style.get('pointer_prompt', '')} {style.get('lettering_prompt', '')}".strip())
            for rule in _lines(style.get("layout_rules")):
                lines.append(f"  - {rule}")
    lines.extend(["", "# Must Preserve", ""])
    continuity = ir.get("style", {}).get("visual_continuity", {})
    for rule in _lines(continuity.get("rules")):
        lines.append(f"- {rule}")
    for element in ir.get("elements", []):
        if _clean(element.get("importance")) == "primary":
            lines.append(f"- Preserve primary {element.get('element_type')} {element.get('display_name')}.")
        sections = element.get("resolved_source_sections", {}) if isinstance(element.get("resolved_source_sections"), dict) else {}
        for key in ("identity_preservation_core", "identity_preservation_costume"):
            if _clean(sections.get(key)):
                lines.append(f"- {element.get('display_name')}: {_clean(sections.get(key))}")
    lines.extend(["", "# Avoid", "", "No " + ", ".join(ir.get("avoid") or ["unrequested text", "malformed hands"]) + ".", "", "# Final Verification", ""])
    for item in ir.get("final_verification", []):
        lines.append(f"- {item}.")
    return "\n".join(lines).strip() + "\n"


def local_render_brief(ir: dict[str, Any]) -> dict[str, Any]:
    canvas = ir.get("canvas", {})
    positive = [
        _clean(ir.get("style", {}).get("art_style")),
        f"{_clean(canvas.get('orientation')) or 'landscape'} {_clean(canvas.get('aspect_ratio')) or '16:9'}",
        _clean(ir.get("camera", {}).get("shot_type")),
        _clean(ir.get("environment", {}).get("location")),
        _clean(ir.get("composition", {}).get("primary_focal_point")),
    ]
    positive.extend(_placement_line(ir, placement) for placement in ir.get("placements", []))
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
