"""Shared, snapshot-friendly universe rendering instructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def universe_style(root: str | Path | None, variant: str = "canonical") -> dict:
    """Read one universe style and return a content-addressed prompt snapshot."""
    if variant not in {"canonical", "environmental"}:
        raise ValueError("Universe style variant must be canonical or environmental.")
    marker = Path(root) / "universe.json" if root is not None else None
    try:
        data = json.loads(marker.read_text(encoding="utf-8")) if marker else {}
    except FileNotFoundError:
        data = {}
    field = "canonical_art_style" if variant == "canonical" else "environmental_art_style"
    style_text = str(data.get(field) or "").strip()
    return {"variant": variant, "text": style_text,
            "sha256": hashlib.sha256(style_text.encode("utf-8")).hexdigest(),
            "source": str(marker.resolve()) if marker else "", "source_field": field}


def compose_style(content: str, style: str, notes: str = "") -> str:
    """Compose once from separate content and style, never mutate saved prose."""
    return "\n\n".join(part for part in (
        f"Art style:\n{style.strip()}" if style.strip() else "",
        content.strip(), f"Additional artistic direction:\n{notes.strip()}" if notes.strip() else "",
    ) if part)
