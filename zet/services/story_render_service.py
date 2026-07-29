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


class StoryRenderService:
    """Compile Scene Builder documents and stage story render tasks."""

    def __init__(self, story_service, reference_service, render_task_type, error_type):
        self.story = story_service
        self.reference_service = reference_service
        self.render_task_type = render_task_type
        self.error_type = error_type

    def _compile(self, story_slug: str, scene_slug: str) -> tuple[Path, Path, dict, list[dict], dict, Path, str]:
        story = self.story
        safe_story_slug = story.safe_slug(story_slug)
        safe_scene_slug = story.safe_slug(scene_slug)
        pipeline_path = story.scene_pipeline_path(safe_story_slug, safe_scene_slug)
        pipeline_path.mkdir(parents=True, exist_ok=True)
        scene_builder_path = story.scene_builder_json_path(safe_story_slug, safe_scene_slug)
        if not scene_builder_path.exists():
            raise self.error_type(f"Scene Builder JSON not found: {scene_builder_path}")
        scene_builder_data = json.loads(scene_builder_path.read_text(encoding="utf-8"))
        references = self.reference_service.resolve_scene_references("\n" + json.dumps(scene_builder_data))
        normalized_scene = story._normalize_scene_builder_data(safe_story_slug, safe_scene_slug, scene_builder_data)
        story_settings_path = story._library_absolute_path(str(normalized_scene.get("scene", {}).get("story_settings_path") or ""))
        if not story_settings_path.exists():
            raise self.error_type(f"Story settings file not found: {story_settings_path}")
        sections_path = story._project_config_path("Prompt_Templates", "final_image_prompt_tail_v1.md")
        try:
            default_prompt_sections = load_final_image_prompt_sections(sections_path)
        except (OSError, ValueError) as exc:
            raise self.error_type(f"Invalid final image prompt sections template {sections_path}: {exc}") from exc
        ir = compile_scene_render_ir(
            normalized_scene,
            story.load_story_settings(story_settings_path),
            {"references": references, "element_sources": story._resolve_scene_element_sources(normalized_scene)},
            default_prompt_sections,
        )
        ir["source"]["scene_json_path"] = str(scene_builder_path)
        ir["source"]["story_settings_path"] = str(story_settings_path)
        return pipeline_path, scene_builder_path, normalized_scene, references, ir, story_settings_path, final_image_prompt_text(ir)

    def compile_scene_prompt(self, story_slug: str, scene_slug: str) -> Path:
        story = self.story
        pipeline_path, scene_builder_path, _, _, ir, story_settings_path, prompt = self._compile(story_slug, scene_slug)
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

    def stage_scene_render(self, story_slug: str, scene_slug: str):
        story = self.story
        safe_story_slug = story.safe_slug(story_slug)
        safe_scene_slug = story.safe_slug(scene_slug)
        pipeline_path, scene_builder_path, normalized_scene, references, ir, story_settings_path, prompt = self._compile(
            safe_story_slug, safe_scene_slug
        )
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
        story._clear_scene_render_queue_items(safe_story_slug, safe_scene_slug)
        ask_id = f"Ask_Story_{safe_story_slug}_{safe_scene_slug}_RENDER_{stamp}"
        ask_path = Path(story.path_service.config.base_ai_queue_path) / "Manual_Render_Queue" / "Ask" / ask_id
        ask_path.mkdir(parents=True, exist_ok=False)
        expected_output = f"{safe_scene_slug}.png"
        manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "asset_id": None, "character": "", "phase": "",
            "pipeline": "Story", "pipeline_stage": "RENDER", "story_slug": safe_story_slug,
            "scene_slug": safe_scene_slug, "ollama_attempt_id": f"{stamp}_{safe_story_slug}_{safe_scene_slug}_RENDER",
            "worker_type": "manual_chatgpt_render", "ollama_model": "", "prompt_file": "Final_Image_Prompt.md",
            "expected_output": expected_output, "candidate_output_file": expected_output, "task_type": "render",
            "render_preset": "chatgpt-manual", "manual": True,
            "target_output_file": str(story.path_service.story_folder_path(safe_story_slug) / expected_output),
            "pipeline_path": str(pipeline_path), "reference_files": reference_files_payload(references),
            "aspect_ratio": str((ir.get("canvas") or {}).get("aspect_ratio") or ""),
        }
        story._write_json(ask_path / "ask_manifest.json", manifest)
        (ask_path / "Final_Image_Prompt.md").write_text(prompt, encoding="utf-8")
        return self.render_task_type(
            story_slug=safe_story_slug, scene_slug=safe_scene_slug, ask_id=ask_id, ask_path=str(ask_path),
            pipeline_path=str(pipeline_path), final_prompt_path=str(final_prompt_path),
            expected_output=expected_output, reference_files=references,
        )
