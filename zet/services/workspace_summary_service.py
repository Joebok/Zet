from __future__ import annotations

from zet.models.workspace import (
    CharacterWorkspaceSummary,
    StorySceneSummary,
    StoryWorkspaceSummary,
    WorkspaceStep,
)


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
        assets = self.asset_repository.list_assets(character, phase) if status.assets_exists else []
        reference_locked, reference_total = self._locked_count(assets, "Body-Reference")
        head_image_locked, head_image_total = self._locked_count(assets, "Head-Image")
        assembly_locked, assembly_total = self._locked_count(assets, "Character-Assembly")
        identity_count = len(self.identity_key_service.list_identity_keys(character, phase))
        turnaround_count = sum(
            1
            for row in self.turnaround_service.list_rows(character, phase)
            if row.locked_image_exists
        )
        costume_count = len(self.costume_service.list_costumes(character, phase))
        expression_count = len(self.expression_service.list_expression_definitions(character, phase))
        reference_complete = reference_total > 0 and reference_locked == reference_total
        head_image_complete = head_image_total > 0 and head_image_locked == head_image_total
        assembly_complete = assembly_total > 0 and assembly_locked == assembly_total
        steps = [
            WorkspaceStep("setup", "Setup", status.complete, int(status.complete), 1, "onboarding"),
            WorkspaceStep("references", "References", reference_complete, reference_locked, reference_total, "assets"),
        ]
        if head_image_total:
            steps.append(WorkspaceStep("head-images", "Head Images", head_image_complete, head_image_locked, head_image_total, "assets"))
        steps.extend([
            WorkspaceStep("assembly", "Assembly", assembly_complete, assembly_locked, assembly_total, "assets"),
            WorkspaceStep("identity", "Identity", identity_count > 0, identity_count, 1, "identity-keys"),
            WorkspaceStep("costumes", "Costumes", costume_count > 0, costume_count, 1, "costumes"),
        ])
        recommendation = next((step for step in steps if not step.complete), None)
        if recommendation is None and turnaround_count == 0:
            destination, action = "turnarounds", "Create a locked turnaround"
        elif recommendation is None:
            destination, action = "assets", "Review character assets"
        else:
            destination = recommendation.destination
            action = {
                "setup": "Edit character setup",
                "references": "Complete base references",
                "head-images": "Complete head images",
                "assembly": "Complete character assembly",
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
        story = next(
            (record for record in self.story_service.list_stories() if record.slug == story_slug),
            None,
        )
        if story is None:
            return StoryWorkspaceSummary("", "No story selected", 0, 0, 0, 0)
        scenes = []
        locked_count = 0
        candidate_count = 0
        for scene in self.story_service.list_scenes(story.slug):
            locked_path = self.path_service.scene_locked_image_path(story.slug, scene.slug)
            candidate_path = self.path_service.scene_candidate_image_path(story.slug, scene.slug)
            candidate_exists = candidate_path.is_file()
            locked_exists = locked_path.is_file()
            if candidate_exists:
                image_state = "Candidate ready"
                image_path = str(candidate_path)
                candidate_count += 1
            elif locked_exists:
                image_state = "Locked"
                image_path = str(locked_path)
            else:
                image_state = "Not rendered"
                image_path = ""
            if locked_exists:
                locked_count += 1
            scenes.append(
                StorySceneSummary(
                    slug=scene.slug,
                    title=scene.title,
                    image_state=image_state,
                    image_path=image_path,
                    candidate_pending=candidate_exists,
                )
            )
        recommended = next((scene for scene in scenes if scene.candidate_pending), None)
        if recommended is not None:
            destination, action = "render-review", "Review the next candidate"
        else:
            recommended = next((scene for scene in scenes if scene.image_state == "Not rendered"), None)
            if recommended is not None:
                destination, action = "scene-builder", "Continue in Scene Builder"
            elif scenes:
                recommended = scenes[0]
                destination, action = "scene-builder", "Continue in Scene Builder"
            else:
                destination, action = "scenes", "Add the first scene"
        return StoryWorkspaceSummary(
            story_slug=story.slug,
            title=story.title,
            scene_count=len(scenes),
            locked_count=locked_count,
            candidate_count=candidate_count,
            unrendered_count=sum(1 for scene in scenes if scene.image_state == "Not rendered"),
            scenes=scenes,
            recommended_scene_slug=recommended.slug if recommended else "",
            recommended_destination=destination,
            recommended_action=action,
        )
