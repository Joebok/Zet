from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class WorkerContext:
    pipeline_path: Path
    candidate_image_path: Path
    locked_image_path: Path
    character_path: Path
    character_asset_path: Path


@dataclass
class WorkerResult:
    """Describe the result of one pipeline worker run."""
    success: bool
    message: str
    output_files: list[str] = field(default_factory=list)
    advance_stage: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    reference_files: Optional[list[dict]] = None
