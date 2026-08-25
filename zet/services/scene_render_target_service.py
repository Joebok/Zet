from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MAIN_RENDER_TARGET = "main"
BACKGROUND_RENDER_TARGET = "background"
MAX_ELEMENT_SUBSCENE_DEPTH = 3


class SceneRenderTargetService:
    """Own scene-subscene membership, projections, paths, and freshness."""

    def __init__(self, story_service, error_type):
        self.story = story_service
        self.error_type = error_type

    @staticmethod
    def image_tag(story_slug: str, scene_slug: str, target_id: str) -> str:
        return f"{{{{SCENE_RENDER:{story_slug}:{scene_slug}:{target_id}}}}}"

    @staticmethod
    def _safe_target_id(value: Any) -> str:
        text = str(value or "").strip()
        return text if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", text) else ""

    @staticmethod
    def _environment_value(value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            mode = str(value.get("mode") or "inherit").strip().lower()
            if mode not in {"inherit", "override", "omit"}:
                mode = "inherit"
            return {"mode": mode, "value": str(value.get("value") or "").strip()}
        text = str(value or "").strip()
        return {"mode": "override" if text else "inherit", "value": text}

    @staticmethod
    def _element_setup(raw: Any) -> dict:
        setup = copy.deepcopy(raw) if isinstance(raw, dict) else {}
        canvas = setup.get("canvas") if isinstance(setup.get("canvas"), dict) else {}
        composition = setup.get("composition") if isinstance(setup.get("composition"), dict) else {}
        environment = setup.get("environment") if isinstance(setup.get("environment"), dict) else {}
        return {
            "canvas": {
                "orientation": str(canvas.get("orientation") or "landscape").strip(),
                "aspect_ratio": str(canvas.get("aspect_ratio") or "16:9").strip(),
                "width": canvas.get("width"),
                "height": canvas.get("height"),
            },
            "composition": {
                "focal_point": str(composition.get("focal_point") or "").strip(),
                "left_to_right": [str(item).strip() for item in composition.get("left_to_right") or [] if str(item).strip()],
                "composition_notes": str(composition.get("composition_notes") or "").strip(),
            },
            "environment": {
                "location": str(environment.get("location") or "").strip(),
                "lighting": SceneRenderTargetService._environment_value(environment.get("lighting")),
                "mood": SceneRenderTargetService._environment_value(environment.get("mood")),
                "weather_or_atmosphere": SceneRenderTargetService._environment_value(environment.get("weather_or_atmosphere")),
                "general_background_notes": str(environment.get("general_background_notes") or "").strip(),
                "general_foreground_notes": str(environment.get("general_foreground_notes") or "").strip(),
            },
        }

    def normalize(self, data: dict) -> None:
        normalized: list[dict] = []
        for raw in data.get("subscenes") or []:
            if not isinstance(raw, dict):
                continue
            item = copy.deepcopy(raw)
            item["id"] = str(item.get("id") or "").strip()
            item["name"] = str(item.get("name") or item["id"]).strip()
            item["enabled"] = bool(item.get("enabled", False))
            item["kind"] = str(item.get("kind") or "background").strip().lower()
            item["assembly_role"] = str(
                item.get("assembly_role") or ("element_reference" if item["kind"] == "element" else "backdrop")
            ).strip()
            item["anchor_element_id"] = str(item.get("anchor_element_id") or "").strip()
            overrides = item.get("prompt_overrides") if isinstance(item.get("prompt_overrides"), dict) else {}
            item["prompt_overrides"] = {
                key: str(overrides.get(key) or "").strip()
                for key in (
                    "focal_point",
                    "composition_notes",
                    "general_foreground_notes",
                    "general_background_notes",
                )
            }
            if item["kind"] == "element":
                item["setup"] = self._element_setup(item.get("setup"))
            normalized.append(item)
        data["subscenes"] = normalized
        for element in data.get("scene_elements") or []:
            if isinstance(element, dict):
                element["subscene_id"] = str(element.get("subscene_id") or "").strip()

    def definition(self, data: dict, target_id: str) -> dict | None:
        if target_id == MAIN_RENDER_TARGET:
            return None
        return next(
            (item for item in data.get("subscenes") or [] if isinstance(item, dict) and item.get("id") == target_id),
            None,
        )

    def target_label(self, data: dict, target_id: str) -> str:
        definition = self.definition(data, target_id)
        return "Full Scene" if target_id == MAIN_RENDER_TARGET else str((definition or {}).get("name") or target_id)

    def pipeline_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        if target_id == MAIN_RENDER_TARGET:
            return self.story.path_service.story_pipeline_path(story_slug, scene_slug)
        return self.story.path_service.scene_subscene_pipeline_path(story_slug, scene_slug, target_id)

    def review_paths(self, story_slug: str, scene_slug: str, target_id: str) -> dict[str, Path]:
        paths = self.story.path_service
        if target_id == MAIN_RENDER_TARGET:
            return {
                "locked": paths.scene_locked_image_path(story_slug, scene_slug),
                "candidate": paths.scene_candidate_image_path(story_slug, scene_slug),
                "comment": paths.scene_render_review_comment_path(story_slug, scene_slug),
                "backups": paths.scene_locked_backups_path(story_slug, scene_slug),
                "metadata": paths.story_pipeline_path(story_slug, scene_slug) / "Locked_Render.render.json",
            }
        return {
            "locked": paths.scene_subscene_locked_path(story_slug, scene_slug, target_id),
            "candidate": paths.scene_subscene_candidate_path(story_slug, scene_slug, target_id),
            "comment": paths.scene_subscene_comment_path(story_slug, scene_slug, target_id),
            "backups": paths.scene_subscene_locked_backups_path(story_slug, scene_slug, target_id),
            "metadata": paths.scene_subscene_locked_metadata_path(story_slug, scene_slug, target_id),
        }

    def freshness(self, story_slug: str, scene_slug: str, target_id: str, current_hash: str) -> dict:
        paths = self.review_paths(story_slug, scene_slug, target_id)
        locked_exists = paths["locked"].is_file()
        if target_id == MAIN_RENDER_TARGET:
            return {"locked_exists": locked_exists, "locked_current": locked_exists, "stale_reason": ""}
        stored_hash = ""
        if paths["metadata"].is_file():
            try:
                stored_hash = str(json.loads(paths["metadata"].read_text(encoding="utf-8")).get("render_input_hash") or "")
            except (OSError, json.JSONDecodeError):
                stored_hash = ""
        if not locked_exists:
            reason = "No locked image exists."
        elif not stored_hash:
            reason = "The locked image has no render-input provenance."
        elif stored_hash != current_hash:
            reason = "The locked image is out of date with the current subscene."
        else:
            reason = ""
        return {"locked_exists": locked_exists, "locked_current": locked_exists and not reason, "stale_reason": reason}

    def target_graph(self, data: dict) -> dict:
        definitions: dict[str, dict] = {}
        elements = {
            str(item.get("id") or ""): item
            for item in data.get("scene_elements") or []
            if isinstance(item, dict) and str(item.get("id") or "")
        }
        errors: list[str] = []
        duplicate_ids: set[str] = set()
        for item in data.get("subscenes") or []:
            if not isinstance(item, dict):
                continue
            target_id = str(item.get("id") or "")
            if not self._safe_target_id(target_id):
                errors.append(f"Invalid subscene id: {target_id or '(blank)' }.")
            if target_id == MAIN_RENDER_TARGET:
                errors.append("Subscene id 'main' is reserved.")
            if item.get("kind") not in {"background", "element"}:
                errors.append(f"Subscene {target_id or '(blank)'} has invalid kind {item.get('kind')}.")
            if target_id in definitions:
                duplicate_ids.add(target_id)
            else:
                definitions[target_id] = item
        for target_id in sorted(duplicate_ids):
            errors.append(f"Duplicate subscene id {target_id}.")

        parents: dict[str, str] = {}
        anchors: dict[str, str] = {}
        for target_id, definition in definitions.items():
            if definition.get("kind") != "element":
                parents[target_id] = MAIN_RENDER_TARGET
                continue
            anchor_id = str(definition.get("anchor_element_id") or "")
            if not anchor_id or anchor_id not in elements:
                errors.append(f"Element subscene {target_id} references missing anchor {anchor_id or '(blank)' }.")
                continue
            if anchor_id in anchors:
                errors.append(f"Scene element {anchor_id} anchors more than one element subscene.")
            anchors[anchor_id] = target_id
            owner = str(elements[anchor_id].get("subscene_id") or MAIN_RENDER_TARGET)
            if owner != MAIN_RENDER_TARGET and owner not in definitions:
                errors.append(f"Element subscene {target_id} anchor {anchor_id} belongs to missing subscene {owner}.")
            parents[target_id] = owner
            if owner == target_id:
                errors.append(f"Element subscene {target_id} cannot contain its own anchor {anchor_id}.")

        for element_id, element in elements.items():
            owner = str(element.get("subscene_id") or "")
            if owner and owner not in definitions:
                errors.append(f"Scene element {element_id} references missing subscene {owner}.")

        depths: dict[str, int] = {}
        visiting: set[str] = set()

        def depth(target_id: str) -> int:
            if target_id in depths:
                return depths[target_id]
            if target_id in visiting:
                errors.append(f"Element subscene cycle detected at {target_id}.")
                return MAX_ELEMENT_SUBSCENE_DEPTH + 1
            visiting.add(target_id)
            parent = parents.get(target_id, MAIN_RENDER_TARGET)
            parent_definition = definitions.get(parent)
            value = depth(parent) + 1 if parent_definition and parent_definition.get("kind") == "element" else 1
            visiting.remove(target_id)
            depths[target_id] = value
            return value

        for target_id, definition in definitions.items():
            if definition.get("kind") != "element":
                depths[target_id] = 0
                continue
            value = depth(target_id)
            if value > MAX_ELEMENT_SUBSCENE_DEPTH:
                errors.append(
                    f"Element subscene {target_id} exceeds the maximum nesting depth of {MAX_ELEMENT_SUBSCENE_DEPTH}."
                )

        children: dict[str, list[str]] = {MAIN_RENDER_TARGET: []}
        for target_id in definitions:
            children.setdefault(target_id, [])
        for target_id, parent in parents.items():
            children.setdefault(parent, []).append(target_id)
        return {
            "definitions": definitions,
            "elements": elements,
            "parents": parents,
            "children": children,
            "depths": depths,
            "errors": list(dict.fromkeys(errors)),
        }

    def assert_valid_graph(self, data: dict) -> None:
        errors = self.target_graph(data)["errors"]
        if errors:
            raise self.error_type("Invalid scene subscene graph: " + " ".join(errors))

    def direct_dependencies(self, data: dict, target_id: str, *, enabled_only: bool = True) -> list[dict]:
        graph = self.target_graph(data)
        dependencies = []
        for child_id in graph["children"].get(target_id, []):
            definition = graph["definitions"].get(child_id)
            if not definition or (enabled_only and not definition.get("enabled")):
                continue
            dependencies.append(definition)
        return dependencies

    def effective_setup(self, data: dict, target_id: str) -> tuple[dict, dict]:
        setup = data.get("setup") if isinstance(data.get("setup"), dict) else {}
        main_canvas = copy.deepcopy(setup.get("canvas") if isinstance(setup.get("canvas"), dict) else {})
        main_environment = copy.deepcopy(
            setup.get("environment") if isinstance(setup.get("environment"), dict) else {}
        )
        if target_id == MAIN_RENDER_TARGET:
            return main_canvas, main_environment
        definition = self.definition(data, target_id)
        if definition is None:
            raise self.error_type(f"Scene subscene not found: {target_id}")
        if definition.get("kind") != "element":
            overrides = definition.get("prompt_overrides") or {}
            main_environment["general_foreground_notes"] = str(overrides.get("general_foreground_notes") or "")
            main_environment["general_background_notes"] = str(overrides.get("general_background_notes") or "")
            return main_canvas, main_environment
        graph = self.target_graph(data)
        parent_id = graph["parents"].get(target_id, MAIN_RENDER_TARGET)
        _, parent_environment = self.effective_setup(data, parent_id)
        target_setup = self._element_setup(definition.get("setup"))
        environment = target_setup["environment"]
        effective_environment = {
            "location": environment["location"],
            "general_background_notes": environment["general_background_notes"],
            "general_foreground_notes": environment["general_foreground_notes"],
        }
        for key in ("lighting", "mood", "weather_or_atmosphere"):
            policy = environment[key]
            if policy["mode"] == "inherit":
                effective_environment[key] = str(parent_environment.get(key) or "")
            elif policy["mode"] == "override":
                effective_environment[key] = policy["value"]
            else:
                effective_environment[key] = ""
        return copy.deepcopy(target_setup["canvas"]), effective_environment

    def enable_element(self, story_slug: str, scene_slug: str, element_id: str):
        document = self.story.load_scene_builder_data(story_slug, scene_slug)
        if document.blocked:
            raise self.error_type(document.error or "Scene Builder JSON is blocked.")
        data = copy.deepcopy(document.data)
        data.pop("_validation_warnings", None)
        element = next(
            (item for item in data.get("scene_elements") or [] if isinstance(item, dict) and item.get("id") == element_id),
            None,
        )
        if element is None:
            raise self.error_type(f"Scene element not found: {element_id}")
        existing = next(
            (
                item for item in data.get("subscenes") or []
                if isinstance(item, dict) and item.get("kind") == "element" and item.get("anchor_element_id") == element_id
            ),
            None,
        )
        if existing is not None:
            existing["enabled"] = True
            return self.story.save_scene_builder_data(story_slug, scene_slug, data)

        base_id = f"{re.sub(r'[^A-Za-z0-9]+', '_', str(element_id)).strip('_') or 'element'}_subscene"
        target_id = base_id
        used = {str(item.get("id") or "") for item in data.get("subscenes") or [] if isinstance(item, dict)}
        suffix = 2
        while target_id in used:
            target_id = f"{base_id}_{suffix}"
            suffix += 1
        parent_target = str(element.get("subscene_id") or MAIN_RENDER_TARGET)
        parent_canvas, _ = self.effective_setup(data, parent_target)
        definition = {
            "id": target_id,
            "name": str(element.get("display_name") or element_id),
            "enabled": True,
            "kind": "element",
            "assembly_role": "element_reference",
            "anchor_element_id": element_id,
            "prompt_overrides": {
                "focal_point": "",
                "composition_notes": "",
                "general_foreground_notes": "",
                "general_background_notes": "",
            },
            "setup": {
                "canvas": copy.deepcopy(parent_canvas),
                "composition": {"focal_point": "", "left_to_right": [], "composition_notes": ""},
                "environment": {
                    "location": "",
                    "lighting": {"mode": "inherit", "value": ""},
                    "mood": {"mode": "inherit", "value": ""},
                    "weather_or_atmosphere": {"mode": "inherit", "value": ""},
                    "general_background_notes": "",
                    "general_foreground_notes": "",
                },
            },
        }
        data.setdefault("subscenes", []).append(definition)
        return self.story.save_scene_builder_data(story_slug, scene_slug, data)

    def enable_background(self, story_slug: str, scene_slug: str):
        document = self.story.load_scene_builder_data(story_slug, scene_slug)
        if document.blocked:
            raise self.error_type(document.error or "Scene Builder JSON is blocked.")
        data = copy.deepcopy(document.data)
        data.pop("_validation_warnings", None)
        definition = self.definition(data, BACKGROUND_RENDER_TARGET)
        if definition is None:
            background_notes = str(data.get("setup", {}).get("environment", {}).get("general_background_notes") or "").strip()
            definition = {
                "id": BACKGROUND_RENDER_TARGET,
                "name": "Background",
                "enabled": True,
                "assembly_role": "backdrop",
                "prompt_overrides": {
                    "focal_point": "",
                    "composition_notes": "",
                    "general_foreground_notes": "",
                    "general_background_notes": background_notes,
                },
            }
            data.setdefault("subscenes", []).append(definition)
            depths = {
                str(item.get("scene_element_id") or ""): str(item.get("depth") or "").strip().casefold()
                for item in data.get("placements") or []
                if isinstance(item, dict)
            }
            for element in data.get("scene_elements") or []:
                if isinstance(element, dict) and depths.get(str(element.get("id") or "")) in {"background", "distant background"}:
                    element["subscene_id"] = BACKGROUND_RENDER_TARGET
        else:
            definition["enabled"] = True
        return self.story.save_scene_builder_data(story_slug, scene_slug, data)

    def disable(self, story_slug: str, scene_slug: str, target_id: str):
        if target_id == MAIN_RENDER_TARGET:
            raise self.error_type("The main render target cannot be disabled.")
        document = self.story.load_scene_builder_data(story_slug, scene_slug)
        data = copy.deepcopy(document.data)
        data.pop("_validation_warnings", None)
        definition = self.definition(data, target_id)
        if definition is None:
            raise self.error_type(f"Scene subscene not found: {target_id}")
        definition["enabled"] = False
        return self.story.save_scene_builder_data(story_slug, scene_slug, data)

    def validate(self, data: dict) -> list[str]:
        warnings: list[str] = []
        ids: set[str] = set()
        for item in data.get("subscenes") or []:
            target_id = str(item.get("id") or "") if isinstance(item, dict) else ""
            if not self._safe_target_id(target_id):
                warnings.append(f"Invalid subscene id: {target_id or '(blank)' }.")
            if target_id == MAIN_RENDER_TARGET:
                warnings.append("Subscene id 'main' is reserved.")
            if target_id in ids:
                warnings.append(f"Duplicate subscene id {target_id}.")
            ids.add(target_id)
            if isinstance(item, dict) and not str(item.get("assembly_role") or "").strip():
                warnings.append(f"Subscene {target_id or '(blank)'} has no assembly role.")
        for element in data.get("scene_elements") or []:
            if not isinstance(element, dict):
                continue
            target_id = str(element.get("subscene_id") or "")
            if target_id and target_id not in ids:
                warnings.append(f"Scene element {element.get('id') or element.get('display_name')} references missing subscene {target_id}.")
        warnings.extend(self.target_graph(data)["errors"])
        return list(dict.fromkeys(warnings))

    def _members(self, data: dict, target_id: str) -> set[str]:
        return {
            str(item.get("id") or "")
            for item in data.get("scene_elements") or []
            if isinstance(item, dict) and str(item.get("subscene_id") or "") == target_id
        }

    def _inject_element_child_references(self, projected: dict, source: dict, target_id: str) -> None:
        elements = {
            str(item.get("id") or ""): item
            for item in projected.get("scene_elements") or []
            if isinstance(item, dict)
        }
        story_slug = str(source.get("scene", {}).get("_story_slug") or "")
        scene_slug = str(source.get("scene", {}).get("slug") or "")
        for definition in self.direct_dependencies(source, target_id):
            if definition.get("kind") != "element":
                continue
            anchor_id = str(definition.get("anchor_element_id") or "")
            anchor = elements.get(anchor_id)
            if anchor is None:
                continue
            anchor.setdefault("reference_images", []).append({
                "tag": self.image_tag(story_slug, scene_slug, str(definition.get("id") or "")),
                "roles": ["complete element or group appearance", "internal arrangement"],
                "ignore": ["source canvas", "source background", "source framing", "outer placement", "source lighting"],
                "notes": "Managed element subscene reference; parent placement and scene instructions take precedence.",
            })

    def _project_element_subscene(self, data: dict, definition: dict) -> dict:
        target_id = str(definition.get("id") or "")
        graph = self.target_graph(data)
        anchor_id = str(definition.get("anchor_element_id") or "")
        anchor = copy.deepcopy(graph["elements"].get(anchor_id) or {})
        anchor_sections = self.story._element_source_sections(anchor)
        if anchor_sections:
            anchor["resolved_source_sections"] = anchor_sections
        projected = copy.deepcopy(data)
        members = self._members(data, target_id)
        projected["scene_elements"] = [item for item in projected.get("scene_elements") or [] if item.get("id") in members]
        projected["placements"] = [item for item in projected.get("placements") or [] if item.get("scene_element_id") in members]
        canvas, environment = self.effective_setup(data, target_id)
        target_setup = self._element_setup(definition.get("setup"))
        projected.setdefault("setup", {})["canvas"] = canvas
        composition = projected["setup"].setdefault("composition", {})
        composition.clear()
        composition.update(copy.deepcopy(target_setup["composition"]))
        composition["left_to_right"] = [item for item in composition.get("left_to_right") or [] if item in members]
        projected["setup"]["environment"] = environment
        projected.setdefault("scene", {})["story_beat"] = ""
        projected["interactions"] = [
            item for item in projected.get("interactions") or []
            if item.get("subject_element_id") in members and item.get("target_element_id") in members
        ]
        projected["custom_interactions"] = ""
        projected["dialogue"] = []
        projected["props_and_states"] = []
        projected["reference_assignments"] = [
            item for item in projected.get("reference_assignments") or []
            if item.get("applies_to_element_id") in members
        ]
        projected["final_image_prompt_overrides"] = {}
        projected["_render_target"] = {
            "id": target_id,
            "label": self.target_label(data, target_id),
            "kind": "element_subscene",
            "anchor_element_id": anchor_id,
            "anchor": anchor,
            "depth": graph["depths"].get(target_id, 1),
        }
        self._inject_element_child_references(projected, data, target_id)
        projected["depth_lanes"] = self.story.rebuild_depth_lanes_from_placements(projected)
        return projected

    def project_subscene(self, data: dict, target_id: str) -> dict:
        definition = self.definition(data, target_id)
        if definition is None:
            raise self.error_type(f"Scene subscene not found: {target_id}")
        if definition.get("kind") == "element":
            return self._project_element_subscene(data, definition)
        projected = copy.deepcopy(data)
        members = self._members(data, target_id)
        projected["scene_elements"] = [item for item in projected.get("scene_elements") or [] if item.get("id") in members]
        projected["placements"] = [item for item in projected.get("placements") or [] if item.get("scene_element_id") in members]
        composition = projected.setdefault("setup", {}).setdefault("composition", {})
        overrides = definition.get("prompt_overrides") or {}
        composition["focal_point"] = overrides.get("focal_point", "")
        composition["composition_notes"] = overrides.get("composition_notes", "")
        composition["left_to_right"] = [item for item in composition.get("left_to_right") or [] if item in members]
        environment = projected["setup"].setdefault("environment", {})
        environment["general_foreground_notes"] = overrides.get("general_foreground_notes", "")
        environment["general_background_notes"] = overrides.get("general_background_notes", "")
        projected.setdefault("scene", {})["story_beat"] = ""
        projected["interactions"] = [
            item for item in projected.get("interactions") or []
            if item.get("subject_element_id") in members and item.get("target_element_id") in members
        ]
        projected["custom_interactions"] = ""
        projected["dialogue"] = []
        projected["props_and_states"] = []
        projected["reference_assignments"] = [
            item for item in projected.get("reference_assignments") or []
            if item.get("applies_to_element_id") in members
        ]
        projected["final_image_prompt_overrides"] = {}
        projected["_render_target"] = {"id": target_id, "label": self.target_label(data, target_id), "kind": "subscene"}
        self._inject_element_child_references(projected, data, target_id)
        projected["depth_lanes"] = self.story.rebuild_depth_lanes_from_placements(projected)
        return projected

    def project_main(self, data: dict, statuses: dict[str, dict]) -> dict:
        projected = copy.deepcopy(data)
        active = [item for item in data.get("subscenes") or [] if item.get("enabled")]
        active_backgrounds = [item for item in active if item.get("kind") != "element"]
        element_target_ids = {
            str(item.get("id") or "")
            for item in data.get("subscenes") or []
            if item.get("kind") == "element"
        }
        baked_ids = {
            str(element.get("id") or "")
            for element in data.get("scene_elements") or []
            if str(element.get("subscene_id") or "") in {str(item.get("id") or "") for item in active_backgrounds}
        }
        hidden_element_ids = {
            str(element.get("id") or "")
            for element in data.get("scene_elements") or []
            if str(element.get("subscene_id") or "") in element_target_ids
        }
        all_elements = {
            str(item.get("id") or ""): item for item in projected.get("scene_elements") or [] if isinstance(item, dict)
        }
        placements = {
            str(item.get("scene_element_id") or ""): item for item in projected.get("placements") or [] if isinstance(item, dict)
        }
        projected["_baked_landmarks"] = [
            {
                "id": element_id,
                "display_name": all_elements[element_id].get("display_name", element_id),
                "position_within_cell": placements.get(element_id, {}).get("position_within_cell", ""),
                "depth": placements.get(element_id, {}).get("depth", ""),
                "world_position": placements.get(element_id, {}).get("world_position", ""),
            }
            for element_id in baked_ids if element_id in all_elements
        ]
        excluded_ids = baked_ids | hidden_element_ids
        projected["scene_elements"] = [item for item in projected.get("scene_elements") or [] if item.get("id") not in excluded_ids]
        projected["placements"] = [item for item in projected.get("placements") or [] if item.get("scene_element_id") not in excluded_ids]
        projected["reference_assignments"] = [
            item for item in projected.get("reference_assignments") or []
            if item.get("applies_to_element_id") not in excluded_ids
        ]
        projected["interactions"] = [
            item for item in projected.get("interactions") or []
            if item.get("subject_element_id") not in hidden_element_ids
            and item.get("target_element_id") not in hidden_element_ids
            and (item.get("subject_element_id") not in baked_ids or item.get("target_element_id") not in baked_ids)
        ]
        if active_backgrounds:
            projected.setdefault("setup", {}).setdefault("environment", {})["general_background_notes"] = ""
        projected["_render_inputs"] = [
            {
                "target_id": item["id"],
                "label": item.get("name") or item["id"],
                "assembly_role": item.get("assembly_role") or "backdrop",
                "tag": self.image_tag(projected["scene"].get("_story_slug", ""), projected["scene"].get("slug", ""), item["id"]),
                "path": statuses.get(item["id"], {}).get("locked_image_path", ""),
            }
            for item in active_backgrounds
        ]
        self._inject_element_child_references(projected, data, MAIN_RENDER_TARGET)
        projected["_render_target"] = {"id": MAIN_RENDER_TARGET, "label": "Full Scene", "kind": "main"}
        projected["depth_lanes"] = self.story.rebuild_depth_lanes_from_placements(projected)
        return projected

    @staticmethod
    def input_hash(ir: dict, story_settings: dict, references: list[dict]) -> str:
        digest = hashlib.sha256()
        payload = copy.deepcopy(ir)
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        for key in ("scene_json_path", "story_settings_path", "source_hashes"):
            source.pop(key, None)
        digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        digest.update(json.dumps(story_settings, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        for reference in sorted(references, key=lambda item: str(item.get("path") or "")):
            path = Path(str(reference.get("path") or ""))
            digest.update(str(reference.get("tag") or "").encode("utf-8"))
            if path.is_file():
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
        return digest.hexdigest()
