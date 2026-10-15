"""Shared, snapshot-friendly universe rendering instructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def universe_style(root: str | Path | None) -> dict:
    marker = Path(root) / "universe.json" if root is not None else None
    try:
        data = json.loads(marker.read_text(encoding="utf-8")) if marker else {}
    except FileNotFoundError:
        data = {}
    text = str(data.get("canonical_art_style") or "").strip()
    return {"text": text, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source": str(marker.resolve()) if marker else ""}


def compose_style(content: str, style: str, notes: str = "") -> str:
    """Compose once from separate content and style, never mutate saved prose."""
    return "\n\n".join(part for part in (
        f"Art style:\n{style.strip()}" if style.strip() else "",
        content.strip(), f"Additional artistic direction:\n{notes.strip()}" if notes.strip() else "",
    ) if part)
