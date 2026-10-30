"""Output-neutral instructions and resolved timeline for Narrative animations."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedAnimation:
    name: str
    aspect_width: float
    aspect_height: float
    duration_ms: int
    shots: tuple[dict, ...]
    assets: dict[str, dict]


def default_spec(name: str) -> dict:
    return {"version": 1, "name": name, "aspect_ratio": "16:9", "shots": []}
