"""Prepare a dressed-view rotation without changing the originating pipeline."""
from __future__ import annotations

from pathlib import Path

from zet.services.local_view_reference_service import selected_reference


_TURN_ORDER = ("FRONT", "FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4",
               "BACK", "BACK_RIGHT_3_4", "RIGHT_PROFILE", "FRONT_RIGHT_3_4")


def rotation_degrees(source: str, target: str) -> int:
    distance = abs(_TURN_ORDER.index(source) - _TURN_ORDER.index(target))
    return min(distance, 8 - distance) * 45


def rotation_instruction(source: str, target: str) -> str:
    steps = (_TURN_ORDER.index(target) - _TURN_ORDER.index(source)) % 8
    degrees = rotation_degrees(source, target)
    if degrees == 180:
        return f"Turn the dressed figure from {source} to {target} by 180 degrees; use Image 2 to resolve the final body and head orientation."
    direction = 1 if steps <= 4 else -1
    start = _TURN_ORDER.index(source)
    arc = " -> ".join(_TURN_ORDER[(start + direction * step) % 8] for step in range(degrees // 45 + 1))
    return f"Turn the dressed figure from {source} to {target} by {degrees} degrees around the body's vertical axis, following this direction through successive viewing orientations: {arc}. Match Image 2 at the endpoint."


def rotation_source(run: dict, view: str) -> dict:
    """Resolve the explicitly saved source; never silently choose another view."""
    from zet.services.costume_render_mode_service import render_settings
    settings = render_settings(run, view)
    if view == "FRONT":
        raise ValueError("FRONT does not support Rotate.")
    return selected_reference(run, view, {"mode": "selected_view", "source_view": settings["costume_reference_view"]})


class CostumeRotationService:
    def __init__(self, workflow):
        self.workflow = workflow

    def prepare(self, run: dict, view: str, directory: Path) -> dict:
        from zet.services.costume_render_mode_service import CostumeRenderModeService, render_settings
        return CostumeRenderModeService(self.workflow).prepare(run, view, directory,
            settings={**render_settings(run, view), "mode": "rotate"})
