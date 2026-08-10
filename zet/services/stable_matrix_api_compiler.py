from __future__ import annotations

from datetime import datetime
import re
from typing import Any


def _terms(text: str) -> list[str]:
    return [part.strip() for part in text.replace("\n", ",").split(",") if part.strip()]


def ensure_prompt_terms(prompt: str, minimum_terms: str) -> str:
    parts = [prompt.strip()]
    lower_prompt = prompt.lower()
    for term in _terms(minimum_terms):
        if term.lower() not in lower_prompt:
            parts.append(term)
    return ", ".join(part for part in parts if part)


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
    marker = "Negative constraints:"
    if marker in prompt_text:
        positive, negative = prompt_text.split(marker, 1)
        return positive.rstrip(), negative.strip()
    return prompt_text, ""


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


def compile_stable_matrix_api_call(
    prompt_text: str,
    preset: dict[str, Any],
    *,
    preset_name: str,
    positive_prompt_globals: str = "",
    negative_prompt_globals: str = "",
    checkpoint: str = "",
    aspect_ratio: str = "",
    render_layout: dict[str, Any] | None = None,
    seed: int | None = None,
    render_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    render_overrides = render_overrides or {}
    positive_prompt, negative_prompt = split_labeled_prompt(prompt_text)
    resolved_seed = preset.get("seed", "random") if seed is None else seed
    if str(resolved_seed).lower() == "random":
        resolved_seed = -1

    selected_aspect_ratio = aspect_ratio or preset.get("aspect_ratio")
    size = _render_size_for_aspect_ratio(str(selected_aspect_ratio)) if selected_aspect_ratio else None
    if render_overrides.get("width") and render_overrides.get("height"):
        width, height = int(render_overrides["width"]), int(render_overrides["height"])
    elif size:
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
        "steps": int(render_overrides.get("steps", preset.get("steps", 32))),
        "cfg_scale": float(render_overrides.get("cfg_scale", preset.get("cfg", 7.0))),
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
        "override_settings": preset.get(
            "override_settings",
            {"sd_model_checkpoint": r"sd\perfectdeliberate_v90.safetensors"},
        ),
        "override_settings_restore_after_call": bool(preset.get("override_settings_restore_after_call", True)),
    }
    if render_layout and render_layout.get("backend") == "forge_couple_basic":
        if str(render_layout.get("mode")) == "Advanced":
            mappings = render_layout.get("mappings")
            prompt_line_count = len([
                line for line in render_layout.get("prompt_lines", []) if str(line).strip()
            ])
            if not isinstance(mappings, list) or len(mappings) != prompt_line_count:
                render_layout = dict(render_layout)
                render_layout["mode"] = "Basic"
                render_layout["mappings"] = []
        prompt_lines = [str(line).strip() for line in render_layout.get("prompt_lines", []) if str(line).strip()]
        subject_count = int(render_layout.get("subject_count") or 0)
        if subject_count < 2 or len(prompt_lines) != subject_count + 1:
            raise ValueError("Forge Couple requires one global prompt line and one line per visible subject.")
        prompt_lines[0] = ensure_prompt_terms(prompt_lines[0], positive_prompt_globals)
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
        payload["prompt"] = ensure_prompt_terms(str(payload["prompt"]), positive_prompt_globals)
    payload["negative_prompt"] = ensure_prompt_terms(str(payload["negative_prompt"]), negative_prompt_globals)
    if checkpoint:
        payload["override_settings"] = dict(payload["override_settings"])
        payload["override_settings"]["sd_model_checkpoint"] = checkpoint
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preset": preset_name,
        "backend": "stable_matrix",
        "server_url": str(preset.get("server_url", "http://127.0.0.1:7860")),
        "api_path": "/sdapi/v1/txt2img",
        "payload": payload,
    }
