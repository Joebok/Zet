from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Callable

from zet.services.comfyui_prompt_compiler import append_prompt_globals, compile_scene_prompts
from zet.services.local_render_types import LocalRenderError
from zet.services.scene_layout_planner import plan_scene_layout


CORE_SCENE_WORKFLOW = "core_txt2img_scene_preview"
CORE_PROMPT_WORKFLOW = "core_txt2img_prompt_only"
IPADAPTER_SCENE_WORKFLOW = "ipadapter_scene_preview"
OPENPOSE_SCENE_WORKFLOW = "openpose_scene_preview"


@dataclass(frozen=True)
class ComfyUICompilation:
    workflow: dict[str, Any]
    prompts: dict[str, Any]
    seed: int
    width: int
    height: int
    workflow_kind: str
    debug: dict[str, Any] = field(default_factory=dict)


SceneCompiler = Callable[..., ComfyUICompilation]
PromptCompiler = Callable[..., ComfyUICompilation]
_SCENE_COMPILERS: dict[str, SceneCompiler] = {}
_PROMPT_COMPILERS: dict[str, PromptCompiler] = {}


def register_scene_compiler(workflow_kind: str, compiler: SceneCompiler) -> None:
    _SCENE_COMPILERS[workflow_kind] = compiler


def register_prompt_compiler(workflow_kind: str, compiler: PromptCompiler) -> None:
    _PROMPT_COMPILERS[workflow_kind] = compiler


def workflow_kind_for_profile(profile: dict[str, Any], *, prompt_only: bool = False) -> str:
    configured = str(profile.get("workflow_kind") or "").strip()
    if prompt_only:
        return str(profile.get("prompt_workflow_kind") or CORE_PROMPT_WORKFLOW).strip()
    return configured or CORE_SCENE_WORKFLOW


def _workflow(
    *,
    global_prompt: str,
    negative_prompt: str,
    region_records: list[dict[str, Any]],
    layout_plan: dict[str, Any],
    profile: dict[str, Any],
    checkpoint: str,
    seed: int,
    width: int,
    height: int,
    output_prefix: str,
    model: list[Any] | None = None,
    prefix_nodes: dict[str, Any] | None = None,
    next_id: int = 10,
) -> dict[str, Any]:
    if not checkpoint.strip():
        raise LocalRenderError("ComfyUI checkpoint cannot be blank.")
    workflow: dict[str, Any] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": global_prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
    }
    if prefix_nodes:
        workflow.update(prefix_nodes)
    positive: list[Any] = ["2", 0]
    regions_by_id = {
        str(region.get("element_id") or ""): region
        for region in layout_plan.get("regions", [])
        if isinstance(region, dict)
    }
    for record in region_records:
        region = regions_by_id.get(str(record.get("element_id") or ""))
        if not region:
            continue
        text_id = str(next_id)
        area_id = str(next_id + 1)
        combine_id = str(next_id + 2)
        next_id += 3
        pixels = region["pixels"]
        workflow[text_id] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": str(record.get("prompt") or ""), "clip": ["1", 1]},
        }
        workflow[area_id] = {
            "class_type": "ConditioningSetArea",
            "inputs": {
                "conditioning": [text_id, 0],
                "width": pixels["width"],
                "height": pixels["height"],
                "x": pixels["x"],
                "y": pixels["y"],
                "strength": region["conditioning_strength"],
            },
        }
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
            "model": model or ["1", 0],
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


def _core_scene_compiler(
    ir: dict[str, Any],
    profile: dict[str, Any],
    *,
    checkpoint: str,
    seed: int,
    width: int,
    height: int,
    positive_prompt_globals: str,
    negative_prompt_globals: str,
    output_prefix: str,
    **_kwargs: Any,
) -> ComfyUICompilation:
    prompts = compile_scene_prompts(
        ir,
        positive_prompt_globals=positive_prompt_globals,
        negative_prompt_globals=negative_prompt_globals,
    )
    layout_plan = plan_scene_layout(ir, width, height)
    workflow = _workflow(
        global_prompt=prompts["global"],
        negative_prompt=prompts["negative"],
        region_records=prompts["region_records"],
        layout_plan=layout_plan,
        profile=profile,
        checkpoint=checkpoint,
        seed=seed,
        width=width,
        height=height,
        output_prefix=output_prefix,
    )
    return ComfyUICompilation(
        workflow=workflow,
        prompts=prompts,
        seed=seed,
        width=width,
        height=height,
        workflow_kind=CORE_SCENE_WORKFLOW,
        debug={"layout_plan": layout_plan, "references_used": []},
    )


def _reference_bindings(
    ir: dict[str, Any],
    reference_files: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    resolved = [
        item
        for item in ir.get("resolved_sources", {}).get("references", [])
        if isinstance(item, dict)
    ]
    resolved.extend(item for item in reference_files or [] if isinstance(item, dict))
    by_tag = {
        str(item.get("tag") or ""): item
        for item in resolved
        if str(item.get("tag") or "").strip()
    }
    elements = {
        str(item.get("id") or ""): item
        for item in ir.get("elements", [])
        if isinstance(item, dict)
    }
    bindings = []
    for assignment in ir.get("references", []):
        if not isinstance(assignment, dict):
            continue
        tag = str(assignment.get("tag") or "").strip()
        source = by_tag.get(tag)
        if not source:
            continue
        path = Path(str(source.get("path") or "")).expanduser()
        element_id = str(assignment.get("applies_to_element_id") or "")
        element = elements.get(element_id, {})
        role = "backdrop" if str(element.get("element_type") or "") == "Backdrop" else "character"
        input_name = source.get("comfyui_input_name")
        if not input_name:
            path_key = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
            input_name = f"Zet/{path_key}/{path.name}"
        bindings.append(
            {
                "tag": tag,
                "element_id": element_id,
                "role": role,
                "path": str(path),
                "comfyui_input_name": str(input_name),
            }
        )
    return bindings


def _ipadapter_scene_compiler(
    ir: dict[str, Any],
    profile: dict[str, Any],
    *,
    checkpoint: str,
    seed: int,
    width: int,
    height: int,
    positive_prompt_globals: str,
    negative_prompt_globals: str,
    output_prefix: str,
    reference_files: list[dict[str, Any]] | None = None,
    available_node_types: set[str] | None = None,
    **_kwargs: Any,
) -> ComfyUICompilation:
    required = {
        "LoadImage",
        "CLIPVisionLoader",
        "IPAdapterModelLoader",
        "IPAdapterAdvanced",
    }
    missing_nodes = sorted(required - (available_node_types or set()))
    if missing_nodes:
        raise LocalRenderError(
            "ComfyUI IP-Adapter profile requires unavailable nodes: "
            + ", ".join(missing_nodes)
            + ". Install ComfyUI_IPAdapter_plus and configure its models."
        )
    bindings = _reference_bindings(ir, reference_files)
    if not bindings:
        raise LocalRenderError("ComfyUI IP-Adapter profile requires at least one resolved reference image.")
    missing_files = [item["path"] for item in bindings if not Path(item["path"]).is_file()]
    if missing_files:
        raise LocalRenderError("ComfyUI reference image file is missing: " + missing_files[0])
    ipadapter_model = str(profile.get("ipadapter_model") or "").strip()
    clip_vision_model = str(profile.get("clip_vision_model") or "").strip()
    if not ipadapter_model or not clip_vision_model:
        raise LocalRenderError(
            "ComfyUI IP-Adapter profile requires ipadapter_model and clip_vision_model settings."
        )

    prompts = compile_scene_prompts(
        ir,
        positive_prompt_globals=positive_prompt_globals,
        negative_prompt_globals=negative_prompt_globals,
    )
    layout_plan = plan_scene_layout(ir, width, height)
    nodes: dict[str, Any] = {
        "5": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": clip_vision_model}},
        "6": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": ipadapter_model}},
    }
    model: list[Any] = ["1", 0]
    next_id = 20
    applications: list[dict[str, Any]] = []
    for index, binding in enumerate(bindings):
        image_id = str(7 + index * 2)
        adapter_id = str(8 + index * 2)
        role_prefix = "backdrop" if binding["role"] == "backdrop" else "character"
        default_weight = 0.20 if role_prefix == "backdrop" else 0.40
        default_end_at = 0.55 if role_prefix == "backdrop" else 0.75
        settings = {
            "weight": float(profile.get(f"{role_prefix}_reference_weight", default_weight)),
            "start_at": 0.0,
            "end_at": float(profile.get(f"{role_prefix}_reference_end_at", default_end_at)),
            "weight_type": str(profile.get("ipadapter_weight_type") or "linear"),
            "combine_embeds": str(profile.get("ipadapter_combine_embeds") or "average"),
            "embeds_scaling": str(profile.get("ipadapter_embeds_scaling") or "V only"),
        }
        nodes[image_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": binding["comfyui_input_name"]},
        }
        nodes[adapter_id] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model,
                "ipadapter": ["6", 0],
                "image": [image_id, 0],
                "clip_vision": ["5", 0],
                **settings,
            },
        }
        applications.append(
            {
                "reference_element_id": binding["element_id"],
                "staged_reference_file": binding["comfyui_input_name"],
                **settings,
            }
        )
        model = [adapter_id, 0]
        next_id = max(next_id, int(adapter_id) + 1)
    workflow = _workflow(
        global_prompt=prompts["global"],
        negative_prompt=prompts["negative"],
        region_records=prompts["region_records"],
        layout_plan=layout_plan,
        profile=profile,
        checkpoint=checkpoint,
        seed=seed,
        width=width,
        height=height,
        output_prefix=output_prefix,
        model=model,
        prefix_nodes=nodes,
        next_id=next_id,
    )
    return ComfyUICompilation(
        workflow=workflow,
        prompts=prompts,
        seed=seed,
        width=width,
        height=height,
        workflow_kind=IPADAPTER_SCENE_WORKFLOW,
        debug={
            "layout_plan": layout_plan,
            "references_used": bindings,
            "ipadapter_applications": applications,
        },
    )


def _core_prompt_compiler(
    positive_prompt: str,
    negative_prompt: str,
    profile: dict[str, Any],
    *,
    checkpoint: str,
    seed: int,
    width: int,
    height: int,
    positive_prompt_globals: str,
    negative_prompt_globals: str,
    output_prefix: str,
    **_kwargs: Any,
) -> ComfyUICompilation:
    positive = append_prompt_globals(positive_prompt, positive_prompt_globals)
    negative = append_prompt_globals(negative_prompt, negative_prompt_globals)
    prompts = {"global": positive, "negative": negative, "regions": [], "region_records": []}
    layout_plan = {
        "schema_version": 1,
        "canvas": {"width": width, "height": height},
        "subject_order": [],
        "regions": [],
        "pose_control": {
            "schema_version": 1,
            "kind": "scene_layout_control",
            "source": "prompt_only",
            "canvas": {"width": width, "height": height},
            "subjects": [],
            "consumed_by_workflow": False,
        },
    }
    return ComfyUICompilation(
        workflow=_workflow(
            global_prompt=positive,
            negative_prompt=negative,
            region_records=[],
            layout_plan=layout_plan,
            profile=profile,
            checkpoint=checkpoint,
            seed=seed,
            width=width,
            height=height,
            output_prefix=output_prefix,
        ),
        prompts=prompts,
        seed=seed,
        width=width,
        height=height,
        workflow_kind=CORE_PROMPT_WORKFLOW,
        debug={"layout_plan": layout_plan, "references_used": []},
    )


def compile_scene_workflow(workflow_kind: str, *args: Any, **kwargs: Any) -> ComfyUICompilation:
    compiler = _SCENE_COMPILERS.get(workflow_kind)
    if compiler is None:
        known = ", ".join(sorted(_SCENE_COMPILERS))
        raise LocalRenderError(f"Unsupported ComfyUI scene workflow_kind {workflow_kind!r}. Available: {known}.")
    return compiler(*args, **kwargs)


def compile_prompt_workflow(workflow_kind: str, *args: Any, **kwargs: Any) -> ComfyUICompilation:
    compiler = _PROMPT_COMPILERS.get(workflow_kind)
    if compiler is None:
        known = ", ".join(sorted(_PROMPT_COMPILERS))
        raise LocalRenderError(f"Unsupported ComfyUI prompt workflow_kind {workflow_kind!r}. Available: {known}.")
    return compiler(*args, **kwargs)


register_scene_compiler(CORE_SCENE_WORKFLOW, _core_scene_compiler)
register_scene_compiler(IPADAPTER_SCENE_WORKFLOW, _ipadapter_scene_compiler)
register_prompt_compiler(CORE_PROMPT_WORKFLOW, _core_prompt_compiler)
