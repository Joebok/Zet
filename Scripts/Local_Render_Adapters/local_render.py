from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zet.services.local_render_types import LocalRenderRequest

from .common import LocalRenderError, LocalRenderResult, LocalRenderUnavailable


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
    render_layout: dict[str, Any] | None = None,
    scene_render_ir_path: Path | None = None,
    seed: int | None = None,
    render_overrides: dict[str, Any] | None = None,
    checkpoint: str | None = None,
) -> LocalRenderResult:
    request = LocalRenderRequest(
        project_root=project_root,
        final_prompt_path=final_prompt_path,
        job_output_dir=job_output_dir,
        profile_name=preset_name,
        prompt_review_path=prompt_review_path,
        scene_render_ir_path=scene_render_ir_path,
        reference_files=reference_files or [],
        aspect_ratio=aspect_ratio,
        render_layout=render_layout,
        seed=seed,
        render_overrides=render_overrides,
        checkpoint=checkpoint,
    )
    return render_request(request)


def render_request(request: LocalRenderRequest) -> LocalRenderResult:
    preset = load_preset(request.project_root, request.profile_name)
    backend = str(preset.get("backend") or "").strip().lower()
    if backend == "stable_matrix":
        from Scripts.Local_Render_Adapters.stable_matrix_adapter import render_preview

        return render_preview(
            project_root=request.project_root,
            final_prompt_path=request.final_prompt_path,
            job_output_dir=request.job_output_dir,
            prompt_review_path=request.prompt_review_path,
            preset_name=request.profile_name,
            reference_files=request.reference_files,
            aspect_ratio=request.aspect_ratio,
            render_layout=request.render_layout,
            seed=request.seed,
            render_overrides=request.render_overrides,
            checkpoint=request.checkpoint,
        )
    if backend == "comfyui":
        from Scripts.Local_Render_Adapters.comfyui_adapter import render_preview

        return render_preview(
            project_root=request.project_root,
            final_prompt_path=request.final_prompt_path,
            job_output_dir=request.job_output_dir,
            prompt_review_path=request.prompt_review_path,
            profile_name=request.profile_name,
            scene_render_ir_path=request.scene_render_ir_path,
            aspect_ratio=request.aspect_ratio,
            reference_files=request.reference_files,
            seed=request.seed,
            render_overrides=request.render_overrides,
            checkpoint=request.checkpoint,
        )
    raise LocalRenderError(f"Unsupported local render backend for profile {request.profile_name}: {backend}")
