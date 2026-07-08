from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class LocalRenderError(Exception):
    pass


class LocalRenderUnavailable(LocalRenderError):
    pass


@dataclass
class LocalRenderResult:
    image_path: Path
    metadata_path: Path
    prompt_review_path: Path | None
    prompt_id: str
