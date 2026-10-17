"""Stable machine-local paths for data attached to a shared AI queue."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket


def queue_local_state_root(
    queue_root: str | Path,
    producer: str | None = None,
    *,
    state_root: str | Path | None = None,
) -> Path:
    queue = Path(queue_root).expanduser().resolve()
    test_root = os.environ.get("ZET_TEST_QUEUE_STATE_ROOT") if state_root is None else ""
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if local:
        base = Path(local)
    else:
        base = Path.home() / ("Library/Application Support" if os.name == "posix" else ".local/share")
    key = hashlib.sha256(os.path.normcase(str(queue)).encode("utf-8")).hexdigest()[:20]
    host = producer or socket.gethostname()
    safe_host = "".join(char if char.isalnum() or char in "-_" else "_" for char in host)[:80]
    root = Path(test_root).resolve() if test_root else (
        Path(state_root).expanduser().resolve() if state_root is not None
        else base / "Zet" / "AI_Queue"
    )
    return root / key / (safe_host or "producer")
