from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Costume:
    """Describe one costume template available to a character phase."""
    name: str
    slug: str
    path: str
    role: Optional[str] = None
    asset_count: int = 0
