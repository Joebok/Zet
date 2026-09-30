"""Shared boundary for retired traditional character image workflows."""

RETIRED_CHARACTER_PIPELINES = frozenset({
    "Body-Reference", "Head-Image", "Character-Assembly", "Costume-Dressing",
    "Scene-Appearance", "Expression",
})


def is_retired_character_pipeline(pipeline: str) -> bool:
    return str(pipeline or "") in RETIRED_CHARACTER_PIPELINES


def require_active_pipeline(pipeline: str) -> None:
    if is_retired_character_pipeline(pipeline):
        raise ValueError(f"Traditional {pipeline} generation is retired. Use the local Assets workflow.")
