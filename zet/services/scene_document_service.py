from __future__ import annotations

from zet.services.scene_prompt_sections import FINAL_IMAGE_PROMPT_SECTION_TITLES


class SceneDocumentService:
    """Own the Scene Builder V4 normalization policy."""

    def __init__(self, story_service, error_type):
        self.story_service = story_service
        self.error_type = error_type

    def normalize(self, story_slug: str, scene_slug: str, data: dict) -> dict:
        story = self.story_service
        if not isinstance(data, dict):
            raise self.error_type("Scene Builder JSON must be an object.")
        schema_version = data.get("schema_version", 4)
        if schema_version != 4:
            raise self.error_type(f"Unsupported Scene Builder schema_version: {schema_version}")
        if data.get("file_kind") not in (None, "scene"):
            raise self.error_type(f"Unsupported Scene Builder file_kind: {data.get('file_kind')}")
        safe_story_slug = story.safe_slug(story_slug)
        safe_scene_slug = story.safe_slug(scene_slug)
        image_path = story.scene_image_path(safe_story_slug, safe_scene_slug)
        default = story.create_default_scene_builder_data(safe_story_slug, safe_scene_slug)
        normalized = story._merge_scene_builder_defaults(default, data)
        normalized["schema_version"] = 4
        normalized["file_kind"] = "scene"
        normalized.setdefault("scene", {})
        normalized["scene"]["id"] = normalized["scene"].get("id") or story.normalize_scene_element_id(safe_scene_slug).lower()
        normalized["scene"]["slug"] = safe_scene_slug
        normalized["scene"]["story_settings_path"] = story._library_relative_path(story.get_story_settings_path_from_story_md(story.path_service.story_file_path(safe_story_slug)))
        normalized["scene"]["associated_png_path"] = story._library_relative_path(image_path)
        if not str(normalized["scene"].get("name") or "").strip():
            normalized["scene"]["name"] = default["scene"]["name"]
        normalized.setdefault("setup", {})
        for key in ("camera", "style"):
            normalized["setup"].pop(key, None)
        composition = normalized["setup"].setdefault("composition", {})
        environment = normalized["setup"].setdefault("environment", {})
        environment.pop("important_exclusions", None)
        normalized.pop("avoid", None)
        overrides = normalized.get("final_image_prompt_overrides")
        if not isinstance(overrides, dict):
            overrides = {}
        normalized["final_image_prompt_overrides"] = {}
        for key in FINAL_IMAGE_PROMPT_SECTION_TITLES:
            value = overrides.get(key)
            normalized["final_image_prompt_overrides"][key] = value if isinstance(value, str) else ""
        composition["focal_point"] = str(composition.get("focal_point") or "").strip()
        composition["composition_notes"] = str(composition.get("composition_notes") or "").strip()
        seen_composition_ids: set[str] = set()
        composition["left_to_right"] = [
            element_id for value in composition.get("left_to_right") or []
            if (element_id := str(value or "").strip())
            and not (element_id in seen_composition_ids or seen_composition_ids.add(element_id))
        ]
        normalized["scene_elements"] = story._normalized_scene_elements(normalized)
        story.scene_render_target_service.normalize(normalized)
        normalized["placements"] = story._normalized_placements(normalized)
        suppressed_element_ids = {
            str(item.get("scene_element_id") or "")
            for item in normalized["placements"]
            if str(item.get("position_within_cell") or "").strip().lower() == "none"
        }
        composition["left_to_right"] = [
            element_id for element_id in composition["left_to_right"]
            if element_id not in suppressed_element_ids
        ]
        for item in normalized.get("dialogue") or []:
            if isinstance(item, dict):
                for key in ("tone", "include_in_final_image_prompt", "include_in_local_render", "panel_style_id", "preferred_screen_region", "must_not_cover"):
                    item.pop(key, None)
        normalized.pop("generation_outputs", None)
        normalized.pop("_validation_warnings", None)
        normalized["depth_lanes"] = story.rebuild_depth_lanes_from_placements(normalized)
        return normalized
