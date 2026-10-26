"""Compatibility entry point for independent Costume-Dressing preparation."""
from pathlib import Path


class CostumeNoReferenceService:
    @staticmethod
    def availability_reason(workflow, run: dict, view: str) -> str:
        from zet.services.costume_render_mode_service import CostumeRenderModeService, render_settings
        return CostumeRenderModeService(workflow).reason(run, view,
            {**render_settings(run, view), "mode": "doll-dressing-no-ref"})

    def prepare(self, workflow, run: dict, view: str, directory: Path) -> dict:
        from zet.services.costume_render_mode_service import CostumeRenderModeService, render_settings
        return CostumeRenderModeService(workflow).prepare(run, view, directory,
            settings={**render_settings(run, view), "mode": "doll-dressing-no-ref"})
