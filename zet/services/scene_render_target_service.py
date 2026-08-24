from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MAIN_RENDER_TARGET = "main"
BACKGROUND_RENDER_TARGET = "background"


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

    def normalize(self, data: dict) -> None:
        normalized: list[dict] = []
        for raw in data.get("subscenes") or []:
            if not isinstance(raw, dict):
                continue
            item = copy.deepcopy(raw)
            item["id"] = str(item.get("id") or "").strip()
            item["name"] = str(item.get("name") or item["id"]).strip()
            item["enabled"] = bool(item.get("enabled", False))
            item["assembly_role"] = str(item.get("assembly_role") or "backdrop").strip()
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
        return warnings

    def _members(self, data: dict, target_id: str) -> set[str]:
        return {
            str(item.get("id") or "")
            for item in data.get("scene_elements") or []
            if isinstance(item, dict) and str(item.get("subscene_id") or "") == target_id
        }

    def project_subscene(self, data: dict, target_id: str) -> dict:
        definition = self.definition(data, target_id)
        if definition is None:
            raise self.error_type(f"Scene subscene not found: {target_id}")
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
        projected["depth_lanes"] = self.story.rebuild_depth_lanes_from_placements(projected)
        return projected

    def project_main(self, data: dict, statuses: dict[str, dict]) -> dict:
        projected = copy.deepcopy(data)
        active = [item for item in data.get("subscenes") or [] if item.get("enabled")]
        if not active:
            projected["_render_target"] = {"id": MAIN_RENDER_TARGET, "label": "Full Scene", "kind": "main"}
            projected["_render_inputs"] = []
            projected["_baked_landmarks"] = []
            return projected
        baked_ids = {
            str(element.get("id") or "")
            for element in data.get("scene_elements") or []
            if str(element.get("subscene_id") or "") in {str(item.get("id") or "") for item in active}
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
        projected["scene_elements"] = [item for item in projected.get("scene_elements") or [] if item.get("id") not in baked_ids]
        projected["placements"] = [item for item in projected.get("placements") or [] if item.get("scene_element_id") not in baked_ids]
        projected["reference_assignments"] = [
            item for item in projected.get("reference_assignments") or []
            if item.get("applies_to_element_id") not in baked_ids
        ]
        projected["interactions"] = [
            item for item in projected.get("interactions") or []
            if item.get("subject_element_id") not in baked_ids or item.get("target_element_id") not in baked_ids
        ]
        projected.setdefault("setup", {}).setdefault("environment", {})["general_background_notes"] = ""
        projected["_render_inputs"] = [
            {
                "target_id": item["id"],
                "label": item.get("name") or item["id"],
                "assembly_role": item.get("assembly_role") or "backdrop",
                "tag": self.image_tag(projected["scene"].get("_story_slug", ""), projected["scene"].get("slug", ""), item["id"]),
                "path": statuses.get(item["id"], {}).get("locked_image_path", ""),
            }
            for item in active
        ]
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
