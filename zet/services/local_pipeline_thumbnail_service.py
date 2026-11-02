"""Derived, bounded previews for current character pipeline images."""
from __future__ import annotations

from io import BytesIO
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError


class LocalPipelineThumbnailService:
    MAX_SIDE = 480

    def __init__(self, workflow):
        self.workflow = workflow
        runtime = str(getattr(workflow.app.config, "runtime_root", "") or "")
        if runtime:
            root = Path(runtime)
        else:
            root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache") / "Zet"
        self.cache = root.resolve() / "cache" / "local-pipeline-thumbnails"

    def candidate(self, run_id: str, candidate_id: str, *, costume: str = "", version: str = "") -> Path:
        options = {"costume": costume} if self.workflow.pipeline == "costume-dressing" else {}
        source = self.workflow.adapter.image_path(run_id, candidate_id, **options)
        return self._thumbnail(source, version)

    def reference(self, run_id: str, view: str, index: int, *, candidate_id: str = "",
                  render_mode: str = "draft", costume: str = "", version: str = "") -> Path:
        source = self.workflow.reference_image_path(run_id, view, index, candidate_id=candidate_id,
                                                    render_mode=render_mode, costume=costume)
        return self._thumbnail(source, version)

    def source(self, run_id: str, view: str, role: str, *, costume: str = "",
               render_mode: str | None = None, version: str = "") -> Path:
        source = self.workflow.adapter.source_path(run_id, view, role, costume, render_mode=render_mode)
        return self._thumbnail(source, version)

    def front_source(self, run_id: str, *, render_mode: str = "draft", version: str = "") -> Path:
        source = self.workflow.adapter.front_source_path(run_id, render_mode)
        return self._thumbnail(source, version)

    def _thumbnail(self, source: Path, expected_version: str) -> Path:
        source = Path(source).resolve()
        try:
            contents = source.read_bytes()
        except OSError as exc:
            raise FileNotFoundError("Preview image is unavailable.") from exc
        digest = hashlib.sha256(contents).hexdigest()
        if expected_version and expected_version != digest:
            raise FileNotFoundError("Preview image changed. Refresh the batch.")
        key = hashlib.sha256(f"{source}\0{digest}\0{self.MAX_SIDE}\0jpeg".encode()).hexdigest()
        destination = self.cache / f"{key}.jpg"
        if destination.is_file():
            return destination
        try:
            with Image.open(BytesIO(contents)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((self.MAX_SIDE, self.MAX_SIDE), Image.Resampling.LANCZOS)
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
