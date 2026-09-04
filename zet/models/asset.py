from dataclasses import dataclass, field
from typing import Optional

from zet.models.reference import ReferenceFile


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
    reference_files: list[dict | ReferenceFile] = field(default_factory=list)
    identity_key_id: Optional[str] = None
    expression_definition_path: Optional[str] = None
    costume_path: Optional[str] = None
    scene_appearance_id: Optional[str] = None
    scene_appearance: Optional[str] = None
    scene_appearance_definition_path: Optional[str] = None
    assembly_style_mode: str = "MATCHED_STYLE"

