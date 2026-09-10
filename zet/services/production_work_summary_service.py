from __future__ import annotations

from pathlib import Path
from typing import Any

from zet.render_console.queue import RenderConsoleQueue
from zet.repositories.asset_repository import AssetRepositoryError
from zet.services.discovery_context import DiscoveryContext
from zet.services.manual_render_submission_service import ManualRenderSubmissionService
from zet.services.summary_cache import SummaryCache


class ProductionWorkSummaryService:
    """Summarize production work from one request-scoped discovered dataset."""

    def __init__(self, config, asset_repository, scene_image_review_service, scene_prompt_analysis_service):
        self.config = config
        self.asset_repository = asset_repository
        self.scene_image_review_service = scene_image_review_service
        self.scene_prompt_analysis_service = scene_prompt_analysis_service
        self.story_service = scene_image_review_service.story_service

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

    def _manual_tasks(self) -> list:
        return ManualRenderSubmissionService(RenderConsoleQueue(self.config)).list_tasks()

    @staticmethod
    def _task_matches(task, *, character: str = "", phase: str = "", story_slug: str = "", scene_slug: str = "") -> bool:
        return (
            (not character or not task.character or task.character == character)
            and (not phase or not task.phase or task.phase == phase)
            and (not story_slug or task.manifest.get("story_slug") == story_slug)
            and (not scene_slug or task.manifest.get("scene_slug") == scene_slug)
        )

    @staticmethod
    def _asset_matches(asset, character: str, phase: str) -> bool:
        return (not character or asset.character == character) and (not phase or asset.phase == phase)

    def _counts_from_dataset(
        self,
        dataset: dict[str, Any],
        workspace: str = "",
        character: str = "",
        phase: str = "",
        story_slug: str = "",
        scene_slug: str = "",
    ) -> dict[str, int]:
        tasks = dataset["manual_tasks"]
        assets = dataset["asset_reviews"]
        scenes = dataset["scene_reviews"]
        pending = dataset["analysis_pending"]
        if workspace == "character":
            tasks = [task for task in tasks if self._task_matches(task, character=character, phase=phase)]
            assets = [asset for asset in assets if self._asset_matches(asset, character, phase)]
            scenes = []
            analysis = len(pending)
        elif workspace == "story":
            tasks = [task for task in tasks if self._task_matches(task, story_slug=story_slug, scene_slug=scene_slug)]
            assets = []
            scenes = [
                row for row in scenes
                if (not story_slug or row.story_slug == story_slug)
                and (not scene_slug or row.scene_slug == scene_slug)
            ]
            analysis = sum(
                1 for story, scene, _target in pending
                if (not story_slug or story == story_slug)
                and (not scene_slug or scene == scene_slug)
            )
        else:
            analysis = len(pending)
        review_count = len(assets) + len(scenes)
        return {
            "prompt_available": len(tasks),
            "analysis_pending": analysis,
            "render_waiting": len(tasks),
            "image_review_waiting": review_count,
        }

    def _compute(self, workspace: str, character: str, phase: str, story_slug: str, scene_slug: str) -> dict:
        context = DiscoveryContext(self.story_service, self.scene_image_review_service.path_service)
        dataset = {
            "manual_tasks": self._manual_tasks(),
            "asset_reviews": self.list_asset_reviews(),
            "scene_reviews": self.scene_image_review_service.list_pending(discovery_context=context),
            "analysis_pending": self.scene_prompt_analysis_service.pending_records(),
        }
        return {
            "scope": {
                "workspace": workspace,
                "character": character,
                "phase": phase,
                "story_slug": story_slug,
                "scene_slug": scene_slug,
            },
            "current": self._counts_from_dataset(
                dataset, workspace, character, phase, story_slug, scene_slug
            ),
            "project": self._counts_from_dataset(dataset),
        }

    def summary(
        self,
        workspace: str,
        character: str = "",
        phase: str = "",
        story_slug: str = "",
        scene_slug: str = "",
    ) -> dict:
        key = (
            str(Path(self.config.base_library_path).resolve()),
            workspace,
            character,
            phase,
            story_slug,
            scene_slug,
        )
        return SummaryCache.get_or_compute(
            key,
            lambda: self._compute(workspace, character, phase, story_slug, scene_slug),
        )
