"""Resolve and frame an image background independently of measured stage geometry."""

from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path

from PIL import Image, ImageOps

from zet.services.scene_layout_service import GROUND_COLOR, SceneLayoutError, SceneLayoutService
from zet.services.scene_render_compiler import _reference_tag
BACKDROP_EXTENSION_COLOR = (215, 221, 223)


class SceneBackgroundService:
    def __init__(self, reference_service, target_service):
        self.references = reference_service
        self.targets = target_service

    @staticmethod
    def aspect(scene: dict) -> float:
        value = ((scene.get("setup") or {}).get("canvas") or {}).get("aspect_ratio") or "16:9"
        try:
            width, height = (float(part) for part in value.split(":", 1))
            ratio = width / height
            if not math.isfinite(ratio) or ratio <= 0:
                raise ValueError
            return ratio
        except (ValueError, TypeError, AttributeError, ZeroDivisionError):
            return 16 / 9

    def options(self, scene: dict) -> list[dict]:
        options = []
        for element in scene.get("_layout_source_elements", scene.get("scene_elements")) or []:
            if element.get("element_type") != "Backdrop":
                continue
            refs = element.get("reference_images") or []
            refs = sorted(refs, key=lambda item: not item.get("primary_prompt_source"))
            for ref in refs:
                tag = _reference_tag(ref)
                if tag:
                    options.append({"label": f"{element.get('display_name') or element['id']} · {ref.get('label') or 'Reference'}",
                                    "source": {"kind": "element", "element_id": element["id"], "reference_tag": tag}})
        for target in scene.get("subscenes") or []:
            if target.get("enabled") and target.get("kind") == "background":
                options.append({"label": f"{target.get('name') or target['id']} · Accepted background",
                                "source": {"kind": "subscene", "target_id": target["id"]}})
        return options

    def resolve(self, scene: dict, layout: dict, *, width: int, height: int,
                resolved_references: list[dict] | None = None) -> dict | None:
        source = layout.get("background")
        if source is None:
            return None
        options = self.options(scene)
        matches = [item for item in options if all(item["source"].get(key) == value for key, value in source.items())]
        if not matches:
            raise SceneLayoutError("The selected background is unavailable. Choose a backdrop reference or enabled background subscene.")
        selected = matches[0]
        source = selected["source"]
        if source["kind"] == "element":
            tag = source["reference_tag"]
        else:
            identity = scene.get("scene") or {}
            tag = self.targets.image_tag(identity.get("_story_slug", ""), identity.get("slug", ""), source["target_id"])
        if resolved_references is not None:
            reference = next((item for item in resolved_references if item.get("tag") == tag), None)
            if reference is None:
                raise SceneLayoutError("The selected background is missing from the frozen render inputs.")
        else:
            try:
                reference = self.references.resolve_scene_references(tag)[0]
            except Exception as exc:
                raise SceneLayoutError(f"Cannot load the selected background: {exc}") from exc
        try:
            payload = Path(reference["path"]).read_bytes()
            with Image.open(io.BytesIO(payload)) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
        except (OSError, ValueError, KeyError) as exc:
            raise SceneLayoutError("The selected background image is missing or unreadable.") from exc
        camera = next(item for item in layout["cameras"] if item["id"] == layout["active_camera_id"])
        ground = SceneLayoutService.ground_projection(layout)
        fraction = ground["visible_fraction"]
        crop_aspect = self.aspect(scene) / max(.001, fraction)
        crop = self.crop(image.width, image.height, crop_aspect, camera.get("background_framing") or {})
        backdrop_height = max(1, round(height * fraction))
        cropped = image.transform((width, backdrop_height), Image.Transform.EXTENT,
                                 (crop["left"] * image.width, crop["top"] * image.height,
                                  (crop["left"] + crop["width"]) * image.width,
                                  (crop["top"] + crop["height"]) * image.height), Image.Resampling.BICUBIC,
                                  fillcolor=BACKDROP_EXTENSION_COLOR)
        framed = Image.new("RGB", (width, height), GROUND_COLOR)
        if fraction > 0:
            framed.paste(cropped, (0, 0))
        stream = io.BytesIO()
        framed.save(stream, format="PNG")
        source_stream = io.BytesIO()
        image.save(source_stream, format="PNG")
        projection = {"source": source, "source_tag": tag, "source_sha256": hashlib.sha256(payload).hexdigest(),
                      "source_width": image.width, "source_height": image.height, "crop": crop,
                      "aspect": crop_aspect, "canvas_aspect": self.aspect(scene), "ground_join_y": fraction,
                      "extension_regions": self.extension_regions(crop, fraction),
                      "image_placement": {"left": -crop["left"] / crop["width"], "top": -crop["top"] / crop["height"] * fraction,
                                          "width": 1 / crop["width"], "height": fraction / crop["height"]}}
        return {"projection": projection, "png_bytes": stream.getvalue(), "source_png_bytes": source_stream.getvalue(),
                "reference": reference, "label": selected["label"]}

    @staticmethod
    def crop(width: int, height: int, aspect: float, framing: dict) -> dict:
        framing = SceneLayoutService.normalize_framing(framing)
        image_aspect = width / height
        crop_width = min(1.0, aspect / image_aspect) / framing["zoom"]
        crop_height = min(1.0, image_aspect / aspect) / framing["zoom"]
        x, y = framing["center"]
        return {"left": x - crop_width / 2, "top": y - crop_height / 2,
                "width": crop_width, "height": crop_height, "center": [x, y], "zoom": framing["zoom"]}

    @staticmethod
    def extension_regions(crop: dict, fraction: float) -> list[dict]:
        left = min(1., max(0., -crop["left"] / crop["width"]))
        right = min(1., max(0., (1 - crop["left"]) / crop["width"]))
        top = min(1., max(0., -crop["top"] / crop["height"]))
        bottom = min(1., max(0., (1 - crop["top"]) / crop["height"]))
        if right <= left or bottom <= top:
            return [{"left": 0., "top": 0., "width": 1., "height": fraction}] if fraction else []
        rectangles = [(0., 0., 1., top), (0., bottom, 1., 1 - bottom),
                      (0., top, left, bottom - top), (right, top, 1 - right, bottom - top)]
        return [{"left": x, "top": y * fraction, "width": width, "height": height * fraction}
                for x, y, width, height in rectangles if width > 1e-8 and height * fraction > 1e-8]
