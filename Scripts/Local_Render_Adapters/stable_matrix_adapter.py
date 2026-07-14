#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import base64
from io import BytesIO
import json
import mimetypes
from pathlib import Path
import re
import tomllib
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from Local_Render_Adapters.common import LocalRenderError, LocalRenderResult, LocalRenderUnavailable, split_positive_negative_prompt
from PIL import Image

LOCAL_IMAGE_GEN_OVERRIDE_KEYS = {
    "prompt",
    "negative_prompt",
    "denoising_strength",
    "steps",
    "cfg_scale",
    "seed",
    "s_noise",
    "sd_model_checkpoint",
    "sampler_name",
    "scheduler",
    "enable_hr",
    "hr_upscaler",
    "hr_second_pass_steps",
    "hr_scale",
    "orientation",
    "aspect_ratio",
    "width",
    "height",
    "restore_faces",
}


def load_presets(project_root: Path) -> dict[str, Any]:
    path = project_root / "Config" / "Local_Render_Presets.json"
    if not path.exists():
        raise LocalRenderError(f"Missing local render presets: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_preset(project_root: Path, preset_name: str) -> dict[str, Any]:
    preset = load_presets(project_root).get(preset_name)
    if not isinstance(preset, dict):
        raise LocalRenderError(f"Unknown local render preset: {preset_name}")
    if preset.get("backend") != "stable_matrix":
        raise LocalRenderError(f"Preset {preset_name} does not use the stable_matrix backend.")
    return preset


def _post_json(server_url: str, path: str, payload: dict[str, Any], timeout: int = 240) -> dict[str, Any]:
    url = server_url.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise LocalRenderUnavailable("Local render backend unavailable.") from exc
    except json.JSONDecodeError as exc:
        raise LocalRenderError(f"Stable Matrix returned invalid JSON for {path}.") from exc


def _first_image_bytes(response: dict[str, Any]) -> bytes:
    images = response.get("images")
    if not isinstance(images, list) or not images:
        raise LocalRenderError("Stable Matrix did not return an image.")
    image_text = str(images[0])
    if "," in image_text:
        image_text = image_text.split(",", 1)[1]
    return base64.b64decode(image_text)


def split_labeled_prompt(prompt_text: str) -> tuple[str, str]:
    positive = ""
    negative = ""
    current: str | None = None
    for line in prompt_text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("prompt:"):
            current = "prompt"
            positive = stripped.split(":", 1)[1].strip()
            continue
        if lower.startswith("negative:") or lower.startswith("negative_prompt:"):
            current = "negative"
            negative = stripped.split(":", 1)[1].strip()
            continue
        if current == "prompt" and stripped:
            positive = f"{positive} {stripped}".strip()
        elif current == "negative" and stripped:
            negative = f"{negative} {stripped}".strip()
    if positive:
        return positive, negative
    return split_positive_negative_prompt(prompt_text)


def _load_local_render_globals(project_root: Path) -> tuple[str, str]:
    path = project_root / "config.toml"
    if not path.exists():
        return "", ""
    local_render = tomllib.loads(path.read_text(encoding="utf-8")).get("LocalRender", {})
    if not isinstance(local_render, dict):
        return "", ""
    return str(local_render.get("PositivePromptGlobals", "")), str(local_render.get("NegativePromptGlobals", ""))


def _terms(text: str) -> list[str]:
    return [part.strip() for part in text.replace("\n", ",").split(",") if part.strip()]


def ensure_prompt_terms(prompt: str, minimum_terms: str) -> str:
    parts = [prompt.strip()]
    lower_prompt = prompt.lower()
    for term in _terms(minimum_terms):
        if term.lower() not in lower_prompt:
            parts.append(term)
    return ", ".join(part for part in parts if part)


def _reference_path(reference: dict[str, Any], project_root: Path) -> Path | None:
    path = str(reference.get("path") or reference.get("image_path") or "").strip()
    if not path:
        return None
    resolved = Path(path)
    return resolved if resolved.is_absolute() else project_root / resolved


def _render_size_for_references(reference_files: list[dict[str, Any]] | None, project_root: Path, default_width: int, default_height: int) -> tuple[int, int]:
    for reference in reference_files or []:
        path = _reference_path(reference, project_root)
        if path is None or not path.exists() or not path.is_file():
            continue
        with Image.open(path) as image:
            if image.width <= 0 or image.height <= 0:
                continue
            if image.width <= image.height:
                return 512, int(round(512 * image.height / image.width))
            return int(round(512 * image.width / image.height)), 512
    return default_width, default_height


def _reference_image_bytes(path: Path, max_width: int, max_height: int) -> tuple[str, bytes]:
    with Image.open(path) as image:
        if image.width <= max_width and image.height <= max_height:
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            return mime, path.read_bytes()
        image.thumbnail((max_width, max_height))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return "image/png", buffer.getvalue()


def encode_reference_images(
    reference_files: list[dict[str, Any]] | None,
    project_root: Path,
    max_width: int,
    max_height: int,
) -> list[str]:
    images: list[str] = []
    for reference in reference_files or []:
        path = _reference_path(reference, project_root)
        if path is None or not path.exists() or not path.is_file():
            continue
        mime, image_bytes = _reference_image_bytes(path, max_width, max_height)
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        images.append(f"data:{mime};base64,{encoded}")
    return images


def _render_size_for_orientation(orientation: str) -> tuple[int, int]:
    value = str(orientation or "portrait").strip().lower()
    if value == "landscape":
        return 768, 512
    if value == "square":
        return 512, 512
    return 512, 768


def _render_size_for_aspect_ratio(aspect_ratio: str, short_side: int = 512) -> tuple[int, int] | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*", str(aspect_ratio or ""))
    if not match:
        return None
    width_ratio = float(match.group(1))
    height_ratio = float(match.group(2))
    if width_ratio <= 0 or height_ratio <= 0:
        return None
    if width_ratio >= height_ratio:
        return int(round((short_side * width_ratio / height_ratio) / 64) * 64), short_side
    return short_side, int(round((short_side * height_ratio / width_ratio) / 64) * 64)


def _coerce_override_value(key: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if key in {"denoising_strength", "cfg_scale", "s_noise", "hr_scale"}:
        return float(value)
    if key in {"steps", "seed", "hr_second_pass_steps", "width", "height"}:
        return int(value)
    if key in {"restore_faces", "enable_hr"}:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return str(value)


def _legacy_override_lines_to_toml(lines: list[str]) -> str:
    converted: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("[") or "=" in stripped or ":" not in stripped:
            converted.append(line)
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in LOCAL_IMAGE_GEN_OVERRIDE_KEYS or not value:
            continue
        if value.endswith(":") and value[:-1] in LOCAL_IMAGE_GEN_OVERRIDE_KEYS:
            continue
        if re.fullmatch(r"-?\d+(?:\.\d+)?", value) or value.lower() in {"true", "false"}:
            converted.append(f"{key} = {value}")
        else:
            converted.append(f"{key} = {json.dumps(value)}")
    return "\n".join(converted)


def load_local_image_gen_overrides(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    marker = "LOCAL_IMAGE_GEN_OVERRIDES"
    in_section = False
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if f"ZET:BEGIN {marker}" in line:
            in_section = True
            continue
        if f"ZET:END {marker}" in line:
            break
        if not in_section:
            continue
        lines.append(line)
    if not lines:
        return {}
    parsed = tomllib.loads(_legacy_override_lines_to_toml(lines))
    overrides: dict[str, Any] = {}
    for key, value in parsed.items():
        if key not in LOCAL_IMAGE_GEN_OVERRIDE_KEYS:
            continue
        coerced = _coerce_override_value(key, value)
        if coerced is not None:
            overrides[key] = coerced
    return overrides


def render_preview(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    preset_name: str = "body-reference-preview",
    reference_files: list[dict[str, Any]] | None = None,
    governing_template_path: Path | None = None,
    aspect_ratio: str = "",
) -> LocalRenderResult:
    preset = load_preset(project_root, preset_name)
    server_url = str(preset.get("server_url", "http://127.0.0.1:7860"))
    prompt_text = final_prompt_path.read_text(encoding="utf-8")
    positive_prompt, negative_prompt = split_labeled_prompt(prompt_text)
    seed = preset.get("seed", "random")
    if str(seed).lower() == "random":
        seed = -1
    overrides = load_local_image_gen_overrides(governing_template_path)

    selected_aspect_ratio = aspect_ratio or overrides.get("aspect_ratio") or preset.get("aspect_ratio")
    size = _render_size_for_aspect_ratio(str(selected_aspect_ratio)) if selected_aspect_ratio else None
    if size:
        width, height = size
    elif "width" in overrides and "height" in overrides:
        width, height = int(overrides["width"]), int(overrides["height"])
    elif preset.get("width") and preset.get("height"):
        width, height = int(preset["width"]), int(preset["height"])
    else:
        width, height = _render_size_for_orientation(str(overrides.get("orientation", preset.get("orientation", "portrait"))))
    payload = {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "denoising_strength": float(preset.get("denoising_strength", 0.06)),
        "width": width,
        "height": height,
        "steps": int(preset.get("steps", 32)),
        "cfg_scale": float(preset.get("cfg", 7.0)),
        "seed": int(seed),
        "sampler_name": str(preset.get("sampler_name", "DPM++ 2M")),
        "scheduler": str(preset.get("scheduler", "Karras")),
        "enable_hr": bool(preset.get("enable_hr", True)),
        "hr_upscaler": str(preset.get("hr_upscaler", "Latent")),
        "hr_second_pass_steps": int(preset.get("hr_second_pass_steps", 32)),
        "hr_scale": float(preset.get("hr_scale", 2.0)),
        "hr_additional_modules": ["Use same choices"],
        "subseed": int(preset.get("subseed", -1)),
        "subseed_strength": float(preset.get("subseed_strength", 0)),
        "seed_resize_from_h": int(preset.get("seed_resize_from_h", -1)),
        "seed_resize_from_w": int(preset.get("seed_resize_from_w", -1)),
        "batch_size": int(preset.get("batch_size", 1)),
        "n_iter": 1,
        "restore_faces": bool(preset.get("restore_faces", False)),
        "tiling": bool(preset.get("tiling", False)),
        "do_not_save_samples": bool(preset.get("do_not_save_samples", True)),
        "do_not_save_grid": bool(preset.get("do_not_save_grid", True)),
        "override_settings": preset.get("override_settings", {"sd_model_checkpoint": r"sd\perfectdeliberate_v90.safetensors"}),
        "override_settings_restore_after_call": bool(preset.get("override_settings_restore_after_call", True)),
    }
    if "prompt" in overrides:
        payload["prompt"] = overrides["prompt"]
    if "negative_prompt" in overrides:
        payload["negative_prompt"] = overrides["negative_prompt"]
    positive_globals, negative_globals = _load_local_render_globals(project_root)
    payload["prompt"] = ensure_prompt_terms(str(payload["prompt"]), positive_globals)
    payload["negative_prompt"] = ensure_prompt_terms(str(payload["negative_prompt"]), negative_globals)
    for key in ("denoising_strength", "cfg_scale", "s_noise", "hr_scale"):
        if key in overrides:
            payload[key] = overrides[key]
    for key in ("steps", "seed", "hr_second_pass_steps"):
        if key in overrides:
            payload[key] = overrides[key]
    for key in ("restore_faces", "enable_hr"):
        if key in overrides:
            payload[key] = overrides[key]
    for key in ("sampler_name", "scheduler", "hr_upscaler"):
        if key in overrides:
            payload[key] = overrides[key]
    if "sd_model_checkpoint" in overrides:
        payload["override_settings"] = dict(payload["override_settings"])
        payload["override_settings"]["sd_model_checkpoint"] = overrides["sd_model_checkpoint"]
    api_path = "/sdapi/v1/txt2img"
    api_call_path = final_prompt_path.parent / "Stable_Matrix_API_Call.json"
    api_call = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preset": preset_name,
        "backend": "stable_matrix",
        "server_url": server_url,
        "api_path": api_path,
        "payload": payload,
    }
    api_call_path.write_text(json.dumps(api_call, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    response = _post_json(server_url, api_path, payload)
    image_bytes = _first_image_bytes(response)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    render_dir = job_output_dir / str(preset.get("output_subdir", "Local_Test_Renders"))
    render_dir.mkdir(parents=True, exist_ok=True)
    image_path = render_dir / f"test_{stamp}.png"
    metadata_path = render_dir / f"test_{stamp}.json"
    image_path.write_bytes(image_bytes)
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preset": preset_name,
        "backend": "stable_matrix",
        "server_url": server_url,
        "final_prompt": str(final_prompt_path),
        "local_image": str(image_path),
        "settings": payload,
        "api_path": api_path,
        "info": response.get("info"),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return LocalRenderResult(
        image_path=image_path,
        metadata_path=metadata_path,
        prompt_review_path=prompt_review_path,
        prompt_id=str(response.get("info") or stamp),
    )
