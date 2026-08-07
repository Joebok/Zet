from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import secrets
import shutil
from typing import Any

import cv2
import numpy as np
from PIL import Image

from zet.services.comfyui_render_service import (
    comfyui_model_options,
    list_comfyui_node_types,
    run_comfyui_workflow,
)
from zet.services.head_fitment_mask_generation_service import improved_foreground_mask


MASK_REMOVE = 0
MASK_EDIT = 128
MASK_PROTECT = 255
HEAD_FITMENT_INPAINT_NODES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "ImageToMask",
    "KSampler",
    "LoadImage",
    "SaveImage",
    "VAEDecode",
    "VAEEncodeForInpaint",
}
HEAD_FITMENT_CHECKPOINT_SHA256 = "aea4ec6c4d248fb9cdc3209bcbf3fccb05acb1a2a901d3f1e805e39810ed0b09"
HEAD_FITMENT_CHECKPOINT_LOCATION = (
    r"D:\Comfy-Desktop\ComfyUI-Shared\models\checkpoints\perfectdeliberate_v90.safetensors"
)


def compile_head_fitment_inpaint_workflow(
    *,
    init_input: str,
    mask_input: str,
    checkpoint: str,
    prompt: str,
    negative_prompt: str,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
    grow_mask_by: int,
    seed: int,
    output_prefix: str,
) -> dict[str, Any]:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "LoadImage", "inputs": {"image": init_input}},
        "3": {"class_type": "LoadImage", "inputs": {"image": mask_input}},
        "4": {"class_type": "ImageToMask", "inputs": {"image": ["3", 0], "channel": "red"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "7": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["2", 0], "vae": ["1", 2], "mask": ["4", 0], "grow_mask_by": grow_mask_by},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "denoise": denoise,
            },
        },
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": output_prefix, "images": ["9", 0]}},
    }


class HeadFitmentEditError(Exception):
    pass


@dataclass(frozen=True)
class HeadFitmentEditPaths:
    mask: Path
    spec: Path
    init: Path
    model_requirements: Path
    render_metadata: Path
    diagnostics: Path


class HeadFitmentEditService:
    """Prepare and render mask-constrained Head-Fitment edits."""

    def __init__(self, asset_repository, path_service):
        self.asset_repository = asset_repository
        self.path_service = path_service

    def paths(self, asset) -> HeadFitmentEditPaths:
        root = self.path_service.pipeline_path(asset)
        return HeadFitmentEditPaths(
            mask=root / "Head_Fitment_Edit_Mask.png",
            spec=root / "Head_Fitment_Edit.json",
            init=root / "Head_Fitment_Init.png",
            model_requirements=root / "Head_Fitment_Model_Requirements.json",
            render_metadata=root / "Head_Fitment_Render_Metadata.json",
            diagnostics=root / "Head_Fitment_Mask_Diagnostics",
        )

    @staticmethod
    def _reference(asset, *roles: str) -> dict:
        for reference in asset.reference_files or []:
            if isinstance(reference, dict) and reference.get("role") in roles:
                path = Path(str(reference.get("path") or ""))
                if path.is_file():
                    return reference
        raise HeadFitmentEditError(f"Missing valid reference role: {' or '.join(roles)}")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _foreground_mask(image: Image.Image) -> np.ndarray:
        return improved_foreground_mask(image)

    @classmethod
    def _body_neck_ratio(cls, body_image: Image.Image) -> float:
        foreground = cls._foreground_mask(body_image)
        h, _ = foreground.shape
        widths: list[int] = []
        for y in range(max(0, int(h * 0.04)), min(h, int(h * 0.28))):
            xs = np.where(foreground[y])[0]
            widths.append(int(xs[-1] - xs[0] + 1) if len(xs) else 0)
        nonzero = [width for width in widths if width]
        if not nonzero:
            return 0.30
        head_width = max(nonzero[: max(1, len(nonzero) // 2)])
        neck_window = nonzero[len(nonzero) // 2 :]
        neck_width = min(neck_window) if neck_window else min(nonzero)
        return float(np.clip(neck_width / max(1, head_width), 0.18, 0.55))

    @classmethod
    def _default_mask(cls, head_image: Image.Image, body_image: Image.Image) -> tuple[np.ndarray, dict[str, Any]]:
        foreground = cls._foreground_mask(head_image)
        h, w = foreground.shape
        ys, xs = np.where(foreground)
        if not len(xs):
            raise HeadFitmentEditError("Unable to identify foreground in Head-Image source.")
        center_x = int(np.median(xs))
        head_width = int(xs.max() - xs.min() + 1)
        neck_ratio = cls._body_neck_ratio(body_image)
        jaw_y = int(h * 0.67)
        cut_y = min(h - 1, int(h * 0.84))
        top_half = max(8, int(head_width * max(0.09, neck_ratio * 0.36)))
        bottom_half = max(8, int(head_width * neck_ratio * 0.50))
        polygon = np.array(
            [[center_x - top_half, jaw_y], [center_x + top_half, jaw_y],
             [center_x + bottom_half, cut_y], [center_x - bottom_half, cut_y]],
            dtype=np.int32,
        )
        editable = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(editable, polygon, 1)
        editable = editable.astype(bool)
        retained = foreground & (np.indices((h, w))[0] <= cut_y)
        protected = retained & ~editable
        mask = np.full((h, w), MASK_REMOVE, np.uint8)
        mask[editable] = MASK_EDIT
        mask[protected] = MASK_PROTECT
        return mask, {
            "jaw_y": jaw_y,
            "cut_y": cut_y,
            "center_x": center_x,
            "body_neck_to_head_ratio": round(neck_ratio, 5),
        }

    @staticmethod
    def _save_init(source: Image.Image, mask: np.ndarray, path: Path) -> None:
        rgba = np.array(source.convert("RGBA"))
        rgba[:, :, 3] = np.where(mask > MASK_REMOVE, 255, 0).astype(np.uint8)
        Image.fromarray(rgba, "RGBA").save(path)

    def initialize(self, character: str, phase: str, asset_id: int) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Head-Fitment":
            raise HeadFitmentEditError("Masked edit is only available for Head-Fitment assets.")
        head_ref = self._reference(asset, "head_image", "headshot")
        body_ref = self._reference(asset, "body_reference")
        head_path = Path(str(head_ref["path"]))
        body_path = Path(str(body_ref["path"]))
        paths = self.paths(asset)
        paths.mask.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(head_path) as head_image, Image.open(body_path) as body_image:
            mask, geometry = self._default_mask(head_image, body_image)
            Image.fromarray(mask, "L").save(paths.mask)
            self._save_init(head_image, mask, paths.init)
            source_size = [head_image.width, head_image.height]
        spec = {
            "schema_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "head_image_path": str(head_path),
            "head_image_sha256": self._sha256(head_path),
            "body_reference_path": str(body_path),
            "body_reference_sha256": self._sha256(body_path),
            "source_size": source_size,
            "mask_values": {"remove": MASK_REMOVE, "edit": MASK_EDIT, "protect": MASK_PROTECT},
            "geometry": geometry,
            "confirmed": False,
        }
        paths.spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        return self.context(character, phase, asset_id)

    def save_mask(self, character: str, phase: str, asset_id: int, contents: bytes) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        paths = self.paths(asset)
        if not paths.spec.exists():
            raise HeadFitmentEditError("Initialize the masked edit before saving its mask.")
        spec = json.loads(paths.spec.read_text(encoding="utf-8"))
        head_path = Path(str(spec["head_image_path"]))
        with Image.open(BytesIO(contents)) as uploaded, Image.open(head_path) as source:
            mask = np.array(uploaded.convert("L"))
            if mask.shape != (source.height, source.width):
                raise HeadFitmentEditError("Edit mask dimensions must match the Head-Image source.")
            normalized = np.where(mask >= 192, MASK_PROTECT, np.where(mask >= 64, MASK_EDIT, MASK_REMOVE)).astype(np.uint8)
            if not np.any(normalized == MASK_EDIT):
                raise HeadFitmentEditError("Edit mask must contain an editable neck region.")
            if not np.any(normalized == MASK_PROTECT):
                raise HeadFitmentEditError("Edit mask must contain a protected head region.")
            Image.fromarray(normalized, "L").save(paths.mask)
            self._save_init(source, normalized, paths.init)
        spec["confirmed"] = True
        spec["auto_confirmed"] = False
        spec["confirmation_source"] = "manual"
        spec["updated_at"] = datetime.now().isoformat(timespec="seconds")
        paths.spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        return self.context(character, phase, asset_id)

    def install_generated_mask(
        self,
        character: str,
        phase: str,
        asset_id: int,
        generated_mask: Path,
        report: dict[str, Any],
        *,
        source_ask_id: str,
        auto_confirm: bool,
        threshold: float,
        replace_confirmed: bool = False,
    ) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        current = self.context(character, phase, asset_id)
        if current["confirmed"] and current["current"] and not replace_confirmed:
            return {**current, "generation_install": "preserved_confirmed"}
        head_path = Path(str(self._reference(asset, "head_image", "headshot")["path"]))
        body_path = Path(str(self._reference(asset, "body_reference")["path"]))
        paths = self.paths(asset)
        with Image.open(generated_mask) as uploaded, Image.open(head_path) as source:
            normalized = np.array(uploaded.convert("L"))
            if normalized.shape != (source.height, source.width):
                raise HeadFitmentEditError("Generated mask dimensions must match the Head-Image source.")
            normalized = np.where(
                normalized >= 192,
                MASK_PROTECT,
                np.where(normalized >= 64, MASK_EDIT, MASK_REMOVE),
            ).astype(np.uint8)
            if not np.any(normalized == MASK_EDIT) or not np.any(normalized == MASK_PROTECT):
                raise HeadFitmentEditError("Generated mask is missing editable or protected pixels.")
            paths.mask.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(normalized, "L").save(paths.mask)
            self._save_init(source, normalized, paths.init)
            source_size = [source.width, source.height]
        score = float(report.get("confidence_score") or 0.0)
        failures = [str(item) for item in report.get("validation_failures", [])]
        confirmed = bool(auto_confirm and score >= threshold and not failures)
        spec = {
            "schema_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "head_image_path": str(head_path),
            "head_image_sha256": self._sha256(head_path),
            "body_reference_path": str(body_path),
            "body_reference_sha256": self._sha256(body_path),
            "source_size": source_size,
            "mask_values": {"remove": MASK_REMOVE, "edit": MASK_EDIT, "protect": MASK_PROTECT},
            "geometry": report.get("geometry") or {},
            "generation_method": "comfyui_ensemble",
            "source_ask_id": source_ask_id,
            "confidence_score": score,
            "validation": report.get("components") or {},
            "validation_failures": failures,
            "geometry_strategy": report.get("geometry_strategy"),
            "mediapipe_accepted": bool(report.get("mediapipe_accepted")),
            "nape_anchor": (report.get("geometry") or {}).get("nape_anchor"),
            "shoulder_line": (report.get("geometry") or {}).get("shoulder_line"),
            "editable_area_ratio": (report.get("geometry") or {}).get("editable_area_ratio"),
            "rejection_history": (current.get("spec") or {}).get("rejection_history") or [],
            "confirmed": confirmed,
            "auto_confirmed": confirmed,
            "confirmation_source": "automation" if confirmed else None,
        }
        paths.spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        return self.context(character, phase, asset_id)

    def reject_mask(
        self,
        character: str,
        phase: str,
        asset_id: int,
        reason: str,
    ) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        paths = self.paths(asset)
        if not paths.spec.is_file() or not paths.mask.is_file():
            raise HeadFitmentEditError("Head-Fitment mask and specification are required before rejection.")
        reason = reason.strip()
        if not reason:
            raise HeadFitmentEditError("Mask rejection reason cannot be blank.")
        spec = json.loads(paths.spec.read_text(encoding="utf-8"))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        rejected_root = paths.diagnostics / "rejected"
        archive = rejected_root / stamp
        temporary = rejected_root / f".{stamp}.tmp"
        temporary.mkdir(parents=True, exist_ok=False)
        try:
            for source in (paths.mask, paths.init, paths.spec):
                if source.is_file():
                    shutil.copy2(source, temporary / source.name)
            for name in ("Head_Fitment_Mask_Overlay.png", "Head_Fitment_Mask_Score.json"):
                source = paths.diagnostics / name
                if source.is_file():
                    shutil.copy2(source, temporary / name)
            rejection = {
                "rejected_at": datetime.now().isoformat(timespec="seconds"),
                "reason": reason,
                "source_ask_id": spec.get("source_ask_id"),
                "confidence_score": spec.get("confidence_score"),
                "confirmation_source": spec.get("confirmation_source"),
            }
            (temporary / "rejection.json").write_text(json.dumps(rejection, indent=2) + "\n", encoding="utf-8")
            temporary.rename(archive)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        history = list(spec.get("rejection_history") or [])
        history.append({**rejection, "archive_path": str(archive)})
        spec.update(
            {
                "confirmed": False,
                "auto_confirmed": False,
                "confirmation_source": None,
                "rejection_history": history,
                "last_rejection_reason": reason,
            }
        )
        replacement = paths.spec.with_suffix(".json.tmp")
        replacement.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        replacement.replace(paths.spec)
        return self.context(character, phase, asset_id)

    def _spec_current(self, asset, spec: dict[str, Any]) -> bool:
        try:
            head_path = Path(str(self._reference(asset, "head_image", "headshot")["path"]))
            body_path = Path(str(self._reference(asset, "body_reference")["path"]))
            return (
                spec.get("head_image_sha256") == self._sha256(head_path)
                and spec.get("body_reference_sha256") == self._sha256(body_path)
            )
        except (HeadFitmentEditError, OSError):
            return False

    def _preset(self, preset_name: str | None = None) -> dict[str, Any]:
        name = str(preset_name or self.path_service.config.head_fitment_masked_local_preset)
        path = self.path_service.project_root / "Config" / "Local_Render_Presets.json"
        try:
            preset = json.loads(path.read_text(encoding="utf-8")).get(name, {})
        except (OSError, json.JSONDecodeError):
            preset = {}
        if not isinstance(preset, dict) or preset.get("backend") != "comfyui" or not preset.get("supports_masks"):
            raise HeadFitmentEditError(f"Masked-local preset is missing or not mask-capable: {name}")
        return preset

    def model_requirements(
        self,
        preset_name: str | None = None,
        checkpoint: str | None = None,
    ) -> dict[str, Any]:
        preset_name = str(preset_name or self.path_service.config.head_fitment_masked_local_preset)
        preset = self._preset(preset_name)
        server_url = str(self.path_service.config.comfyui_server_url)
        configured = str(
            checkpoint
            or self.path_service.config.head_fitment_masked_local_checkpoint
            or preset.get("checkpoint")
            or self.path_service.config.local_render_checkpoint
        ).strip()
        available_nodes = list_comfyui_node_types(server_url)
        missing_nodes = sorted(HEAD_FITMENT_INPAINT_NODES - available_nodes)
        installed = comfyui_model_options(server_url, "CheckpointLoaderSimple", "ckpt_name")
        match = next((name for name in installed if name.replace("\\", "/").split("/")[-1] == configured), None)
        checkpoint_path = Path(HEAD_FITMENT_CHECKPOINT_LOCATION)
        actual_sha256 = self._sha256(checkpoint_path) if checkpoint_path.is_file() else ""
        hash_valid = actual_sha256.lower() == HEAD_FITMENT_CHECKPOINT_SHA256
        requirements = {
            "schema_version": 1,
            "backend": "comfyui",
            "server_url": server_url,
            "preset": preset_name,
            "required_nodes": sorted(HEAD_FITMENT_INPAINT_NODES),
            "missing_nodes": missing_nodes,
            "models": [
                {
                    "kind": "checkpoint",
                    "required": True,
                    "configured": configured,
                    "available": match is not None and hash_valid,
                    "resolved": {"name": match} if match else {},
                    "expected_sha256": HEAD_FITMENT_CHECKPOINT_SHA256,
                    "actual_sha256": actual_sha256,
                    "hash_valid": hash_valid,
                    "expected_location": HEAD_FITMENT_CHECKPOINT_LOCATION,
                }
            ],
            "not_required": ["ControlNet", "IP-Adapter", "LoRA", "separate VAE", "upscaler"],
        }
        return requirements

    def context(self, character: str, phase: str, asset_id: int) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        paths = self.paths(asset)
        spec = json.loads(paths.spec.read_text(encoding="utf-8")) if paths.spec.exists() else {}
        current = bool(spec) and self._spec_current(asset, spec)
        diagnostic_paths = (
            sorted(str(path) for path in paths.diagnostics.iterdir() if path.is_file())
            if paths.diagnostics.exists()
            else []
        )
        return {
            "mode": self.path_service.config.head_fitment_render_mode,
            "available_modes": ["prompt", "masked_local"],
            "mask_path": str(paths.mask),
            "mask_exists": paths.mask.exists(),
            "init_path": str(paths.init),
            "init_exists": paths.init.exists(),
            "spec_path": str(paths.spec),
            "spec": spec,
            "current": current,
            "confirmed": bool(spec.get("confirmed")),
            "diagnostics_path": str(paths.diagnostics),
            "diagnostic_paths": diagnostic_paths,
            "generation_status": "ready" if paths.mask.exists() and current else "stale" if paths.mask.exists() else "missing",
            "source_ask_id": spec.get("source_ask_id"),
            "confidence_score": spec.get("confidence_score"),
            "auto_confirmed": bool(spec.get("auto_confirmed")),
            "validation_failures": spec.get("validation_failures") or [],
            "geometry_strategy": spec.get("geometry_strategy"),
            "mediapipe_accepted": spec.get("mediapipe_accepted"),
            "nape_anchor": spec.get("nape_anchor"),
            "shoulder_line": spec.get("shoulder_line"),
            "editable_area_ratio": spec.get("editable_area_ratio"),
            "rejection_history": spec.get("rejection_history") or [],
        }

    def render(self, asset, prompt_text: str, output_path: Path) -> list[Path]:
        paths = self.paths(asset)
        if not paths.spec.exists() or not paths.mask.exists() or not paths.init.exists():
            raise HeadFitmentEditError("Masked edit artifacts are missing; initialize and confirm the mask first.")
        spec = json.loads(paths.spec.read_text(encoding="utf-8"))
        if not spec.get("confirmed") or not self._spec_current(asset, spec):
            raise HeadFitmentEditError("Masked edit is unconfirmed or stale for the selected references.")
        outputs = self.render_artifacts(
            prompt_text=prompt_text,
            init_path=paths.init,
            mask_path=paths.mask,
            output_path=output_path,
        )
        return [outputs[0], paths.mask, paths.spec, paths.init, *outputs[1:]]

    def render_artifacts(
        self,
        *,
        prompt_text: str,
        init_path: Path,
        mask_path: Path,
        output_path: Path,
        preset_name: str | None = None,
        checkpoint: str | None = None,
        feather_pixels: int | None = None,
    ) -> list[Path]:
        """Render from queue-local mask artifacts; safe to call inside the serialized AI Proxy worker."""
        preset_name = str(preset_name or self.path_service.config.head_fitment_masked_local_preset)
        requirements = self.model_requirements(preset_name, checkpoint)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model_requirements_path = output_path.parent / "Head_Fitment_Model_Requirements.json"
        render_metadata_path = output_path.parent / "Head_Fitment_Render_Metadata.json"
        model_requirements_path.write_text(json.dumps(requirements, indent=2) + "\n", encoding="utf-8")
        if requirements["missing_nodes"]:
            raise HeadFitmentEditError(
                "Required ComfyUI nodes are unavailable: " + ", ".join(requirements["missing_nodes"])
            )
        if any(item["required"] and not item["available"] for item in requirements["models"]):
            missing = ", ".join(item["configured"] or item["kind"] for item in requirements["models"] if not item["available"])
            raise HeadFitmentEditError(f"Required masked-local model is unavailable: {missing}")
        preset = self._preset(preset_name)
        with Image.open(init_path) as init_source, Image.open(mask_path) as mask_source:
            source_rgba = init_source.convert("RGBA")
            source_semantic = np.array(mask_source.convert("L"))
            width = int(np.ceil(source_rgba.width / 8) * 8)
            height = int(np.ceil(source_rgba.height / 8) * 8)
            offset_x = (width - source_rgba.width) // 2
            offset_y = (height - source_rgba.height) // 2
            init_rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            init_rgba.paste(source_rgba, (offset_x, offset_y))
            semantic = np.full((height, width), MASK_REMOVE, np.uint8)
            semantic[offset_y:offset_y + source_rgba.height, offset_x:offset_x + source_rgba.width] = source_semantic
            editable = semantic == MASK_EDIT
            protected = semantic == MASK_PROTECT
            neutral = Image.new("RGB", init_rgba.size, (192, 192, 192))
            neutral.paste(init_rgba.convert("RGB"), mask=init_rgba.getchannel("A"))
            edit_mask = Image.fromarray(np.where(editable, 255, 0).astype(np.uint8), "L")
            protected_layer = np.array(init_rgba)
        checkpoint = requirements["models"][0]["resolved"].get("name") or requirements["models"][0]["configured"]
        init_input = "Zet/Head_Fitment_ComfyUI_Init.png"
        mask_input = "Zet/Head_Fitment_ComfyUI_Edit_Mask.png"
        init_comfy_path = output_path.parent / "Head_Fitment_ComfyUI_Init.png"
        mask_comfy_path = output_path.parent / "Head_Fitment_ComfyUI_Edit_Mask.png"
        workflow_path = output_path.parent / "Head_Fitment_ComfyUI_Workflow.json"
        raw_output_path = output_path.parent / "Head_Fitment_ComfyUI_Raw.png"
        neutral.save(init_comfy_path)
        edit_mask.convert("RGB").save(mask_comfy_path)
        seed = secrets.randbelow(2**63 - 1)
        settings = {
            "steps": int(preset.get("steps", 24)),
            "cfg": float(preset.get("cfg", 6.0)),
            "sampler_name": str(preset.get("sampler_name", "dpmpp_2m")),
            "scheduler": str(preset.get("scheduler", "karras")),
            "denoise": float(preset.get("denoise", preset.get("denoising_strength", 0.22))),
            "grow_mask_by": int(preset.get("mask_growth", preset.get("mask_blur", 6))),
            "seed": seed,
        }
        workflow = compile_head_fitment_inpaint_workflow(
            init_input=init_input,
            mask_input=mask_input,
            checkpoint=checkpoint,
            prompt=prompt_text,
            negative_prompt=str(preset.get("negative_prompt") or "face change, hair change, shoulders, torso, background"),
            output_prefix="Zet/Head_Fitment_Inpaint",
            **settings,
        )
        workflow_path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
        response = run_comfyui_workflow(
            workflow,
            server_url=str(requirements["server_url"]),
            output_dir=output_path.parent,
            reference_files=[
                {"path": str(init_comfy_path), "comfyui_input_name": init_input},
                {"path": str(mask_comfy_path), "comfyui_input_name": mask_input},
            ],
        )
        if not response.image_paths:
            raise HeadFitmentEditError("ComfyUI returned no image.")
        shutil.copy2(response.image_paths[0], raw_output_path)
        with Image.open(raw_output_path) as rendered_image:
            rendered = np.array(rendered_image.convert("RGBA").resize((neutral.width, neutral.height), Image.Resampling.LANCZOS))
        rendered[:, :, 3] = np.where(editable | protected, 255, 0).astype(np.uint8)
        feather = max(0, int(feather_pixels if feather_pixels is not None else self.path_service.config.head_fitment_mask_feather_pixels))
        if feather:
            distance = cv2.distanceTransform(editable.astype(np.uint8), cv2.DIST_L2, 3)
            blend = np.clip(distance / max(1, feather), 0.0, 1.0)[:, :, None]
            source_rgb = protected_layer[:, :, :3].astype(np.float32)
            rendered[:, :, :3] = np.where(
                editable[:, :, None],
                rendered[:, :, :3].astype(np.float32) * blend + source_rgb * (1.0 - blend),
                rendered[:, :, :3],
            ).astype(np.uint8)
        rendered[protected] = protected_layer[protected]
        rendered = rendered[
            offset_y:offset_y + source_rgba.height,
            offset_x:offset_x + source_rgba.width,
        ]
        Image.fromarray(rendered, "RGBA").save(output_path)
        metadata = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "masked_local",
            "backend": "comfyui",
            "workflow_kind": "head_fitment_inpaint",
            "preset": preset_name,
            "checkpoint": checkpoint,
            "output": str(output_path),
            "mask": str(mask_path),
            "model_requirements": str(model_requirements_path),
            "source_canvas_offset": [offset_x, offset_y],
            "settings": settings,
            "prompt_id": response.prompt_id,
        }
        render_metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return [
            output_path,
            model_requirements_path,
            render_metadata_path,
            workflow_path,
            mask_comfy_path,
            raw_output_path,
        ]
