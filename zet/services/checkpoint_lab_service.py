from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
from typing import Any

from zet.services.comfyui_render_service import compile_ir_to_comfyui_workflow
from zet.services.scene_prompt_sections import load_final_image_prompt_sections
from zet.services.scene_render_compiler import (
    compile_scene_render_ir,
    local_render_brief,
    local_render_prompt_text,
)
from zet.services.stable_matrix_api_compiler import compile_stable_matrix_api_call
from zet.services.view_service import ViewService


class CheckpointLabServiceError(ValueError):
    pass


class CheckpointLabService:
    """Build standalone Checkpoint Lab inputs through Zet's production compilers."""

    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.views = ViewService(self.project_root)

    @staticmethod
    def _normalize_costume(value: str) -> str:
        return " ".join(str(value or "").replace("-", " ").replace("_", " ").casefold().split())

    def _view_token(self, value: str) -> str:
        try:
            return self.views.normalize_token(value)
        except ValueError as exc:
            raise CheckpointLabServiceError(str(exc)) from exc

    def costume_reference_image(
        self,
        *,
        character: str,
        phase: str,
        view: str,
        costume: str,
    ) -> dict[str, str]:
        view_token = self._view_token(view)
        costume_key = self._normalize_costume(costume)
        rows = self.app.story_service.image_reference_rows(
            character,
            "",
            phase,
            costume,
            scope="context",
            include_unavailable=False,
        )
        matches = [
            row
            for row in rows
            if row.pipeline == "Costume-Dressing"
            and row.view
            and self._normalize_costume(row.costume) == costume_key
            and self._view_token(row.view) == view_token
        ]
        if not matches:
            raise CheckpointLabServiceError(
                f"No locked costume reference image found for {character}/{phase}, {view}, {costume}."
            )
        if len(matches) != 1:
            raise CheckpointLabServiceError(
                f"Multiple locked costume reference images found for {character}/{phase}, {view}, {costume}."
            )
        row = matches[0]
        return {
            "image_tag": row.tag,
            "image_path": str(Path(row.image_path).resolve()),
        }

    def _load_json(self, name: str) -> dict[str, Any]:
        path = self.project_root / "Config" / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CheckpointLabServiceError(f"Checkpoint Lab template not found: {path}") from exc
        if not isinstance(data, dict):
            raise CheckpointLabServiceError(f"Checkpoint Lab template must contain a JSON object: {path}")
        return data

    def _scene_ir(
        self,
        *,
        character: str,
        phase: str,
        costume: str,
        reference: dict[str, str],
    ) -> dict[str, Any]:
        scene_path = self.project_root / "Config" / "Checkpoint_Lab_Scene.json"
        settings_path = self.project_root / "Config" / "Checkpoint_Lab_Story_Settings.json"
        scene = copy.deepcopy(self._load_json(scene_path.name))
        story_settings = self._load_json(settings_path.name)
        element_id = self.app.story_service.normalize_scene_element_id(character)
        scene["scene_elements"] = [{
            "id": element_id,
            "display_name": character,
            "resource_type": "Character",
            "element_type": "Character",
            "character": character,
            "phase": phase,
            "costume": costume,
            "aux_category": "",
            "aux_resource_id": "",
            "reference_images": [{"tag": reference["image_tag"]}],
            "element_visual_override": "",
            "fallback_visual_description": "",
            "notes": "",
        }]
        scene["placements"] = [{
            "id": f"placement_{element_id}",
            "scene_element_id": element_id,
            "position_within_cell": "center",
            "depth": "midground",
            "frame_coverage": "",
            "distance_from_camera": "",
            "visual_scale": "",
            "pose": {
                "summary": "",
                "temporary_condition": "",
                "gaze_target_element_id": "",
                "expression": "",
                "left_arm_action": "",
                "right_arm_action": "",
                "leg_foot_detail": "",
                "balance_weight_detail": "",
            },
            "motion": {"state": "stationary", "direction_screen": "", "cue": ""},
            "placement_notes": "",
        }]
        scene["depth_lanes"] = {"foreground": [], "midground": [element_id], "background": []}
        scene["scene"]["story_settings_path"] = str(settings_path)
        references = self.app.story_service.story_reference_service.resolve_scene_references(
            "\n" + json.dumps(scene)
        )
        sections = load_final_image_prompt_sections(
            self.project_root / "Config" / "Prompt_Templates" / "final_image_prompt_tail_v1.md"
        )
        ir = compile_scene_render_ir(
            scene,
            story_settings,
            {
                "references": references,
                "element_sources": self.app.story_service._resolve_scene_element_sources(scene),
            },
            sections,
        )
        ir["source"]["scene_json_path"] = str(scene_path)
        ir["source"]["story_settings_path"] = str(settings_path)
        return ir

    def _profile(self, name: str, image_generation: str) -> tuple[str, dict[str, Any]]:
        profiles = self._load_json("Local_Render_Presets.json")
        profile = profiles.get(name)
        if not isinstance(profile, dict):
            raise CheckpointLabServiceError(f"Unknown render profile: {name}")
        backend = str(profile.get("backend") or "").strip().lower()
        requested = str(image_generation or "").strip().lower().replace("-", "_").replace(" ", "_")
        if requested == "stablematrix":
            requested = "stable_matrix"
        if requested not in {"stable_matrix", "comfyui"}:
            raise CheckpointLabServiceError(f"Unsupported image generation backend: {image_generation}")
        if backend != requested:
            raise CheckpointLabServiceError(
                f"Render profile {name} uses {backend}, not {requested}."
            )
        return requested, profile

    def local_image_recipe(
        self,
        *,
        character: str,
        phase: str,
        view: str,
        costume: str,
        image_generation: str,
        render_profile: str,
        output_path: str | Path | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        reference = self.costume_reference_image(
            character=character,
            phase=phase,
            view=view,
            costume=costume,
        )
        ir = self._scene_ir(
            character=character,
            phase=phase,
            costume=costume,
            reference=reference,
        )
        backend, profile = self._profile(render_profile, image_generation)
        if backend == "comfyui":
            compilation = compile_ir_to_comfyui_workflow(
                ir,
                profile,
                checkpoint=self.app.config.comfyui_checkpoint,
                positive_prompt_globals=self.app.config.comfyui_positive_prompt_globals,
                negative_prompt_globals=self.app.config.comfyui_negative_prompt_globals,
                seed=seed,
                output_prefix="Zet/CheckpointLab",
                reference_files=ir["resolved_sources"]["references"],
                available_node_types={"LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced"},
            )
            api_json = compilation.workflow
            prompts = compilation.prompts
            default_name = "ComfyUI_Workflow_API.json"
        else:
            brief = local_render_brief(ir, {
                "strict_primary_subject_count": self.app.config.local_render_strict_primary_subject_count,
                "forge_couple_debug_base_pass": self.app.config.local_render_forge_couple_debug_base_pass,
            })
            api_json = compile_stable_matrix_api_call(
                local_render_prompt_text(brief),
                profile,
                preset_name=render_profile,
                positive_prompt_globals=self.app.config.local_render_positive_prompt_globals,
                negative_prompt_globals=self.app.config.local_render_negative_prompt_globals,
                checkpoint=self.app.config.local_render_checkpoint,
                aspect_ratio=str(ir.get("canvas", {}).get("aspect_ratio") or ""),
                seed=seed,
            )
            prompts = {
                "global": api_json["payload"]["prompt"],
                "negative": api_json["payload"]["negative_prompt"],
                "regions": [item.get("prompt", "") for item in brief.get("regions", [])],
            }
            default_name = "Stable_Matrix_API_Call.json"
        if output_path is None:
            output = Path(tempfile.mkdtemp(prefix="zet_checkpoint_lab_")) / default_name
        else:
            output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(api_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {
            "api_json_path": str(output.resolve()),
            "image_generation": backend,
            "render_profile": render_profile,
            "reference": reference,
            "prompts": prompts,
        }
