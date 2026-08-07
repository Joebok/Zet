from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np
from PIL import Image


MASK_REMOVE = 0
MASK_EDIT = 128
MASK_PROTECT = 255


class HeadFitmentEditError(Exception):
    pass


@dataclass(frozen=True)
class HeadFitmentEditPaths:
    mask: Path
    spec: Path
    init: Path
    model_requirements: Path
    render_metadata: Path


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
        rgba = np.array(image.convert("RGBA"))
        alpha = rgba[:, :, 3]
        if int(alpha.min()) < 250:
            return alpha > 8
        full_rgb = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
        full_h, full_w = full_rgb.shape[:2]
        scale = min(1.0, 768.0 / max(full_h, full_w))
        rgb = (
            cv2.resize(full_rgb, (max(1, round(full_w * scale)), max(1, round(full_h * scale))), interpolation=cv2.INTER_AREA)
            if scale < 1.0
            else full_rgb
        )
        h, w = rgb.shape[:2]
        grab = np.zeros((h, w), np.uint8)
        margin_x = max(2, int(w * 0.025))
        margin_y = max(2, int(h * 0.025))
        rect = (margin_x, margin_y, max(1, w - margin_x * 2), max(1, h - margin_y * 2))
        try:
            bgd = np.zeros((1, 65), np.float64)
            fgd = np.zeros((1, 65), np.float64)
            cv2.grabCut(rgb, grab, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
            foreground = np.isin(grab, [cv2.GC_FGD, cv2.GC_PR_FGD])
        except cv2.error:
            corners = np.concatenate(
                [rgb[:24, :24], rgb[:24, -24:], rgb[-24:, :24], rgb[-24:, -24:]], axis=0
            )
            background = np.median(corners.reshape(-1, 3), axis=0)
            foreground = np.linalg.norm(rgb.astype(np.float32) - background, axis=2) > 22
        if foreground.shape != (full_h, full_w):
            foreground = cv2.resize(
                foreground.astype(np.uint8), (full_w, full_h), interpolation=cv2.INTER_NEAREST
            ).astype(bool)
        kernel = np.ones((3, 3), np.uint8)
        cleaned = cv2.morphologyEx(foreground.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=2)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
        if count <= 1:
            return cleaned > 0
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        return labels == largest

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
        editable &= retained
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
        spec["updated_at"] = datetime.now().isoformat(timespec="seconds")
        paths.spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
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
        if not isinstance(preset, dict) or preset.get("backend") != "stable_matrix" or not preset.get("supports_masks"):
            raise HeadFitmentEditError(f"Masked-local preset is missing or not mask-capable: {name}")
        return preset

    @staticmethod
    def _get_json(server_url: str, api_path: str) -> Any:
        try:
            with urlopen(Request(server_url.rstrip("/") + api_path, method="GET"), timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, json.JSONDecodeError) as exc:
            raise HeadFitmentEditError("Masked-local image backend unavailable.") from exc

    def model_requirements(
        self,
        preset_name: str | None = None,
        checkpoint: str | None = None,
    ) -> dict[str, Any]:
        preset_name = str(preset_name or self.path_service.config.head_fitment_masked_local_preset)
        preset = self._preset(preset_name)
        server_url = str(preset.get("server_url") or "http://127.0.0.1:7860")
        configured = str(
            checkpoint
            or self.path_service.config.head_fitment_masked_local_checkpoint
            or preset.get("checkpoint")
            or self.path_service.config.local_render_checkpoint
        ).strip()
        models = self._get_json(server_url, "/sdapi/v1/sd-models")
        installed = [item for item in models if isinstance(item, dict)] if isinstance(models, list) else []
        def matches(item: dict) -> bool:
            values = {str(item.get(key) or "").lower() for key in ("title", "model_name", "filename", "hash")}
            needle = configured.lower()
            return bool(needle) and any(needle == value or needle in value or value in needle for value in values if value)
        match = next((item for item in installed if matches(item)), None)
        requirements = {
            "schema_version": 1,
            "backend": "stable_matrix",
            "server_url": server_url,
            "preset": preset_name,
            "models": [
                {
                    "kind": "checkpoint",
                    "required": True,
                    "configured": configured,
                    "available": match is not None,
                    "resolved": match or {},
                }
            ],
            "not_required": ["ControlNet", "IP-Adapter", "LoRA", "separate VAE", "upscaler"],
        }
        return requirements

    def context(self, character: str, phase: str, asset_id: int) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        paths = self.paths(asset)
        spec = json.loads(paths.spec.read_text(encoding="utf-8")) if paths.spec.exists() else {}
        return {
            "mode": self.path_service.config.head_fitment_render_mode,
            "available_modes": ["prompt", "masked_local"],
            "mask_path": str(paths.mask),
            "mask_exists": paths.mask.exists(),
            "init_path": str(paths.init),
            "init_exists": paths.init.exists(),
            "spec_path": str(paths.spec),
            "spec": spec,
            "current": bool(spec) and self._spec_current(asset, spec),
            "confirmed": bool(spec.get("confirmed")),
        }

    @staticmethod
    def _data_url(image: Image.Image, mode: str = "PNG") -> str:
        buffer = BytesIO()
        image.save(buffer, format=mode)
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    @staticmethod
    def _post_json(server_url: str, api_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            server_url.rstrip("/") + api_path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, json.JSONDecodeError) as exc:
            raise HeadFitmentEditError("Masked-local image render failed.") from exc

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
        if any(item["required"] and not item["available"] for item in requirements["models"]):
            missing = ", ".join(item["configured"] or item["kind"] for item in requirements["models"] if not item["available"])
            raise HeadFitmentEditError(f"Required masked-local model is unavailable: {missing}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model_requirements_path = output_path.parent / "Head_Fitment_Model_Requirements.json"
        render_metadata_path = output_path.parent / "Head_Fitment_Render_Metadata.json"
        model_requirements_path.write_text(json.dumps(requirements, indent=2) + "\n", encoding="utf-8")
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
        checkpoint = requirements["models"][0]["resolved"].get("title") or requirements["models"][0]["configured"]
        payload = {
            "init_images": [self._data_url(neutral)],
            "mask": self._data_url(edit_mask),
            "prompt": prompt_text,
            "negative_prompt": str(preset.get("negative_prompt") or "face change, hair change, shoulders, torso, background"),
            "width": neutral.width,
            "height": neutral.height,
            "steps": int(preset.get("steps", 24)),
            "cfg_scale": float(preset.get("cfg", 6.0)),
            "denoising_strength": float(preset.get("denoising_strength", 0.22)),
            "sampler_name": str(preset.get("sampler_name", "DPM++ 2M")),
            "scheduler": str(preset.get("scheduler", "Karras")),
            "mask_blur": int(preset.get("mask_blur", feather_pixels if feather_pixels is not None else self.path_service.config.head_fitment_mask_feather_pixels)),
            "inpainting_fill": 1,
            "inpaint_full_res": True,
            "inpaint_full_res_padding": int(preset.get("inpaint_full_res_padding", 32)),
            "inpainting_mask_invert": 0,
            "restore_faces": False,
            "do_not_save_samples": True,
            "do_not_save_grid": True,
            "override_settings": {"sd_model_checkpoint": checkpoint},
            "override_settings_restore_after_call": True,
        }
        response = self._post_json(str(requirements["server_url"]), "/sdapi/v1/img2img", payload)
        images = response.get("images") if isinstance(response, dict) else None
        if not isinstance(images, list) or not images:
            raise HeadFitmentEditError("Masked-local backend returned no image.")
        encoded = str(images[0]).split(",", 1)[-1]
        with Image.open(BytesIO(base64.b64decode(encoded))) as rendered_image:
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
        Image.fromarray(rendered, "RGBA").save(output_path)
        metadata = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "masked_local",
            "backend": "stable_matrix",
            "preset": preset_name,
            "checkpoint": checkpoint,
            "output": str(output_path),
            "mask": str(mask_path),
            "model_requirements": str(model_requirements_path),
            "source_canvas_offset": [offset_x, offset_y],
            "settings": {key: value for key, value in payload.items() if key not in {"init_images", "mask"}},
            "backend_info": response.get("info"),
        }
        render_metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return [output_path, model_requirements_path, render_metadata_path]
