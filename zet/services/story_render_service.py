from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.models.reference import reference_files_payload
from zet.services.scene_render_compiler import (
    compile_scene_render_ir,
    final_image_prompt_text,
    local_render_brief,
    local_render_forge_couple_prompt_text,
    local_render_prompt_text,
)
from zet.services.scene_prompt_sections import load_final_image_prompt_sections
from zet.services.scene_render_target_service import MAIN_RENDER_TARGET


class StoryRenderService:
    """Compile Scene Builder documents and stage story render tasks."""

    def __init__(self, story_service, reference_service, render_task_type, error_type):
        self.story = story_service
        self.reference_service = reference_service
        self.render_task_type = render_task_type
        self.error_type = error_type

    def _compile_projected(
        self,
        projected: dict,
        story_settings: dict,
        default_prompt_sections: dict[str, str],
    ) -> tuple[list[dict], dict, str]:
        story = self.story
        references = self.reference_service.resolve_scene_references("\n" + json.dumps(projected))
        ir = compile_scene_render_ir(
            projected,
            story_settings,
            {"references": references, "element_sources": story._resolve_scene_element_sources(projected)},
            default_prompt_sections,
        )
        return references, ir, story.scene_render_target_service.input_hash(ir, story_settings, references)

    def _compile(
        self,
        story_slug: str,
        scene_slug: str,
        render_target_id: str = MAIN_RENDER_TARGET,
        allow_stale_dependencies: bool = False,
    ) -> tuple[Path, Path, dict, list[dict], dict, Path, str, str]:
        story = self.story
        safe_story_slug = story.safe_slug(story_slug)
        safe_scene_slug = story.safe_slug(scene_slug)
        target_id = str(render_target_id or MAIN_RENDER_TARGET).strip()
        pipeline_path = story.scene_render_target_service.pipeline_path(safe_story_slug, safe_scene_slug, target_id)
        scene_builder_path = story.scene_builder_json_path(safe_story_slug, safe_scene_slug)
        if not scene_builder_path.exists():
            raise self.error_type(f"Scene Builder JSON not found: {scene_builder_path}")
        scene_builder_data = json.loads(scene_builder_path.read_text(encoding="utf-8"))
        normalized_scene = story._normalize_scene_builder_data(safe_story_slug, safe_scene_slug, scene_builder_data)
        normalized_scene.setdefault("scene", {})["_story_slug"] = safe_story_slug
        story.scene_render_target_service.assert_valid_graph(normalized_scene)
        story_settings_path = story._library_absolute_path(str(normalized_scene.get("scene", {}).get("story_settings_path") or ""))
        if not story_settings_path.exists():
            raise self.error_type(f"Story settings file not found: {story_settings_path}")
        sections_path = story._project_config_path("Prompt_Templates", "final_image_prompt_tail_v1.md")
        try:
            default_prompt_sections = load_final_image_prompt_sections(sections_path)
        except (OSError, ValueError) as exc:
            raise self.error_type(f"Invalid final image prompt sections template {sections_path}: {exc}") from exc
        story_settings = story.load_story_settings(story_settings_path)
        if target_id != MAIN_RENDER_TARGET and story.scene_render_target_service.definition(normalized_scene, target_id) is None:
            raise self.error_type(f"Scene subscene not found: {target_id}")

        compiled: dict[str, tuple[dict, list[dict], dict, str]] = {}

        def compile_target(current_target_id: str) -> tuple[dict, list[dict], dict, str]:
            if current_target_id in compiled:
                return compiled[current_target_id]
            statuses: dict[str, dict] = {}
            for definition in story.scene_render_target_service.direct_dependencies(normalized_scene, current_target_id):
                subscene_id = str(definition.get("id") or "")
                _, _, _, current_hash = compile_target(subscene_id)
                freshness = story.scene_render_target_service.freshness(
                    safe_story_slug, safe_scene_slug, subscene_id, current_hash
                )
                paths = story.scene_render_target_service.review_paths(safe_story_slug, safe_scene_slug, subscene_id)
                statuses[subscene_id] = {**freshness, "locked_image_path": str(paths["locked"])}
                if not freshness["locked_current"] and not (
                    allow_stale_dependencies and freshness["locked_exists"]
                ):
                    raise self.error_type(
                        f"Cannot render {story.scene_render_target_service.target_label(normalized_scene, current_target_id)}: "
                        f"{definition.get('name') or subscene_id} is not current. "
                        f"{freshness['stale_reason']} Render and lock that subscene first."
                    )
            projected = (
                story.scene_render_target_service.project_main(normalized_scene, statuses)
                if current_target_id == MAIN_RENDER_TARGET
                else story.scene_render_target_service.project_subscene(normalized_scene, current_target_id)
            )
            references, ir, current_hash = self._compile_projected(projected, story_settings, default_prompt_sections)
            compiled[current_target_id] = (projected, references, ir, current_hash)
            return compiled[current_target_id]

        _, references, ir, render_input_hash = compile_target(target_id)
        ir["source"]["scene_json_path"] = str(scene_builder_path)
        ir["source"]["story_settings_path"] = str(story_settings_path)
        return pipeline_path, scene_builder_path, normalized_scene, references, ir, story_settings_path, final_image_prompt_text(ir), render_input_hash

    def compile_scene_prompt(self, story_slug: str, scene_slug: str, render_target_id: str = MAIN_RENDER_TARGET) -> Path:
        story = self.story
        pipeline_path, scene_builder_path, _, _, ir, story_settings_path, prompt, _ = self._compile(story_slug, scene_slug, render_target_id)
        pipeline_path.mkdir(parents=True, exist_ok=True)
        prompt_path = pipeline_path / "Final_Image_Prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        story._write_json(pipeline_path / "Scene_Render_IR.json", ir)
        story._write_json(
            pipeline_path / "Prompt_Source_Map.json",
            story._scene_prompt_source_map(
                ir, prompt, prompt_path, scene_builder_path, story_settings_path,
                ["Scene_Render_IR.json", "Final_Image_Prompt.md"],
            ),
        )
        return prompt_path

    def stage_scene_render(
        self,
        story_slug: str,
        scene_slug: str,
        render_target_id: str = MAIN_RENDER_TARGET,
        allow_stale_dependencies: bool = False,
    ):
        story = self.story
        safe_story_slug = story.safe_slug(story_slug)
        safe_scene_slug = story.safe_slug(scene_slug)
        target_id = str(render_target_id or MAIN_RENDER_TARGET).strip()
        pipeline_path, scene_builder_path, normalized_scene, references, ir, story_settings_path, prompt, render_input_hash = self._compile(
            safe_story_slug, safe_scene_slug, target_id, allow_stale_dependencies
        )
        if target_id != MAIN_RENDER_TARGET:
            definition = story.scene_render_target_service.definition(normalized_scene, target_id)
            if not definition or not definition.get("enabled"):
                raise self.error_type(f"Scene subscene is disabled: {target_id}")
        pipeline_path.mkdir(parents=True, exist_ok=True)
        final_prompt_path = pipeline_path / "Final_Image_Prompt.md"
        warnings = story.validate_scene_builder_data(normalized_scene)
        brief = local_render_brief(ir, {
            "strict_primary_subject_count": getattr(story.path_service.config, "local_render_strict_primary_subject_count", True),
            "forge_couple_debug_base_pass": getattr(story.path_service.config, "local_render_forge_couple_debug_base_pass", True),
        })
        story._write_json(pipeline_path / "Scene_Render_Validation.json", {"errors": [], "warnings": warnings})
        final_prompt_path.write_text(prompt, encoding="utf-8")
        story._write_json(pipeline_path / "Scene_Render_IR.json", ir)
        story._write_json(pipeline_path / "Local_Render_Brief.json", brief)
        (pipeline_path / "Local_Render_Prompt.md").write_text(local_render_prompt_text(brief), encoding="utf-8")
        artifacts = ["Scene_Render_IR.json", "Final_Image_Prompt.md", "Local_Render_Brief.json", "Local_Render_Prompt.md"]
        if getattr(story.path_service.config, "local_render_layout_backend", "forge_couple_basic") == "forge_couple_basic":
            (pipeline_path / "Local_Render_Forge_Couple_Prompt.md").write_text(local_render_forge_couple_prompt_text(brief), encoding="utf-8")
            artifacts.append("Local_Render_Forge_Couple_Prompt.md")
        else:
            (pipeline_path / "Local_Render_Forge_Couple_Prompt.md").unlink(missing_ok=True)
        story._write_json(
            pipeline_path / "Prompt_Source_Map.json",
            story._scene_prompt_source_map(ir, prompt, final_prompt_path, scene_builder_path, story_settings_path, artifacts),
        )
        story._write_json(pipeline_path / "dependency_manifest.json", {
            "story_slug": safe_story_slug,
            "scene_slug": safe_scene_slug,
            "reference_files": reference_files_payload(references),
        })

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        story._clear_scene_render_queue_items(safe_story_slug, safe_scene_slug, target_id)
        target_token = "" if target_id == MAIN_RENDER_TARGET else f"_{target_id}"
        ask_id = f"Ask_Story_{safe_story_slug}_{safe_scene_slug}{target_token}_RENDER_{stamp}"
        ask_path = Path(story.path_service.config.base_ai_queue_path) / "Manual_Render_Queue" / "Ask" / ask_id
        ask_path.mkdir(parents=True, exist_ok=False)
        expected_output = f"{safe_scene_slug}.png" if target_id == MAIN_RENDER_TARGET else f"{target_id}.png"
        target_paths = story.scene_render_target_service.review_paths(safe_story_slug, safe_scene_slug, target_id)
        manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "asset_id": None, "character": "", "phase": "",
            "pipeline": "Story", "pipeline_stage": "RENDER", "story_slug": safe_story_slug,
            "scene_slug": safe_scene_slug, "ollama_attempt_id": f"{stamp}_{safe_story_slug}_{safe_scene_slug}_RENDER",
            "render_target_id": target_id, "render_input_hash": render_input_hash,
            "worker_type": "manual_chatgpt_render", "ollama_model": "", "prompt_file": "Final_Image_Prompt.md",
            "expected_output": expected_output, "candidate_output_file": expected_output, "task_type": "render",
            "render_preset": "chatgpt-manual", "manual": True,
            "target_output_file": str(target_paths["candidate"]),
            "scene_image_review": True,
            "pipeline_path": str(pipeline_path), "reference_files": reference_files_payload(references),
            "aspect_ratio": str((ir.get("canvas") or {}).get("aspect_ratio") or ""),
        }
        story._write_json(ask_path / "ask_manifest.json", manifest)
        (ask_path / "Final_Image_Prompt.md").write_text(prompt, encoding="utf-8")
        return self.render_task_type(
            story_slug=safe_story_slug, scene_slug=safe_scene_slug, ask_id=ask_id, ask_path=str(ask_path),
            pipeline_path=str(pipeline_path), final_prompt_path=str(final_prompt_path),
            expected_output=expected_output, reference_files=references,
            render_target_id=target_id,
        )
