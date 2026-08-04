from __future__ import annotations

import sys
from datetime import datetime
from typing import Mapping

ANSI_RESET = "\033[0m"
ANSI_WHITE = "\033[37m"
ANSI_YELLOW = "\033[33m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"


def job_type(manifest: Mapping[str, object]) -> str:
    worker_type = str(manifest.get("worker_type") or "").strip()
    task_type = str(manifest.get("task_type") or "").strip()
    pipeline_stage = str(manifest.get("pipeline_stage") or "").strip()

    if worker_type == "local_image_render":
        return "LOCAL_RENDER"
    if pipeline_stage:
        return pipeline_stage.upper()
    if task_type:
        return task_type.upper()
    return worker_type.upper() or "PROXY_JOB"


def log_job(
    manifest: Mapping[str, object],
    action: str,
    *,
    result: str = "",
    error_message: str = "",
) -> None:
    action = action.upper()
    result = result.upper()
    is_error = bool(error_message) or result not in {"", "SUCCESS"}
    if action == "DONE" and result == "SUCCESS" and not is_error:
        color = ANSI_GREEN
    elif is_error:
        color = ANSI_RED
    else:
        color = ANSI_YELLOW

    timestamp = datetime.now().strftime("%y-%m-%d %H:%M")
    result_text = f" {result}" if action == "DONE" and result else ""
    ask_id = str(manifest.get("ask_id") or "<unknown>")
    stream = sys.stderr if is_error else sys.stdout

    print(
        f"{color}{timestamp} {job_type(manifest)} {action}{result_text}{ANSI_RESET}",
        file=stream,
        flush=True,
    )
    print(f"{ANSI_WHITE}    {ask_id}{ANSI_RESET}", file=stream, flush=True)
    if error_message:
        for line in error_message.splitlines() or [error_message]:
            print(f"{ANSI_RED}{line}{ANSI_RESET}", file=stream, flush=True)
