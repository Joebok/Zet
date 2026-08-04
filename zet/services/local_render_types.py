from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class LocalRenderError(Exception):
    pass


class LocalRenderUnavailable(LocalRenderError):
    pass


@dataclass(frozen=True)
class LocalRenderRequest:
    project_root: Path
    final_prompt_path: Path
    job_output_dir: Path
    profile_name: str
    prompt_review_path: Path | None = None
    scene_render_ir_path: Path | None = None
    reference_files: list[dict[str, Any]] = field(default_factory=list)
    aspect_ratio: str = ""
    render_layout: dict[str, Any] | None = None
    seed: int | None = None


@dataclass
class LocalRenderResult:
    image_path: Path
    metadata_path: Path
    prompt_review_path: Path | None
    prompt_id: str
    artifact_paths: list[Path] = field(default_factory=list)
