#!/usr/bin/env python3
"""
Claim Zet file-proxy local image render asks and complete them with the
configured local render backend.

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

WORKER_VERSION = "1.0"
SUPPORTED_WORKER_TYPES = {"local_image_render"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(message: str, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(f"{now_iso()} {message}", file=stream, flush=True)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict) -> None:
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    ensure_directory(path.parent)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def ensure_dirs(proxy_root: Path, worker_id: str) -> dict[str, Path]:
    dirs = {
        "ask": proxy_root / "Ask",
        "claims": proxy_root / "Claims",
        "claimed": proxy_root / "Claimed" / worker_id,
        "answer": proxy_root / "Answer",
        "failed": proxy_root / "Failed" / worker_id,
        "control": proxy_root / "Control",
        "monitor_requests": proxy_root / "Monitor" / "Requests",
        "monitor_responses": proxy_root / "Monitor" / "Responses" / worker_id,
    }
    for path in dirs.values():
        ensure_directory(path)
    return dirs


def normalize_proxy_root(path: Path) -> Path:
    if path.name != "Ollama_Proxy" and (path.name == "AI_Queue" or (path / "Ollama_Proxy").exists()):
        return path / "Ollama_Proxy"
    return path


def write_claim_file(path: Path, ask_name: str, worker_id: str) -> bool:
    data = {
        "version": 1,
        "ask_folder": ask_name,
        "worker_id": worker_id,
        "claimed_at": now_iso(),
        "host": socket.gethostname(),
        "pid": os.getpid(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(str(path), flags)
    except FileExistsError:
        return False
    except Exception:
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except Exception:
                pass
        return True
    except Exception:
        path.unlink(missing_ok=True)
        return False


def claim_one_local_render(dirs: dict[str, Path], worker_id: str) -> Path | None:
    for ask in sorted(dirs["ask"].iterdir() if dirs["ask"].exists() else []):
        if not ask.is_dir() or not ask.name.startswith("Ask_"):
            continue
        ask_manifest = read_json(ask / "ask_manifest.json")
        if ask_manifest.get("worker_type") not in SUPPORTED_WORKER_TYPES:
            continue

        claim_file = dirs["claims"] / f"{ask.name}.claim.json"
        if not write_claim_file(claim_file, ask.name, worker_id):
            continue

        dest = dirs["claimed"] / ask.name
        try:
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(str(ask), str(dest))
            shutil.copy2(str(claim_file), str(dest / "claim_manifest.json"))
            shutil.rmtree(ask, ignore_errors=True)
            log(f"CLAIMED {ask.name} -> {dest}")
            return dest
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            claim_file.unlink(missing_ok=True)
            continue
    return None


def move_to_answer(folder: Path, dirs: dict[str, Path]) -> Path:
    dest = dirs["answer"] / folder.name
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(folder), str(dest))
    return dest


def release_claim_to_ask(folder: Path, dirs: dict[str, Path], worker_id: str, reason: str) -> None:
    ask_name = folder.name
    claim_file = dirs["claims"] / f"{ask_name}.claim.json"
    ask_dest = dirs["ask"] / ask_name
    claim_file.unlink(missing_ok=True)
    (folder / "claim_manifest.json").unlink(missing_ok=True)
    write_json(
        folder / "transient_worker_status.json",
        {
            "version": 1,
            "status": "RETRY_LATER",
            "worker_id": worker_id,
            "reason": reason,
            "released_at": now_iso(),
        },
    )
    if ask_dest.exists():
        failed_dest = dirs["failed"] / f"{ask_name}__released_duplicate_{int(time.time())}"
        shutil.move(str(folder), str(failed_dest))
        log(f"RETRY_LATER_DUPLICATE {ask_name}: {reason}; parked at {failed_dest}", error=True)
        return
    shutil.move(str(folder), str(ask_dest))
    log(f"RETRY_LATER_RELEASED {ask_name} -> {ask_dest}: {reason}", error=True)


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
        kwargs["reference_files"] = ask_manifest.get("reference_files") or []
    if "aspect_ratio" in parameters:
        kwargs["aspect_ratio"] = str(ask_manifest.get("aspect_ratio") or "")
    return kwargs


def process_monitor_tests(dirs: dict[str, Path], worker_id: str) -> int:
    responses_written = 0
    host = socket.gethostname()
    for request_dir in sorted(path for path in dirs["monitor_requests"].iterdir() if path.is_dir()):
        test_id = request_dir.name
        response_path = dirs["monitor_responses"] / f"{test_id}.json"
        if response_path.exists():
            continue

        instruction = str(read_json(request_dir / "request.json").get("instruction") or "").strip()
        payload = {
            "version": 1,
            "test_id": test_id,
            "worker_id": worker_id,
            "host": host,
            "status": "ONLINE",
            "ollama_ok": False,
            "models": [],
            "message": instruction or "Monitoring and connected to local image worker.",
            "responded_at": now_iso(),
            "worker_type": "local_image_render",
        }
        write_json(response_path, payload)
        print(f"MONITOR_RESPONSE {worker_id} -> {response_path}")
        responses_written += 1
    return responses_written


def process_claimed(folder: Path, dirs: dict[str, Path], worker_id: str, return_transient_to_ask: bool) -> str:
    ask_manifest = read_json(folder / "ask_manifest.json")
    prompt_file = str(ask_manifest.get("prompt_file") or "Final_Image_Prompt.md")
    expected_output = str(ask_manifest.get("expected_output") or "")
    preset_name = str(ask_manifest.get("render_preset") or "body-reference-preview")
    answer_manifest = answer_manifest_base(ask_manifest, worker_id, expected_output)
    t0 = time.time()
    log(
        "START "
        f"{folder.name} ask_id={ask_manifest.get('ask_id') or folder.name} "
        f"asset_id={ask_manifest.get('asset_id') or ''} "
        f"worker_type={ask_manifest.get('worker_type') or ''} "
        f"task_type={ask_manifest.get('task_type') or ''} "
        f"preset={preset_name} expected_output={expected_output or '<blank>'}"
    )

    try:
        if ask_manifest.get("worker_type") not in SUPPORTED_WORKER_TYPES:
            raise ValueError(f"Unsupported local image worker_type: {ask_manifest.get('worker_type')}")
        if not expected_output:
            raise ValueError("ask_manifest expected_output is blank")
        prompt_path = folder / prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file missing: {prompt_file}")

        result = render_image(**render_image_kwargs(ask_manifest, prompt_path, folder, preset_name))
        shutil.copy2(result.image_path, folder / expected_output)
        write_json(
            folder / "LOCAL_RENDER_METADATA.json",
            {
                "version": 1,
                "preset": preset_name,
                "local_render": str(result.image_path),
                "local_render_metadata": str(result.metadata_path),
                "backend_prompt_id": result.prompt_id,
                "candidate_output": expected_output,
                "completed_at": now_iso(),
            },
        )

        answer_manifest["status"] = "SUCCESS"
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(folder / "answer_manifest.json", answer_manifest)
        dest = move_to_answer(folder, dirs)
        log(f"DONE SUCCESS {folder.name} -> {dest} elapsed={answer_manifest['elapsed_seconds']}s")
        return "SUCCESS"
    except LocalRenderUnavailable as exc:
        if return_transient_to_ask:
            release_claim_to_ask(folder, dirs, worker_id, str(exc))
            log(f"DONE RETRY_LATER {folder.name}: {exc}", error=True)
            return "RETRY_LATER"
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
    dest = move_to_answer(folder, dirs)
    log(
        f"DONE {answer_manifest['status']} {folder.name} -> {dest} "
        f"elapsed={answer_manifest['elapsed_seconds']}s: {answer_manifest['error_message']}",
        error=True,
    )
    return str(answer_manifest["status"])


def default_proxy_root(config_path: Path) -> Path:
    from zet.services.config_service import ConfigService

    config = ConfigService.load(config_path)
    return Path(config.base_ai_queue_path) / "Ollama_Proxy"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claim and process Zet local image render proxy ask folders.")
    parser.add_argument("--config", default="config.toml", help="Zet config path, used when --proxy-root is omitted")
    parser.add_argument("--proxy-root", default="", help="Path to Zet proxy root")
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-local-image", help="Worker ID for claim and answer manifests")
    parser.add_argument("--poll-seconds", type=int, default=30, help="Seconds between polls in loop mode")
    parser.add_argument("--once", action="store_true", help="Process at most one ask and exit")
    parser.add_argument("--max-jobs", type=int, default=None, help="Process at most N asks and exit")
    parser.add_argument("--send-transient-to-answer", action="store_true", help="Write RETRY_LATER answer folders instead of returning Ask")
    args = parser.parse_args(argv)

    proxy_root = Path(args.proxy_root).expanduser() if args.proxy_root else default_proxy_root(Path(args.config))
    proxy_root = normalize_proxy_root(proxy_root).resolve()
    dirs = ensure_dirs(proxy_root, args.worker_id)
    processed = 0
    log(f"Local image worker {args.worker_id} v{WORKER_VERSION} watching {proxy_root}")

    while True:
        process_monitor_tests(dirs, args.worker_id)
        claimed = claim_one_local_render(dirs, args.worker_id)
        if claimed is None:
            if args.once or (args.max_jobs is not None and processed >= args.max_jobs):
                return 0
            time.sleep(args.poll_seconds)
            continue

        result = process_claimed(
            claimed,
            dirs,
            args.worker_id,
            return_transient_to_ask=not args.send_transient_to_answer,
        )
        if result in {"SUCCESS", "ERROR"}:
            processed += 1

        if args.once or (args.max_jobs is not None and processed >= args.max_jobs):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
