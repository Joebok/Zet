#!/usr/bin/env python3
"""
Unified Zet filesystem proxy worker.

This worker claims one supported ask at a time and dispatches it to the
appropriate local handler:
- ollama_generate -> Ollama text generation
- local_image_render -> local image rendering
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import local_image_proxy_worker as image_worker
import ollama_proxy_worker as ollama_worker
from proxy_worker_output import log_job
from zet.repositories import ai_proxy_worker_protocol_repository as worker_protocol

WORKER_VERSION = "1.0"
SUPPORTED_WORKER_TYPES = {"ollama_generate"} | image_worker.SUPPORTED_WORKER_TYPES


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(message: str, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(f"{now_iso()} {message}", file=stream, flush=True)


def claim_one_supported(dirs: dict[str, Path], worker_id: str) -> Path | None:
    for ask in sorted(dirs["ask"].iterdir() if dirs["ask"].exists() else []):
        if not ask.is_dir() or not ask.name.startswith("Ask_"):
            continue

        ask_manifest = ollama_worker.read_ask_manifest(ask / "ask_manifest.json")
        worker_type = str(ask_manifest.get("worker_type") or "")
        if worker_type not in SUPPORTED_WORKER_TYPES:
            continue

        claim_file = dirs["claims"] / f"{ask.name}.claim.json"
        if not ollama_worker.write_claim_file(claim_file, ask.name, worker_id):
            continue

        dest = dirs["claimed"] / ask.name
        try:
            worker_protocol.move_ask_to_claimed(ask, dest, claim_file)
            log_job(ask_manifest, "CLAIMED")
            return dest
        except Exception as exc:
            shutil.rmtree(dest, ignore_errors=True)
            claim_file.unlink(missing_ok=True)
            log_job(ask_manifest, "CLAIM", result="ERROR", error_message=str(exc))
            continue
    return None


def process_claimed(
    folder: Path,
    dirs: dict[str, Path],
    worker_id: str,
    args: argparse.Namespace,
) -> str:
    ask_manifest = ollama_worker.read_ask_manifest(folder / "ask_manifest.json")
    worker_type = str(ask_manifest.get("worker_type") or "")
    if worker_type in image_worker.SUPPORTED_WORKER_TYPES:
        return image_worker.process_claimed(
            folder,
            dirs,
            worker_id,
            return_transient_to_ask=not args.send_transient_to_answer,
        )
    if worker_type == "ollama_generate":
        return ollama_worker.process_claimed(
            folder,
            dirs,
            worker_id,
            args.ollama_url,
            args.timeout,
            args.ollama_retries,
            args.ollama_retry_seconds,
            args.preflight_attempts,
            return_transient_to_ask=not args.send_transient_to_answer,
        )
    log_job(
        ask_manifest,
        "DONE",
        result="ERROR",
        error_message=f"Unsupported worker_type: {worker_type}",
    )
    return "UNSUPPORTED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claim and process Zet proxy asks one at a time.")
    parser.add_argument("--proxy-root", default=ollama_worker.DEFAULT_PROXY_ROOT, help="Path to Zet Ollama proxy root")
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-unified", help="Worker ID for manifests")
    parser.add_argument("--ollama-url", default=ollama_worker.DEFAULT_OLLAMA_URL, help="Local Ollama generate endpoint")
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

    proxy_root = ollama_worker.normalize_proxy_root(Path(args.proxy_root).expanduser()).resolve()
    dirs = ollama_worker.ensure_dirs(proxy_root, args.worker_id)
    processed = 0
    log(
        f"Unified worker {args.worker_id} v{WORKER_VERSION} watching {proxy_root}; "
        f"supported={', '.join(sorted(SUPPORTED_WORKER_TYPES))}"
    )

    while True:
        ollama_worker.process_monitor_tests(dirs, args.worker_id, args.ollama_url)
        claimed = claim_one_supported(dirs, args.worker_id)
        if claimed is None:
            if args.once or (args.max_jobs is not None and processed >= args.max_jobs):
                return 0
            time.sleep(args.poll_seconds)
            continue

        result = process_claimed(claimed, dirs, args.worker_id, args)
        if result in {"SUCCESS", "ERROR"}:
            processed += 1
        elif result == "RETRY_LATER":
            time.sleep(args.transient_cooldown_seconds)

        if args.once or (args.max_jobs is not None and processed >= args.max_jobs):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
