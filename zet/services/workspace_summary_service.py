from __future__ import annotations

from pathlib import Path
from zet.models.workspace import (
    CharacterWorkspaceSummary,
    StorySceneSummary,
    StoryWorkspaceSummary,
    WorkspaceStep,
)
from zet.services.local_asset_store_service import LocalAssetStoreService


class WorkspaceSummaryService:
    """Build reusable Character Development and Story Telling summaries."""

    def __init__(
        self,
        onboarding_service,
        asset_repository,
        identity_key_service,
        turnaround_service,
        costume_service,
        expression_service,
        story_service,
        path_service,
    ):
        self.onboarding_service = onboarding_service
        self.asset_repository = asset_repository
        self.identity_key_service = identity_key_service
        self.turnaround_service = turnaround_service
        self.costume_service = costume_service
        self.expression_service = expression_service
        self.story_service = story_service
        self.path_service = path_service
        library_root = getattr(getattr(path_service, "config", None), "base_library_path", None)
        self.local_asset_store = (
            LocalAssetStoreService(library_root)
            if isinstance(library_root, (str, Path)) and str(library_root).strip()
            else None
        )

    @staticmethod
    def _locked_count(assets, pipeline: str) -> tuple[int, int]:
        rows = [asset for asset in assets if asset.pipeline == pipeline]
        locked = sum(
            1
            for asset in rows
            if asset.asset_state == "LOCKED" or asset.pipeline_stage == "LOCKED"
        )
        return locked, len(rows)

    def character_summary(self, character: str, phase: str) -> CharacterWorkspaceSummary:
        status = self.onboarding_service.status(character, phase)
        assets = self.local_asset_store.locked_assets(character, phase) if self.local_asset_store else []
        reference_locked = sum(str(item.get("pipeline") or "").lower() == "body-reference" for item in assets)
        head_image_locked = sum(str(item.get("pipeline") or "").lower() == "head-image" for item in assets)
        assembly_locked = sum(str(item.get("pipeline") or "").lower() == "character-assembly" for item in assets)
        reference_total = head_image_total = assembly_total = 8
        identity_count = len(self.identity_key_service.list_identity_keys(character, phase))
        turnaround_count = sum(
            1
            for row in self.turnaround_service.list_rows(character, phase)
            if row.locked_image_exists
        )
        costume_count = len(self.costume_service.list_costumes(character, phase))
        expression_count = 0
        reference_complete = reference_locked == reference_total
        head_image_complete = head_image_locked == head_image_total
        assembly_complete = assembly_locked == assembly_total
        steps = [
            WorkspaceStep("setup", "Setup", status.complete, int(status.complete), 1, "onboarding"),
            WorkspaceStep("references", "References", reference_complete, reference_locked, reference_total, "local-body-reference"),
        ]
        steps.append(WorkspaceStep("head-images", "Head Images", head_image_complete, head_image_locked, head_image_total, "local-head-image"))
        steps.extend([
            WorkspaceStep("assembly", "Assembly", assembly_complete, assembly_locked, assembly_total, "local-character-assembly"),
            WorkspaceStep("identity", "Identity", identity_count > 0, identity_count, 1, "identity-keys"),
            WorkspaceStep("costumes", "Costumes", costume_count > 0, costume_count, 1, "costumes"),
        ])
        recommendation = next((step for step in steps if not step.complete), None)
        if recommendation is None and turnaround_count == 0:
            destination, action = "turnarounds", "Create a locked turnaround"
        elif recommendation is None:
            destination, action = "local-batch-status", "Review local character assets"
        else:
            destination = recommendation.destination
            action = {
                "setup": "Edit character setup",
                "references": "Complete local body references",
                "head-images": "Complete local head images",
                "assembly": "Complete local character assembly",
                "identity": "Create an identity key",
                "costumes": "Create the first costume",
            }[recommendation.key]
        return CharacterWorkspaceSummary(
            character=character,
            phase=phase,
            ready=status.complete,
            steps=steps,
            base_reference_locked=reference_locked,
            base_reference_total=reference_total,
            head_image_locked=head_image_locked,
            head_image_total=head_image_total,
            assembly_locked=assembly_locked,
            assembly_total=assembly_total,
            identity_count=identity_count,
            turnaround_count=turnaround_count,
            costume_count=costume_count,
            expression_count=expression_count,
            recommended_destination=destination,
            recommended_action=action,
        )

    def story_summary(self, story_slug: str) -> StoryWorkspaceSummary:
        author = getattr(self, "narrative", None)
        if not author or not story_slug:
            return StoryWorkspaceSummary("", "No story selected", 0, 0, 0, 0)
        try:
            story = author.story(story_slug)
        except KeyError:
            return StoryWorkspaceSummary("", "No story selected", 0, 0, 0, 0)
        finals = {s["scene_id"]: s for s in author.finished_sources(story_slug)}
        scenes = []
        for scene in story["scenes"]:
            source = finals.get(scene["id"])
            state = "Locked" if source and source["locked"] else "Selected final assembly" if source else "Legacy image · stub" if scene.get("legacy_image") else "Not rendered"
            scenes.append(StorySceneSummary(scene["id"], scene["title"], state, source["image_path"] if source else "", False))
        return StoryWorkspaceSummary(story_slug, story["title"], len(scenes), sum(s["locked"] for s in finals.values()),
            0, len(scenes) - len(finals), scenes=scenes, recommended_scene_slug=scenes[0].slug if scenes else "",
            recommended_destination="narrative", recommended_action="Continue in Narrative Scenes")
