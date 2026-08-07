from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import time
from uuid import uuid4


_RETRYABLE_ERRNOS = {errno.EACCES, errno.EBUSY, errno.EPERM}
_RETRYABLE_WINERRORS = {5, 32, 33}


def _retryable(exc: OSError) -> bool:
    return (
        isinstance(exc, (FileExistsError, FileNotFoundError, PermissionError))
        or exc.errno in _RETRYABLE_ERRNOS
        or getattr(exc, "winerror", None) in _RETRYABLE_WINERRORS
    )


def replace_with_retry(source: Path, destination: Path, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    delay = 0.05
    while True:
        try:
            os.replace(source, destination)
            return
        except FileNotFoundError:
            raise
        except OSError as exc:
            if not _retryable(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 1.0)


def write_text_atomic(path: Path, contents: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    delay = 0.05
    while True:
        temp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid4().hex}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(contents, encoding="utf-8")
            replace_with_retry(temp_path, path, max(0.0, deadline - time.monotonic()))
            return
        except OSError as exc:
            if not _retryable(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 1.0)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def write_json_atomic(path: Path, data: dict, timeout_seconds: float = 15.0) -> None:
    write_text_atomic(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        timeout_seconds,
    )
