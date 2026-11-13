"""Prepare a character view for the independent Image Generation asset."""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from zet.services.ad_hoc_image_generation_service import (
    IMAGE_GENERATION_MAX_REFERENCE_BYTES,
    IMAGE_GENERATION_MAX_REFERENCES,
)
from zet.services.local_render_policy import require_qwen_profile
from zet.services.render_slot_service import RenderSlotConflict
from zet.services.workflow_storage import file_lock, validate_image


class ImageGeneratorStagingService:
    def __init__(self, workflow, generator):
        self.workflow = workflow
        self.generator = generator

    def stage(self, run_id: str, view: str, costume: str = "", *, recompile: bool = False,
              rotation: bool = False, no_costume_ref: bool = False, render_mode: str = "draft"):
        workflow = self.workflow
        if no_costume_ref and rotation:
            raise ValueError("Stage no Costume Ref cannot be combined with Stage Rotation.")
        if no_costume_ref and workflow.pipeline != "costume-dressing":
            raise ValueError("Stage no Costume Ref is available only for Costume Dressing.")
        from zet.services.image_sizing_service import resolve_image_sizing
        from zet.services.local_view_reference_service import selected_run_for_mode
        ratio = "1:1" if workflow.pipeline in {"head-image", "head-image-edit"} else "2:3"
        sizing = resolve_image_sizing(workflow.app.config, render_mode, ratio)
        run = workflow.prompt_improvement.detail(run_id, costume)
        with file_lock(Path(run["root"]) / "state.lock"), TemporaryDirectory(prefix="zet-stage-view-") as directory:
            run = workflow.prompt_improvement.detail(run_id, costume)
            view = view.upper()
            if view not in run["views"]:
                raise ValueError("Unknown character view.")
            if workflow.pipeline == "costume-dressing":
                from zet.services.costume_render_mode_service import CostumeRenderModeService, render_settings
                run = selected_run_for_mode(run, render_mode)
                resolved = workflow.adapter._locked_view_inputs(run, view, render_mode=render_mode)
                run = {**run, "sources": {**(run.get("sources") or {}), view: resolved}}
                settings = render_settings(run, view)
                if rotation or no_costume_ref:
                    settings = {**settings, "mode": "rotate" if rotation else "doll-dressing-no-ref"}
                modes = CostumeRenderModeService(workflow)
                reason = modes.reason(run, view, settings)
                if reason:
                    raise RenderSlotConflict(reason)
                saved = modes.prepare(run, view, Path(directory), settings=settings)
            elif rotation:
                from zet.services.costume_rotation_service import CostumeRotationService
                saved = CostumeRotationService(workflow).prepare(run, view, Path(directory))
            elif no_costume_ref:
                from zet.services.costume_no_reference_service import CostumeNoReferenceService
                saved = CostumeNoReferenceService().prepare(workflow, run, view, Path(directory))
            else:
                reason = workflow.slots._prerequisite(run, view, render_mode)
                if reason:
                    raise RenderSlotConflict(reason)
                saved = workflow.slots.prepare_input(run, view, Path(directory), recompile=recompile,
                                                     render_mode=render_mode, aspect_ratio=ratio)
            if not saved["prompt"].strip():
                raise ValueError("This view has no image prompt to stage.")
            if len(saved["references"]) > IMAGE_GENERATION_MAX_REFERENCES:
                raise ValueError("Image Generator supports at most 10 references. This view cannot be staged without dropping inputs.")
            profile = require_qwen_profile(workflow.project_root, saved["preset"],
                                           presets_path=self.generator.presets_path)
            if workflow.pipeline == "head-image-edit":
                profile = saved.get("render_settings") or profile
            if workflow.pipeline == "costume-dressing":
                profile = saved.get("render_profile") or profile
            inputs = {
                "universe_style_variant": run.get("universe_style_variant") or "canonical",
                **({"universe_style": run["universe_style"]} if run.get("universe_style") else {}),
                "mode": "img2img" if saved["references"] else "txt2img",
                "prompt": saved["prompt"], "negative_prompt": "",
                "render_mode": render_mode, "aspect_ratio": ratio,
                "reference_images": [],
                "render_config": {"preset": saved["preset"],
                                  "checkpoint": str(profile.get("diffusion_model") or ""),
                                  "disable_prompt_globals": bool(profile.get("disable_prompt_globals", False)),
                                  "append_reference_labels": False},
            }
            if workflow.pipeline in {"head-image-edit", "costume-dressing"}:
                inputs["render_config"]["overrides"] = {key: profile[key] for key in
                    ("steps", "cfg", "sampler_name", "scheduler", "denoise", "text_encoder", "vae") if key in profile}
            self.generator.render_configuration(inputs, inputs["mode"])
            inputs["reference_images"] = self._encode_references(saved["references"])
        # Persist the validated recipe in a new asset.
        asset = self.generator.slot_workspace.create_asset(f"{run_id} - {view}"[:160], inputs)
        return {"asset_id": asset["asset_id"]}

    def stage_container(self, character, phase, pipeline, costume, view, payload):
        workflow = self.workflow
        container = workflow.detail(character, phase, pipeline, costume)
        if container["revision"] != payload.get("expected_revision"):
            raise RenderSlotConflict("The character container changed. Refresh and stage again.")
        render_mode = str(payload.get("render_mode") or "draft")
        aspect_ratio = str(payload.get("aspect_ratio") or container["render_settings"]["aspect_ratio"])
        self.generator.sizing(render_mode, aspect_ratio)
        style_mode = str(payload.get("assembly_style_mode") or "")
        compiled = workflow.compile_prompt(character, phase, pipeline, costume, view,
            render_mode=render_mode, apply_phase_change=payload.get("apply_phase_change") is True,
            assembly_style_mode=style_mode, costume_settings=payload.get("costume_settings"))
        references = compiled["reference_inputs"]
        preset = workflow._preset(pipeline, bool(references), view, style_mode)
        profile = require_qwen_profile(self.generator.project_root, preset, presets_path=self.generator.presets_path)
        inputs = {
            "mode": "img2img" if references else "txt2img", "prompt": compiled["prompt"],
            "negative_prompt": "", "aspect_ratio": aspect_ratio,
            "reference_images": self._encode_references(references),
            "render_config": {
                "preset": preset,
                "checkpoint": str(profile.get("diffusion_model") or ""),
                "append_reference_labels": False,
                "disable_prompt_globals": bool(profile.get("disable_prompt_globals", False)),
                "overrides": {key: profile[key] for key in
                              ("steps", "cfg", "sampler_name", "scheduler", "denoise", "text_encoder", "vae")
                              if key in profile},
            },
        }
        self.generator.render_configuration(inputs, inputs["mode"])
        name = " - ".join(filter(None, (character, phase, costume or pipeline, view)))
        asset = self.generator.slot_workspace.create_asset(name[:160], inputs)
        return {"asset_id": asset["asset_id"]}

    @staticmethod
    def _encode_references(references):
        if len(references) > IMAGE_GENERATION_MAX_REFERENCES:
            raise ValueError(f"Image Generation accepts up to {IMAGE_GENERATION_MAX_REFERENCES} references.")
        encoded = []
        for index, reference in enumerate(references, 1):
            contents = Path(reference["path"]).read_bytes()
            if len(contents) > IMAGE_GENERATION_MAX_REFERENCE_BYTES:
                raise ValueError(f"Reference image {index} exceeds Image Generator's 20 MiB limit.")
            validate_image(contents)
            with Image.open(BytesIO(contents)) as image:
                mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
            if not mime:
                raise ValueError(f"Reference image {index} must be PNG, JPEG or WebP.")
            encoded.append({
                "label": str(reference.get("label") or reference.get("prompt_role") or reference.get("role") or f"Image {index}"),
                "image": f"data:{mime};base64," + base64.b64encode(contents).decode("ascii"),
                "metadata": {key: reference[key] for key in
                             ("role", "prompt_role", "image_index", "view", "source_view", "render_mode") if key in reference},
            })
        return encoded
