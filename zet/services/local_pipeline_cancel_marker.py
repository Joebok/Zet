"""Identify Body-Reference cancellation markers without changing their bytes."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def cancellation_marker_digest(root: Path) -> str | None:
    try:
        return sha256((Path(root) / "cancelled.json").read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def cancellation_marker_applies(root: Path, state: dict) -> bool:
    digest = cancellation_marker_digest(root)
    return digest is not None and digest != state.get("resumed_cancel_marker_sha256")
