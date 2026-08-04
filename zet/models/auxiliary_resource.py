from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuxiliaryResource:
    """Track one global auxiliary resource folder for scene references."""
    resource_id: str
    category: str
    label: str
    resource_path: str
    template_path: str
    updated_at: str
    created_at: str
    images: list[dict] = field(default_factory=list)
    tag: str = ""
    image_path: str = ""
    notes: Optional[str] = None
