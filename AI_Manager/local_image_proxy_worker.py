#!/usr/bin/env python3
"""
Process one Zet file-proxy local-image job with the configured render backend.

The queue contract is backend-neutral:
- ask_manifest.json worker_type = "local_image_render"
- ask_manifest.json render_preset selects a preset from Config/Local_Render_Presets.json
- the preset's backend field selects the render adapter
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import shutil
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("ZET_PROJECT_ROOT", "")).resolve() if os.environ.get("ZET_PROJECT_ROOT") else DEFAULT_PROJECT_ROOT
if not (PROJECT_ROOT / "Config").exists() and (SCRIPT_DIR / "Config").exists():
    PROJECT_ROOT = SCRIPT_DIR

for import_path in (
    PROJECT_ROOT,
    PROJECT_ROOT / "Scripts",
    SCRIPT_DIR,
    SCRIPT_DIR / "Scripts",
):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "Scripts"):
    import_text = str(import_path)
    while import_text in sys.path:
        sys.path.remove(import_text)
    sys.path.insert(0, import_text)

from Local_Render_Adapters import LocalRenderUnavailable, render_image
from zet.models.ai_proxy import AIProxyAskManifest
from zet.services.atomic_file_service import write_json_atomic
from AI_Manager.proxy_worker_output import log_job

SUPPORTED_WORKER_TYPES = {"local_image_render"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_ask_manifest(path: Path) -> dict:
    return AIProxyAskManifest.from_dict(read_json(path)).to_dict()


def write_json(path: Path, data: dict) -> None:
    write_json_atomic(path, data)


def localize_output_json_paths(folder: Path) -> None:
    root = folder.resolve()

    def localize(value):
        if isinstance(value, dict):
            return {key: localize(child) for key, child in value.items()}
        if isinstance(value, list):
            return [localize(child) for child in value]
        if not isinstance(value, str) or not Path(value).is_absolute():
            return value
        try:
            return Path(value).resolve().relative_to(root).as_posix()
        except (OSError, ValueError):
            return value

    for path in folder.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        localized = localize(payload)
        if localized != payload:
            write_json(path, localized)


def answer_manifest_base(ask_manifest: dict, worker_id: str, expected_output: str) -> dict:
    return {
        "version": 1,
        "ask_id": ask_manifest.get("ask_id"),
        "asset_id": ask_manifest.get("asset_id"),
        "ollama_attempt_id": ask_manifest.get("ollama_attempt_id") or "",
        "worker_id": worker_id,
        "status": "",
        "expected_output": expected_output,
        "started_at": now_iso(),
        "completed_at": "",
        "elapsed_seconds": 0,
        "error_type": "",
        "error_message": "",
    }


def render_image_kwargs(ask_manifest: dict, prompt_path: Path, folder: Path, preset_name: str) -> dict:
    kwargs = {
        "project_root": PROJECT_ROOT,
        "final_prompt_path": prompt_path,
        "job_output_dir": folder,
        "prompt_review_path": None,
        "preset_name": preset_name,
    }
    parameters = inspect.signature(render_image).parameters
    if "reference_files" in parameters:
        references = []
        for reference in ask_manifest.get("reference_files") or []:
            localized = dict(reference)
            value = str(localized.get("path") or "")
            if value and not Path(value).is_absolute():
                localized["path"] = str((folder / value).resolve())
            references.append(localized)
        kwargs["reference_files"] = references
    if "aspect_ratio" in parameters:
        kwargs["aspect_ratio"] = str(ask_manifest.get("aspect_ratio") or "")
    if "render_layout" in parameters:
        kwargs["render_layout"] = ask_manifest.get("render_layout") or None
    if "scene_render_ir_path" in parameters:
        ir_file = str(ask_manifest.get("scene_render_ir_file") or "").strip()
        kwargs["scene_render_ir_path"] = folder / ir_file if ir_file else None
    if "seed" in parameters:
        value = ask_manifest.get("seed")
        kwargs["seed"] = int(value) if str(value or "").strip() else None
    return kwargs


def process_claimed(
    folder: Path,
    worker_id: str,
    config_path: str | Path = "config.toml",
) -> str:
    ask_manifest = read_ask_manifest(folder / "ask_manifest.json")
    prompt_file = str(ask_manifest.get("prompt_file") or "Final_Image_Prompt.md")
    expected_output = str(ask_manifest.get("expected_output") or "")
    preset_name = str(ask_manifest.get("render_preset") or "body-reference-preview")
    answer_manifest = answer_manifest_base(ask_manifest, worker_id, expected_output)
    t0 = time.time()
    log_job(ask_manifest, "START")

    try:
        if ask_manifest.get("worker_type") not in SUPPORTED_WORKER_TYPES:
            raise ValueError(f"Unsupported local image worker_type: {ask_manifest.get('worker_type')}")
        if not expected_output:
            raise ValueError("ask_manifest expected_output is blank")
        prompt_path = folder / prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file missing: {prompt_file}")

        result = render_image(**render_image_kwargs(ask_manifest, prompt_path, folder, preset_name))
        output_path = folder / expected_output
        if Path(result.image_path).resolve() != output_path.resolve():
            shutil.copy2(result.image_path, output_path)
        backend_metadata = read_json(result.metadata_path) if result.metadata_path.exists() else {}
        artifact_files = []
        for artifact_path in getattr(result, "artifact_paths", []) or []:
            source = Path(artifact_path)
            if not source.exists() or not source.is_file():
                continue
            destination = folder / source.name
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            artifact_files.append(destination.name)
        write_json(
            folder / "LOCAL_RENDER_METADATA.json",
            {
                "version": 1,
                "preset": preset_name,
                "image_generation": ask_manifest.get("image_generation") or backend_metadata.get("backend"),
                "render_profile": preset_name,
                "checkpoint": ask_manifest.get("checkpoint") or backend_metadata.get("checkpoint"),
                "workflow_kind": backend_metadata.get("workflow_kind"),
                "seed": backend_metadata.get("resolved_seed", backend_metadata.get("seed")),
                "local_render": expected_output,
                "local_render_metadata": Path(result.metadata_path).name,
                "backend_prompt_id": result.prompt_id,
                "candidate_output": expected_output,
                "artifact_files": artifact_files,
                "completed_at": now_iso(),
            },
        )

        answer_manifest["status"] = "SUCCESS"
        answer_manifest["render_preset"] = preset_name
        answer_manifest["workflow_kind"] = backend_metadata.get("workflow_kind")
        answer_manifest["seed"] = backend_metadata.get("resolved_seed", backend_metadata.get("seed"))
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(folder / "answer_manifest.json", answer_manifest)
        localize_output_json_paths(folder)
        log_job(ask_manifest, "DONE", result="SUCCESS")
        return "SUCCESS"
    except LocalRenderUnavailable as exc:
        answer_manifest["status"] = "RETRY_LATER"
        answer_manifest["error_type"] = "LOCAL_RENDER_UNAVAILABLE"
        answer_manifest["error_message"] = str(exc)
    except Exception as exc:
        answer_manifest["status"] = "ERROR"
        answer_manifest["error_type"] = "LOCAL_RENDER_WORKER_ERROR"
        answer_manifest["error_message"] = str(exc)

    answer_manifest["completed_at"] = now_iso()
    answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
    write_json(folder / "answer_manifest.json", answer_manifest)
    localize_output_json_paths(folder)
    log_job(
        ask_manifest,
        "DONE",
        result=str(answer_manifest["status"]),
        error_message=str(answer_manifest["error_message"]),
    )
    return str(answer_manifest["status"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one Zet local-image file-proxy job.")
    parser.add_argument("--job-dir", required=True, type=Path)
    parser.add_argument("--config", default="config.toml", help="Zet config path retained for the registered worker contract")
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-local-image", help="Worker ID for claim and answer manifests")
    args = parser.parse_args(argv)
    job_dir = args.job_dir.resolve()
    result = process_claimed(
        job_dir,
        args.worker_id,
        args.config,
    )
    return 0 if result == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
