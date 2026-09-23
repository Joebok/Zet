#!/usr/bin/env python3
"""
ollama_proxy_worker.py

One-job Ollama executable for Zet's standalone file-proxy subscription.

The proxy passes one Running job with --job-dir. This process performs only
the Ollama work and writes subscriber outputs inside that folder.

It does not modify Zet asset state.
It does not edit Assets.json.
It does not edit Pipelines.json.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("ZET_PROJECT_ROOT", "")).resolve() if os.environ.get("ZET_PROJECT_ROOT") else DEFAULT_PROJECT_ROOT
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "Scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from zet.models.ai_proxy import AIProxyAskManifest
from zet.services.atomic_file_service import write_json_atomic, write_text_atomic as atomic_write_text
from zet.services.ollama_model_service import OllamaModelService
from AI_Manager.proxy_worker_output import log_job

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_KEEP_ALIVE = "5m"
THINKING_OUTPUT_FILE = "OLLAMA_THINKING.txt"
INITIAL_THINKING_OUTPUT_FILE = "OLLAMA_THINKING_ATTEMPT_1.txt"
RETRY_PROMPT_FILE = "OLLAMA_RETRY_PROMPT.md"

ANSI_RESET = "\033[0m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"


class TransientOllamaConnectionError(RuntimeError):
    """Raised when Ollama is temporarily unavailable and the ask should be retried later."""


@dataclass(frozen=True)
class OllamaGenerationResult:
    response: str
    done_reason: str
    eval_count: int | None
    thinking: str = ""

    def evidence(self) -> dict:
        return {
            "done_reason": self.done_reason,
            "eval_count": self.eval_count,
        }


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(message: str, *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    color = ""
    if error:
        color = ANSI_RED
    elif message.startswith("CLAIMED"):
        color = ANSI_YELLOW
    elif message.startswith("START "):
        color = ANSI_BLUE
    elif message.startswith("DONE SUCCESS"):
        color = ANSI_GREEN
    text = f"{now_iso()} {message}"
    print(f"{color}{text}{ANSI_RESET if color else ''}", file=stream, flush=True)


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


def write_text_atomic(path: Path, contents: str) -> None:
    atomic_write_text(path, contents)


def ollama_health_url(generate_url: str) -> str:
    for endpoint in ("/api/generate", "/api/chat"):
        if generate_url.endswith(endpoint):
            return generate_url[: -len(endpoint)] + "/api/tags"
    return generate_url.rstrip("/") + "/api/tags"


def ollama_chat_url(url: str) -> str:
    return url[: -len("/api/generate")] + "/api/chat" if url.endswith("/api/generate") else url


def ensure_explicit_image_tags(prompt: str, image_count: int) -> str:
    if image_count <= 0:
        return prompt
    tag_count = prompt.count("[img]")
    if tag_count == image_count:
        return prompt
    if tag_count:
        raise ValueError(f"Ollama prompt has {tag_count} [img] tags for {image_count} images.")
    labels = "\n".join(f"Image {index}: [img]" for index in range(1, image_count + 1))
    return f"{labels}\n\n{prompt}"


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
                log(f"Ollama preflight failed after {attempts} attempt(s): {exc}", error=True)
                return False
            log(f"Ollama preflight failed attempt {attempt}/{attempts}: {exc}; retrying in {delay_seconds}s", error=True)
            time.sleep(delay_seconds)
    return False


def call_ollama_once(
    url: str,
    model: str,
    prompt: str,
    temperature: float = 0.1,
    timeout: int = 600,
    images: list[str] | None = None,
    json_output: bool = False,
    response_schema: dict | None = None,
    keep_alive: str | int = 0,
    think: bool | None = False,
    use_chat: bool = False,
) -> OllamaGenerationResult:
    multimodal_chat = use_chat or bool(images and len(images) > 1)
    if multimodal_chat:
        if images and len(images) > 1:
            prompt = ensure_explicit_image_tags(prompt, len(images))
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": images}],
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"temperature": temperature},
        }
        request_url = ollama_chat_url(url)
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"temperature": temperature},
        }
        if images:
            payload["images"] = images
        request_url = url
    if think is not None:
        payload["think"] = think
    if response_schema is not None:
        if not isinstance(response_schema, dict):
            raise ValueError("Ollama response_schema must be a JSON object")
        payload["format"] = response_schema
    elif json_output:
        payload["format"] = "json"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        request_url,
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
    if multimodal_chat:
        message = parsed.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise RuntimeError(f"Ollama chat response missing 'message.content': {body[:500]}")
        response_text = str(message["content"])
        thinking_text = str(message.get("thinking") or "")
    else:
        if "response" not in parsed:
            raise RuntimeError(f"Ollama response missing 'response': {body[:500]}")
        response_text = str(parsed["response"])
        thinking_text = str(parsed.get("thinking") or "")
    raw_eval_count = parsed.get("eval_count")
    eval_count = raw_eval_count if isinstance(raw_eval_count, int) and not isinstance(raw_eval_count, bool) else None
    return OllamaGenerationResult(
        response=response_text,
        done_reason=str(parsed.get("done_reason") or ""),
        eval_count=eval_count,
        thinking=thinking_text,
    )


def call_ollama(
    url: str,
    model: str,
    prompt: str,
    temperature: float = 0.1,
    timeout: int = 600,
    retries: int = 8,
    retry_seconds: float = 10.0,
    preflight_attempts: int = 3,
    images: list[str] | None = None,
    json_output: bool = False,
    response_schema: dict | None = None,
    keep_alive: str | int = 0,
    think: bool | None = False,
    use_chat: bool = False,
) -> OllamaGenerationResult:
    if preflight_attempts > 0:
        wait_for_ollama(url, attempts=preflight_attempts, delay_seconds=retry_seconds, timeout=min(timeout, 10))

    last_exc: BaseException | None = None
    total_attempts = max(1, retries + 1)
    for attempt in range(1, total_attempts + 1):
        try:
            return call_ollama_once(
                url, model, prompt, temperature=temperature,
                timeout=timeout, images=images, json_output=json_output, response_schema=response_schema,
                keep_alive=keep_alive,
                think=think,
                use_chat=use_chat,
            )
        except Exception as exc:
            if not is_transient_ollama_error(exc):
                raise
            last_exc = exc
            if attempt >= total_attempts:
                break
            log(f"Ollama connection failure attempt {attempt}/{total_attempts}: {exc}; retrying in {retry_seconds}s", error=True)
            time.sleep(retry_seconds)

    raise TransientOllamaConnectionError(f"Ollama unavailable after {total_attempts} attempt(s): {last_exc}")


def scheduled_keep_alive(model: str) -> str | int:
    if os.environ.get("AI_PROXY_NEXT_JOB_PRESENT") != "1":
        return DEFAULT_KEEP_ALIVE
    current_key = os.environ.get("AI_PROXY_CURRENT_RESOURCE_KEY") or f"ollama:{model}"
    return DEFAULT_KEEP_ALIVE if os.environ.get("AI_PROXY_NEXT_RESOURCE_KEY") == current_key else 0


def ollama_generation_options(ask_manifest: dict) -> float:
    raw_temperature = ask_manifest.get("ollama_temperature")
    if raw_temperature is None or raw_temperature == "":
        temperature = 0.1
    else:
        if isinstance(raw_temperature, bool):
            raise ValueError("ask_manifest ollama_temperature must be a number between 0 and 2")
        try:
            temperature = float(raw_temperature)
        except (TypeError, ValueError) as exc:
            raise ValueError("ask_manifest ollama_temperature must be a number between 0 and 2") from exc
        if not 0.0 <= temperature <= 2.0:
            raise ValueError("ask_manifest ollama_temperature must be a number between 0 and 2")

    return temperature


def ollama_think_option(ask_manifest: dict) -> bool | None:
    think = ask_manifest.get("ollama_think", False)
    if think is not None and not isinstance(think, bool):
        raise ValueError("ask_manifest ollama_think must be a boolean or null")
    return think


def ollama_runtime_evidence(url: str, model: str, timeout: int) -> dict:
    base_url = url
    for endpoint in ("/api/generate", "/api/chat"):
        if base_url.endswith(endpoint):
            base_url = base_url[: -len(endpoint)]
            break
    return OllamaModelService(base_url=base_url, timeout_seconds=min(timeout, 30)).runtime_evidence(model)


def process_claimed(
    folder: Path,
    worker_id: str,
    ollama_url: str,
    timeout: int,
    ollama_retries: int,
    ollama_retry_seconds: float,
    preflight_attempts: int,
) -> str:
    ask_manifest = read_ask_manifest(folder / "ask_manifest.json")
    prompt_file = str(ask_manifest.get("prompt_file") or "")
    expected_output = str(ask_manifest.get("expected_output") or "")
    model = str(ask_manifest.get("ollama_model") or "general:latest")
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
    log_job(ask_manifest, "START")
    try:
        temperature = ollama_generation_options(ask_manifest)
        think = ollama_think_option(ask_manifest)
        use_chat = ask_manifest.get("ollama_chat", False)
        if not isinstance(use_chat, bool):
            raise ValueError("ask_manifest ollama_chat must be a boolean")
        if not prompt_file or not (folder / prompt_file).exists():
            raise FileNotFoundError(f"Prompt file missing: {prompt_file}")
        if not expected_output:
            raise ValueError("ask_manifest expected_output is blank")

        prompt = (folder / prompt_file).read_text(encoding="utf-8")
        encoded_images = []
        for value in ask_manifest.get("image_files") or []:
            name = str(value)
            if not name or Path(name).name != name:
                raise ValueError(f"Invalid Ollama image filename: {name}")
            image_path = folder / name
            if not image_path.is_file():
                raise FileNotFoundError(f"Ollama image missing: {name}")
            encoded_images.append(base64.b64encode(image_path.read_bytes()).decode("ascii"))
        answer_manifest["ollama_runtime"] = ollama_runtime_evidence(ollama_url, model, timeout)
        def generate(current_prompt: str) -> OllamaGenerationResult:
            return call_ollama(
                ollama_url,
                model,
                current_prompt,
                temperature=temperature,
                timeout=timeout,
                retries=ollama_retries,
                retry_seconds=ollama_retry_seconds,
                preflight_attempts=preflight_attempts,
                images=encoded_images,
                json_output=bool(ask_manifest.get("json_output")),
                response_schema=ask_manifest.get("response_schema"),
                keep_alive=scheduled_keep_alive(model),
                think=think,
                use_chat=use_chat,
            )

        generation = generate(prompt)
        initial_attempt = None
        if think is not False and not generation.response.strip() and generation.done_reason == "length":
            initial_attempt = generation.evidence()
            if generation.thinking:
                write_text_atomic(folder / INITIAL_THINKING_OUTPUT_FILE, generation.thinking)
                initial_attempt["thinking_file"] = INITIAL_THINKING_OUTPUT_FILE
            retry_prompt = prompt + "\n\nLimit your private analysis to 200 tokens, then give the required answer."
            write_text_atomic(folder / RETRY_PROMPT_FILE, retry_prompt)
            answer_manifest["ollama_generation"] = {
                "think_requested": think, "initial_attempt": initial_attempt,
                "retry_prompt_file": RETRY_PROMPT_FILE,
            }
            generation = generate(retry_prompt)

        answer_manifest["ollama_generation"] = generation.evidence()
        answer_manifest["ollama_generation"]["think_requested"] = think
        if initial_attempt is not None:
            answer_manifest["ollama_generation"]["initial_attempt"] = initial_attempt
            answer_manifest["ollama_generation"]["retry_prompt_file"] = RETRY_PROMPT_FILE
        if generation.thinking:
            write_text_atomic(folder / THINKING_OUTPUT_FILE, generation.thinking)
            answer_manifest["ollama_generation"]["thinking_file"] = THINKING_OUTPUT_FILE
        if not generation.response.strip():
            raise ValueError(f"Ollama returned no answer (done_reason={generation.done_reason or 'unknown'}).")
        write_text_atomic(folder / expected_output, generation.response)
        answer_manifest["status"] = "SUCCESS"
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(folder / "answer_manifest.json", answer_manifest)
        log_job(ask_manifest, "DONE", result="SUCCESS")
        return "SUCCESS"
    except TransientOllamaConnectionError as exc:
        answer_manifest["status"] = "RETRY_LATER"
        answer_manifest["error_type"] = "TRANSIENT_OLLAMA_CONNECTION"
        answer_manifest["error_message"] = str(exc)
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(folder / "answer_manifest.json", answer_manifest)
        log_job(ask_manifest, "DONE", result="RETRY_LATER", error_message=str(exc))
        return "RETRY_LATER"
    except Exception as exc:
        answer_manifest["status"] = "ERROR"
        answer_manifest["error_type"] = "WORKER_ERROR"
        answer_manifest["error_message"] = str(exc)
        answer_manifest["completed_at"] = now_iso()
        answer_manifest["elapsed_seconds"] = round(time.time() - t0, 2)
        write_json(folder / "answer_manifest.json", answer_manifest)
        log_job(ask_manifest, "DONE", result="ERROR", error_message=str(exc))
        return "ERROR"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one Zet Ollama file-proxy job.")
    parser.add_argument("--job-dir", required=True, type=Path)
    parser.add_argument("--worker-id", default=socket.gethostname(), help="Worker ID for claim and answer manifests")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Local Ollama generate endpoint")
    parser.add_argument("--timeout", type=int, default=7200, help="Ollama HTTP timeout seconds")
    parser.add_argument("--ollama-retries", type=int, default=8, help="Retries for transient Ollama connection failures")
    parser.add_argument("--ollama-retry-seconds", type=float, default=10.0, help="Seconds between transient retries")
    parser.add_argument("--preflight-attempts", type=int, default=3, help="Check Ollama /api/tags before generation")
    args = parser.parse_args(argv)
    job_dir = args.job_dir.resolve()
    result = process_claimed(
        job_dir,
        args.worker_id,
        args.ollama_url,
        args.timeout,
        args.ollama_retries,
        args.ollama_retry_seconds,
        args.preflight_attempts,
    )
    return 0 if result == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
