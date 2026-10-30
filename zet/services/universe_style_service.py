"""Shared, snapshot-friendly universe rendering instructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def universe_style(root: str | Path | None, variant: str = "canonical") -> dict:
    """Read one universe style and return a content-addressed prompt snapshot."""
    variant = variant or "canonical"
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


def freeze_batch_style(root, universe_root, payload):
    """Freeze the selected universe style before any batch prompt is compiled."""
    from zet.services.atomic_file_service import write_json_atomic
    style = universe_style(universe_root, payload.get("universe_style_variant") or "canonical")
    if not style["text"] and payload.get("universe_style_variant"):
        raise ValueError(f"Set the universe's {style['variant']} style before creating a batch.")
    write_json_atomic(Path(root) / "Universe_Style.json", style)
    return style
