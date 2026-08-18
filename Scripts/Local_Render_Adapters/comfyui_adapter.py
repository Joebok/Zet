from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import tomllib
from typing import Any

from zet.services.comfyui_render_service import (
    compile_ir_to_comfyui_workflow,
    compile_prompt_to_comfyui_workflow,
    list_comfyui_node_types,
    run_comfyui_workflow,
)
from zet.services.local_render_types import LocalRenderError, LocalRenderResult

from .stable_matrix_adapter import split_labeled_prompt


def _load_profile(project_root: Path, profile_name: str) -> dict[str, Any]:
    path = project_root / "Config" / "Local_Render_Presets.json"
    if not path.exists():
        raise LocalRenderError(f"Missing local render profiles: {path}")
    profiles = json.loads(path.read_text(encoding="utf-8"))
    profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict) or profile.get("backend") != "comfyui":
        raise LocalRenderError(f"Profile {profile_name} does not use the comfyui backend.")
    return profile


def _load_config(project_root: Path) -> dict[str, Any]:
    path = project_root / "config.toml"
    if not path.exists():
        return {}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    comfyui = payload.get("ComfyUI", {})
    return comfyui if isinstance(comfyui, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_preview(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    profile_name: str = "comfyui-core-preview",
    scene_render_ir_path: Path | None = None,
    aspect_ratio: str = "",
    reference_files: list[dict[str, Any]] | None = None,
    seed: int | None = None,
    render_overrides: dict[str, Any] | None = None,
    checkpoint: str | None = None,
) -> LocalRenderResult:
    profile = _load_profile(project_root, profile_name)
    allowed_overrides = {
        "steps", "cfg", "sampler_name", "scheduler", "denoise",
        "control_preprocessor", "controlnet_model", "control_strength",
        "control_start", "control_end",
    }
    profile = {
        **profile,
        **{
            key: value for key, value in (render_overrides or {}).items()
            if key in allowed_overrides
        },
    }
    config = _load_config(project_root)
    selected_checkpoint = str(checkpoint if checkpoint is not None else config.get("Checkpoint") or "")
    positive_globals = str(config.get("PositivePromptGlobals") or "")
    negative_globals = str(config.get("NegativePromptGlobals") or "")
    profile_seed = profile.get("seed")
    selected_seed = seed if seed is not None else profile_seed
    workflow_kind = str(
        profile.get("workflow_kind")
        or profile.get("prompt_workflow_kind")
        or "core_txt2img_scene_preview"
    )
    server_url = str(config.get("ServerURL") or "http://127.0.0.1:8188")

    ir: dict[str, Any] | None = None
    ir_hash = ""
    if scene_render_ir_path is not None:
        ir_bytes = scene_render_ir_path.read_bytes()
        ir = json.loads(ir_bytes.decode("utf-8-sig"))
        ir_hash = hashlib.sha256(ir_bytes).hexdigest()
        scene_slug = str(ir.get("scene", {}).get("slug") or "Scene")
        compilation = compile_ir_to_comfyui_workflow(
            ir,
            profile,
            checkpoint=selected_checkpoint,
            positive_prompt_globals=positive_globals,
            negative_prompt_globals=negative_globals,
            seed=None if str(selected_seed).lower() == "random" else int(selected_seed),
            output_prefix=f"Zet/{scene_slug}",
            reference_files=reference_files,
            available_node_types=(
                list_comfyui_node_types(server_url)
                if workflow_kind == "ipadapter_scene_preview"
                else None
            ),
        )
    else:
        positive, negative = split_labeled_prompt(final_prompt_path.read_text(encoding="utf-8"))
        compilation = compile_prompt_to_comfyui_workflow(
            positive,
            negative,
            profile,
            checkpoint=selected_checkpoint,
            positive_prompt_globals=positive_globals,
            negative_prompt_globals=negative_globals,
            seed=None if str(selected_seed).lower() == "random" else int(selected_seed),
            aspect_ratio=aspect_ratio,
            reference_files=reference_files,
            available_node_types=(
                list_comfyui_node_types(server_url)
                if workflow_kind != "core_txt2img_prompt_only"
                else None
            ),
        )

    workflow_path = job_output_dir / "ComfyUI_Workflow_API.json"
    debug_path = job_output_dir / "ComfyUI_Compilation_Debug.json"
    pose_path = job_output_dir / "ComfyUI_Pose_Layout_Control.json"
    _write_json(workflow_path, compilation.workflow)
    _write_json(debug_path, {
        "workflow_kind": compilation.workflow_kind,
        "seed": compilation.seed,
        "prompts": compilation.prompts,
        **compilation.debug,
    })
    _write_json(
        pose_path,
        compilation.debug.get("layout_plan", {}).get("pose_control", {}),
    )
    render_dir = job_output_dir / str(profile.get("output_subdir") or "Local_Test_Renders")
    started_at = datetime.now()
    run = run_comfyui_workflow(
        compilation.workflow,
        server_url=server_url,
        output_dir=render_dir,
        reference_files=compilation.debug.get("references_used", []),
        poll_seconds=float(config.get("PollSeconds", 1.0)),
        timeout_seconds=float(config.get("TimeoutSeconds", 300.0)),
    )
    completed_at = datetime.now()
    metadata_path = render_dir / "ComfyUI_Render_Metadata.json"
    metadata = {
        "created_at": completed_at.isoformat(timespec="seconds"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "elapsed_seconds": round((completed_at - started_at).total_seconds(), 3),
        "backend": "comfyui",
        "profile": profile_name,
        "workflow_kind": compilation.workflow_kind,
        "profile_settings": profile,
        "server_url": server_url,
        "checkpoint": selected_checkpoint,
        "scene_render_ir": str(scene_render_ir_path) if scene_render_ir_path else None,
        "scene_render_ir_sha256": ir_hash or None,
        "final_prompt": str(final_prompt_path),
        "prompts": compilation.prompts,
        "layout_plan": compilation.debug.get("layout_plan", {}),
        "references_used": compilation.debug.get("references_used", []),
        "ipadapter_applications": compilation.debug.get("ipadapter_applications", []),
        "seed": compilation.seed,
        "resolved_seed": compilation.seed,
        "width": compilation.width,
        "height": compilation.height,
        "prompt_id": run.prompt_id,
        "status": "SUCCESS",
        "outputs": run.outputs,
        "images": [str(path) for path in run.image_paths],
    }
    _write_json(metadata_path, metadata)
    return LocalRenderResult(
        image_path=run.image_paths[0],
        metadata_path=metadata_path,
        prompt_review_path=prompt_review_path,
        prompt_id=run.prompt_id,
        artifact_paths=[workflow_path, debug_path, pose_path, metadata_path],
    )
