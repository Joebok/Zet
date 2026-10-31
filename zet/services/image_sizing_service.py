"""Resolve image generation dimensions from an aspect ratio and pixel target."""
import math


def image_dimensions(aspect_ratio: str, target_pixels: int) -> tuple[int, int]:
    if isinstance(target_pixels, bool) or not isinstance(target_pixels, int) or not 65536 <= target_pixels <= 16777216:
        raise ValueError("Target pixels must be an integer between 65536 and 16777216.")
    try:
        width_ratio, height_ratio = (float(part) for part in aspect_ratio.split(":"))
        if not all(math.isfinite(value) and value > 0 for value in (width_ratio, height_ratio)):
            raise ValueError
        ratio = width_ratio / height_ratio
        if not 1 / 16 <= ratio <= 16:
            raise ValueError
    except (AttributeError, TypeError, ValueError, OverflowError):
        raise ValueError("Aspect ratio must be a positive width:height ratio between 1:16 and 16:1.") from None
    width = math.sqrt(target_pixels * ratio)
    height = math.sqrt(target_pixels / ratio)
    scale = min(4096 / max(width, height), max(1.0, 256 / min(width, height)))
    return tuple(max(256, min(4096, round(value * scale / 32) * 32)) for value in (width, height))


def resolve_image_sizing(config, render_mode: str, aspect_ratio: str) -> dict:
    if not isinstance(render_mode, str) or render_mode not in {"draft", "final"}:
        raise ValueError("Render mode must be draft or final.")
    target = config.draft_target_pixels if render_mode == "draft" else config.final_target_pixels
    width, height = image_dimensions(aspect_ratio, target)
    return {"render_mode": render_mode, "aspect_ratio": aspect_ratio,
            "target_pixels": target, "width": width, "height": height}


def validate_frozen_image_sizing(sizing: dict) -> dict:
    """Validate a captured request without consulting mutable configuration."""
    if not isinstance(sizing, dict) or sizing.get("render_mode") not in ("draft", "final"):
        raise ValueError("Invalid frozen render mode.")
    width, height = image_dimensions(sizing.get("aspect_ratio"), sizing.get("target_pixels"))
    if type(sizing.get("width")) is not int or type(sizing.get("height")) is not int or (sizing["width"], sizing["height"]) != (width, height):
        raise ValueError("Frozen output dimensions do not match the saved aspect ratio and target pixels.")
    return {key: sizing[key] for key in ("render_mode", "aspect_ratio", "target_pixels", "width", "height")}
