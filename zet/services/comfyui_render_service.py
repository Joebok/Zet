from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
import time
from typing import Any
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zet.services.local_render_types import LocalRenderError, LocalRenderUnavailable
from zet.services.scene_render_compiler import (
    collect_primary_characters,
    local_render_brief,
    resolve_character_order,
    validate_scene_render_ir,
)


@dataclass(frozen=True)
class ComfyUICompilation:
    workflow: dict[str, Any]
    prompts: dict[str, Any]
    seed: int
    width: int
    height: int


@dataclass(frozen=True)
class ComfyUIRunResult:
    prompt_id: str
    image_paths: list[Path]
    outputs: dict[str, Any]
    history: dict[str, Any]


def _prompt_terms(prompt: str, additions: str) -> str:
    parts = [prompt.strip()]
    lower_prompt = prompt.lower()
    for term in (item.strip() for item in additions.replace("\n", ",").split(",")):
        if term and term.lower() not in lower_prompt:
            parts.append(term)
    return ", ".join(part for part in parts if part)


def _even8(value: float) -> int:
    return max(8, int(round(value / 8.0)) * 8)


def _render_size(ir: dict[str, Any] | None, profile: dict[str, Any]) -> tuple[int, int]:
    aspect_ratio = str((ir or {}).get("canvas", {}).get("aspect_ratio") or profile.get("aspect_ratio") or "")
    try:
        width_ratio, height_ratio = (float(item.strip()) for item in aspect_ratio.split(":", 1))
        if width_ratio <= 0 or height_ratio <= 0:
            raise ValueError
        short_side = int(profile.get("short_side", 640))
        max_long_side = int(profile.get("max_long_side", 960))
        if width_ratio >= height_ratio:
            natural_width = _even8(short_side * width_ratio / height_ratio)
            width = min(max_long_side, natural_width)
            height = short_side if width == natural_width else width * height_ratio / width_ratio
            return _even8(width), _even8(height)
        natural_height = _even8(short_side * height_ratio / width_ratio)
        height = min(max_long_side, natural_height)
        width = short_side if height == natural_height else height * width_ratio / height_ratio
        return _even8(width), _even8(height)
    except (TypeError, ValueError):
        return _even8(float(profile.get("width", 640))), _even8(float(profile.get("height", 960)))


def _resolved_seed(profile: dict[str, Any], seed: int | None) -> int:
    value: Any = profile.get("seed", "random") if seed is None else seed
    if str(value).strip().lower() == "random" or int(value) < 0:
        return random.SystemRandom().randrange(0, 2**63 - 1)
    return int(value)


def _region_box(index: int, count: int, width: int, height: int) -> dict[str, int | float]:
    if count <= 1:
        return {"x": 0, "y": 0, "width": width, "height": height, "strength": 1.1}
    overlap = 0.12 / count
    left = max(0.0, index / count - overlap / 2)
    right = min(1.0, (index + 1) / count + overlap / 2)
    top = _even8(height * 0.08)
    region_height = min(height - top, _even8(height * 0.88))
    x = _even8(width * left) if left else 0
    region_width = width - x if right >= 1 else min(width - x, _even8(width * (right - left)))
    return {
        "x": x,
        "y": top,
        "width": max(8, region_width),
        "height": max(8, region_height),
        "strength": 1.15 if index == 0 else 1.1,
    }


def _workflow(
    *,
    global_prompt: str,
    negative_prompt: str,
    region_prompts: list[str],
    profile: dict[str, Any],
    checkpoint: str,
    seed: int,
    width: int,
    height: int,
    output_prefix: str,
) -> dict[str, Any]:
    if not checkpoint.strip():
        raise LocalRenderError("ComfyUI checkpoint cannot be blank.")
    workflow: dict[str, Any] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": global_prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
    }
    next_id = 10
    positive: list[Any] = ["2", 0]
    for index, prompt in enumerate(region_prompts):
        text_id = str(next_id)
        area_id = str(next_id + 1)
        next_id += 2
        box = _region_box(index, len(region_prompts), width, height)
        workflow[text_id] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        }
        workflow[area_id] = {
            "class_type": "ConditioningSetArea",
            "inputs": {
                "conditioning": [text_id, 0],
                "width": box["width"],
                "height": box["height"],
                "x": box["x"],
                "y": box["y"],
                "strength": box["strength"],
            },
        }
        combine_id = str(next_id)
        next_id += 1
        workflow[combine_id] = {
            "class_type": "ConditioningCombine",
            "inputs": {"conditioning_1": positive, "conditioning_2": [area_id, 0]},
        }
        positive = [combine_id, 0]

    sampler_id = str(next_id)
    decode_id = str(next_id + 1)
    save_id = str(next_id + 2)
    workflow[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": int(profile.get("steps", 28)),
            "cfg": float(profile.get("cfg", 7.0)),
            "sampler_name": str(profile.get("sampler_name", "dpmpp_2m")),
            "scheduler": str(profile.get("scheduler", "karras")),
            "denoise": float(profile.get("denoise", 1.0)),
            "model": ["1", 0],
            "positive": positive,
            "negative": ["3", 0],
            "latent_image": ["4", 0],
        },
    }
    workflow[decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": [sampler_id, 0], "vae": ["1", 2]},
    }
    workflow[save_id] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": output_prefix, "images": [decode_id, 0]},
    }
    return workflow


def compile_ir_to_comfyui_workflow(
    ir: dict[str, Any],
    profile: dict[str, Any],
    *,
    checkpoint: str,
    positive_prompt_globals: str = "",
    negative_prompt_globals: str = "",
    seed: int | None = None,
    output_prefix: str = "Zet/Scene",
) -> ComfyUICompilation:
    validate_scene_render_ir(ir)
    brief = local_render_brief(ir)
    characters, _ = resolve_character_order(ir, collect_primary_characters(ir))
    character_ids = {str(element.get("id") or "") for element, _ in characters}
    regions_by_id = {
        str(region.get("element_ids", [""])[0]): str(region.get("prompt") or "")
        for region in brief.get("regions", [])
        if isinstance(region, dict)
        and isinstance(region.get("element_ids"), list)
        and region.get("element_ids")
    }
    region_prompts = [
        regions_by_id.get(str(element.get("id") or ""), "")
        for element, _ in characters
        if regions_by_id.get(str(element.get("id") or ""), "") and str(element.get("id") or "") in character_ids
    ]
    plain = brief.get("plain_txt2img", {}) if isinstance(brief.get("plain_txt2img"), dict) else {}
    global_prompt = _prompt_terms(str(brief.get("global_prompt") or plain.get("prompt") or ""), positive_prompt_globals)
    negative_prompt = _prompt_terms(str(plain.get("negative_prompt") or ""), negative_prompt_globals)
    resolved_seed = _resolved_seed(profile, seed)
    width, height = _render_size(ir, profile)
    prompts = {"global": global_prompt, "negative": negative_prompt, "regions": region_prompts}
    return ComfyUICompilation(
        workflow=_workflow(
            global_prompt=global_prompt,
            negative_prompt=negative_prompt,
            region_prompts=region_prompts,
            profile=profile,
            checkpoint=checkpoint,
            seed=resolved_seed,
            width=width,
            height=height,
            output_prefix=output_prefix,
        ),
        prompts=prompts,
        seed=resolved_seed,
        width=width,
        height=height,
    )


def compile_prompt_to_comfyui_workflow(
    positive_prompt: str,
    negative_prompt: str,
    profile: dict[str, Any],
    *,
    checkpoint: str,
    positive_prompt_globals: str = "",
    negative_prompt_globals: str = "",
    seed: int | None = None,
    aspect_ratio: str = "",
    output_prefix: str = "Zet/Preview",
) -> ComfyUICompilation:
    resolved_seed = _resolved_seed(profile, seed)
    width, height = _render_size({"canvas": {"aspect_ratio": aspect_ratio}}, profile)
    positive = _prompt_terms(positive_prompt, positive_prompt_globals)
    negative = _prompt_terms(negative_prompt, negative_prompt_globals)
    return ComfyUICompilation(
        workflow=_workflow(
            global_prompt=positive,
            negative_prompt=negative,
            region_prompts=[],
            profile=profile,
            checkpoint=checkpoint,
            seed=resolved_seed,
            width=width,
            height=height,
            output_prefix=output_prefix,
        ),
        prompts={"global": positive, "negative": negative, "regions": []},
        seed=resolved_seed,
        width=width,
        height=height,
    )


def _request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 60) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise LocalRenderUnavailable(f"ComfyUI request failed: {url}") from exc
    except json.JSONDecodeError as exc:
        raise LocalRenderError(f"ComfyUI returned invalid JSON: {url}") from exc


def _request_bytes(url: str, timeout: float = 60) -> bytes:
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise LocalRenderUnavailable(f"ComfyUI image download failed: {url}") from exc


def run_comfyui_workflow(
    workflow: dict[str, Any],
    *,
    server_url: str,
    output_dir: Path,
    poll_seconds: float = 1.0,
    timeout_seconds: float = 300.0,
) -> ComfyUIRunResult:
    base_url = server_url.rstrip("/")
    submitted = _request_json(f"{base_url}/prompt", "POST", {"prompt": workflow})
    if not isinstance(submitted, dict):
        raise LocalRenderError("ComfyUI prompt response must be a JSON object.")
    if submitted.get("node_errors") or submitted.get("error"):
        details = submitted.get("node_errors") or submitted.get("error")
        raise LocalRenderError(f"ComfyUI workflow validation failed: {json.dumps(details, ensure_ascii=False)}")
    prompt_id = str(submitted.get("prompt_id") or "")
    if not prompt_id:
        raise LocalRenderError("ComfyUI prompt response did not include prompt_id.")

    deadline = time.monotonic() + timeout_seconds
    record: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        history = _request_json(f"{base_url}/history/{urllib.parse.quote(prompt_id)}")
        if isinstance(history, dict) and isinstance(history.get(prompt_id), dict):
            record = history[prompt_id]
            break
        time.sleep(max(0.0, poll_seconds))
    if record is None:
        raise LocalRenderError(f"ComfyUI workflow timed out after {timeout_seconds:g} seconds.")
    status = record.get("status") if isinstance(record.get("status"), dict) else {}
    if status.get("status_str") == "error":
        raise LocalRenderError(f"ComfyUI execution failed: {json.dumps(status, ensure_ascii=False)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    outputs = record.get("outputs") if isinstance(record.get("outputs"), dict) else {}
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for image in node_output.get("images", []):
            if not isinstance(image, dict) or not image.get("filename"):
                continue
            query = urllib.parse.urlencode({
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            })
            safe_name = Path(str(image["filename"])).name
            destination = output_dir / safe_name
            destination.write_bytes(_request_bytes(f"{base_url}/view?{query}"))
            image_paths.append(destination)
    if not image_paths:
        raise LocalRenderError("ComfyUI completed without returning an image.")
    return ComfyUIRunResult(prompt_id=prompt_id, image_paths=image_paths, outputs=outputs, history=record)
