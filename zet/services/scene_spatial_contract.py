"""Shared prompt wording for measured Scene Builder camera projections."""

from __future__ import annotations

import copy
import re
from typing import Any


_SPATIAL_LANGUAGE = re.compile(
    r"\b(?:screen[- ]?(?:left|right|center|centre)|left[- ]to[- ]right|"
    r"foreground|midground|background|distant background|"
    r"(?:left|right|center|centre|middle) (?:side|half|third|edge|column|row)|"
    r"(?:on|at|to) (?:the )?(?:far )?(?:left|right|center|centre|middle)\b|"
    r"\b(?:front|back) row\b|"
    r"\b(?:behind|ahead of|in front of)\b|"
    r"(?:nearer|farther|closer|nearest|farthest|closest)\b|"
    r"(?:face|faces|facing|oriented|turn|turns|turned|viewed|seen) toward the camera|"
    r"(?:front|rear|back)[- ](?:view|three[- ]quarter)|"
    r"(?:backs?|torsos?|hips?|feet|shoulders|knees) (?:face|point|remain|are oriented)|"
    r"(?:toward|towards|away from) (?:the )?(?:camera|viewer)\b)",
    re.IGNORECASE,
)
_ANATOMICAL_SIDE = re.compile(r"\b(?:left|right) (?:hand|arm|leg|foot|eye|ear|shoulder|knee)\b", re.IGNORECASE)


def has_measured_layout(ir: dict[str, Any]) -> bool:
    """Whether this target has measured projection facts to use for staging."""
    projection = ir.get("layout_projection")
    return bool(
        isinstance(projection, dict) and projection.get("subjects")
        or any(isinstance(item.get("layout_projection"), dict) for item in ir.get("placements") or [])
    )


def projection_for_element(ir: dict[str, Any], element_id: str) -> dict[str, Any] | None:
    """Find a subject's projected facts in its placement or target projection."""
    for placement in ir.get("placements") or []:
        if str(placement.get("scene_element_id") or "") == element_id:
            projection = placement.get("layout_projection")
            if isinstance(projection, dict):
                return projection
    for subject in (ir.get("layout_projection") or {}).get("subjects") or []:
        if str(subject.get("element_id") or "") == element_id:
            return subject
        for member in subject.get("members") or []:
            if str(member.get("element_id") or "") == element_id:
                return member
    return None


def _location_from_screen(screen: dict[str, Any]) -> str:
    feet = screen.get("feet") or {}
    x, y = float(feet.get("x", screen.get("x", .5))), float(feet.get("y", 1.0))
    width, height = float(screen.get("width") or 0), float(screen.get("height") or 0)
    center_x, center_y = float(screen.get("x", x)), float(screen.get("y", 1 - height / 2))
    return (
        f"feet anchored {x * 100:.1f}% from screen-left and {y * 100:.1f}% from screen-top; "
        f"visible bounds centered at ({center_x * 100:.1f}%, {center_y * 100:.1f}%), "
        f"{width * 100:.1f}% wide by {height * 100:.1f}% high"
    )


def projected_subject_text(projection: dict[str, Any], *, display_name: str = "") -> str:
    """Return authoritative placement, scale, and facing details for a subject."""
    name = display_name or "Subject"
    if projection.get("kind") == "group":
        members = projection.get("members") or []
        parts = [f"{name} contains exactly {len(members)} members in the measured group arrangement"]
        for member in members:
            member_name = str(member.get("display_name") or member.get("element_id") or "Group member")
            details = [f"{member_name}: {_location_from_screen(member.get('screen') or {})}"]
            if member.get("camera_facing"):
                details.append(f"body in a {member['camera_facing']} view")
            if member.get("head_facing"):
                details.append(f"head in a {member['head_facing']} view")
            if member.get("physical_height"):
                details.append(f"standing height {member['physical_height']}")
            parts.append(", ".join(details))
        return "; ".join(parts)

    parts = [_location_from_screen(projection.get("screen") or {})]
    for label, value in (("body", projection.get("camera_facing")), ("head", projection.get("head_facing"))):
        if value:
            parts.append(f"{label} in a {value} view")
    if projection.get("physical_height"):
        parts.append(f"standing height {projection['physical_height']}")
    if projection.get("occupied_height"):
        parts.append(f"staged occupied height {projection['occupied_height']}")
    if projection.get("depth_m") is not None:
        parts.append(f"camera distance approximately {float(projection['depth_m']) / .3048:.1f} ft")
    if "elevation_m" in projection:
        elevation = float(projection["elevation_m"])
        parts.append("feet contacting the ground surface" if abs(elevation) < .01
                     else f"base elevated {elevation / .3048:.1f} ft above ground")
    return ", ".join(parts)


def gaze_is_consistent(ir: dict[str, Any], source_projection: dict[str, Any], target_id: str) -> bool:
    """Only retain authored gaze when it agrees with measured screen geometry."""
    target = projection_for_element(ir, target_id)
    if not target:
        return False
    source_screen = source_projection.get("screen") or {}
    target_screen = target.get("screen") or {}
    source_x = float((source_screen.get("feet") or {}).get("x", source_screen.get("x", .5)))
    target_x = float((target_screen.get("feet") or {}).get("x", target_screen.get("x", .5)))
    facing = str(source_projection.get("head_facing") or "").casefold()
    delta = target_x - source_x
    if "left" in facing:
        return delta < -.02
    if "right" in facing:
        return delta > .02
    if any(word in facing for word in ("front", "camera", "forward")):
        return abs(delta) <= .12
    return True


def suppress_spatial_clauses(value: Any) -> str:
    """Drop camera-layout prose while keeping actions and anatomical sides."""
    text = str(value or "").strip()
    if not text:
        return ""
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        clauses = []
        for clause in re.split(r"\s*[,;]\s*", sentence):
            normalized = clause.strip()
            if not normalized:
                continue
            spatial = _SPATIAL_LANGUAGE.search(normalized)
            if spatial:
                anatomical = _ANATOMICAL_SIDE.search(normalized)
                if not anatomical or spatial.start() != anatomical.start():
                    continue
            clauses.append(normalized)
        if clauses:
            kept.append(", ".join(clauses))
    return " ".join(kept)


def layout_reference_contract() -> str:
    return (
        "Follow the measured camera-view layout as the sole authority for screen position, "
        "relative size, depth, body and head view, overlap, and ground contact. Replace guide "
        "pawns with their named subjects; do not reproduce guide labels, gray shapes, or guide colors. "
        "Keep assigned characters distinct and add no unassigned people."
    )


def group_reference_contract() -> str:
    return (
        "Use accepted group renders for member identity, costume, and assigned action. The parent measured projection "
        "controls each member's final screen placement, relative size, body and head view, and ground contact; ignore "
        "the group reference's camera angle, framing, background, and outer placement."
    )


def frame_extension_contract(ir: dict[str, Any]) -> list[str]:
    """Describe the selected backdrop crop, measured extension zones, and foreground join."""
    layout = ir.get("layout_projection") or {}
    background = layout.get("background") or {}
    lines = []
    placement = background.get("image_placement") or {}
    if placement:
        lines.append(
            "Keep the selected background crop positioned at "
            f"{float(placement.get('left', 0)) * 100:.1f}% from screen-left and "
            f"{float(placement.get('top', 0)) * 100:.1f}% from screen-top, occupying "
            f"{float(placement.get('width', 1)) * 100:.1f}% of frame width and "
            f"{float(placement.get('height', 1)) * 100:.1f}% of frame height; preserve its crop and framing."
        )
    regions = background.get("extension_regions") or []
    sides = set()
    for region in regions:
        x, y = float(region.get("left", 0)), float(region.get("top", 0))
        width, height = float(region.get("width", 0)), float(region.get("height", 0))
        if width < .5:
            sides.add("left" if x < .5 else "right")
        elif height > 0 and y < .5:
            sides.add("top")
        elif height > 0:
            sides.add("bottom")
    if sides:
        lines.append(
            "Extend its walls, sky, vegetation and terrain into the measured " + ", ".join(sorted(sides))
            + " extension areas beyond the reference image, preserving architecture scale and continuity; do not shift or stretch the selected crop, and omit guide colors and borders."
        )
    ground = layout.get("ground") or {}
    if ground.get("enabled") and ground.get("join_y") is not None:
        lines.append(
            f"Keep the background-to-foreground ground join at {float(ground['join_y']) * 100:.1f}% of frame height; "
            "continue the foreground surface from that join and preserve projected feet and contact shadows."
        )
    return lines


def fingerprint_payload(ir: dict[str, Any]) -> dict[str, Any]:
    """Remove only legacy spatial prose that measured-layout prompts suppress."""
    payload = copy.deepcopy(ir)
    if not has_measured_layout(payload):
        return payload
    composition = payload.get("composition")
    if isinstance(composition, dict):
        composition["left_to_right"] = []
        composition["composition_notes"] = suppress_spatial_clauses(composition.get("composition_notes"))
        composition["focal_point"] = suppress_spatial_clauses(composition.get("focal_point"))
    for placement in payload.get("placements") or []:
        if str(placement.get("position_within_cell") or "").casefold() != "none":
            placement["position_within_cell"] = ""
            placement["depth"] = ""
        placement["world_position"] = ""
        placement["placement_notes"] = suppress_spatial_clauses(placement.get("placement_notes"))
        pose = placement.get("pose")
        if isinstance(pose, dict):
            pose["summary"] = suppress_spatial_clauses(pose.get("summary"))
            projection = placement.get("layout_projection") or projection_for_element(
                payload, str(placement.get("scene_element_id") or ""))
            target_id = str(pose.get("gaze_target_element_id") or "")
            if target_id and projection and not gaze_is_consistent(payload, projection, target_id):
                pose["gaze_target_element_id"] = ""
        motion = placement.get("motion")
        if isinstance(motion, dict):
            motion["direction_screen"] = ""
            motion["cue"] = suppress_spatial_clauses(motion.get("cue"))
    for element in payload.get("elements") or []:
        element["element_visual_override"] = suppress_spatial_clauses(element.get("element_visual_override"))
    for interaction in payload.get("interactions") or []:
        interaction["note"] = suppress_spatial_clauses(interaction.get("note"))
    payload["custom_interactions"] = "\n".join(
        clause for line in str(payload.get("custom_interactions") or "").splitlines()
        if (clause := suppress_spatial_clauses(line))
    )
    environment = payload.get("environment")
    if isinstance(environment, dict):
        for key in ("location", "general_background_notes", "general_foreground_notes"):
            environment[key] = suppress_spatial_clauses(environment.get(key))
    scene = payload.get("scene")
    if isinstance(scene, dict):
        scene["story_beat"] = suppress_spatial_clauses(scene.get("story_beat"))
    return payload
