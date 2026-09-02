from __future__ import annotations

import copy
from datetime import datetime
import json
from pathlib import Path
import re
import tempfile
import time
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from zet.services.comfyui_render_service import (
    compile_ir_to_comfyui_workflow,
    compile_prompt_to_comfyui_workflow,
    list_comfyui_node_types,
    run_comfyui_workflow,
)
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
            "pose": {
                "summary": "",
                "gaze_target_element_id": "",
                "expression": "",
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
        checkpoint: str | None = None,
        profile_overrides: dict[str, Any] | None = None,
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
        profile = {**profile, **(profile_overrides or {})}
        selected_checkpoint = str(checkpoint or (
            self.app.config.comfyui_checkpoint
            if backend == "comfyui"
            else self.app.config.local_render_checkpoint
        ))
        if backend == "comfyui":
            compilation = compile_ir_to_comfyui_workflow(
                ir,
                profile,
                checkpoint=selected_checkpoint,
                positive_prompt_globals=self.app.config.comfyui_positive_prompt_globals,
                negative_prompt_globals=self.app.config.comfyui_negative_prompt_globals,
                seed=seed,
                output_prefix="Zet/CheckpointLab",
                reference_files=ir["resolved_sources"]["references"],
                available_node_types={"LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced"},
            )
            api_json = compilation.workflow
            prompts = compilation.prompts
            reference_files = compilation.debug.get("references_used", [])
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
                checkpoint=selected_checkpoint,
                aspect_ratio=str(ir.get("canvas", {}).get("aspect_ratio") or ""),
                seed=seed,
            )
            prompts = {
                "global": api_json["payload"]["prompt"],
                "negative": api_json["payload"]["negative_prompt"],
                "regions": [item.get("prompt", "") for item in brief.get("regions", [])],
            }
            reference_files = []
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
            "profile_settings": profile,
            "checkpoint": selected_checkpoint,
            "reference": reference,
            "reference_files": reference_files,
            "prompts": prompts,
        }

    @staticmethod
    def _path_token(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-_") or "condition"

    @staticmethod
    def _contact_sheet(records: list[dict[str, Any]], output_path: Path) -> None:
        cell_width, cell_height, label_height = 320, 480, 56
        columns = min(4, max(1, len(records)))
        rows = (len(records) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_width, rows * (cell_height + label_height)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, record in enumerate(records):
            with Image.open(record["image_path"]) as source:
                image = ImageOps.contain(source.convert("RGB"), (cell_width, cell_height))
            x = (index % columns) * cell_width
            y = (index // columns) * (cell_height + label_height)
            sheet.paste(image, (x + (cell_width - image.width) // 2, y + (cell_height - image.height) // 2))
            label = f"{record['candidate_id']}\nseed {record['seed']}"
            draw.multiline_text((x + 6, y + cell_height + 4), label, fill="black", spacing=2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)

    def run_comfyui_reference_matrix(
        self,
        *,
        character: str,
        phase: str,
        view: str,
        costume: str,
        render_profile: str,
        checkpoints: list[str],
        reference_weights: list[float],
        seeds: list[int],
        output_dir: str | Path,
    ) -> dict[str, Any]:
        if not checkpoints or not reference_weights or not seeds:
            raise CheckpointLabServiceError("Checkpoint, reference weight, and seed lists cannot be empty.")
        if any(weight < 0 or weight > 2 for weight in reference_weights):
            raise CheckpointLabServiceError("IP-Adapter reference weights must be between 0 and 2.")
        root = Path(output_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, Any]] = []
        for checkpoint in checkpoints:
            for weight in reference_weights:
                for seed in seeds:
                    candidate_id = f"c{len(records) + 1:03d}"
                    condition = self._path_token(f"{checkpoint}-w{weight:g}-s{seed}")
                    candidate_dir = root / condition
                    recipe = self.local_image_recipe(
                        character=character,
                        phase=phase,
                        view=view,
                        costume=costume,
                        image_generation="comfyui",
                        render_profile=render_profile,
                        output_path=candidate_dir / "ComfyUI_Workflow_API.json",
                        seed=seed,
                        checkpoint=checkpoint,
                        profile_overrides={"character_reference_weight": weight},
                    )
                    workflow = json.loads(Path(recipe["api_json_path"]).read_text(encoding="utf-8"))
                    started = time.perf_counter()
                    result = run_comfyui_workflow(
                        workflow,
                        server_url=self.app.config.comfyui_server_url,
                        output_dir=candidate_dir / "images",
                        reference_files=recipe["reference_files"],
                        poll_seconds=self.app.config.comfyui_poll_seconds,
                        timeout_seconds=self.app.config.comfyui_timeout_seconds,
                    )
                    records.append({
                        "candidate_id": candidate_id,
                        "checkpoint": checkpoint,
                        "reference_weight": weight,
                        "seed": seed,
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                        "image_path": str(result.image_paths[0]),
                        "workflow_path": recipe["api_json_path"],
                        "prompt_id": result.prompt_id,
                    })
        contact_sheet = root / "contact_sheet.png"
        self._contact_sheet(records, contact_sheet)
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "character": character,
            "phase": phase,
            "view": view,
            "costume": costume,
            "render_profile": render_profile,
            "rubric": str((self.project_root / "Config" / "Image_Quality_Rubric.json").resolve()),
            "contact_sheet": str(contact_sheet),
            "candidates": records,
        }
        manifest_path = root / "experiment.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {**manifest, "manifest_path": str(manifest_path)}

    def run_comfyui_prompt_matrix(
        self,
        *,
        positive_prompt: str,
        negative_prompt: str,
        reference_image: str | Path,
        pose_image: str | Path | None,
        render_profile: str,
        checkpoints: list[str],
        reference_weights: list[float],
        seeds: list[int],
        output_dir: str | Path,
    ) -> dict[str, Any]:
        if not positive_prompt.strip():
            raise CheckpointLabServiceError("Positive prompt cannot be empty.")
        if not checkpoints or not reference_weights or not seeds:
            raise CheckpointLabServiceError("Checkpoint, reference weight, and seed lists cannot be empty.")
        if any(weight < 0 or weight > 2 for weight in reference_weights):
            raise CheckpointLabServiceError("IP-Adapter reference weights must be between 0 and 2.")
        reference_path = Path(reference_image).expanduser().resolve()
        if not reference_path.is_file():
            raise CheckpointLabServiceError(f"Reference image not found: {reference_path}")
        pose_path = Path(pose_image).expanduser().resolve() if pose_image else None
        if pose_path is not None and not pose_path.is_file():
            raise CheckpointLabServiceError(f"Pose image not found: {pose_path}")
        _backend, base_profile = self._profile(render_profile, "comfyui")
        root = Path(output_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        node_types = list_comfyui_node_types(self.app.config.comfyui_server_url)
        records: list[dict[str, Any]] = []
        for checkpoint in checkpoints:
            for weight in reference_weights:
                for seed in seeds:
                    candidate_id = f"c{len(records) + 1:03d}"
                    condition = self._path_token(f"{checkpoint}-w{weight:g}-s{seed}")
                    candidate_dir = root / condition
                    profile = {**base_profile, "character_reference_weight": weight}
                    references = [{
                        "role": "prompt_evolution_appearance",
                        "path": str(reference_path),
                    }]
                    if pose_path is not None:
                        references.append({"role": "prompt_evolution_pose", "path": str(pose_path)})
                    compilation = compile_prompt_to_comfyui_workflow(
                        positive_prompt,
                        negative_prompt,
                        profile,
                        checkpoint=checkpoint,
                        positive_prompt_globals=self.app.config.comfyui_positive_prompt_globals,
                        negative_prompt_globals=self.app.config.comfyui_negative_prompt_globals,
                        seed=seed,
                        output_prefix="Zet/ImageRecipeLab",
                        reference_files=references,
                        available_node_types=node_types,
                    )
                    candidate_dir.mkdir(parents=True, exist_ok=True)
                    workflow_path = candidate_dir / "ComfyUI_Workflow_API.json"
                    workflow_path.write_text(
                        json.dumps(compilation.workflow, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    started = time.perf_counter()
                    result = run_comfyui_workflow(
                        compilation.workflow,
                        server_url=self.app.config.comfyui_server_url,
                        output_dir=candidate_dir / "images",
                        reference_files=compilation.debug["references_used"],
                        poll_seconds=self.app.config.comfyui_poll_seconds,
                        timeout_seconds=self.app.config.comfyui_timeout_seconds,
                    )
                    records.append({
                        "candidate_id": candidate_id,
                        "checkpoint": checkpoint,
                        "reference_weight": weight,
                        "seed": seed,
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                        "image_path": str(result.image_paths[0]),
                        "workflow_path": str(workflow_path),
                        "prompt_id": result.prompt_id,
                    })
        contact_sheet = root / "contact_sheet.png"
        self._contact_sheet(records, contact_sheet)
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "render_profile": render_profile,
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "reference_image": str(reference_path),
            "pose_image": str(pose_path) if pose_path else "",
            "rubric": str((self.project_root / "Config" / "Image_Quality_Rubric.json").resolve()),
            "contact_sheet": str(contact_sheet),
            "candidates": records,
        }
        manifest_path = root / "experiment.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {**manifest, "manifest_path": str(manifest_path)}
