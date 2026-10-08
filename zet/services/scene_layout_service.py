"""Imperial measurement resolution and scene-space projection/rendering."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from zet.models.scene_layout import SceneCamera, SceneLayout3D, ScenePawn
from zet.services.imperial_units import format_feet_inches, parse_feet_inches
from zet.services.pipeline_compiler_support import extract_template_field


HEIGHT_FIELDS = {
    "standing_barefoot_height": "Standing Barefoot Height",
    "eye_height": "Eye Height",
    "shoulder_width": "Shoulder Width",
    "body_depth": "Body Depth",
}
_DEFAULT_HEIGHTS = {"Character": 1.70, "Person": 1.70, "Prop": 0.75, "Backdrop": 5.0}
GROUND_COLOR = (185, 176, 160)


class SceneLayoutError(ValueError):
    """Report invalid 3D scene geometry or character measurements."""


class SceneLayoutService:
    """Normalize, project, and render the camera view of a Scene Builder layout."""

    def __init__(self, path_service):
        self.path_service = path_service

    @staticmethod
    def output_size(aspect_ratio: str = "16:9", pixel_budget: int = 1_048_576) -> tuple[int, int]:
        try:
            width_ratio, height_ratio = (float(part.strip()) for part in aspect_ratio.split(":", 1))
            if width_ratio <= 0 or height_ratio <= 0:
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            width_ratio, height_ratio = 16.0, 9.0
        budget = min(max(4096, int(pixel_budget)), 16_777_216)
        width = max(32, round(math.sqrt(budget * width_ratio / height_ratio) / 32) * 32)
        height = max(32, round(math.sqrt(budget * height_ratio / width_ratio) / 32) * 32)
        if width > 4096 or height > 4096:
            scale = min(4096 / width, 4096 / height)
            width = max(32, round(width * scale / 32) * 32)
            height = max(32, round(height * scale / 32) * 32)
        return width, height

    def draft_from_scene(self, scene: dict) -> dict:
        placements = {str(item.get("scene_element_id") or ""): item for item in scene.get("placements") or []}
        raw = {"version": 1, "active_camera_id": "main", "cameras": [SceneCamera().__dict__],
               "pawns": [], "migration_review_required": bool(placements)}
        raw["legacy_placements"] = [
            {"element_id": key, "position": value.get("position_within_cell"), "depth": value.get("depth")}
            for key, value in placements.items()
        ]
        return self.normalize(raw, scene.get("scene_elements") or [], scene=scene)

    def measurements(self, element: dict[str, Any]) -> dict[str, float | None]:
        element_type = str(element.get("element_type") or "Character")
        result: dict[str, float | None] = {key: None for key in HEIGHT_FIELDS}
        if element_type in {"Character", "Person"}:
            character = str(element.get("character") or "").strip()
            phase = str(element.get("phase") or "").strip()
            if character and phase:
                if any(part in {".", ".."} or "/" in part or "\\" in part for part in (character, phase)):
                    raise SceneLayoutError("Character and phase must be valid library names.")
                template = self.path_service.character_template_path(character, phase)
                if template.is_file():
                    for key, label in HEIGHT_FIELDS.items():
                        raw = extract_template_field(template, [label])
                        if raw and raw.casefold() not in {"optional", "n/a", "none"}:
                            try:
                                result[key] = parse_feet_inches(raw)
                            except ValueError as exc:
                                raise SceneLayoutError(f"{element.get('display_name') or character}: invalid {label}: {exc}") from exc
        return result

    @staticmethod
    def _point(value: Any, label: str) -> tuple[float, float, float]:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise SceneLayoutError(f"{label} must contain three coordinates.")
        point = tuple(float(item) for item in value)
        if not all(math.isfinite(item) and abs(item) <= 10000 for item in point):
            raise SceneLayoutError(f"{label} must contain finite coordinates within 10,000 meters.")
        return point

    def normalize(self, data: dict, elements: list[dict], *, scene: dict | None = None) -> dict:
        if not isinstance(data, dict) or data.get("version") not in {1, 2, 3}:
            raise SceneLayoutError("3D layout version must be 1, 2, or 3.")
        element_map = {str(item.get("id") or ""): item for item in elements if item.get("id")}
        backdrop_ids = {key for key, item in element_map.items() if item.get("element_type") == "Backdrop"}
        notices = list(data.get("migration_notices") or [])
        incoming = {str(item.get("element_id") or ""): item for item in data.get("pawns") or [] if isinstance(item, dict)}
        if len(incoming) != len([item for item in data.get("pawns") or [] if isinstance(item, dict)]):
            raise SceneLayoutError("Each scene element may have only one pawn.")
        pawns = []
        for index, (element_id, element) in enumerate(element_map.items()):
            if element_id in backdrop_ids:
                continue
            prior = incoming.get(element_id, {})
            measurements = self.measurements(element)
            overrides = prior.get("measurement_overrides") if isinstance(prior.get("measurement_overrides"), dict) else {}
            measured_height = measurements["standing_barefoot_height"]
            override = overrides.get("height")
            if override:
                try:
                    measured_height = parse_feet_inches(str(override))
                except ValueError as exc:
                    raise SceneLayoutError(f"{element.get('display_name') or element_id}: invalid height override: {exc}") from exc
            element_type = str(element.get("element_type") or "Character")
            provisional = measured_height is None and element_type in {"Character", "Person"}
            height = measured_height if measured_height is not None else _DEFAULT_HEIGHTS.get(element_type, 1.0)
            legacy = next((item for item in data.get("legacy_placements", []) if item.get("element_id") == element_id), {})
            if "position" in prior:
                position = self._point(prior["position"], f"{element_id} position")
            elif legacy:
                x = {"left": -1.5, "right": 1.5}.get(str(legacy.get("position") or "").casefold(), 0.0)
                z = {"foreground": 0.0, "midground": -3.0, "background": -6.0, "distant background": -10.0}.get(str(legacy.get("depth") or "midground"), -3.0)
                position = (x, 0.0, z)
            else:
                position = ((index - (len(element_map) - 1) / 2) * 1.6, 0.0, 0.0)
            dimensions = prior.get("dimensions")
            occupied_override = overrides.get("occupied_height")
            if occupied_override:
                try:
                    occupied_height = parse_feet_inches(str(occupied_override))
                except ValueError as exc:
                    raise SceneLayoutError(f"{element.get('display_name') or element_id}: invalid occupied-height override: {exc}") from exc
            elif element_type not in {"Character", "Person"} and isinstance(dimensions, dict) and "height" in dimensions:
                occupied_height = float(dimensions["height"])
            else:
                occupied_height = height
            if isinstance(dimensions, dict):
                width = float(dimensions.get("width", max(0.3, (measurements["shoulder_width"] or height * 0.24))))
                depth = float(dimensions.get("depth", max(0.25, (measurements["body_depth"] or height * 0.16))))
            else:
                width = max(0.3, float(measurements["shoulder_width"] or height * 0.24))
                depth = max(0.25, float(measurements["body_depth"] or height * 0.16))
            if any(not math.isfinite(value) or value <= 0 or value > 100 for value in (width, depth, height, occupied_height)):
                raise SceneLayoutError(f"{element_id} dimensions must be positive and no greater than 100 meters.")
            pawns.append({
                "element_id": element_id, "position": list(position),
                "dimensions": {"width": width, "height": occupied_height, "depth": depth},
                "stature_m": height,
                "eye_height_m": measurements["eye_height"],
                "body_yaw": self._angle(prior.get("body_yaw", 180 if element_type in {"Character", "Person"} else 0), f"{element_id} body yaw"),
                "head_yaw": self._angle(prior.get("head_yaw", 0), f"{element_id} head yaw"),
                "head_pitch": self._angle(prior.get("head_pitch", 0), f"{element_id} head pitch"),
                "look_at": "" if prior.get("look_at") in backdrop_ids else str(prior.get("look_at") or ""), "provisional_height": bool(provisional),
                "measurement_overrides": copy.deepcopy(overrides),
                "measurement_source": "scene override" if overrides.get("height") else "character template" if measured_height else "provisional",
            })
            if prior.get("look_at") in backdrop_ids:
                notices.append(f"{element.get('display_name') or element_id}: kept the existing gaze angles as manual facing after converting the backdrop.")
        raw_cameras = data.get("cameras") or []
        if not raw_cameras:
            raw_cameras = [SceneCamera().__dict__]
        cameras = []
        seen = set()
        for raw in raw_cameras:
            if not isinstance(raw, dict):
                continue
            camera_id = str(raw.get("id") or "main")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", camera_id) or camera_id in seen:
                raise SceneLayoutError("Camera IDs must be unique letters, numbers, underscores, or hyphens.")
            seen.add(camera_id)
            fov = float(raw.get("vertical_fov", 50))
            if not math.isfinite(fov) or not 5 <= fov <= 120:
                raise SceneLayoutError(f"Camera {camera_id} vertical field of view must be between 5 and 120 degrees.")
            cameras.append({"id": camera_id, "name": str(raw.get("name") or camera_id),
                            "position": list(self._point(raw.get("position", [0, 1.68, 8]), f"{camera_id} camera position")),
                            "target": list(self._point(raw.get("target", [0, 0.99, 0]), f"{camera_id} camera target")),
                            "vertical_fov": fov,
                            "background_framing": self.normalize_framing(raw.get("background_framing") or {})})
            ground_distance = raw.get("ground_distance_m")
            if ground_distance is None:
                ground_distance = self.default_ground_distance(cameras[-1], pawns)
            ground_distance = float(ground_distance)
            if not math.isfinite(ground_distance) or not 1 <= ground_distance <= 30000:
                raise SceneLayoutError("Ground join distance must be between 1 and 30,000 meters.")
            cameras[-1]["ground_distance_m"] = ground_distance
        active = str(data.get("active_camera_id") or "main")
        if not cameras or active not in seen:
            raise SceneLayoutError("The active 3D camera must reference a saved camera.")
        background = copy.deepcopy(data.get("background"))
        if "background" not in data:
            active_backgrounds = [item for item in (scene or {}).get("subscenes") or []
                                  if item.get("enabled") and item.get("kind") == "background"]
            if len(active_backgrounds) == 1:
                background = {"kind": "subscene", "target_id": active_backgrounds[0]["id"]}
            elif len(backdrop_ids) == 1:
                background = {"kind": "element", "element_id": next(iter(backdrop_ids))}
        if background is not None:
            if not isinstance(background, dict) or background.get("kind") not in {"element", "subscene"}:
                raise SceneLayoutError("Background source must be a backdrop element or background subscene.")
            key = "element_id" if background["kind"] == "element" else "target_id"
            if not isinstance(background.get(key), str) or not background[key]:
                raise SceneLayoutError("Background source must identify its element or subscene.")
            background = {"kind": background["kind"], key: background[key],
                          **({"reference_tag": str(background["reference_tag"])} if background.get("reference_tag") else {})}
        ground = data.get("ground", {})
        if not isinstance(ground, dict) or not isinstance(ground.get("enabled", True), bool):
            raise SceneLayoutError("Ground must contain an enabled flag and surface description.")
        surface = ground.get("surface", "Ground surface matching the setting")
        if not isinstance(surface, str) or len(surface) > 1000:
            raise SceneLayoutError("Ground surface must be a description of at most 1,000 characters.")
        return {"version": 3, "active_camera_id": active, "pawns": pawns, "cameras": cameras,
                "ground": {"enabled": ground.get("enabled", True), "surface": surface.strip() or "Ground surface matching the setting"},
                "background": background, "migration_notices": list(dict.fromkeys(notices)),
                "migration_review_required": bool(data.get("migration_review_required", False))}

    @staticmethod
    def _rotate_xz(point: list[float] | tuple[float, ...], yaw: float) -> list[float]:
        angle = math.radians(yaw)
        cosine, sine = math.cos(angle), math.sin(angle)
        x, y, z = point
        return [cosine * x + sine * z, y, -sine * x + cosine * z]

    @staticmethod
    def _target_owner(data: dict, element: dict) -> str:
        owner = str(element.get("subscene_id") or "")
        return owner if owner and any(str(item.get("id") or "") == owner for item in data.get("subscenes") or []) else "main"

    def _target_elements(self, data: dict, target_id: str) -> list[dict]:
        definitions = {str(item.get("id") or ""): item for item in data.get("subscenes") or []}
        target = definitions.get(target_id) if target_id != "main" else None
        if target_id != "main" and target is None:
            raise SceneLayoutError(f"Scene subscene not found: {target_id}")
        elements = [item for item in data.get("scene_elements") or []
                    if self._target_owner(data, item) == target_id and item.get("element_type") != "Backdrop"]
        for definition in data.get("subscenes") or []:
            if definition.get("kind") != "element" or not definition.get("enabled"):
                continue
            anchor = str(definition.get("anchor_element_id") or "")
            element = next((item for item in data.get("scene_elements") or [] if str(item.get("id") or "") == anchor), None)
            if element and self._target_owner(data, element) == target_id and all(item.get("id") != anchor for item in elements):
                elements.append(element)
        return elements

    @staticmethod
    def _frame_camera(pawns: list[dict]) -> dict:
        if not pawns:
            return SceneCamera().__dict__
        left = min(item["position"][0] - item["dimensions"]["width"] / 2 for item in pawns)
        right = max(item["position"][0] + item["dimensions"]["width"] / 2 for item in pawns)
        back = min(item["position"][2] - item["dimensions"]["depth"] / 2 for item in pawns)
        front = max(item["position"][2] + item["dimensions"]["depth"] / 2 for item in pawns)
        top = max(item["position"][1] + item["dimensions"]["height"] for item in pawns)
        center = [(left + right) / 2, top / 2, (back + front) / 2]
        extent = max(right - left, top, front - back, 1.0)
        distance = max(3.0, extent * 1.8)
        return {**SceneCamera().__dict__, "position": [center[0], center[1] + extent * .18, center[2] + distance],
                "target": center}

    def normalize_targets(self, data: dict, *, migrate: bool = True) -> dict:
        """Normalize a scene's versioned main and subscene layouts, migrating flat layouts in memory."""
        scene = copy.deepcopy(data)
        elements = scene.get("scene_elements") or []
        raw = scene.get("layout_3d") if isinstance(scene.get("layout_3d"), dict) else {"version": 3}
        definitions = {str(item.get("id") or ""): item for item in scene.get("subscenes") or [] if isinstance(item, dict)}
        nested = bool(raw.get("version") == 3 and isinstance(raw.get("targets"), dict))
        if nested:
            raw_targets = raw["targets"]
            main_raw = raw_targets.get("main") or {}
        else:
            raw_targets = {"main": raw}
            main_raw = raw or {"version": 3}
        flat = self.normalize(main_raw, elements, scene=scene)
        raw_by_target = {"main": main_raw}
        for target_id, definition in definitions.items():
            raw_by_target[target_id] = raw_targets.get(target_id) or (definition.get("layout_3d") if isinstance(definition.get("layout_3d"), dict) else {})
        # A pre-v3 layout stores all elements in world coordinates. Preserve those positions
        # while converting each member into its immediate parent's coordinate space.
        source = {item["element_id"]: item for item in flat["pawns"]}
        layouts: dict[str, dict] = {"main": flat}
        parents: dict[str, str] = {"main": ""}
        for target_id, definition in definitions.items():
            if definition.get("kind") == "element":
                anchor = next((item for item in elements if str(item.get("id") or "") == str(definition.get("anchor_element_id") or "")), None)
                parents[target_id] = self._target_owner(scene, anchor) if anchor else "main"
            else:
                parents[target_id] = "main"
        scoped_layouts = nested or any(bool(value) for key, value in raw_by_target.items() if key != "main")

        def raw_pawn(target_id: str, element_id: str) -> dict | None:
            return next((item for item in (raw_by_target.get(target_id) or {}).get("pawns") or []
                         if str(item.get("element_id") or "") == element_id), None)

        def workspace_transform(target_id: str, seen: set[str] | None = None) -> tuple[list[float], float]:
            if target_id == "main":
                return [0, 0, 0], 0.0
            seen = set(seen or ())
            if target_id in seen:
                raise SceneLayoutError(f"Element subscene cycle detected at {target_id}.")
            seen.add(target_id)
            definition = definitions[target_id]
            anchor_id = str(definition.get("anchor_element_id") or "")
            anchor = next((item for item in elements if str(item.get("id") or "") == anchor_id), None)
            parent_id = self._target_owner(scene, anchor) if anchor else "main"
            origin, parent_yaw = workspace_transform(parent_id, seen)
            pawn = raw_pawn(parent_id, anchor_id) or source.get(anchor_id)
            if not pawn:
                return origin, parent_yaw
            offset = self._rotate_xz(pawn["position"], parent_yaw)
            return [origin[i] + offset[i] for i in range(3)], parent_yaw + float(pawn.get("body_yaw", 0))

        # When an element changes render target, move its saved pose between the two
        # coordinate frames before normalizing either layout.
        if scoped_layouts:
            for element in elements:
                element_id = str(element.get("id") or "")
                current_owner = self._target_owner(scene, element)
                if raw_pawn(current_owner, element_id):
                    continue
                previous_owner = next((owner for owner in definitions if raw_pawn(owner, element_id)), "")
                if not previous_owner:
                    continue
                pawn = copy.deepcopy(raw_pawn(previous_owner, element_id))
                old_origin, old_yaw = workspace_transform(previous_owner)
                local_offset = self._rotate_xz(pawn["position"], old_yaw)
                world_position = [old_origin[i] + local_offset[i] for i in range(3)]
                world_yaw = float(pawn.get("body_yaw", 0)) + old_yaw
                new_origin, new_yaw = workspace_transform(current_owner)
                relative = [world_position[i] - new_origin[i] for i in range(3)]
                pawn["position"] = self._rotate_xz(relative, -new_yaw)
                pawn["body_yaw"] = (world_yaw - new_yaw) % 360
                if not raw_by_target.get(current_owner):
                    raw_by_target[current_owner] = {**SceneLayout3D().__dict__, "pawns": []}
                raw_by_target[current_owner].setdefault("pawns", []).append(pawn)
        flat = self.normalize(raw_by_target["main"], elements, scene=scene)
        source = {item["element_id"]: item for item in flat["pawns"]}
        layouts = {"main": flat}
        depths: dict[str, int] = {}
        def depth(target_id: str, seen: set[str] | None = None) -> int:
            if target_id in depths:
                return depths[target_id]
            seen = set(seen or ())
            if target_id in seen:
                raise SceneLayoutError(f"Element subscene cycle detected at {target_id}.")
            seen.add(target_id)
            parent = parents.get(target_id, "main")
            value = 1 + depth(parent, seen) if parent != "main" else 1
            if value > 3:
                raise SceneLayoutError("Element subscene nesting exceeds the maximum depth of 3.")
            depths[target_id] = value
            return value
        if migrate:
            for target_id in sorted(definitions, key=depth):
                definition = definitions[target_id]
                parent_id = parents[target_id]
                parent_raw = raw_by_target.get(parent_id) or {}
                existing_local = raw_by_target.get(target_id)
                if existing_local:
                    local_source = self.normalize(existing_local, self._target_elements(scene, target_id), scene=scene)
                    layouts[target_id] = local_source
                    continue
                local = self.normalize(parent_raw if nested else main_raw, elements, scene=scene)
                member_ids = {str(item.get("id") or "") for item in elements if self._target_owner(scene, item) == target_id}
                # Anchors of child groups stay in this workspace as movable group pivots.
                member_ids.update(str(child.get("anchor_element_id") or "") for child in definitions.values()
                                  if parents.get(str(child.get("id") or "")) == target_id and child.get("enabled"))
                selection_source = local["pawns"] if nested else list(source.values())
                selected = [copy.deepcopy(pawn) for pawn in selection_source if pawn["element_id"] in member_ids]
                if not nested and definition.get("kind") == "element":
                    anchor_id = str(definition.get("anchor_element_id") or "")
                    anchor = source.get(anchor_id)
                    anchor_position = anchor["position"] if anchor else [0, 0, 0]
                    anchor_yaw = anchor["body_yaw"] if anchor else 0
                    for pawn in selected:
                        pawn["position"] = self._rotate_xz([pawn["position"][axis] - anchor_position[axis] for axis in range(3)], -anchor_yaw)
                        pawn["body_yaw"] = (pawn["body_yaw"] - anchor_yaw) % 360
                        pawn["head_yaw"] = (pawn["head_yaw"] - anchor_yaw) % 360
                local["pawns"] = selected
                local["cameras"] = [self._frame_camera(selected)]
                local["active_camera_id"] = "main"
                local["background"] = None
                local["ground"] = {"enabled": False, "surface": "Ground surface matching the setting"}
                local["migration_review_required"] = True
                local["migration_notices"] = list(dict.fromkeys([*local.get("migration_notices", []),
                    f"The {definition.get('name') or target_id} layout was initialized from existing scene positions. Review it before rendering."]))
                layouts[target_id] = local
        # Keep only direct children and child anchors in each workspace; v3 targets own their geometry.
        for target_id in ["main", *definitions]:
            current = layouts.get(target_id, flat)
            allowed = {str(item.get("id") or "") for item in self._target_elements(scene, target_id)}
            if not nested and target_id != "main" and target_id in layouts:
                allowed = {pawn["element_id"] for pawn in layouts[target_id]["pawns"]}
            if target_id == "main":
                allowed = {str(item.get("id") or "") for item in elements if self._target_owner(scene, item) == "main"}
                allowed.update(str(child.get("anchor_element_id") or "") for child in definitions.values()
                               if parents.get(str(child.get("id") or "")) == "main" and child.get("enabled"))
            current["pawns"] = [pawn for pawn in current["pawns"] if pawn["element_id"] in allowed]
            layouts[target_id] = current
        if nested:
            for target_id in definitions:
                target_layout = raw_targets.get(target_id) or definitions[target_id].get("layout_3d")
                if target_layout:
                    layouts[target_id] = self.normalize(target_layout, self._target_elements(scene, target_id), scene=scene)
        return {"version": 3, "targets": layouts, "parents": parents}

    def compose_targets(self, data: dict, target_id: str = "main") -> dict:
        """Return a workspace layout and composed member geometry in scene coordinates."""
        normalized = self.normalize_targets(data)
        targets, parents = normalized["targets"], normalized["parents"]
        if target_id not in targets:
            raise SceneLayoutError(f"Scene subscene not found: {target_id}")
        elements = {str(item.get("id") or ""): item for item in data.get("scene_elements") or []}
        definitions = {str(item.get("id") or ""): item for item in data.get("subscenes") or []}
        flat: list[dict] = []
        groups: list[dict] = []
        def walk(owner: str, origin: list[float], yaw: float) -> None:
            layout = targets[owner]
            for pawn in layout["pawns"]:
                element = elements.get(pawn["element_id"], {})
                group = next((item for item in definitions.values() if item.get("kind") == "element" and item.get("enabled") and str(item.get("anchor_element_id") or "") == pawn["element_id"]), None)
                if group:
                    group_id = str(group["id"])
                    pos = self._rotate_xz(pawn["position"], yaw)
                    composed = {**copy.deepcopy(pawn), "position": [origin[i] + pos[i] for i in range(3)], "body_yaw": pawn["body_yaw"] + yaw}
                    groups.append({"target_id": group_id, "anchor_element_id": pawn["element_id"], "name": group.get("name") or group_id,
                                   "parent_id": owner, "position": composed["position"], "body_yaw": composed["body_yaw"]})
                    if group_id in targets:
                        walk(group_id, composed["position"], composed["body_yaw"])
                else:
                    pos = self._rotate_xz(pawn["position"], yaw)
                    flat.append({**copy.deepcopy(pawn), "element": element,
                                 "subscene_id": str(element.get("subscene_id") or ""),
                                 "position": [origin[i] + pos[i] for i in range(3)],
                                 "body_yaw": pawn["body_yaw"] + yaw})
        walk(target_id, [0, 0, 0], 0)
        return {"layout": copy.deepcopy(targets[target_id]), "pawns": flat, "groups": groups,
                "parents": parents, "targets": targets}

    @staticmethod
    def aggregate_group_projection(projection: dict, composition: dict, elements: list[dict]) -> dict:
        """Map composed member bounds back to their single parent-level anchor subject."""
        definitions = {str(item.get("target_id") or ""): item for item in composition.get("groups") or []}
        parents = composition.get("parents") or {}
        subjects = {str(item.get("element_id") or ""): item for item in projection.get("subjects") or []}
        element_map = {str(item.get("id") or ""): item for item in elements}
        hidden: set[str] = set()
        aggregate: list[dict] = []
        workspace_id = str(composition.get("groups_workspace") or "main")
        for target_id, group in definitions.items():
            if str(group.get("parent_id") or "main") != workspace_id:
                continue
            descendants = {target_id}
            changed = True
            while changed:
                changed = False
                for child_id, parent_id in parents.items():
                    if child_id not in descendants and parent_id in descendants:
                        descendants.add(child_id)
                        changed = True
            members = [pawn for pawn in composition.get("pawns") or []
                       if str(pawn.get("subscene_id") or "") in descendants and pawn["element_id"] in subjects]
            if not members:
                continue
            member_subjects = [subjects[pawn["element_id"]] for pawn in members]
            bounds = {
                key: min(item["pixel_bounds"][key] for item in member_subjects) if key in {"left", "top"}
                else max(item["pixel_bounds"][key] for item in member_subjects)
                for key in ("left", "top", "right", "bottom")
            }
            width, height = projection["width"], projection["height"]
            anchor_id = group["anchor_element_id"]
            member_facts = [{
                "element_id": pawn["element_id"],
                "display_name": element_map.get(pawn["element_id"], {}).get("display_name") or pawn["element_id"],
                "screen": copy.deepcopy(subjects[pawn["element_id"]]["screen"]),
                "physical_height": subjects[pawn["element_id"]].get("physical_height"),
                "occupied_height": subjects[pawn["element_id"]].get("occupied_height"),
                "depth_m": subjects[pawn["element_id"]].get("depth_m"),
                "camera_facing": subjects[pawn["element_id"]].get("camera_facing"),
                "head_facing": subjects[pawn["element_id"]].get("head_facing"),
                "body_yaw": pawn["body_yaw"],
            } for pawn in members]
            aggregate.append({
                "element_id": anchor_id, "kind": "group", "group_id": target_id, "members": member_facts,
                "pixel_bounds": bounds,
                "screen": {"x": (bounds["left"] + bounds["right"]) / (2 * width),
                           "y": (bounds["top"] + bounds["bottom"]) / (2 * height),
                           "width": (bounds["right"] - bounds["left"]) / width,
                           "height": (bounds["bottom"] - bounds["top"]) / height,
                           "feet": {"x": sum(subject["screen"].get("feet", {}).get("x", .5) for subject in member_subjects) / len(member_subjects)}},
                "depth_m": sum(subject.get("depth_m", 0) for subject in member_subjects) / len(member_subjects),
                "physical_height_m": None, "physical_height": "group", "occupied_height": "group bounds",
                "camera_facing": "group arrangement", "head_facing": "mixed", "elevation_m": 0,
                "in_frame": all(subject.get("in_frame", False) for subject in member_subjects),
                "group_dimensions": {"width_m": bounds["right"] - bounds["left"], "height_m": bounds["bottom"] - bounds["top"]},
            })
            hidden.update(pawn["element_id"] for pawn in members)
        projection["subjects"] = [item for item in projection.get("subjects") or [] if item["element_id"] not in hidden]
        projection["subjects"].extend(aggregate)
        projection["subjects"].sort(key=lambda item: item.get("depth_m", 0), reverse=True)
        return projection

    @staticmethod
    def empty_group_warnings(composition: dict, definitions: list[dict]) -> list[str]:
        parents = composition.get("parents") or {}
        warnings = []
        for group in composition.get("groups") or []:
            target_id = str(group.get("target_id") or "")
            descendants = {target_id}
            changed = True
            while changed:
                changed = False
                for child_id, parent_id in parents.items():
                    if child_id not in descendants and parent_id in descendants:
                        descendants.add(child_id)
                        changed = True
            if any(str(pawn.get("subscene_id") or "") in descendants for pawn in composition.get("pawns") or []):
                continue
            definition = next((item for item in definitions if str(item.get("id") or "") == target_id), {})
            label = str(definition.get("name") or target_id)
            warnings.append(f"{label} has no members; its group outline is available for editing but it will not appear in renders.")
        return warnings

    @staticmethod
    def normalize_framing(framing: dict) -> dict:
        if not isinstance(framing, dict):
            raise SceneLayoutError("Background framing must contain a center and zoom.")
        center = framing.get("center", [0.5, 0.5])
        if not isinstance(center, (list, tuple)) or len(center) != 2:
            raise SceneLayoutError("Background center must contain two coordinates.")
        values = [float(value) for value in center]
        zoom = float(framing.get("zoom", 1))
        if not all(math.isfinite(value) for value in [*values, zoom]):
            raise SceneLayoutError("Background framing must be finite.")
        return {"center": [min(5, max(-5, value)) for value in values], "zoom": min(20, max(.05, zoom))}

    @staticmethod
    def _angle(value: Any, label: str) -> float:
        angle = float(value)
        if not math.isfinite(angle) or abs(angle) > 3600:
            raise SceneLayoutError(f"{label} must be a finite angle within 3,600 degrees.")
        return angle % 360

    @staticmethod
    def _camera_basis(camera: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        position = np.asarray(camera["position"], dtype=float)
        target = np.asarray(camera["target"], dtype=float)
        forward = target - position
        norm = np.linalg.norm(forward)
        if norm < 1e-6:
            raise SceneLayoutError("Camera position and target must differ.")
        forward /= norm
        right = np.cross(forward, np.asarray([0.0, 1.0, 0.0]))
        if np.linalg.norm(right) < 1e-6:
            right = np.asarray([1.0, 0.0, 0.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        up /= np.linalg.norm(up)
        return position, right, up, forward

    @staticmethod
    def default_ground_distance(camera: dict, pawns: list[dict]) -> float:
        position = np.asarray(camera["position"], dtype=float)
        horizontal = np.asarray(camera["target"], dtype=float) - position
        horizontal[1] = 0
        norm = np.linalg.norm(horizontal)
        horizontal = horizontal / norm if norm > 1e-6 else np.asarray([0., 0., -1.])
        return max([10., *(float(np.dot(np.asarray(pawn["position"]) - position, horizontal)) + 5 for pawn in pawns)])

    @classmethod
    def ground_projection(cls, layout: dict) -> dict:
        ground = layout.get("ground") or {"enabled": True, "surface": "Ground surface matching the setting"}
        camera = next(item for item in layout["cameras"] if item["id"] == layout["active_camera_id"])
        position, _, up, forward = cls._camera_basis(camera)
        horizontal_length = math.hypot(float(forward[0]), float(forward[2]))
        horizontal = np.asarray([forward[0], 0., forward[2]]) / horizontal_length if horizontal_length > 1e-6 else np.asarray([0., 0., -1.])
        minimum = max([1., *(float(np.dot(np.asarray(pawn["position"]) - position, horizontal))
                            + max(pawn["dimensions"]["depth"], pawn["dimensions"]["width"]) / 2 + .02 for pawn in layout["pawns"])])
        distance = float(camera.get("ground_distance_m") or cls.default_ground_distance(camera, layout["pawns"]))
        tangent = math.tan(math.radians(camera["vertical_fov"]) / 2)
        def join_at(value):
            relative = horizontal * value - np.asarray([0., position[1], 0.])
            depth = float(np.dot(relative, forward))
            return (1 - float(np.dot(relative, up)) / (max(1e-5, depth) * tangent)) / 2
        join = join_at(distance)
        enabled = ground.get("enabled", True)
        return {"enabled": enabled, "surface": ground.get("surface") or "Ground surface matching the setting",
                "distance_m": distance, "minimum_distance_m": minimum,
                "join_y": join if enabled else 1.0, "visible_fraction": min(1., max(0., join)) if enabled else 1.0,
                "join_min": min(1., max(0., join_at(max(1000., minimum + 1)))),
                "join_max": min(1., max(0., join_at(minimum))),
                "origin": (position + horizontal * distance - np.asarray([0., position[1], 0.])).tolist(),
                "forward": horizontal.tolist(), "color": list(GROUND_COLOR)}

    def project(self, layout: dict, *, width: int = 1024, height: int = 576, aspect: float | None = None) -> dict:
        if width < 64 or height < 64 or width > 4096 or height > 4096:
            raise SceneLayoutError("Projection dimensions must be between 64 and 4096 pixels.")
        camera = next(item for item in layout["cameras"] if item["id"] == layout["active_camera_id"])
        position, right, up, forward = self._camera_basis(camera)
        tan_v = math.tan(math.radians(camera["vertical_fov"]) / 2)
        tan_h = tan_v * (aspect or width / height)
        subjects = []
        warnings = []
        ground = self.ground_projection(layout)
        if ground["enabled"] and position[1] <= .01:
            warnings.append("Raise the render camera above the ground surface.")
        if ground["enabled"] and ground["join_y"] <= 0:
            warnings.append("The backdrop is above the camera frame. Aim the camera up to show it.")
        for pawn in layout["pawns"]:
            base = np.asarray(pawn["position"], dtype=float)
            if ground["enabled"] and base[1] < -.01:
                warnings.append(f"{pawn['element_id']} is below the ground surface.")
            dims = pawn["dimensions"]
            if layout.get("background") and float(np.dot(base - position, ground["forward"])) + max(dims["width"], dims["depth"]) / 2 > ground["distance_m"]:
                warnings.append(f"{pawn['element_id']} is beyond the locked backdrop plane.")
            yaw = math.radians(pawn["body_yaw"])
            cos_y, sin_y = math.cos(yaw), math.sin(yaw)
            offsets = []
            for x in (-dims["width"] / 2, dims["width"] / 2):
                for y in (0, dims["height"]):
                    for z in (-dims["depth"] / 2, dims["depth"] / 2):
                        offsets.append([cos_y * x + sin_y * z, y, -sin_y * x + cos_y * z])
            corners = base + np.asarray(offsets)
            rel = corners - position
            depths = rel @ forward
            if np.all(depths <= 0):
                warnings.append(f"{pawn['element_id']} is behind the camera.")
                continue
            safe_depth = np.maximum(depths, 1e-5)
            nx = (rel @ right) / (safe_depth * tan_h)
            ny = (rel @ up) / (safe_depth * tan_v)
            left = (float(np.min(nx)) + 1) * width / 2
            right_px = (float(np.max(nx)) + 1) * width / 2
            top = (1 - float(np.max(ny))) * height / 2
            bottom = (1 - float(np.min(ny))) * height / 2
            center = base + np.asarray([0, dims["height"] / 2, 0])
            center_depth = float(np.dot(center - position, forward))
            body = np.asarray([math.sin(yaw), 0, -math.cos(yaw)])
            camera_to_subject = position - center
            body_dot = float(np.dot(body, camera_to_subject / max(np.linalg.norm(camera_to_subject), 1e-8)))
            body_side = float(np.dot(body, right))
            camera_facing = _facing_label(body_dot, body_side)
            head_yaw = math.radians(pawn["body_yaw"] + pawn["head_yaw"])
            head = np.asarray([math.sin(head_yaw), math.tan(math.radians(pawn["head_pitch"])), -math.cos(head_yaw)])
            head_dot = float(np.dot(head, camera_to_subject / max(np.linalg.norm(camera_to_subject), 1e-8)))
            head_facing = _facing_label(head_dot, float(np.dot(head, right)))
            screen = {"x": round((left + right_px) / 2 / width, 5), "y": round((top + bottom) / 2 / height, 5),
                      "width": round(max(0, right_px - left) / width, 5), "height": round(max(0, bottom - top) / height, 5),
                      "feet": {"x": round((float(np.mean((rel @ right) / (safe_depth * tan_h))) + 1) / 2, 5), "y": round(bottom / height, 5)}}
            head_world = base + np.asarray([0.0, dims["height"], 0.0])
            head_rel = head_world - position
            head_depth = max(float(np.dot(head_rel, forward)), 1e-5)
            screen["head"] = {"x": round((float(np.dot(head_rel, right)) / (head_depth * tan_h) + 1) / 2, 5),
                              "y": round((1 - float(np.dot(head_rel, up)) / (head_depth * tan_v)) / 2, 5)}
            eye_height = pawn.get("eye_height_m")
            if eye_height and eye_height <= dims["height"]:
                eye_world = base + np.asarray([0.0, eye_height, 0.0])
                eye_rel = eye_world - position
                eye_depth = max(float(np.dot(eye_rel, forward)), 1e-5)
                screen["eye"] = {"x": round((float(np.dot(eye_rel, right)) / (eye_depth * tan_h) + 1) / 2, 5),
                                 "y": round((1 - float(np.dot(eye_rel, up)) / (eye_depth * tan_v)) / 2, 5)}
            in_frame = right_px > 0 and left < width and bottom > 0 and top < height
            if not in_frame:
                warnings.append(f"{pawn['element_id']} is outside the camera frame.")
            ground_relative = np.asarray([base[0], 0., base[2]]) - position
            ground_depth = max(1e-5, float(np.dot(ground_relative, forward)))
            ground_contact = {"x": (float(np.dot(ground_relative, right)) / (ground_depth * tan_h) + 1) / 2,
                              "y": (1 - float(np.dot(ground_relative, up)) / (ground_depth * tan_v)) / 2}
            subjects.append({"element_id": pawn["element_id"], "screen": screen, "depth_m": round(center_depth, 5),
                             "ground_contact": ground_contact,
                             "elevation_m": float(base[1]),
                             "physical_height_m": pawn.get("stature_m", dims["height"]),
                             "physical_height": format_feet_inches(pawn.get("stature_m", dims["height"])),
                             "occupied_height": format_feet_inches(dims["height"]),
                             "camera_facing": camera_facing, "body_yaw": pawn["body_yaw"],
                             "head_facing": head_facing, "head_yaw": pawn["head_yaw"], "head_pitch": pawn["head_pitch"],
                             "in_frame": in_frame, "provisional_height": pawn["provisional_height"],
                             "pixel_bounds": {"left": int(round(left)), "top": int(round(top)),
                                              "right": int(round(right_px)), "bottom": int(round(bottom))}})
        subjects.sort(key=lambda item: item["depth_m"], reverse=True)
        for farther, nearer in zip(subjects, subjects[1:]):
            if farther["depth_m"] > nearer["depth_m"] and _overlap(farther["pixel_bounds"], nearer["pixel_bounds"]):
                warnings.append(f"{farther['element_id']} may be occluded by {nearer['element_id']}.")
        camera_facts = copy.deepcopy(camera)
        horizontal = math.hypot(float(forward[0]), float(forward[2]))
        camera_facts.update({
            "height": format_feet_inches(float(position[1])),
            "pitch_degrees": round(math.degrees(math.atan2(float(forward[1]), horizontal)), 2),
            "yaw_degrees": round(math.degrees(math.atan2(float(forward[0]), -float(forward[2]))), 2),
            "vertical_fov": camera["vertical_fov"],
            "target_distance_m": round(float(np.linalg.norm(np.asarray(camera["target"]) - position)), 5),
        })
        return {"version": 1, "width": width, "height": height, "camera": camera_facts,
                "subjects": subjects, "ground": ground, "warnings": warnings}

    def render_guidance(self, layout: dict, projection: dict, elements: list[dict], *, background_png: bytes | None = None) -> bytes:
        width, height = projection["width"], projection["height"]
        image = Image.new("RGB", (width, height), (238, 238, 238))
        if background_png:
            with Image.open(io.BytesIO(background_png)) as background:
                image.paste(background.convert("RGB"))
        draw = ImageDraw.Draw(image)
        ground = projection.get("ground") or {}
        ground_top = min(height, max(0, round(height * ground.get("visible_fraction", 1))))
        if ground.get("enabled") and ground_top < height:
            draw.rectangle((0, ground_top, width - 1, height - 1), fill=GROUND_COLOR)
        element_map = {str(item.get("id")): item for item in elements}
        for subject in projection["subjects"]:
            bounds = subject["pixel_bounds"]
            left, top = max(0, bounds["left"]), max(0, bounds["top"])
            right, bottom = min(width - 1, bounds["right"]), min(height - 1, bounds["bottom"])
            if right <= left or bottom <= top:
                continue
            element = element_map.get(subject["element_id"], {})
            color = (112, 119, 125)
            label = str(element.get("display_name") or subject["element_id"])
            draw.text((left, max(0, top - 12)), label, fill=(38, 43, 48))
            if ground.get("enabled") and subject.get("elevation_m", 0) >= 0:
                shadow_y = round(height * subject.get("ground_contact", {}).get("y", bottom / height))
                shadow_height = max(2, min(12, round((bottom - top) * .035)))
                if shadow_y >= ground_top:
                    draw.ellipse((left, shadow_y - shadow_height, right, shadow_y + shadow_height), fill=(139, 132, 120))
            if str(element.get("element_type")) in {"Character", "Person"}:
                h = bottom - top
                head = max(5, int(h * .13))
                torso_w = max(7, int((right - left) * .58))
                center_x = (left + right) // 2
                draw.ellipse((center_x - head // 2, top, center_x + head // 2, top + head), fill=color)
                torso_top = top + head
                torso_bottom = top + int(h * .66)
                draw.polygon([(center_x - torso_w // 2, torso_top), (center_x + torso_w // 2, torso_top),
                              (center_x + torso_w // 3, torso_bottom), (center_x - torso_w // 3, torso_bottom)], fill=color)
                draw.rectangle((center_x - torso_w // 3, torso_bottom, center_x - torso_w // 9, bottom), fill=color)
                draw.rectangle((center_x + torso_w // 9, torso_bottom, center_x + torso_w // 3, bottom), fill=color)
                # A small forward marker communicates orientation without labels.
                nose_y = top + head // 2
                draw.polygon([(center_x, nose_y), (center_x + max(2, head // 4), nose_y + max(1, head // 5)),
                              (center_x - max(2, head // 4), nose_y + max(1, head // 5))], fill=(65, 70, 75))
            else:
                draw.rectangle((left, top, right, bottom), fill=color)
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=False)
        return stream.getvalue()

    def guidance_reference(self, layout: dict, elements: list[dict], *, width: int = 1024, height: int = 576,
                           aspect: float | None = None, background: dict | None = None) -> dict:
        if layout.get("migration_review_required"):
            raise SceneLayoutError("Review and confirm the approximate migrated 3D placements before guided rendering.")
        projection = self.project(layout, width=width, height=height, aspect=aspect)
        if background:
            projection["background"] = background["projection"]
        if any(item["provisional_height"] for item in layout["pawns"]):
            missing = [item["element_id"] for item in layout["pawns"] if item["provisional_height"]]
            raise SceneLayoutError("Enter or confirm character height before guided rendering: " + ", ".join(missing))
        if any("behind the camera" in warning for warning in projection["warnings"]):
            raise SceneLayoutError("Move visible pawns in front of the render camera before rendering.")
        if any("below the ground" in warning or "Raise the render camera" in warning for warning in projection["warnings"]):
            raise SceneLayoutError("Keep visible pawns on or above the ground and raise the render camera above it.")
        if any("locked backdrop" in warning for warning in projection["warnings"]):
            raise SceneLayoutError("Move visible pawns in front of the locked backdrop plane before rendering.")
        payload = self.render_guidance(layout, projection, elements, background_png=background["png_bytes"] if background else None)
        digest = hashlib.sha256(json.dumps({"layout": layout, "projection": projection}, sort_keys=True).encode() + payload).hexdigest()
        return {"projection": projection, "png_bytes": payload, "sha256": digest}


def _overlap(a: dict, b: dict) -> bool:
    return a["left"] < b["right"] and a["right"] > b["left"] and a["top"] < b["bottom"] and a["bottom"] > b["top"]


def _facing_label(camera_dot: float, screen_side: float) -> str:
    if camera_dot > .94:
        return "front"
    if camera_dot < -.94:
        return "rear"
    side = "screen-right" if screen_side > .15 else "screen-left" if screen_side < -.15 else "straight ahead"
    if abs(camera_dot) < .2:
        return f"profile facing {side}"
    return f"{'front' if camera_dot > 0 else 'rear'} three-quarter facing {side}"
