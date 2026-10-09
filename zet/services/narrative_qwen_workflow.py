"""Prompt-only Qwen graph. No scene schemas, layout planners or enrichment."""
from pathlib import Path

from zet.services.local_render_types import LocalRenderError


WORKFLOW_KIND = "qwen_narrative_prompt"


def compile_narrative_qwen(positive_prompt, negative_prompt, profile, *, checkpoint, seed, width, height,
                           output_prefix, reference_files=None, available_node_types=None, **_kwargs):
    from zet.services.comfyui_workflow_registry import ComfyUICompilation, _apply_qwen_reference_cache

    refs = reference_files or []
    if len(refs) > 10:
        raise LocalRenderError("Narrative Qwen rendering accepts up to ten reference images.")
    required = {"UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21", "EmptyLatentImage",
                "KSampler", "VAEDecode", "SaveImage"}
    if refs:
        required.add("LoadImage")
    missing = required - (available_node_types or set())
    if missing:
        raise LocalRenderError("Narrative Qwen requires unavailable nodes: " + ", ".join(sorted(missing)))
    if not checkpoint or not profile.get("text_encoder") or not profile.get("vae"):
        raise LocalRenderError("Narrative Qwen needs a diffusion model, text encoder and VAE.")
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": profile["text_encoder"], "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": profile["vae"]}},
    }
    encode = {"clip": ["2", 0], "vae": ["3", 0], "prompt": positive_prompt,
              "negative_prompt": negative_prompt, "resolution": max(width, height)}
    bindings = []
    for index, ref in enumerate(refs, 1):
        source = Path(str(ref.get("path") or ""))
        if not source.is_file():
            raise LocalRenderError(f"Narrative reference {index} is missing.")
        name = ref.get("comfyui_input_name") or source.name
        node = str(index + 9)
        graph[node] = {"class_type": "LoadImage", "inputs": {"image": name}}
        encode[f"images.image_{index}"] = [node, 0]
        bindings.append({**ref, "comfyui_input_name": name, "image_index": index})
    graph["4"] = {"class_type": "TextEncodeQwenImage21", "inputs": encode}
    graph["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
    graph["6"] = {"class_type": "KSampler", "inputs": {
        "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0],
        "seed": seed, "steps": int(profile.get("steps", 40)), "cfg": float(profile.get("cfg", 1.0)),
        "sampler_name": profile.get("sampler_name", "euler"), "scheduler": profile.get("scheduler", "simple"),
        "denoise": float(profile.get("denoise", 1.0)),
    }}
    graph["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}}
    graph["8"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": output_prefix, "images": ["7", 0]}}
    cache = _apply_qwen_reference_cache(graph, profile, len(refs), available_node_types)
    return ComfyUICompilation(graph, {"global": positive_prompt, "negative": negative_prompt}, seed, width, height,
                              WORKFLOW_KIND, {"references_used": bindings, "qwen_reference_cache": cache})
