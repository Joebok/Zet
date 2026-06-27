#!/usr/bin/env python3
"""
Ollama_File_Worker.py

Disposable filesystem-worker for the Ollama file proxy.

The worker claims Ask folders, runs local Ollama, and places completed folders
in Answer. It does not update Job_List.json. Silent failure is acceptable; the
coordinator will reset stale asks.

This version distinguishes transient Ollama connectivity failures from real job
failures. Transient Ollama connection failures are retried and, if still failing,
the Ask is returned to Ask/ instead of being reported as an Answer error.
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

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"


class TransientOllamaConnectionError(RuntimeError):
    """Raised when Ollama is temporarily unavailable and the job should be retried later."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_dirs(proxy_root: Path, worker_id: str) -> dict[str, Path]:
    dirs = {
        "ask": proxy_root / "Ask",
        "claims": proxy_root / "Claims",
        "claimed": proxy_root / "Claimed" / worker_id,
        "answer": proxy_root / "Answer",
        "failed": proxy_root / "Failed" / worker_id,
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def ollama_health_url(generate_url: str) -> str:
    """Return the likely /api/tags URL for an Ollama /api/generate endpoint."""
    if generate_url.endswith("/api/generate"):
        return generate_url[: -len("/api/generate")] + "/api/tags"
    return generate_url.rstrip("/") + "/api/tags"


def is_transient_ollama_error(exc: BaseException) -> bool:
    """Classify connection-level errors that should not be treated as bad model output."""
    if isinstance(exc, (ConnectionRefusedError, TimeoutError, socket.timeout, ConnectionResetError, BrokenPipeError)):
        return True

    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, BaseException) and is_transient_ollama_error(reason):
            return True
        reason_text = str(reason or exc).lower()
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

    text = str(exc).lower()
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
    return any(needle in text for needle in transient_needles)


def wait_for_ollama(url: str, attempts: int, delay_seconds: float, timeout: int = 10) -> bool:
    """Best-effort preflight. Returns True if Ollama answers /api/tags."""
    health_url = ollama_health_url(url)
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if 200 <= int(resp.status) < 500:
                    return True
        except Exception as exc:
            if attempt >= attempts:
                print(f"Ollama preflight failed after {attempts} attempt(s): {exc}", file=sys.stderr)
                return False
            print(f"Ollama preflight failed attempt {attempt}/{attempts}: {exc}; retrying in {delay_seconds}s", file=sys.stderr)
            time.sleep(delay_seconds)
    return False


def call_ollama_once(url: str, model: str, prompt: str, temperature: float = 0.1, num_ctx: int | None = None, timeout: int = 600) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if num_ctx:
        payload["options"]["num_ctx"] = int(num_ctx)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # HTTP errors mean Ollama answered. Keep these as real worker/model errors.
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
    """
    Call Ollama with retries for connection-level failures.

    If Ollama actively refuses the connection, times out, resets, or is otherwise
    temporarily unreachable, retry. After all retries, raise
    TransientOllamaConnectionError so the Ask can be returned to Ask/.
    """
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
    """
    Try to create a tiny sidecar claim file using exclusive create.

    This is much faster than moving/copying an entire Ask folder and substantially
    reduces double-claims on sync-backed folders. It is still not a true distributed
    lock on services like Dropbox, but it narrows the race window.
    """
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
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        return True
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
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

            # Copy after the tiny claim file is in place. This avoids relying on a
            # whole-folder move as the first visible claim signal.
            shutil.copytree(str(ask), str(dest))

            # Preserve the claim record inside the claimed folder for dashboard/status.
            try:
                shutil.copy2(str(claim_file), str(dest / "claim_manifest.json"))
            except Exception:
                pass

            # Best-effort cleanup. If a sync provider delays/rematerializes the source
            # folder, other workers should still skip it because the claim sidecar exists.
            try:
                shutil.rmtree(ask, ignore_errors=True)
            except Exception:
                pass
            return dest
        except Exception:
            # Release the claim only if we never successfully copied the folder.
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
    """
    Return a claimed folder back to Ask/ after a transient local failure.

    This is used for Ollama connectivity problems. It does not create an Answer
    folder because there is no completed model output for Stage_Ollama_Jobs.py to
    harvest.
    """
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
            # Avoid overwriting a visible Ask. Park this claimed copy in Failed so it
            # cannot duplicate active work.
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
    prompt_file = ask_manifest.get("ollama_prompt_file") or ""
    expected_output = ask_manifest.get("expected_output") or ""
    model = ask_manifest.get("ollama_model") or "llama3.2:3b"
    temperature = float(ask_manifest.get("temperature") if ask_manifest.get("temperature") is not None else 0.1)
    num_ctx = ask_manifest.get("num_ctx") or None
    job_id = ask_manifest.get("job_id") or ""
    attempt_id = ask_manifest.get("ollama_attempt_id") or ""
    answer_manifest = {
        "version": 1,
        "job_id": job_id,
        "ollama_attempt_id": attempt_id,
        "worker_id": worker_id,
        "ollama_model": model,
        "expected_output": expected_output,
        "started_at": now_iso(),
    }
    t0 = time.time()
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
            temperature=temperature,
            num_ctx=int(num_ctx) if num_ctx else None,
            timeout=timeout,
            retries=ollama_retries,
            retry_seconds=ollama_retry_seconds,
            preflight_attempts=preflight_attempts,
        )
        (folder / expected_output).write_text(response, encoding="utf-8")
        answer_manifest.update({
            "status": "SUCCESS",
            "completed_at": now_iso(),
            "elapsed_seconds": round(time.time() - t0, 2),
        })
        write_json(folder / "answer_manifest.json", answer_manifest)
        dest = move_to_answer(folder, dirs)
        print(f"SUCCESS {folder.name} -> {dest}")
        return "SUCCESS"
    except TransientOllamaConnectionError as exc:
        if return_transient_to_ask:
            release_claim_to_ask(folder, dirs, worker_id, str(exc))
            return "RETRY_LATER"

        answer_manifest.update({
            "status": "RETRY_LATER",
            "error_type": "TRANSIENT_OLLAMA_CONNECTION",
            "error_message": str(exc),
            "completed_at": now_iso(),
            "elapsed_seconds": round(time.time() - t0, 2),
        })
        try:
            write_json(folder / "answer_manifest.json", answer_manifest)
            dest = move_to_answer(folder, dirs)
            print(f"RETRY_LATER {folder.name} -> {dest}: {exc}", file=sys.stderr)
        except Exception:
            try:
                shutil.move(str(folder), str(dirs["failed"] / folder.name))
            except Exception:
                pass
        return "RETRY_LATER"
    except Exception as exc:
        answer_manifest.update({
            "status": "ERROR",
            "error_message": str(exc),
            "completed_at": now_iso(),
            "elapsed_seconds": round(time.time() - t0, 2),
        })
        try:
            write_json(folder / "answer_manifest.json", answer_manifest)
            # Put real failures in Answer so Stage_Ollama_Jobs.py can immediately restage or park.
            dest = move_to_answer(folder, dirs)
        except Exception:
            try:
                shutil.move(str(folder), str(dirs["failed"] / folder.name))
            except Exception:
                pass
        print(f"ERROR {folder.name}: {exc}", file=sys.stderr)
        return "ERROR"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claim Ollama file-proxy Ask folders and run local Ollama.")
    parser.add_argument("--proxy-root", required=True, help="Path to Ollama_File_Proxy root")
    parser.add_argument("--worker-id", default=socket.gethostname(), help="Worker ID for claimed folder names and answer manifests")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Local Ollama generate endpoint")
    parser.add_argument("--poll-seconds", type=int, default=30, help="Seconds between polls in loop mode")
    parser.add_argument("--timeout", type=int, default=7200, help="Ollama HTTP timeout seconds")
    parser.add_argument("--ollama-retries", type=int, default=8, help="Retries for transient Ollama connection failures before returning the Ask to Ask/. Default: 8")
    parser.add_argument("--ollama-retry-seconds", type=float, default=10.0, help="Seconds between transient Ollama connection retries. Default: 10")
    parser.add_argument("--preflight-attempts", type=int, default=3, help="Check Ollama /api/tags before generation. Default: 3; use 0 to disable")
    parser.add_argument("--transient-cooldown-seconds", type=float, default=60.0, help="Sleep after returning a transient failure to Ask/. Default: 60")
    parser.add_argument("--send-transient-to-answer", action="store_true", help="Send transient Ollama connection failures to Answer/ as RETRY_LATER instead of returning them to Ask/")
    parser.add_argument("--once", action="store_true", help="Process at most one ask and exit")
    parser.add_argument("--max-jobs", type=int, default=None, help="Process at most N asks and exit")
    args = parser.parse_args(argv)

    proxy_root = Path(args.proxy_root).expanduser().resolve()
    dirs = ensure_dirs(proxy_root, args.worker_id)
    processed = 0
    print(f"Worker {args.worker_id} watching {proxy_root}")
    while True:
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
