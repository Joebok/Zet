from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TurnaroundSheet:
    """Track one generated turnaround sheet outside the asset pipeline table."""
    turnaround_id: str
    character: str
    phase: str
    source_pipeline: str
    costume: Optional[str] = None
    expression: Optional[str] = None
    label: Optional[str] = None
    sheet_type: str = "full"
    parent_turnaround_id: Optional[str] = None
    crop_percent: Optional[float] = None
    detection_tolerance: float = 50.0
    deletable: bool = False
    status: str = "NEW"
    source_asset_ids: list[int] = field(default_factory=list)
    candidate_image_path: Optional[str] = None
    locked_image_path: Optional[str] = None
    analysis_path: Optional[str] = None
    diagnostics_path: Optional[str] = None
    updated_at: Optional[str] = None
