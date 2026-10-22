"""Prepare a character view for the independent Image Generator workspace."""
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
from zet.services.comfyui_render_service import _render_size
from zet.services.local_render_policy import require_qwen_profile
from zet.services.render_slot_service import RenderSlotConflict
from zet.services.workflow_storage import file_lock, validate_image


class ImageGeneratorStagingService:
    def __init__(self, workflow, generator):
        self.workflow = workflow
        self.generator = generator

    def stage(self, run_id: str, view: str, costume: str = "", *, recompile: bool = False, rotation: bool = False):
        workflow = self.workflow
        run = workflow.prompt_improvement.detail(run_id, costume)
        with file_lock(Path(run["root"]) / "state.lock"), TemporaryDirectory(prefix="zet-stage-view-") as directory:
            run = workflow.prompt_improvement.detail(run_id, costume)
            view = view.upper()
            if view not in run["views"]:
                raise ValueError("Unknown character view.")
            if rotation:
                from zet.services.costume_rotation_service import CostumeRotationService
                saved = CostumeRotationService(workflow).prepare(run, view, Path(directory))
            else:
                reason = workflow.slots._prerequisite(run, view)
                if reason:
                    raise RenderSlotConflict(reason)
                saved = workflow.slots.prepare_input(run, view, Path(directory), recompile=recompile)
            if not saved["prompt"].strip():
                raise ValueError("This view has no image prompt to stage.")
            if len(saved["references"]) > IMAGE_GENERATION_MAX_REFERENCES:
                raise ValueError("Image Generator supports at most 10 references. This view cannot be staged without dropping inputs.")
            profile = require_qwen_profile(workflow.project_root, saved["preset"],
                                           presets_path=self.generator.presets_path)
            if workflow.pipeline == "head-image-edit":
                profile = saved.get("render_settings") or profile
            width, height = _render_size(None, profile)
            inputs = {
                "mode": "img2img" if saved["references"] else "txt2img",
                "prompt": saved["prompt"], "negative_prompt": "",
                "width": self.generator._dimension(width, "Width"),
                "height": self.generator._dimension(height, "Height"),
                "reference_images": [],
                "render_config": {"preset": saved["preset"],
                                  "checkpoint": str(profile.get("diffusion_model") or ""),
                                  "disable_prompt_globals": bool(profile.get("disable_prompt_globals", False)),
                                  "append_reference_labels": False},
            }
            if workflow.pipeline == "head-image-edit":
                inputs["render_config"]["overrides"] = {key: profile[key] for key in
                    ("steps", "cfg", "sampler_name", "scheduler", "denoise", "text_encoder", "vae") if key in profile}
            self.generator.render_configuration(inputs, inputs["mode"])
            for index, reference in enumerate(saved["references"], 1):
                contents = Path(reference["path"]).read_bytes()
                if len(contents) > IMAGE_GENERATION_MAX_REFERENCE_BYTES:
                    raise ValueError(f"Reference image {index} exceeds Image Generator's 20 MiB limit.")
                validate_image(contents)
                with Image.open(BytesIO(contents)) as image:
                    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image.format)
                if not mime:
                    raise ValueError(f"Reference image {index} must be PNG, JPEG or WebP.")
                inputs["reference_images"].append({
                    "label": str(reference.get("label") or reference.get("prompt_role") or reference.get("role") or f"Image {index}"),
                    "image": f"data:{mime};base64," + base64.b64encode(contents).decode("ascii"),
                    "metadata": {key: reference[key] for key in
                                 ("role", "prompt_role", "image_index", "view", "source_view") if key in reference},
                })
        # Preparation must succeed before detaching any existing results.
        return {"inputs": inputs, "workspace": self.generator.slot_workspace.reset_for_staging()}
