#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import copy
import json
import random
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid


DEFAULT_NEGATIVE_PROMPT = (
    "low quality, worst quality, blurry, cropped, text, watermark, signature, "
    "bad anatomy, bad hands, extra fingers, missing fingers, extra limbs, "
    "deformed, disfigured, distorted proportions, sexualized, revealing clothing, "
    "dramatic lighting, narrative background, props, weapons"
)

NEGATIVE_SECTION_MARKER = "Negative constraints:"


class LocalRenderError(Exception):
    pass


class LocalRenderUnavailable(LocalRenderError):
    pass


@dataclass
class LocalRenderResult:
    image_path: Path
    metadata_path: Path
    prompt_review_path: Path | None
    prompt_id: str


def load_presets(project_root: Path) -> dict[str, Any]:
    path = project_root / "Config" / "Local_Render_Presets.json"
    if not path.exists():
        raise LocalRenderError(f"Missing local render presets: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_preset(project_root: Path, preset_name: str) -> dict[str, Any]:
    presets = load_presets(project_root)
    preset = presets.get(preset_name)
    if not isinstance(preset, dict):
        raise LocalRenderError(f"Unknown local render preset: {preset_name}")
    if preset.get("backend") != "comfyui":
        raise LocalRenderError(f"Preset {preset_name} does not use the comfyui backend.")
    return preset


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise LocalRenderError(f"Missing ComfyUI workflow: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _post_json(server_url: str, path: str, payload: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
    url = server_url.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise LocalRenderUnavailable("Local render backend unavailable.") from exc


def _get_bytes(server_url: str, path: str, query: dict[str, str] | None = None, timeout: int = 20) -> bytes:
    url = server_url.rstrip("/") + path
    if query:
        url += "?" + urlencode(query)
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read()
    except URLError as exc:
        raise LocalRenderUnavailable("Local render backend unavailable.") from exc


def _get_json(server_url: str, path: str, timeout: int = 10) -> dict[str, Any]:
    try:
        return json.loads(_get_bytes(server_url, path, timeout=timeout).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalRenderError(f"ComfyUI returned invalid JSON for {path}.") from exc


def _link_source(workflow: dict[str, Any], link_id: int) -> list[Any] | None:
    for link in workflow.get("links", []):
        if isinstance(link, list) and len(link) >= 3 and link[0] == link_id:
            return [str(link[1]), link[2]]
    return None


def _node_by_id(workflow: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(node["id"]): node for node in workflow.get("nodes", []) if isinstance(node, dict) and "id" in node}


def is_api_prompt(workflow: dict[str, Any]) -> bool:
    return bool(workflow) and all(
        isinstance(node, dict) and "class_type" in node and "inputs" in node
        for node in workflow.values()
    )


def _widget_inputs(node: dict[str, Any]) -> dict[str, Any]:
    values = list(node.get("widgets_values") or [])
    node_type = node.get("type")
    if node_type == "CheckpointLoaderSimple" and values:
        return {"ckpt_name": values[0]}
    if node_type == "CLIPTextEncode" and values:
        return {"text": values[0]}
    if node_type == "EmptyLatentImage" and len(values) >= 3:
        return {"width": values[0], "height": values[1], "batch_size": values[2]}
    if node_type == "KSampler" and len(values) >= 7:
        return {
            "seed": values[0],
            "steps": values[2],
            "cfg": values[3],
            "sampler_name": values[4],
            "scheduler": values[5],
            "denoise": values[6],
        }
    if node_type == "VAEDecode":
        return {}
    if node_type == "SaveImage" and values:
        return {"filename_prefix": values[0]}
    return {}


def workflow_to_api_prompt(workflow: dict[str, Any]) -> dict[str, Any]:
    if is_api_prompt(workflow):
        return {
            str(node_id): {
                "class_type": node["class_type"],
                "inputs": copy.deepcopy(node.get("inputs", {})),
            }
            for node_id, node in workflow.items()
        }

    prompt: dict[str, Any] = {}
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict) or "id" not in node or "type" not in node:
            continue
        if str(node["type"]).endswith("Note"):
            continue
        inputs = _widget_inputs(node)
        for input_spec in node.get("inputs", []) or []:
            if not isinstance(input_spec, dict) or "link" not in input_spec or input_spec["link"] is None:
                continue
            source = _link_source(workflow, input_spec["link"])
            if source is not None:
                inputs[input_spec["name"]] = source
        prompt[str(node["id"])] = {"class_type": node["type"], "inputs": inputs}
    return prompt


def _ksampler_nodes(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in workflow.get("nodes", []) if isinstance(node, dict) and node.get("type") == "KSampler"]


def _clip_node_for_ksampler_input(workflow: dict[str, Any], ksampler: dict[str, Any], input_name: str) -> dict[str, Any] | None:
    nodes = _node_by_id(workflow)
    for input_spec in ksampler.get("inputs", []) or []:
        if input_spec.get("name") != input_name:
            continue
        source = _link_source(workflow, input_spec.get("link"))
        if source is None:
            return None
        node = nodes.get(int(source[0]))
        if node and node.get("type") == "CLIPTextEncode":
            return node
    return None


def inject_preview_values(
    workflow: dict[str, Any],
    api_prompt: dict[str, Any],
    positive_prompt: str,
    preset: dict[str, Any],
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
) -> None:
    seed = preset.get("seed", "random")
    if str(seed).lower() == "random":
        seed = random.randint(1, 2**63 - 1)

    if is_api_prompt(workflow):
        for node in api_prompt.values():
            if node.get("class_type") != "KSampler":
                continue
            inputs = node.get("inputs", {})
            for input_name, text in (("positive", positive_prompt), ("negative", negative_prompt)):
                link = inputs.get(input_name)
                if isinstance(link, list) and link:
                    clip_node = api_prompt.get(str(link[0]))
                    if clip_node and clip_node.get("class_type") == "CLIPTextEncode":
                        clip_node.setdefault("inputs", {})["text"] = text
    else:
        ksamplers = _ksampler_nodes(workflow)
        for ksampler in ksamplers:
            positive_node = _clip_node_for_ksampler_input(workflow, ksampler, "positive")
            negative_node = _clip_node_for_ksampler_input(workflow, ksampler, "negative")
            if positive_node:
                api_prompt[str(positive_node["id"])]["inputs"]["text"] = positive_prompt
            if negative_node:
                api_prompt[str(negative_node["id"])]["inputs"]["text"] = negative_prompt

    for node_id, node in api_prompt.items():
        class_type = node.get("class_type")
        inputs = node.setdefault("inputs", {})
        if class_type == "EmptyLatentImage":
            for key in ("width", "height", "batch_size"):
                if key in inputs and key in preset:
                    inputs[key] = preset[key]
        if class_type == "KSampler":
            for key in ("steps", "cfg"):
                if key in inputs and key in preset:
                    inputs[key] = preset[key]
            if "seed" in inputs:
                inputs["seed"] = seed
        if class_type == "SaveImage" and "filename_prefix" in inputs:
            inputs["filename_prefix"] = "Zet_Local_Test"


def split_positive_negative_prompt(prompt_text: str) -> tuple[str, str]:
    if NEGATIVE_SECTION_MARKER not in prompt_text:
        return prompt_text, DEFAULT_NEGATIVE_PROMPT
    positive, negative = prompt_text.split(NEGATIVE_SECTION_MARKER, 1)
    negative_parts = [negative.strip(), DEFAULT_NEGATIVE_PROMPT]
    return positive.rstrip(), "\n\n".join(part for part in negative_parts if part)


def sampler_settings(api_prompt: dict[str, Any]) -> dict[str, Any]:
    for node in api_prompt.values():
        if node.get("class_type") == "KSampler":
            inputs = node.get("inputs", {})
            return {
                "width": next(
                    (
                        latent.get("inputs", {}).get("width")
                        for latent in api_prompt.values()
                        if latent.get("class_type") == "EmptyLatentImage"
                    ),
                    None,
                ),
                "height": next(
                    (
                        latent.get("inputs", {}).get("height")
                        for latent in api_prompt.values()
                        if latent.get("class_type") == "EmptyLatentImage"
                    ),
                    None,
                ),
                "steps": inputs.get("steps"),
                "cfg": inputs.get("cfg"),
                "batch_size": next(
                    (
                        latent.get("inputs", {}).get("batch_size")
                        for latent in api_prompt.values()
                        if latent.get("class_type") == "EmptyLatentImage"
                    ),
                    None,
                ),
                "seed": inputs.get("seed"),
            }
    return {}


def queue_prompt(server_url: str, api_prompt: dict[str, Any]) -> str:
    response = _post_json(
        server_url,
        "/prompt",
        {"prompt": api_prompt, "client_id": str(uuid.uuid4())},
        timeout=10,
    )
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise LocalRenderError("ComfyUI did not return a prompt_id.")
    return str(prompt_id)


def wait_for_history(server_url: str, prompt_id: str, timeout_seconds: int = 240) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + timeout_seconds
    while datetime.now().timestamp() < deadline:
        history = _get_json(server_url, f"/history/{prompt_id}", timeout=10)
        item = history.get(prompt_id)
        if isinstance(item, dict):
            return item
        import time

        time.sleep(1)
    raise LocalRenderError("Timed out waiting for ComfyUI render completion.")


def first_output_image(history_item: dict[str, Any]) -> dict[str, Any]:
    outputs = history_item.get("outputs", {})
    if not isinstance(outputs, dict):
        raise LocalRenderError("ComfyUI history did not include outputs.")
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        images = output.get("images")
        if isinstance(images, list) and images:
            image = images[0]
            if isinstance(image, dict) and image.get("filename"):
                return image
    raise LocalRenderError("ComfyUI did not return an image output.")


def append_prompt_review_entry(prompt_review_path: Path | None, image_path: Path, metadata_path: Path, prompt_id: str) -> None:
    if prompt_review_path is None:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        "\n## Local Test Renders\n\n"
        f"- {timestamp}: `{image_path}`\n"
        f"  - Metadata: `{metadata_path}`\n"
        f"  - ComfyUI prompt id: `{prompt_id}`\n"
    )
    if prompt_review_path.exists():
        text = prompt_review_path.read_text(encoding="utf-8")
        if "## Local Test Renders" in text:
            entry = (
                f"\n- {timestamp}: `{image_path}`\n"
                f"  - Metadata: `{metadata_path}`\n"
                f"  - ComfyUI prompt id: `{prompt_id}`\n"
            )
        prompt_review_path.write_text(text.rstrip() + entry, encoding="utf-8")


def render_preview(
    *,
    project_root: Path,
    final_prompt_path: Path,
    job_output_dir: Path,
    prompt_review_path: Path | None = None,
    preset_name: str = "body-reference-preview",
) -> LocalRenderResult:
    preset = load_preset(project_root, preset_name)
    server_url = str(preset.get("server_url", "http://127.0.0.1:8188"))
    workflow_path = project_root / str(preset["workflow_file"])
    prompt_text = final_prompt_path.read_text(encoding="utf-8")
    positive_prompt, negative_prompt = split_positive_negative_prompt(prompt_text)
    workflow = _read_json(workflow_path)
    api_prompt = workflow_to_api_prompt(workflow)
    inject_preview_values(workflow, api_prompt, positive_prompt, preset, negative_prompt)
    settings = sampler_settings(api_prompt)

    prompt_id = queue_prompt(server_url, api_prompt)
    history_item = wait_for_history(server_url, prompt_id)
    output_image = first_output_image(history_item)
    image_bytes = _get_bytes(
        server_url,
        "/view",
        {
            "filename": str(output_image["filename"]),
            "subfolder": str(output_image.get("subfolder", "")),
            "type": str(output_image.get("type", "output")),
        },
        timeout=30,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    render_dir = job_output_dir / str(preset.get("output_subdir", "Local_Test_Renders"))
    render_dir.mkdir(parents=True, exist_ok=True)
    image_path = render_dir / f"test_{stamp}.png"
    metadata_path = render_dir / f"test_{stamp}.json"
    image_path.write_bytes(image_bytes)
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "preset": preset_name,
        "backend": "comfyui",
        "server_url": server_url,
        "workflow_file": str(workflow_path),
        "final_prompt": str(final_prompt_path),
        "prompt_id": prompt_id,
        "comfyui_image": output_image,
        "local_image": str(image_path),
        "settings": settings,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_prompt_review_entry(prompt_review_path, image_path, metadata_path, prompt_id)

    return LocalRenderResult(
        image_path=image_path,
        metadata_path=metadata_path,
        prompt_review_path=prompt_review_path,
        prompt_id=prompt_id,
    )
