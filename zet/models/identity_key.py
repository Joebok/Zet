from dataclasses import dataclass
from typing import Optional


@dataclass
class IdentityKey:
    """Track one deterministic identity crop derived from a locked asset."""
    identity_key_id: str
    character: str
    phase: str
    label: str
    crop_percent: float
    source_asset_id: int
    source_pipeline: str
    source_body_view: str
    source_head_view: Optional[str] = None
    source_costume: Optional[str] = None
    source_expression: Optional[str] = None
    image_path: str = ""
    source_image_path: str = ""
    analysis_path: str = ""
    crop_box: list[int] | None = None
    updated_at: Optional[str] = None
