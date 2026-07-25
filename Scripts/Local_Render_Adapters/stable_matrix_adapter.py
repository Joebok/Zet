#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import base64
from io import BytesIO
import json
import logging
import mimetypes
from pathlib import Path
import re
import tomllib
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .common import LocalRenderError, LocalRenderResult, LocalRenderUnavailable, split_positive_negative_prompt
from PIL import Image


LOGGER = logging.getLogger(__name__)

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


def _get_json(server_url: str, path: str, timeout: int = 10) -> Any:
    url = server_url.rstrip("/") + path
    request = Request(url, method="GET")
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


def _load_local_render_config(project_root: Path) -> dict[str, str]:
    path = project_root / "config.toml"
    if not path.exists():
        return {}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    local_render = payload.get("LocalRender", {})
    if not isinstance(local_render, dict):
        return {}
    stable_matrix = payload.get("StableMatrix", {})
    if not isinstance(stable_matrix, dict):
        stable_matrix = {}
    return {
        "positive_prompt_globals": str(
            stable_matrix.get("PositivePromptGlobals", local_render.get("PositivePromptGlobals", ""))
        ),
        "negative_prompt_globals": str(
            stable_matrix.get("NegativePromptGlobals", local_render.get("NegativePromptGlobals", ""))
        ),
        "checkpoint": str(stable_matrix.get("Checkpoint", local_render.get("Checkpoint", ""))),
    }


def _terms(text: str) -> list[str]:
    return [part.strip() for part in text.replace("\n", ",").split(",") if part.strip()]


def ensure_prompt_terms(prompt: str, minimum_terms: str) -> str:
    parts = [prompt.strip()]
    lower_prompt = prompt.lower()
    for term in _terms(minimum_terms):
        if term.lower() not in lower_prompt:
            parts.append(term)
    return ", ".join(part for part in parts if part)


def forge_couple_args(layout: dict[str, Any]) -> list[Any]:
    advanced = str(layout.get("mode") or "Basic") == "Advanced"
    return [
        True,
        bool(layout.get("disable_hr", True)),
        str(layout.get("mode") or "Basic"),
        str(layout.get("separator") or ""),
        None if advanced else str(layout.get("direction") or "Horizontal"),
        None if advanced else str(layout.get("background") or "First Line"),
        None if advanced else float(layout.get("background_weight", 0.5)),
        layout.get("mappings") if advanced else None,
        str(layout.get("common_parser") or "{ }"),
        bool(layout.get("common_debug", False)),
        bool(layout.get("def_in_prompt", True)),
        None,
        None,
        None,
        None,
        None,
        None,
    ]


def ensure_forge_couple_available(server_url: str) -> None:
    scripts = _get_json(server_url, "/sdapi/v1/scripts")
    txt2img = scripts.get("txt2img", []) if isinstance(scripts, dict) else []
    if "forge couple" not in {str(name).strip().lower() for name in txt2img}:
        raise LocalRenderError("Forge Couple was requested, but the 'forge couple' txt2img script is unavailable.")


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


def render_preview(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    preset_name: str = "body-reference-preview",
    reference_files: list[dict[str, Any]] | None = None,
    aspect_ratio: str = "",
    render_layout: dict[str, Any] | None = None,
    seed: int | None = None,
) -> LocalRenderResult:
    preset = load_preset(project_root, preset_name)
    server_url = str(preset.get("server_url", "http://127.0.0.1:7860"))
    prompt_text = final_prompt_path.read_text(encoding="utf-8")
    positive_prompt, negative_prompt = split_labeled_prompt(prompt_text)
    resolved_seed = preset.get("seed", "random") if seed is None else seed
    if str(resolved_seed).lower() == "random":
        resolved_seed = -1

    selected_aspect_ratio = aspect_ratio or preset.get("aspect_ratio")
    size = _render_size_for_aspect_ratio(str(selected_aspect_ratio)) if selected_aspect_ratio else None
    if size:
        width, height = size
    elif preset.get("width") and preset.get("height"):
        width, height = int(preset["width"]), int(preset["height"])
    else:
        width, height = _render_size_for_orientation(str(preset.get("orientation", "portrait")))
    payload = {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": int(preset.get("steps", 32)),
        "cfg_scale": float(preset.get("cfg", 7.0)),
        "seed": int(resolved_seed),
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
    local_render_config = _load_local_render_config(project_root)
    if render_layout and render_layout.get("backend") == "forge_couple_basic":
        prompt_lines = [str(line).strip() for line in render_layout.get("prompt_lines", []) if str(line).strip()]
        subject_count = int(render_layout.get("subject_count") or 0)
        if subject_count < 2 or len(prompt_lines) != subject_count + 1:
            raise LocalRenderError("Forge Couple requires one global prompt line and one line per visible subject.")
        if str(render_layout.get("mode")) == "Advanced":
            mappings = render_layout.get("mappings")
            if not isinstance(mappings, list) or len(mappings) != len(prompt_lines):
                LOGGER.warning("Forge Couple Advanced prompt/mapping count mismatch; falling back to Basic mode.")
                render_layout = dict(render_layout)
                render_layout["mode"] = "Basic"
                render_layout["mappings"] = []
        ensure_forge_couple_available(server_url)
        prompt_lines[0] = ensure_prompt_terms(prompt_lines[0], local_render_config.get("positive_prompt_globals", ""))
        payload["prompt"] = "\n".join(prompt_lines)
        payload["alwayson_scripts"] = {"forge couple": {"args": forge_couple_args(render_layout)}}
        if bool(render_layout.get("disable_hr", True)):
            payload["enable_hr"] = False
            if str(render_layout.get("mode")) == "Advanced":
                if width <= height:
                    payload["width"], payload["height"] = 640, 800
                else:
                    payload["width"], payload["height"] = 896, 512
    else:
        payload["prompt"] = ensure_prompt_terms(str(payload["prompt"]), local_render_config.get("positive_prompt_globals", ""))
    payload["negative_prompt"] = ensure_prompt_terms(str(payload["negative_prompt"]), local_render_config.get("negative_prompt_globals", ""))
    if local_render_config.get("checkpoint"):
        payload["override_settings"] = dict(payload["override_settings"])
        payload["override_settings"]["sd_model_checkpoint"] = local_render_config["checkpoint"]
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

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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
        "seed": int(payload["seed"]),
        "resolved_seed": int(payload["seed"]),
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
