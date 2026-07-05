#!/usr/bin/env python3
"""
ollama_proxy_worker.py

Disposable filesystem worker for Zet's Ollama file proxy.

This script:
- watches Ask/ for staged asks
- claims one ask at a time using a claim sidecar file
- runs local Ollama against OLLAMA_PROMPT.md
- writes OLLAMA_RESPONSE.md plus answer_manifest.json
- moves completed asks to Answer/

It does not modify Zet asset state.
It does not edit Assets.json.
It does not edit Pipelines.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.services.config_service import ConfigService

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_PROXY_ROOT = ""
WORKER_VERSION = "7D.5"


class TransientOllamaConnectionError(RuntimeError):
    """Raised when Ollama is temporarily unavailable and the ask should be retried later."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_proxy_root() -> Path:
    """Return the configured Ollama proxy root."""
    config = ConfigService.load(PROJECT_ROOT / "config.toml")
    return Path(config.base_ai_queue_path) / "Ollama_Proxy"


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
    missing_paths: list[Path] = []
    current = path

    while True:
        if current.is_dir():
            break
        if current.exists():
            raise FileExistsError(f"Path exists but is not a directory: {current}")
        missing_paths.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    for missing_path in reversed(missing_paths):
        try:
            missing_path.mkdir()
        except FileExistsError:
            # Some macOS-hosted SMB shares surface existing directories as WinError 183.
            time.sleep(0.1)
            continue


def write_json(path: Path, data: dict) -> None:
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    last_exc: BaseException | None = None
    for _attempt in range(3):
        temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
        try:
            ensure_directory(path.parent)
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(path)
            return
        except (FileNotFoundError, FileExistsError) as exc:
            last_exc = exc
            time.sleep(0.2)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
    if last_exc is not None:
        raise last_exc


def write_text_atomic(path: Path, contents: str) -> None:
    last_exc: BaseException | None = None
    for _attempt in range(3):
        temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
        try:
            ensure_directory(path.parent)
            temp_path.write_text(contents, encoding="utf-8")
            temp_path.replace(path)
            return
        except (FileNotFoundError, FileExistsError) as exc:
            last_exc = exc
            time.sleep(0.2)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
    if last_exc is not None:
        raise last_exc


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


def stop_manifest_path(dirs: dict[str, Path]) -> Path:
    return dirs["control"] / "stop.json"


def read_stop_state(dirs: dict[str, Path]) -> dict:
    return read_json(stop_manifest_path(dirs))


def compact_attempt_id(attempt_id: str) -> str:
    return str(attempt_id or "").replace("_", "")


def should_reject_ask(ask_manifest: dict, dirs: dict[str, Path]) -> bool:
    stop_state = read_stop_state(dirs)
    if not bool(stop_state.get("active", False)):
        return False
    reject_before = str(stop_state.get("reject_before_compact") or "")
    attempt_id = compact_attempt_id(str(ask_manifest.get("ollama_attempt_id") or ""))
    if not reject_before or not attempt_id:
        return True
    return attempt_id <= reject_before


def write_rejected_answer(folder: Path, dirs: dict[str, Path], worker_id: str, reason: str) -> str:
    ask_manifest = read_json(folder / "ask_manifest.json")
    answer_manifest = {
        "version": 1,
        "ask_id": ask_manifest.get("ask_id") or folder.name,
        "asset_id": ask_manifest.get("asset_id"),
        "ollama_attempt_id": ask_manifest.get("ollama_attempt_id") or "",
        "worker_id": worker_id,
        "status": "REJECTED",
        "expected_output": ask_manifest.get("expected_output") or "OLLAMA_RESPONSE.md",
        "started_at": now_iso(),
        "completed_at": now_iso(),
        "elapsed_seconds": 0,
        "error_type": "STOPPED",
        "error_message": reason,
    }
    write_json(folder / "answer_manifest.json", answer_manifest)
    dest = move_to_answer(folder, dirs)
    print(f"REJECTED {folder.name} -> {dest}: {reason}", file=sys.stderr)
    return "REJECTED"


def list_ollama_models(generate_url: str, timeout: int = 10) -> list[str]:
    health_url = ollama_health_url(generate_url)
    request = urllib.request.Request(health_url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    models = payload.get("models", [])
    results: list[str] = []
    for item in models:
        if isinstance(item, dict) and item.get("name"):
            results.append(str(item["name"]))
    return results


def process_monitor_tests(dirs: dict[str, Path], worker_id: str, ollama_url: str) -> int:
    responses_written = 0
    host = socket.gethostname()
    for request_dir in sorted(path for path in dirs["monitor_requests"].iterdir() if path.is_dir()):
        test_id = request_dir.name
        response_path = dirs["monitor_responses"] / f"{test_id}.json"
        if response_path.exists():
            continue

        instruction = str(read_json(request_dir / "request.json").get("instruction") or "").strip()
        try:
            models = list_ollama_models(ollama_url)
            payload = {
                "version": 1,
                "test_id": test_id,
                "worker_id": worker_id,
                "host": host,
                "status": "ONLINE",
                "ollama_ok": True,
                "models": models,
                "message": instruction or "Monitoring and connected to Ollama.",
                "responded_at": now_iso(),
            }
        except Exception as exc:
            payload = {
                "version": 1,
                "test_id": test_id,
                "worker_id": worker_id,
                "host": host,
                "status": "OLLAMA_UNAVAILABLE",
                "ollama_ok": False,
                "models": [],
                "message": str(exc),
                "responded_at": now_iso(),
            }

        write_json(response_path, payload)
        print(f"MONITOR_RESPONSE {worker_id} -> {response_path}")
        responses_written += 1
    return responses_written


def ollama_health_url(generate_url: str) -> str:
    if generate_url.endswith("/api/generate"):
        return generate_url[: -len("/api/generate")] + "/api/tags"
    return generate_url.rstrip("/") + "/api/tags"


def is_transient_ollama_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionRefusedError, TimeoutError, socket.timeout, ConnectionResetError, BrokenPipeError)):
        return True

    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, BaseException) and is_transient_ollama_error(reason):
            return True
        reason_text = str(reason or exc).lower()
    else:
        reason_text = str(exc).lower()

    transient_needles = [
        "connection refused",
        "actively refused",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "failed to establish",
        "no route to host",
        "network is unreachable",
    ]
    return any(needle in reason_text for needle in transient_needles)


def wait_for_ollama(url: str, attempts: int, delay_seconds: float, timeout: int = 10) -> bool:
    health_url = ollama_health_url(url)
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if 200 <= int(response.status) < 500:
                    return True
        except Exception as exc:
            if attempt >= attempts:
                print(f"Ollama preflight failed after {attempts} attempt(s): {exc}", file=sys.stderr)
                return False
            print(
                f"Ollama preflight failed attempt {attempt}/{attempts}: {exc}; retrying in {delay_seconds}s",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)
    return False


def call_ollama_once(
    url: str,
    model: str,
    prompt: str,
    temperature: float = 0.1,
    num_ctx: int | None = None,
    timeout: int = 600,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if num_ctx:
        payload["options"]["num_ctx"] = int(num_ctx)
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail[:500]}") from exc

    parsed = json.loads(body)
    if "response" not in parsed:
        raise RuntimeError(f"Ollama response missing 'response': {body[:500]}")
    return str(parsed["response"])


def call_ollama(
    url: str,
    model: str,
    prompt: str,
    temperature: float = 0.1,
    num_ctx: int | None = None,
    timeout: int = 600,
    retries: int = 8,
    retry_seconds: float = 10.0,
    preflight_attempts: int = 3,
) -> str:
    if preflight_attempts > 0:
        wait_for_ollama(url, attempts=preflight_attempts, delay_seconds=retry_seconds, timeout=min(timeout, 10))

    last_exc: BaseException | None = None
    total_attempts = max(1, retries + 1)
    for attempt in range(1, total_attempts + 1):
        try:
            return call_ollama_once(url, model, prompt, temperature=temperature, num_ctx=num_ctx, timeout=timeout)
        except Exception as exc:
            if not is_transient_ollama_error(exc):
                raise
            last_exc = exc
            if attempt >= total_attempts:
                break
            print(
                f"Ollama connection failure attempt {attempt}/{total_attempts}: {exc}; retrying in {retry_seconds}s",
                file=sys.stderr,
            )
            time.sleep(retry_seconds)

    raise TransientOllamaConnectionError(f"Ollama unavailable after {total_attempts} attempt(s): {last_exc}")


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
        try:
            path.unlink()
        except Exception:
            pass
        return False


def claim_one(dirs: dict[str, Path], worker_id: str) -> Path | None:
    for ask in sorted(dirs["ask"].iterdir() if dirs["ask"].exists() else []):
        if not ask.is_dir() or not ask.name.startswith("Ask_"):
            continue

        claim_file = dirs["claims"] / f"{ask.name}.claim.json"
        if not write_claim_file(claim_file, ask.name, worker_id):
            continue

        dest = dirs["claimed"] / ask.name
        try:
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(str(ask), str(dest))
            try:
                shutil.copy2(str(claim_file), str(dest / "claim_manifest.json"))
            except Exception:
                pass
            try:
                shutil.rmtree(ask, ignore_errors=True)
            except Exception:
                pass
            log(f"CLAIMED {ask.name} -> {dest}")
            return dest
        except Exception:
            try:
                shutil.rmtree(dest, ignore_errors=True)
            except Exception:
                pass
            try:
                claim_file.unlink()
            except Exception:
                pass
            continue
    return None


def release_claim_to_ask(folder: Path, dirs: dict[str, Path], worker_id: str, reason: str) -> bool:
    ask_name = folder.name
    ask_dest = dirs["ask"] / ask_name
    claim_file = dirs["claims"] / f"{ask_name}.claim.json"

    try:
        transient = {
            "version": 1,
            "status": "RETRY_LATER",
            "worker_id": worker_id,
            "reason": reason,
            "released_at": now_iso(),
        }
        write_json(folder / "transient_worker_status.json", transient)
    except Exception:
        pass

    try:
        claim_file.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        (folder / "claim_manifest.json").unlink(missing_ok=True)
    except Exception:
        pass

    try:
        if ask_dest.exists():
            failed_dest = dirs["failed"] / f"{ask_name}__released_duplicate_{int(time.time())}"
            shutil.move(str(folder), str(failed_dest))
            print(f"TRANSIENT_RELEASE_DUPLICATE {ask_name}: {reason}; parked at {failed_dest}", file=sys.stderr)
            return True
        shutil.move(str(folder), str(ask_dest))
        print(f"TRANSIENT_RELEASE {ask_name} -> {ask_dest}: {reason}", file=sys.stderr)
        return True
    except Exception as exc:
        try:
            failed_dest = dirs["failed"] / f"{ask_name}__release_failed_{int(time.time())}"
            shutil.move(str(folder), str(failed_dest))
        except Exception:
            pass
        print(f"ERROR releasing transient claim {ask_name}: {exc}", file=sys.stderr)
        return False


def move_to_answer(folder: Path, dirs: dict[str, Path]) -> Path:
    dest = dirs["answer"] / folder.name
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(folder), str(dest))
    return dest


def process_claimed(
    folder: Path,
    dirs: dict[str, Path],
    worker_id: str,
    ollama_url: str,
    timeout: int,
    ollama_retries: int,
    ollama_retry_seconds: float,
    preflight_attempts: int,
    return_transient_to_ask: bool,
) -> str:
    ask_manifest = read_json(folder / "ask_manifest.json")
    if should_reject_ask(ask_manifest, dirs):
        return write_rejected_answer(
            folder,
            dirs,
            worker_id,
            "Ask rejected because AI proxy stop is active.",
        )

    prompt_file = str(ask_manifest.get("prompt_file") or "")
    expected_output = str(ask_manifest.get("expected_output") or "")
    model = str(ask_manifest.get("ollama_model") or "llama3.2:3b")
    job_id = str(ask_manifest.get("ask_id") or folder.name)
    asset_id = str(ask_manifest.get("asset_id") or "")
    attempt_id = str(ask_manifest.get("ollama_attempt_id") or "")

    answer_manifest = {
        "version": 1,
        "ask_id": job_id,
        "asset_id": asset_id,
        "ollama_attempt_id": attempt_id,
        "worker_id": worker_id,
        "status": "",
        "expected_output": expected_output,
        "started_at": now_iso(),
        "completed_at": "",
        "elapsed_seconds": 0,
        "error_type": "",
        "error_message": "",
    }

    t0 = time.time()
    log(
        "START "
        f"{folder.name} ask_id={job_id} asset_id={asset_id} "
        f"worker_type={ask_manifest.get('worker_type') or ''} "
        f"task_type={ask_manifest.get('task_type') or ''} "
        f"model={model} prompt_file={prompt_file or '<blank>'} "
        f"expected_output={expected_output or '<blank>'}"
    )
    try:
        if not prompt_file or not (folder / prompt_file).exists():
            raise FileNotFoundError(f"Prompt file missing: {prompt_file}")
        if not expected_output:
            raise ValueError("ask_manifest expected_output is blank")

        prompt = (folder / prompt_file).read_text(encoding="utf-8")
        response = call_ollama(
            ollama_url,
            model,
            prompt,
            timeout=timeout,
            retries=ollama_retries,
            retry_seconds=ollama_retry_seconds,
            preflight_attempts=preflight_attempts,
        )
        if should_reject_ask(ask_manifest, dirs):
            return write_rejected_answer(
                folder,
                dirs,
                worker_id,
                "Ask rejected because AI proxy stop became active during processing.",
            )
        write_text_atomic(folder / expected_output, response)
        answer_manifest["status"] = "SUCCESS"
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(folder / "answer_manifest.json", answer_manifest)
        dest = move_to_answer(folder, dirs)
        log(f"DONE SUCCESS {folder.name} -> {dest} elapsed={answer_manifest['elapsed_seconds']}s")
        return "SUCCESS"
    except TransientOllamaConnectionError as exc:
        if return_transient_to_ask:
            release_claim_to_ask(folder, dirs, worker_id, str(exc))
            log(f"DONE RETRY_LATER {folder.name}: {exc}", error=True)
            return "RETRY_LATER"

        answer_manifest["status"] = "RETRY_LATER"
        answer_manifest["error_type"] = "TRANSIENT_OLLAMA_CONNECTION"
        answer_manifest["error_message"] = str(exc)
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        try:
            write_json(folder / "answer_manifest.json", answer_manifest)
            dest = move_to_answer(folder, dirs)
            log(
                f"DONE RETRY_LATER {folder.name} -> {dest} "
                f"elapsed={answer_manifest['elapsed_seconds']}s: {exc}",
                error=True,
            )
        except Exception:
            try:
                shutil.move(str(folder), str(dirs["failed"] / folder.name))
            except Exception:
                pass
        return "RETRY_LATER"
    except Exception as exc:
        answer_manifest["status"] = "ERROR"
        answer_manifest["error_type"] = "WORKER_ERROR"
        answer_manifest["error_message"] = str(exc)
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        try:
            write_json(folder / "answer_manifest.json", answer_manifest)
            dest = move_to_answer(folder, dirs)
            log(
                f"DONE ERROR {folder.name} -> {dest} "
                f"elapsed={answer_manifest['elapsed_seconds']}s: {exc}",
                error=True,
            )
        except Exception:
            try:
                shutil.move(str(folder), str(dirs["failed"] / folder.name))
            except Exception:
                pass
        return "ERROR"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claim and process Zet Ollama proxy ask folders.")
    parser.add_argument("--proxy-root", default=DEFAULT_PROXY_ROOT, help="Path to Zet Ollama proxy root")
    parser.add_argument("--worker-id", default=socket.gethostname(), help="Worker ID for claim and answer manifests")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Local Ollama generate endpoint")
    parser.add_argument("--poll-seconds", type=int, default=30, help="Seconds between polls in loop mode")
    parser.add_argument("--timeout", type=int, default=7200, help="Ollama HTTP timeout seconds")
    parser.add_argument("--ollama-retries", type=int, default=8, help="Retries for transient Ollama connection failures")
    parser.add_argument("--ollama-retry-seconds", type=float, default=10.0, help="Seconds between transient retries")
    parser.add_argument("--preflight-attempts", type=int, default=3, help="Check Ollama /api/tags before generation")
    parser.add_argument("--transient-cooldown-seconds", type=float, default=60.0, help="Sleep after transient retry release")
    parser.add_argument("--send-transient-to-answer", action="store_true", help="Write RETRY_LATER answer folders instead of returning Ask")
    parser.add_argument("--once", action="store_true", help="Process at most one ask and exit")
    parser.add_argument("--max-jobs", type=int, default=None, help="Process at most N asks and exit")
    args = parser.parse_args(argv)

    proxy_root_arg = Path(args.proxy_root).expanduser() if args.proxy_root else default_proxy_root()
    proxy_root = normalize_proxy_root(proxy_root_arg).resolve()
    dirs = ensure_dirs(proxy_root, args.worker_id)
    processed = 0
    log(f"Worker {args.worker_id} v{WORKER_VERSION} watching {proxy_root}")

    while True:
        process_monitor_tests(dirs, args.worker_id, args.ollama_url)
        claimed = claim_one(dirs, args.worker_id)
        if claimed is None:
            if args.once or (args.max_jobs is not None and processed >= args.max_jobs):
                return 0
            time.sleep(args.poll_seconds)
            continue

        result = process_claimed(
            claimed,
            dirs,
            args.worker_id,
            args.ollama_url,
            args.timeout,
            args.ollama_retries,
            args.ollama_retry_seconds,
            args.preflight_attempts,
            return_transient_to_ask=not args.send_transient_to_answer,
        )
        if result in {"SUCCESS", "ERROR"}:
            processed += 1
        elif result == "RETRY_LATER":
            time.sleep(args.transient_cooldown_seconds)

        if args.once or (args.max_jobs is not None and processed >= args.max_jobs):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
