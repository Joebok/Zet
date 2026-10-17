"""Freeze provider requests; compilation is separate from backend execution."""
from __future__ import annotations

import json
from pathlib import Path
import tomllib

from zet.services.atomic_file_service import write_json_atomic


def prepare_request(staging: Path, worker_type: str, config=None):
    if (staging / "ai_request.json").is_file():
        return
    ask = json.loads((staging / "ask_manifest.json").read_text(encoding="utf-8"))
    if worker_type in {"ollama_generate", "codex_generate"}:
        provider = "codex" if worker_type == "codex_generate" else "ollama"
        request = {"version": 1, "provider": provider, "model": ask.get("model") or ask.get("ollama_model", ""),
                   "prompt": (staging / ask["prompt_file"]).read_text(encoding="utf-8"),
                   "system": ask.get("ollama_request_options", {}).get("system", ""),
                   "images": ask.get("image_files", []), "schema": ask.get("response_schema"),
                   "output": ask["expected_output"], "options": {
                       "think": ask.get("ollama_think", False), "temperature": ask.get("ollama_temperature", 0.2),
                       "json_output": ask.get("json_output", False),
                       **{key: value for key, value in ask.get("ollama_request_options", {}).items() if key != "system"}}}
        if provider == "codex":
            request["options"]["effort"] = ask.get("request_config", {}).get("think", "high")
        else:
            request["options"]["api"] = ask.get("request_config", {}).get("api", "chat" if ask.get("ollama_chat", True) else "generate")
        if config is not None:
            from zet.services.ai_model_catalog_service import AIModelCatalogService
            AIModelCatalogService(config.base_ai_queue_path, config=config).validate(request["model"], required=["vision"] if request["images"] else ["text"])
    elif worker_type == "local_image_render" and config is not None:
        request = prepare_render(staging, ask, config)
        ask["checkpoint"] = request["model"]
        write_json_atomic(staging / "ask_manifest.json", ask)
    else:
        return
    request["owner"] = {key: value for key, value in ask.items() if key.endswith("_id")}
    write_json_atomic(staging / "ai_request.json", request)


def prepare_render(staging, ask, config):
    from zet.services.ai_model_catalog_service import AIModelCatalogService
    from zet.services.comfyui_render_service import compile_prompt_to_comfyui_workflow
    from zet.services.qwen_reference_preparation_service import QwenReferencePolicy, prepare_qwen_references
    from Scripts.Local_Render_Adapters.stable_matrix_adapter import split_labeled_prompt
    project = Path(__file__).resolve().parents[2]
    profiles = json.loads(config.state_file(project, "Local_Render_Presets.json").read_text(encoding="utf-8"))
    profile = dict(profiles[ask["render_preset"]])
    allowed = {"width", "height", "steps", "cfg", "sampler_name", "scheduler", "denoise",
               "text_encoder", "vae", "disable_prompt_globals"}
    profile.update({key: value for key, value in ask.get("render_overrides", {}).items() if key in allowed})
    config_path = project / "config.toml"
    machine = tomllib.loads(config_path.read_text(encoding="utf-8")).get("ComfyUI", {}) if config_path.is_file() else {}
    refs = ask.get("reference_files", [])
    preparation = {}
    if profile.get("workflow_kind") in {"qwen_narrative_prompt", "qwen_image_21_local_edit", "qwen_body_reference_edit"}:
        policy = QwenReferencePolicy.resolve(profile, machine.get("QwenImage21", {}))
        profile.update(qwen_reference_resize_enabled=policy.enabled, qwen_cache_device=policy.cache_device,
                       qwen_cache_dtype=policy.cache_dtype)
        refs, preparation = prepare_qwen_references(refs, staging, policy)
    prompt = (staging / ask["prompt_file"]).read_text(encoding="utf-8")
    positive, negative = (prompt, "") if profile.get("workflow_kind") == "qwen_narrative_prompt" else split_labeled_prompt(prompt)
    catalog = AIModelCatalogService(config.base_ai_queue_path, config=config).catalog()
    nodes = set(catalog.get("comfyui_node_types", []))
    # Managed ComfyUI is normally stopped until admission. Compile the registered
    # graph contract offline; the proxy validates actual nodes after starting it.
    if not nodes:
        nodes = {"UNETLoader", "CLIPLoader", "VAELoader", "LoadImage", "TextEncodeQwenImage21",
                 "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"}
    compilation = compile_prompt_to_comfyui_workflow(
        positive, negative, profile, checkpoint=ask.get("checkpoint") or profile.get("diffusion_model", ""),
        seed=ask.get("seed"), reference_files=refs, available_node_types=nodes,
        positive_prompt_globals="" if profile.get("disable_prompt_globals") else machine.get("PositivePromptGlobals", ""),
        negative_prompt_globals="" if profile.get("disable_prompt_globals") else machine.get("NegativePromptGlobals", ""))
    bindings = []
    for ref in compilation.debug.get("references_used", []):
        name = ref.get("comfyui_input_name") or Path(ref["path"]).name
        for node, definition in compilation.workflow.items():
            if definition.get("class_type") == "LoadImage" and definition.get("inputs", {}).get("image") == name:
                bindings.append({"node": node, "file": ref["path"], "input": "image"})
    metadata = {"backend": "comfyui", "profile": ask["render_preset"], "workflow_kind": compilation.workflow_kind,
                "checkpoint": ask.get("checkpoint") or profile.get("diffusion_model", ""),
                "seed": compilation.seed, "resolved_seed": compilation.seed, "width": compilation.width,
                "height": compilation.height, "prompts": compilation.prompts, "qwen_reference_preparation": preparation,
                "qwen_reference_cache": compilation.debug.get("qwen_reference_cache")}
    # Managed ComfyUI may be stopped until this request is admitted. Treat its
    # checkpoint as available here; the proxy reports actual model failures from
    # the submitted job.
    write_json_atomic(staging / "ComfyUI_Workflow_API.json", compilation.workflow)
    write_json_atomic(staging / "ComfyUI_Compilation_Debug.json", {**compilation.debug, **metadata})
    return {"version": 1, "provider": "comfyui", "model": metadata["checkpoint"], "workflow": compilation.workflow,
            "bindings": bindings, "output": ask["expected_output"], "options": {"timeout_seconds": 7500},
            "render_metadata": metadata}
