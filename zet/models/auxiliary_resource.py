from dataclasses import dataclass
from typing import Optional


@dataclass
class AuxiliaryResource:
    """Track one global auxiliary image resource for scene references."""
    resource_id: str
    category: str
    label: str
    tag: str
    image_path: str
    updated_at: str
    created_at: str
    notes: Optional[str] = None
