from dataclasses import dataclass
from typing import Optional


@dataclass
class Asset:
    asset_id: int
    character: str
    phase: str
    pipeline: str
    body_view: str
    head_view: Optional[str] = None
    costume: Optional[str] = None
    expression: Optional[str] = None
    asset_state: str = "NEW"
    pipeline_stage: str = "MANIFEST"
    actor: str = "PYTHON"
    ai_state: Optional[str] = None
    final_image_output: Optional[str] = None
    last_ai_update: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: Optional[str] = None

