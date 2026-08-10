#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import base64
from io import BytesIO
import json
import mimetypes
from pathlib import Path
import tomllib
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .common import LocalRenderError, LocalRenderResult, LocalRenderUnavailable
from PIL import Image
from zet.services.stable_matrix_api_compiler import (
    compile_stable_matrix_api_call,
    ensure_prompt_terms,
    split_labeled_prompt,
)


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
    render_overrides: dict[str, Any] | None = None,
) -> LocalRenderResult:
    preset = load_preset(project_root, preset_name)
    prompt_text = final_prompt_path.read_text(encoding="utf-8")
    local_render_config = _load_local_render_config(project_root)
    if render_layout and render_layout.get("backend") == "forge_couple_basic":
        ensure_forge_couple_available(str(preset.get("server_url", "http://127.0.0.1:7860")))
    try:
        api_call = compile_stable_matrix_api_call(
            prompt_text,
            preset,
            preset_name=preset_name,
            positive_prompt_globals=local_render_config.get("positive_prompt_globals", ""),
            negative_prompt_globals=local_render_config.get("negative_prompt_globals", ""),
            checkpoint=local_render_config.get("checkpoint", ""),
            aspect_ratio=aspect_ratio,
            render_layout=render_layout,
            seed=seed,
            render_overrides=render_overrides,
        )
    except ValueError as exc:
        raise LocalRenderError(str(exc)) from exc
    server_url = str(api_call["server_url"])
    api_path = str(api_call["api_path"])
    payload = api_call["payload"]
    api_call_path = final_prompt_path.parent / "Stable_Matrix_API_Call.json"
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
