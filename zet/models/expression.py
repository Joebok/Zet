from dataclasses import dataclass


@dataclass(frozen=True)
class ExpressionDefinition:
    """Summarize one expression definition markdown file."""
    label: str
    slug: str
    path: str
    asset_count: int = 0
