from __future__ import annotations

from pathlib import Path

from zet.render_console.queue import RenderConsoleQueue
from zet.repositories.asset_repository import AssetRepositoryError
from zet.services.manual_render_submission_service import ManualRenderSubmissionService


class ProductionWorkSummaryService:
    """Summarize production work across character and story scopes."""

    def __init__(self, config, asset_repository, scene_image_review_service, scene_prompt_analysis_service):
        self.config = config
        self.asset_repository = asset_repository
        self.scene_image_review_service = scene_image_review_service
        self.scene_prompt_analysis_service = scene_prompt_analysis_service

    def list_asset_reviews(self, character: str = "", phase: str = "") -> list:
        rows = []
        root = Path(self.config.base_character_path)
        if not root.is_dir():
            return rows
        for character_path in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("_")):
            if character and character_path.name != character:
                continue
            for phase_path in sorted(path for path in character_path.iterdir() if path.is_dir() and not path.name.startswith("_")):
                if phase and phase_path.name != phase:
                    continue
                try:
                    assets = self.asset_repository.list_assets(character_path.name, phase_path.name)
                except AssetRepositoryError:
                    continue
                rows.extend(
                    asset
                    for asset in assets
                    if asset.pipeline_stage == "RENDER_REVIEW" and asset.actor == "HUMAN_AGENT"
                )
        return rows

    def _manual_tasks(self, character: str = "", phase: str = "", story_slug: str = "", scene_slug: str = "") -> list:
        service = ManualRenderSubmissionService(RenderConsoleQueue(self.config))
        return service.list_tasks(character, phase, story_slug, scene_slug)

    def _counts(
        self,
        workspace: str = "",
        character: str = "",
        phase: str = "",
        story_slug: str = "",
        scene_slug: str = "",
    ) -> dict[str, int]:
        if workspace == "character":
            manual = self._manual_tasks(character=character, phase=phase)
            reviews = self.list_asset_reviews(character, phase)
            scene_story = scene_scene = ""
        elif workspace == "story":
            manual = self._manual_tasks(story_slug=story_slug, scene_slug=scene_slug)
            reviews = self.scene_image_review_service.list_pending(story_slug, scene_slug)
            scene_story, scene_scene = story_slug, scene_slug
        else:
            manual = self._manual_tasks()
            reviews = [*self.list_asset_reviews(), *self.scene_image_review_service.list_pending()]
            scene_story = scene_scene = ""
        return {
            "prompt_available": len(manual),
            "analysis_pending": self.scene_prompt_analysis_service.pending_count(scene_story, scene_scene),
            "render_waiting": len(manual),
            "image_review_waiting": len(reviews),
        }

    def summary(
        self,
        workspace: str,
        character: str = "",
        phase: str = "",
        story_slug: str = "",
        scene_slug: str = "",
    ) -> dict:
        current = self._counts(workspace, character, phase, story_slug, scene_slug)
        return {
            "scope": {
                "workspace": workspace,
                "character": character,
                "phase": phase,
                "story_slug": story_slug,
                "scene_slug": scene_slug,
            },
            "current": current,
            "project": self._counts(),
        }
