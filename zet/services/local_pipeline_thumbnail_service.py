"""Derived, bounded previews for current character pipeline images."""
from __future__ import annotations

import os
from pathlib import Path
from zet.services.image_thumbnail_service import ImageThumbnailService


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
        return ImageThumbnailService(self.cache, max_side=self.MAX_SIDE).create(source, expected_version)
