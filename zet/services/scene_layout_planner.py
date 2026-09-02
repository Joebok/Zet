from __future__ import annotations

from typing import Any

from zet.services.scene_render_compiler import (
    collect_primary_characters,
    get_element_display_name,
    resolve_character_order,
)


_HORIZONTAL_ANCHORS = {
    "far_left": 0.12,
    "left": 0.23,
    "center_left": 0.37,
    "center": 0.50,
    "center_right": 0.63,
    "right": 0.77,
    "far_right": 0.88,
}
_DEPTH_GEOMETRY = {
    "foreground": (0.18, 0.78, 0.30, 1.12),
    "midground": (0.27, 0.64, 0.27, 1.08),
    "background": (0.35, 0.50, 0.23, 0.92),
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _even8(value: float) -> int:
    return max(8, int(round(value / 8.0)) * 8)


def _focal_ids(ir: dict[str, Any]) -> set[str]:
    focal = _clean(ir.get("composition", {}).get("focal_point")).lower()
    if not focal:
        return set()
    result = set()
    elements = {
        _clean(item.get("id")): item
        for item in ir.get("elements", [])
        if isinstance(item, dict) and _clean(item.get("id"))
    }
    for element_id, element in elements.items():
        display_name = get_element_display_name(element_id, elements).lower()
        if focal in {element_id.lower(), display_name} or element_id.lower() in focal or display_name in focal:
            result.add(element_id)
    return result


def _slot(placement: dict[str, Any], index: int, count: int) -> str:
    value = _clean(placement.get("position_within_cell")).lower().replace("-", "_").replace(" ", "_")
    if value in _HORIZONTAL_ANCHORS:
        return value
    if count == 1:
        return "center"
    return f"ordered_{index}"


def _depth(ir: dict[str, Any], element_id: str, placement: dict[str, Any]) -> str:
    explicit = _clean(placement.get("depth")).lower()
    if explicit:
        return explicit
    lanes = ir.get("depth_lanes") if isinstance(ir.get("depth_lanes"), dict) else {}
    for lane in ("foreground", "midground", "background"):
        if element_id in [str(value) for value in lanes.get(lane, [])]:
            return lane
    return "midground"


def _pixel_box(box: dict[str, Any], width: int, height: int) -> dict[str, int]:
    x = _even8(float(box["x"]) * width)
    y = _even8(float(box["y"]) * height)
    region_width = min(width - x, _even8(float(box["w"]) * width))
    region_height = min(height - y, _even8(float(box["h"]) * height))
    return {
        "x": max(0, x),
        "y": max(0, y),
        "width": max(8, region_width),
        "height": max(8, region_height),
    }


def plan_scene_layout(ir: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    """Derive deterministic normalized and pixel layout boxes from scene IR."""
    characters, _ = resolve_character_order(ir, collect_primary_characters(ir))
    focal_ids = _focal_ids(ir)
    count = len(characters)
    slots = [_slot(placement, index, count) for index, (_element, placement) in enumerate(characters)]
    slot_members: dict[str, list[int]] = {}
    for index, slot in enumerate(slots):
        slot_members.setdefault(slot, []).append(index)

    regions: list[dict[str, Any]] = []
    for index, (element, placement) in enumerate(characters):
        element_id = _clean(element.get("id"))
        depth = _depth(ir, element_id, placement)
        is_focal = element_id in focal_ids
        if count <= 1:
            x, y, box_width, box_height = 0.06, 0.04, 0.88, 0.92
            strength = 1.14 if is_focal else 1.10
        elif count == 2:
            x = 0.01 if index == 0 else 0.47
            y, box_height, box_width, strength = 0.08, 0.88, 0.52, 1.12
        else:
            y, box_height, box_width, strength = _DEPTH_GEOMETRY.get(
                depth, _DEPTH_GEOMETRY["midground"]
            )
            slot = slots[index]
            if slot.startswith("ordered_"):
                center = 0.10 + index * (0.80 / max(1, count - 1))
            else:
                center = _HORIZONTAL_ANCHORS[slot]
                members = slot_members[slot]
                member_index = members.index(index)
                center += (member_index - (len(members) - 1) / 2.0) * min(0.11, 0.24 / len(members))
            scale = 1.10 if is_focal else 1.0
            box_width = min(0.38, box_width * scale)
            box_height = min(0.88, box_height * scale)
            y = max(0.03, y - (box_height - _DEPTH_GEOMETRY.get(depth, _DEPTH_GEOMETRY["midground"])[1]) / 2)
            x = max(0.0, min(1.0 - box_width, center - box_width / 2))
            strength = min(1.22, strength + (0.09 if is_focal else 0.0))

        normalized = {
            "x": round(x, 4),
            "y": round(y, 4),
            "w": round(min(box_width, 1.0 - x), 4),
            "h": round(min(box_height, 1.0 - y), 4),
        }
        region = {
            "element_id": element_id,
            "display_name": _clean(element.get("display_name")) or element_id,
            "role": "character",
            **normalized,
            "depth": depth,
            "horizontal_slot": slots[index],
            "order_index": index,
            "is_focal": is_focal,
            "conditioning_strength": round(strength, 2),
        }
        region["normalized"] = normalized
        region["pixels"] = _pixel_box(region, width, height)
        regions.append(region)

    pose_control = {
        "schema_version": 1,
        "kind": "scene_layout_control",
        "source": "Scene_Render_IR.json",
        "canvas": {"width": width, "height": height},
        "subjects": [
            {
                "element_id": region["element_id"],
                "box": region["normalized"],
                "depth": region["depth"],
                "order_index": region["order_index"],
            }
            for region in regions
        ],
        "consumed_by_workflow": False,
    }
    return {
        "schema_version": 1,
        "canvas": {"width": width, "height": height},
        "subject_order": [region["element_id"] for region in regions],
        "regions": regions,
        "pose_control": pose_control,
    }
