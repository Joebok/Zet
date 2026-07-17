from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Local_Render_Adapters.common import LocalRenderError, LocalRenderResult, LocalRenderUnavailable


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
    return preset


def render_image(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    preset_name: str = "body-reference-preview",
    reference_files: list[dict[str, Any]] | None = None,
    aspect_ratio: str = "",
) -> LocalRenderResult:
    preset = load_preset(project_root, preset_name)
    backend = str(preset.get("backend") or "").strip().lower()
    if backend == "stable_matrix":
        from Local_Render_Adapters.stable_matrix_adapter import render_preview

        return render_preview(
            project_root=project_root,
            final_prompt_path=final_prompt_path,
            job_output_dir=job_output_dir,
            prompt_review_path=prompt_review_path,
            preset_name=preset_name,
            reference_files=reference_files,
            aspect_ratio=aspect_ratio,
        )
    raise LocalRenderError(f"Unsupported local render backend for preset {preset_name}: {backend}")
