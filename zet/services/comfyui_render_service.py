from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
import mimetypes
from pathlib import Path
import random
import time
from typing import Any
import urllib.parse
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zet.services.comfyui_workflow_registry import (
    ComfyUICompilation,
    compile_prompt_workflow,
    compile_scene_workflow,
    workflow_kind_for_profile,
)
from zet.services.local_render_types import LocalRenderError, LocalRenderUnavailable
from zet.services.scene_render_compiler import validate_scene_render_ir
from zet.services.atomic_file_service import write_json_atomic, write_bytes_atomic
from zet.services.workflow_storage import file_lock, validate_image


@dataclass(frozen=True)
class ComfyUIRunResult:
    prompt_id: str
    image_paths: list[Path]
    outputs: dict[str, Any]
    history: dict[str, Any]


def _even8(value: float) -> int:
    return max(8, int(round(value / 8.0)) * 8)


def _render_size(ir: dict[str, Any] | None, profile: dict[str, Any]) -> tuple[int, int]:
    aspect_ratio = str((ir or {}).get("canvas", {}).get("aspect_ratio") or profile.get("aspect_ratio") or "")
    try:
        width_ratio, height_ratio = (float(item.strip()) for item in aspect_ratio.split(":", 1))
        if width_ratio <= 0 or height_ratio <= 0:
            raise ValueError
        if profile.get("workflow_kind") == "qwen_image_21_scene_preview":
            pixel_budget = int(profile.get("pixel_budget") or 1024 * 1024)
            width = max(32, round((pixel_budget * width_ratio / height_ratio) ** 0.5 / 32) * 32)
            height = max(32, round((pixel_budget * height_ratio / width_ratio) ** 0.5 / 32) * 32)
            return width, height
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


def compile_ir_to_comfyui_workflow(
    ir: dict[str, Any],
    profile: dict[str, Any],
    *,
    checkpoint: str,
    positive_prompt_globals: str = "",
    negative_prompt_globals: str = "",
    seed: int | None = None,
    output_prefix: str = "Zet/Scene",
    reference_files: list[dict[str, Any]] | None = None,
    available_node_types: set[str] | None = None,
    scene_prompt_override: str = "",
) -> ComfyUICompilation:
    if profile.get("workflow_kind") == "qwen_image_21_scene_preview" and len(ir.get("image_inputs") or []) > 10:
        raise LocalRenderError("Qwen Image 2.1 supports at most ten scene reference images.")
    validate_scene_render_ir(ir)
    resolved_seed = _resolved_seed(profile, seed)
    width, height = _render_size(ir, profile)
    return compile_scene_workflow(
        workflow_kind_for_profile(profile),
        ir,
        profile,
        checkpoint=checkpoint,
        seed=resolved_seed,
        width=width,
        height=height,
        positive_prompt_globals=positive_prompt_globals,
        negative_prompt_globals=negative_prompt_globals,
        output_prefix=output_prefix,
        reference_files=reference_files,
        available_node_types=available_node_types,
        scene_prompt_override=scene_prompt_override,
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
    reference_files: list[dict[str, Any]] | None = None,
    available_node_types: set[str] | None = None,
) -> ComfyUICompilation:
    resolved_seed = _resolved_seed(profile, seed)
    width, height = _render_size({"canvas": {"aspect_ratio": aspect_ratio}}, profile)
    return compile_prompt_workflow(
        workflow_kind_for_profile(profile, prompt_only=True),
        positive_prompt,
        negative_prompt,
        profile,
        checkpoint=checkpoint,
        seed=resolved_seed,
        width=width,
        height=height,
        positive_prompt_globals=positive_prompt_globals,
        negative_prompt_globals=negative_prompt_globals,
        output_prefix=output_prefix,
        reference_files=reference_files,
        available_node_types=available_node_types,
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


def list_comfyui_node_types(server_url: str) -> set[str]:
    payload = _request_json(f"{server_url.rstrip('/')}/object_info")
    if not isinstance(payload, dict):
        raise LocalRenderError("ComfyUI object_info response must be a JSON object.")
    return {str(key) for key in payload}


def comfyui_model_options(server_url: str, node_type: str, input_name: str) -> set[str]:
    payload = _request_json(f"{server_url.rstrip('/')}/object_info/{urllib.parse.quote(node_type)}")
    node = payload.get(node_type) if isinstance(payload, dict) else None
    required = node.get("input", {}).get("required", {}) if isinstance(node, dict) else {}
    definition = required.get(input_name)
    if not isinstance(definition, list) or not definition:
        return set()
    raw = definition[0]
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if len(definition) > 1 and isinstance(definition[1], dict):
        return {str(item) for item in definition[1].get("options", [])}
    return set()


def _upload_comfyui_input(server_url: str, reference: dict[str, Any], timeout: float = 60) -> None:
    source = Path(str(reference.get("path") or "")).expanduser()
    if not source.is_file():
        raise LocalRenderError(f"ComfyUI reference image file is missing: {source}")
    input_name = str(reference.get("comfyui_input_name") or source.name).replace("\\", "/")
    input_path = Path(input_name)
    filename = input_path.name
    subfolder = input_path.parent.as_posix()
    if subfolder == ".":
        subfolder = ""

    boundary = f"----ZetComfyUI{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="subfolder"\r\n\r\n{subfolder}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'.encode(),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode(),
        source.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    url = f"{server_url.rstrip('/')}/upload/image"
    request = Request(url, data=b"".join(parts), method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise LocalRenderUnavailable(f"ComfyUI reference upload failed: {url}") from exc
    except json.JSONDecodeError as exc:
        raise LocalRenderError(f"ComfyUI returned invalid JSON: {url}") from exc
    if not isinstance(payload, dict) or not payload.get("name"):
        raise LocalRenderError("ComfyUI reference upload response did not include a filename.")


def run_comfyui_workflow(
    workflow: dict[str, Any],
    *,
    server_url: str,
    output_dir: Path,
    reference_files: list[dict[str, Any]] | None = None,
    poll_seconds: float = 1.0,
    timeout_seconds: float = 300.0,
) -> ComfyUIRunResult:
    with file_lock(output_dir / "ComfyUI_Submission.lock"):
        return _run_comfyui_workflow(workflow, server_url=server_url, output_dir=output_dir,
                                    reference_files=reference_files, poll_seconds=poll_seconds,
                                    timeout_seconds=timeout_seconds)


def _run_comfyui_workflow(workflow, *, server_url, output_dir, reference_files, poll_seconds, timeout_seconds):
    base_url = server_url.rstrip("/")
    journal_path = output_dir / "ComfyUI_Submission.json"
    journal = json.loads(journal_path.read_text(encoding="utf-8")) if journal_path.is_file() else {}
    fingerprint = hashlib.sha256(json.dumps(workflow, sort_keys=True).encode("utf-8")).hexdigest()
    if journal.get("status") == "SUBMITTING":
        raise LocalRenderError(f"Previous ComfyUI submission has an unknown outcome. Check the server queue before resetting {journal_path}.")
    resuming = journal.get("status") == "PENDING" and journal.get("prompt_id")
    if resuming:
        if journal.get("server_url") != base_url:
            raise LocalRenderError("A pending ComfyUI render belongs to another server; recover it before starting another render.")
        if journal.get("workflow_sha256") != fingerprint:
            raise LocalRenderError("A pending ComfyUI render uses different inputs. Restore its settings and retry before starting another render.")
        submitted = {"prompt_id": journal["prompt_id"]}
    else:
        for reference in reference_files or []:
            _upload_comfyui_input(base_url, reference)
        journal = {"status": "SUBMITTING", "server_url": base_url, "workflow_sha256": fingerprint}
        write_json_atomic(journal_path, journal)
        submitted = _request_json(f"{base_url}/prompt", "POST", {"prompt": workflow})
    if not isinstance(submitted, dict):
        raise LocalRenderError("ComfyUI prompt response must be a JSON object.")
    if submitted.get("node_errors") or submitted.get("error"):
        details = submitted.get("node_errors") or submitted.get("error")
        write_json_atomic(journal_path, {**journal, "status": "FAILED", "error": details})
        raise LocalRenderError(f"ComfyUI workflow validation failed: {json.dumps(details, ensure_ascii=False)}")
    prompt_id = str(submitted.get("prompt_id") or "")
    if not prompt_id:
        raise LocalRenderError("ComfyUI prompt response did not include prompt_id.")
    journal.update(status="PENDING", prompt_id=prompt_id)
    write_json_atomic(journal_path, journal)

    deadline = time.monotonic() + timeout_seconds
    record: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        history = _request_json(f"{base_url}/history/{urllib.parse.quote(prompt_id)}")
        if isinstance(history, dict) and isinstance(history.get(prompt_id), dict):
            record = history[prompt_id]
            break
        time.sleep(max(0.0, poll_seconds))
    if record is None:
        raise LocalRenderError(f"ComfyUI workflow {prompt_id} timed out after {timeout_seconds:g} seconds. Retry to resume this job.")
    status = record.get("status") if isinstance(record.get("status"), dict) else {}
    if status.get("status_str") == "error":
        write_json_atomic(journal_path, {**journal, "status": "FAILED", "error": status})
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
            job_key = hashlib.sha256(prompt_id.encode("utf-8")).hexdigest()[:12]
            destination = output_dir / f"{job_key}_{len(image_paths) + 1}_{safe_name}"
            contents = _request_bytes(f"{base_url}/view?{query}")
            validate_image(contents)
            write_bytes_atomic(destination, contents)
            image_paths.append(destination)
    if not image_paths:
        raise LocalRenderError("ComfyUI completed without returning an image.")
    write_json_atomic(journal_path, {**journal, "status": "COMPLETE", "image_paths": [str(path) for path in image_paths]})
    return ComfyUIRunResult(prompt_id=prompt_id, image_paths=image_paths, outputs=outputs, history=record)
