#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import base64
from io import BytesIO
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from Local_Render_Adapters.common import LocalRenderError, LocalRenderResult, LocalRenderUnavailable
from Local_Render_Adapters.comfyui_adapter import DEFAULT_NEGATIVE_PROMPT, split_positive_negative_prompt
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
        return positive, negative or DEFAULT_NEGATIVE_PROMPT
    return split_positive_negative_prompt(prompt_text)


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


def load_local_image_gen_overrides(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    marker = "LOCAL_IMAGE_GEN_OVERRIDES"
    in_section = False
    overrides: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if f"ZET:BEGIN {marker}" in line:
            in_section = True
            continue
        if f"ZET:END {marker}" in line:
            break
        if not in_section or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in LOCAL_IMAGE_GEN_OVERRIDE_KEYS and value:
            overrides[key] = value
    return overrides


def render_preview(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    preset_name: str = "body-reference-preview-stable-matrix",
    reference_files: list[dict[str, Any]] | None = None,
    governing_template_path: Path | None = None,
) -> LocalRenderResult:
    preset = load_preset(project_root, preset_name)
    server_url = str(preset.get("server_url", "http://127.0.0.1:7860"))
    prompt_text = final_prompt_path.read_text(encoding="utf-8")
    positive_prompt, negative_prompt = split_labeled_prompt(prompt_text)
    seed = preset.get("seed", "random")
    if str(seed).lower() == "random":
        seed = -1

    width, height = _render_size_for_references(
        reference_files,
        project_root,
        int(preset.get("width", 512)),
        int(preset.get("height", 512)),
    )
    init_images = encode_reference_images(reference_files, project_root, width, height)
    payload = {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        "init_images": init_images,
        "denoising_strength": float(preset.get("denoising_strength", 0.55)),
        "width": width,
        "height": height,
        "steps": int(preset.get("steps", 25)),
        "cfg_scale": float(preset.get("cfg", 7.0)),
        "seed": int(seed),
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
        "eta": float(preset.get("eta", 0)),
        "s_churn": float(preset.get("s_churn", 0)),
        "s_tmax": float(preset.get("s_tmax", 0)),
        "s_tmin": float(preset.get("s_tmin", 0)),
        "s_noise": float(preset.get("s_noise", 1)),
        "override_settings": preset.get("override_settings", {"sd_model_checkpoint": "sd/novaAnimeXL_ilV190.safetensors"}),
        "override_settings_restore_after_call": bool(preset.get("override_settings_restore_after_call", True)),
    }
    overrides = load_local_image_gen_overrides(governing_template_path)
    if "prompt" in overrides:
        payload["prompt"] = overrides["prompt"]
    if "negative_prompt" in overrides:
        payload["negative_prompt"] = overrides["negative_prompt"]
    for key in ("denoising_strength", "cfg_scale", "s_noise"):
        if key in overrides:
            payload[key] = float(overrides[key])
    for key in ("steps", "seed"):
        if key in overrides:
            payload[key] = int(overrides[key])
    if "restore_faces" in overrides:
        payload["restore_faces"] = overrides["restore_faces"].lower() in {"1", "true", "yes", "on"}
    if "sd_model_checkpoint" in overrides:
        payload["override_settings"] = dict(payload["override_settings"])
        payload["override_settings"]["sd_model_checkpoint"] = overrides["sd_model_checkpoint"]
    sampler = str(preset.get("sampler_name") or "").strip()
    if sampler:
        payload["sampler_name"] = sampler

    api_path = "/sdapi/v1/img2img" if init_images else "/sdapi/v1/txt2img"
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
        "reference_count": len(init_images),
        "info": response.get("info"),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return LocalRenderResult(
        image_path=image_path,
        metadata_path=metadata_path,
        prompt_review_path=prompt_review_path,
        prompt_id=str(response.get("info") or stamp),
    )
