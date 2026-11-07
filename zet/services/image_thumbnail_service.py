"""Shared bounded, cached image previews."""
from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageThumbnailService:
    def __init__(self, cache: Path, *, max_side: int = 480):
        self.cache = Path(cache)
        self.max_side = max_side

    def create(self, source: Path, expected_version: str = "") -> Path:
        source = Path(source).resolve()
        try:
            contents = source.read_bytes()
        except OSError as exc:
            raise FileNotFoundError("Preview image is unavailable.") from exc
        digest = hashlib.sha256(contents).hexdigest()
        if expected_version and expected_version not in {digest, f"{source.stat().st_size}-{source.stat().st_mtime_ns}"}:
            raise FileNotFoundError("Preview image changed. Refresh the overview.")
        key = hashlib.sha256(f"{source}\0{digest}\0{self.max_side}\0jpeg".encode()).hexdigest()
        destination = self.cache / f"{key}.jpg"
        if destination.is_file():
            return destination
        try:
            with Image.open(BytesIO(contents)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((self.max_side, self.max_side), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, format="JPEG", quality=82, optimize=True)
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise FileNotFoundError("Preview image cannot be decoded.") from exc
        self.cache.mkdir(parents=True, exist_ok=True)
        temporary = self.cache / f".{key}.{uuid4().hex}.tmp"
        try:
            temporary.write_bytes(output.getvalue())
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
