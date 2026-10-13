from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import tomllib
from typing import Any

from zet.services.comfyui_render_service import (
    ComfyUICompilation,
    compile_ir_to_comfyui_workflow,
    compile_prompt_to_comfyui_workflow,
    list_comfyui_node_types,
    run_comfyui_workflow,
)
from zet.services.local_render_types import LocalRenderError, LocalRenderResult
from zet.services.local_render_policy import require_qwen_profile, SCENE_PROFILE, configured_qwen_checkpoint
from zet.services.qwen_reference_preparation_service import QwenReferencePolicy, prepare_qwen_references

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


_QWEN_REFERENCE_WORKFLOWS = {
    "qwen_narrative_prompt",
    "qwen_image_21_local_edit",
    "qwen_body_reference_edit",
}


def _pending_compilation(
    workflow_path: Path,
    debug_path: Path,
    pending: dict[str, Any],
    profile: dict[str, Any],
    output_dir: Path,
) -> ComfyUICompilation:
    """Restore the exact graph/debug bundle associated with a pending prompt."""
    if not workflow_path.is_file() or not debug_path.is_file():
        raise LocalRenderError("Pending ComfyUI render is missing its saved workflow or debug artifact; its submission was not changed.")
    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        debug = json.loads(debug_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LocalRenderError(f"Pending ComfyUI render artifacts are unreadable; its submission was not changed: {exc}") from exc
    if not isinstance(workflow, dict) or not isinstance(debug, dict):
        raise LocalRenderError("Pending ComfyUI workflow/debug artifacts have invalid structure; its submission was not changed.")
    fingerprint = hashlib.sha256(json.dumps(workflow, sort_keys=True).encode("utf-8")).hexdigest()
    if pending.get("workflow_sha256") != fingerprint:
        raise LocalRenderError("Pending ComfyUI workflow checksum does not match its submission journal; artifacts were preserved.")

    preparation = debug.get("qwen_reference_preparation")
    if isinstance(preparation, dict) and preparation.get("enabled") is True:
        references = preparation.get("references")
        if not isinstance(references, list) or any(not isinstance(item, dict) for item in references):
            raise LocalRenderError("Pending Qwen reference preparation metadata is malformed; artifacts were preserved.")
        for reference in references:
            relative = str(reference.get("prepared_path") or "")
            expected_hash = reference.get("prepared_sha256")
            if not relative or not isinstance(expected_hash, str):
                raise LocalRenderError("Pending Qwen reference preparation metadata is incomplete; artifacts were preserved.")
            path = (output_dir / relative).resolve()
            try:
                path.relative_to(output_dir.resolve())
            except ValueError as exc:
                raise LocalRenderError("Pending Qwen reference snapshot escapes its job directory; artifacts were preserved.") from exc
            if not path.is_file():
                raise LocalRenderError(f"Pending Qwen reference snapshot is missing: {relative}; artifacts were preserved.")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise LocalRenderError(f"Pending Qwen reference snapshot checksum changed: {relative}; artifacts were preserved.")

    width, height = int(profile.get("width", 1024)), int(profile.get("height", 1024))
    for node in workflow.values():
        if not isinstance(node, dict) or node.get("class_type") != "KSampler":
            continue
        latent = node.get("inputs", {}).get("latent_image")
        latent_node = workflow.get(str(latent[0])) if isinstance(latent, list) and latent else None
        dimensions = latent_node.get("inputs", {}) if isinstance(latent_node, dict) else {}
        if isinstance(dimensions.get("width"), int) and isinstance(dimensions.get("height"), int):
            width, height = dimensions["width"], dimensions["height"]
            break
    return ComfyUICompilation(
        workflow=workflow,
        prompts=debug.get("prompts") if isinstance(debug.get("prompts"), dict) else {},
        seed=int(debug.get("seed") or 0),
        width=width,
        height=height,
        workflow_kind=str(debug.get("workflow_kind") or "pending_legacy"),
        debug=debug,
    )


def render_preview(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    profile_name: str = SCENE_PROFILE,
    scene_render_ir_path: Path | None = None,
    aspect_ratio: str = "",
    reference_files: list[dict[str, Any]] | None = None,
    seed: int | None = None,
    render_overrides: dict[str, Any] | None = None,
    checkpoint: str | None = None,
) -> LocalRenderResult:
    profile = _load_profile(project_root, profile_name)
    allowed_overrides = {
        "width", "height", "steps", "cfg", "sampler_name", "scheduler", "denoise",
        "character_reference_weight",
        "character_reference_end_at", "ipadapter_model", "clip_vision_model",
        "ipadapter_weight_type", "ipadapter_combine_embeds", "ipadapter_embeds_scaling",
        "control_preprocessor", "controlnet_model", "control_strength",
        "control_start", "control_end", "preprocessor_resolution",
        "text_encoder", "vae",
        "disable_prompt_globals",
    }
    profile = {
        **profile,
        **{
            key: value for key, value in (render_overrides or {}).items()
            if key in allowed_overrides
        },
    }
    config = _load_config(project_root)
    workflow_kind = str(
        profile.get("workflow_kind")
        or profile.get("prompt_workflow_kind")
        or "core_txt2img_scene_preview"
    )
    server_url = str(config.get("ServerURL") or "http://127.0.0.1:8188")
    render_dir = job_output_dir / str(profile.get("output_subdir") or "Local_Test_Renders")
    submission_path = render_dir / "ComfyUI_Submission.json"
    pending = json.loads(submission_path.read_text(encoding="utf-8")) if submission_path.is_file() else {}
    if pending.get("status") == "SUBMITTING":
        raise LocalRenderError(
            f"Previous ComfyUI submission has an unknown outcome. Check the server queue before resetting {submission_path}."
        )
    if pending.get("status") == "PENDING":
        saved_server = str(pending.get("server_url") or "").strip()
        if saved_server:
            server_url = saved_server.rstrip("/")
    workflow_path = job_output_dir / "ComfyUI_Workflow_API.json"
    debug_path = job_output_dir / "ComfyUI_Compilation_Debug.json"
    pending_render = pending.get("status") == "PENDING"
    ir_hash = ""
    qwen_preparation: dict[str, Any] = {}

    if pending_render:
        # Do not let current config, prompts, source images, or compiler defaults
        # rewrite a graph that ComfyUI may already be executing.
        compilation = _pending_compilation(workflow_path, debug_path, pending, profile, job_output_dir)
        checkpoint_node = compilation.workflow.get("1", {})
        checkpoint_inputs = checkpoint_node.get("inputs", {}) if isinstance(checkpoint_node, dict) else {}
        selected_checkpoint = str(checkpoint_inputs.get("unet_name") or profile.get("diffusion_model") or "")
        saved_metadata = render_dir / "ComfyUI_Render_Metadata.json"
        if saved_metadata.is_file():
            try:
                ir_hash = str(json.loads(saved_metadata.read_text(encoding="utf-8")).get("scene_render_ir_sha256") or "")
            except (OSError, ValueError):
                pass
        qwen_preparation = compilation.debug.get("qwen_reference_preparation", {})
    else:
        selected_checkpoint = str(checkpoint if checkpoint is not None else config.get("Checkpoint") or "")
        if checkpoint is None:
            selected_checkpoint = configured_qwen_checkpoint(selected_checkpoint)
        selected_checkpoint = selected_checkpoint or str(profile.get("diffusion_model") or "")
        require_qwen_profile(project_root, profile_name, checkpoint=selected_checkpoint)

        machine_settings = config.get("QwenImage21", {})
        if not isinstance(machine_settings, dict):
            raise LocalRenderError("ComfyUI.QwenImage21 must be a TOML table.")
        if workflow_kind in _QWEN_REFERENCE_WORKFLOWS:
            policy = QwenReferencePolicy.resolve(profile, machine_settings)
            profile["qwen_reference_resize_enabled"] = policy.enabled
            profile["qwen_cache_device"] = policy.cache_device
            profile["qwen_cache_dtype"] = policy.cache_dtype
            reference_files, qwen_preparation = prepare_qwen_references(
                reference_files or [], job_output_dir, policy
            )

        disable_prompt_globals = bool(profile.get("disable_prompt_globals"))
        positive_globals = "" if disable_prompt_globals else str(config.get("PositivePromptGlobals") or "")
        negative_globals = "" if disable_prompt_globals else str(config.get("NegativePromptGlobals") or "")
        profile_seed = profile.get("seed")
        selected_seed = seed if seed is not None else profile_seed

        if scene_render_ir_path is not None:
            # Scene Builder IR compilation is retired; keep its existing clear error.
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
                available_node_types=None,
            )
        else:
            prompt_text = final_prompt_path.read_text(encoding="utf-8")
            positive, negative = ((prompt_text, "") if workflow_kind == "qwen_narrative_prompt"
                                  else split_labeled_prompt(prompt_text))
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
            if qwen_preparation:
                compilation.debug["qwen_reference_preparation"] = qwen_preparation

    debug_path = job_output_dir / "ComfyUI_Compilation_Debug.json"
    pose_path = job_output_dir / "ComfyUI_Pose_Layout_Control.json"
    if not pending_render:
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
        timeout_seconds=float(profile.get("timeout_seconds") or config.get("TimeoutSeconds", 300.0)),
    )
    completed_at = datetime.now()
    metadata_path = render_dir / "ComfyUI_Render_Metadata.json"
    profile_settings = profile
    if pending_render:
        saved_metadata = render_dir / "ComfyUI_Render_Metadata.json"
        try:
            previous = json.loads(saved_metadata.read_text(encoding="utf-8"))
            profile_settings = previous.get("profile_settings", {"recovered_from_saved_workflow": True})
        except (OSError, ValueError):
            profile_settings = {"recovered_from_saved_workflow": True}
    metadata = {
        "created_at": completed_at.isoformat(timespec="seconds"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "elapsed_seconds": round((completed_at - started_at).total_seconds(), 3),
        "backend": "comfyui",
        "profile": profile_name,
        "workflow_kind": compilation.workflow_kind,
        "profile_settings": profile_settings,
        "server_url": server_url,
        "checkpoint": selected_checkpoint,
        "scene_render_ir": str(scene_render_ir_path) if scene_render_ir_path else None,
        "scene_render_ir_sha256": ir_hash or None,
        "final_prompt": str(final_prompt_path),
        "prompts": compilation.prompts,
        "layout_plan": compilation.debug.get("layout_plan", {}),
        "references_used": compilation.debug.get("references_used", []),
        "qwen_reference_cache": compilation.debug.get("qwen_reference_cache"),
        "qwen_reference_preparation": compilation.debug.get("qwen_reference_preparation", {}),
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
        artifact_paths=[
            workflow_path, debug_path, pose_path, metadata_path,
            job_output_dir / "Qwen_Reference_Preparation.json",
        ],
    )
