from pathlib import Path
from datetime import datetime

from zet.models.asset import Asset
from zet.models.auxiliary_resource import AuxiliaryResource
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.repositories.turnaround_repository import TurnaroundRepository
from zet.services.asset_service import (
    AssetService,
    BatchRenderResetPreviewResult,
    BatchRenderResetResult,
    asset_sort_key,
)
from zet.services.auxiliary_resource_service import AuxiliaryResourceService
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.ai_proxy_service import AIProxyService
from zet.services.ai_answer_harvester import AIAnswerHarvester
from zet.services.character_onboarding_service import CharacterOnboardingService
from zet.services.character_source_service import CharacterSourceService
from zet.services.config_service import ConfigService
from zet.services.costume_service import CostumeCreateResult, CostumeService, CostumeUpdateResult
from zet.services.expression_service import ExpressionCreateResult, ExpressionService, ExpressionUpdateResult
from zet.services.housekeeping_service import HousekeepingService
from zet.services.head_fitment_edit_service import HeadFitmentEditService
from zet.services.identity_key_service import IdentityKeyPreview, IdentityKeyService
from zet.services.path_service import PathService
from zet.services.phase_comparison_service import PhaseComparisonResult, PhaseComparisonService
from zet.services.process_service import ProcessService
from zet.services.pipeline_control_service import AutomationSettings, PipelineControlService, PipelineControlSnapshot
from zet.services.pipeline_inspection_service import PipelineInspectionService
from zet.services.prompt_review_service import PromptReviewContext, PromptReviewService
from zet.services.prompt_artifact_service import PromptArtifactService
from zet.services.reference_service import ReferenceService
from zet.services.story_service import ImageReferenceRow, SceneBuilderDocument, SceneDocument, SceneRecord, StoryDocument, StoryGitResult, StoryRecord, StoryRenderTask, StoryService
from zet.services.scene_prompt_analysis_service import ScenePromptAnalysisService
from zet.services.scene_image_review_service import SceneImageReviewService
from zet.services.state_machine import StateMachine
from zet.services.turnaround_service import TurnaroundRow, TurnaroundService
from zet.services.worker_service import WorkerService
from zet.services.workspace_summary_service import WorkspaceSummaryService
from zet.services.zine_service import ZineService


class AssetRef:
    def __init__(self, app: "ZetApp", character: str, phase: str, asset_id: int):
        self._app = app
        self._character = character
        self._phase = phase
        self._asset_id = asset_id

    def get(self) -> Asset:
        return self._app.asset_repository.get_asset(self._character, self._phase, self._asset_id)

    def show(self) -> None:
        asset = self.get()
        for field_name, value in asset.__dict__.items():
            print(f"{field_name}: {value}")

    def pipeline_path(self) -> Path:
        return self._app.path_service.pipeline_path(self.get())

    def candidate_image_path(self) -> Path:
        return self._app.path_service.candidate_image_path(self.get())

    def locked_image_path(self) -> Path:
        return self._app.path_service.locked_image_path(self.get())

    def move_next(self) -> Asset:
        return self._app.asset_service.move_next(self._character, self._phase, self._asset_id)

    def prompt_review_context(self) -> PromptReviewContext:
        return self._app.prompt_review_service.get_context(self._character, self._phase, self._asset_id)

    def generate_local_test_render(self):
        return self._app.prompt_review_service.generate_local_test_render(self._character, self._phase, self._asset_id)

    def recompile_prompt_review(self, invalidate_review_artifacts: bool = False) -> PromptReviewContext:
        return self._app.prompt_review_service.recompile(
            self._character,
            self._phase,
            self._asset_id,
            invalidate_review_artifacts,
        )

    def run_housekeeping(self) -> Path:
        return self._app.asset_service.run_housekeeping(self._character, self._phase, self._asset_id)

    def regenerate(self) -> Asset:
        return self._app.asset_service.regenerate(self._character, self._phase, self._asset_id)

    def regenerate_and_advance(self):
        return self._app.asset_service.regenerate_and_advance(self._character, self._phase, self._asset_id)

    def regenerate_and_clear_references(self) -> Asset:
        return self._app.asset_service.regenerate_and_clear_references(self._character, self._phase, self._asset_id)

    def promote_to_locked(self) -> Asset:
        return self._app.asset_service.promote_to_locked(self._character, self._phase, self._asset_id)

    def discard_candidate(self) -> Asset:
        return self._app.asset_service.discard_candidate(self._character, self._phase, self._asset_id)

    def keep_locked(self) -> Asset:
        return self._app.asset_service.keep_locked(self._character, self._phase, self._asset_id)

    def render_review_comment(self) -> str:
        """Read the render-review comment for this asset."""
        return self._app.asset_service.get_render_review_comment(self._character, self._phase, self._asset_id)

    def save_render_review_comment(self, comment: str) -> str:
        """Save the render-review comment for this asset."""
        return self._app.asset_service.save_render_review_comment(self._character, self._phase, self._asset_id, comment)

    def fail_render_review_to_render(self, reason: str = "") -> Asset:
        return self._app.asset_service.fail_render_review_to_render(
            self._character,
            self._phase,
            self._asset_id,
            reason,
        )

    def run_current_worker(self) -> Asset:
        return self._app.asset_service.run_current_worker(self._character, self._phase, self._asset_id)

    def run_current_worker_chain(self):
        return self._app.asset_service.run_current_worker_chain(self._character, self._phase, self._asset_id)

    def stage_ai_ask(self) -> Path:
        return self._app.asset_service.stage_ai_ask(self._character, self._phase, self._asset_id)


class ZetApp:
    def __init__(
        self,
        config,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        asset_service: AssetService,
        prompt_review_service: PromptReviewService,
        reference_service: ReferenceService,
        housekeeping_service: HousekeepingService,
        path_service: PathService,
        turnaround_service: TurnaroundService,
        identity_key_service: IdentityKeyService,
        costume_service: CostumeService,
        expression_service: ExpressionService,
        character_onboarding_service: CharacterOnboardingService,
        auxiliary_resource_service: AuxiliaryResourceService,
        phase_comparison_service: PhaseComparisonService,
        story_service: StoryService,
        config_path: str | Path = "config.toml",
    ):
        self.config = config
        self.config_path = Path(config_path)
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.asset_service = asset_service
        self.prompt_review_service = prompt_review_service
        self.reference_service = reference_service
        self.head_fitment_edit_service = HeadFitmentEditService(asset_repository, path_service)
        self.housekeeping_service = housekeeping_service
        self.path_service = path_service
        self.turnaround_service = turnaround_service
        self.identity_key_service = identity_key_service
        self.costume_service = costume_service
        self.expression_service = expression_service
        self.character_onboarding_service = character_onboarding_service
        self.auxiliary_resource_service = auxiliary_resource_service
        self.phase_comparison_service = phase_comparison_service
        self.story_service = story_service
        self.scene_image_review_service = SceneImageReviewService(story_service)
        self.workspace_summary_service = WorkspaceSummaryService(
            character_onboarding_service,
            asset_repository,
            identity_key_service,
            turnaround_service,
            costume_service,
            expression_service,
            story_service,
            path_service,
        )
        self.asset_service.ai_answer_harvester.scene_image_review_service = self.scene_image_review_service
        self.character_source_service = CharacterSourceService(
            path_service,
            costume_service,
            story_service,
            Path(__file__).resolve().parents[1],
        )
        self.zine_service = ZineService(path_service, story_service)
        self.scene_prompt_analysis_service = ScenePromptAnalysisService(config, story_service)
        self.process_service = ProcessService(Path(__file__).resolve().parents[1])
        self.pipeline_control_service = PipelineControlService(
            self.config_path,
            config,
            asset_repository,
            pipeline_repository,
        )
        self.pipeline_inspection_service = PipelineInspectionService(config.base_pipeline_path, asset_repository, path_service)

    def list_pipeline_inspections(self) -> list[dict]:
        return self.pipeline_inspection_service.list_pipelines()

    def list_pipeline_files(self, pipeline_id: str) -> list[dict[str, str]]:
        return self.pipeline_inspection_service.list_files(pipeline_id)

    def read_pipeline_file(self, pipeline_id: str, file_id: str) -> str:
        return self.pipeline_inspection_service.read_text(pipeline_id, file_id)

    def pipeline_file_path(self, pipeline_id: str, file_id: str) -> Path:
        return self.pipeline_inspection_service.file_path(pipeline_id, file_id)

    def open_pipeline_folder(self, pipeline_id: str, file_id: str) -> Path:
        return self.pipeline_inspection_service.open_folder(pipeline_id, file_id)

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ZetApp":
        config = ConfigService.load(config_path)
        path_service = PathService(config, Path(config_path).resolve().parent)
        asset_repository = AssetRepository(path_service)
        auxiliary_resource_repository = AuxiliaryResourceRepository(path_service)
        pipeline_repository = PipelineRepository(path_service)
        turnaround_repository = TurnaroundRepository(path_service)
        identity_key_repository = IdentityKeyRepository(path_service)
        state_machine = StateMachine()
        housekeeping_service = HousekeepingService(path_service)
        worker_service = WorkerService(asset_repository, pipeline_repository, path_service)
        prompt_artifact_service = PromptArtifactService(asset_repository, path_service)
        ai_proxy_path_service = AIProxyPathService(config)
        ai_proxy_service = AIProxyService(
            asset_repository,
            pipeline_repository,
            path_service,
            prompt_artifact_service,
            ai_proxy_path_service,
            housekeeping_service,
        )
        worker_service.ai_proxy_service = ai_proxy_service
        ai_answer_harvester = AIAnswerHarvester(
            asset_repository,
            pipeline_repository,
            ai_proxy_path_service,
            path_service,
            housekeeping_service,
            state_machine,
            timestamp_provider=lambda: datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            ai_proxy_service=ai_proxy_service,
        )
        asset_service = AssetService(
            asset_repository,
            pipeline_repository,
            state_machine,
            housekeeping_service,
            path_service,
            prompt_artifact_service,
            worker_service,
            ai_proxy_service,
            ai_answer_harvester,
        )
        prompt_review_service = PromptReviewService(
            asset_repository,
            pipeline_repository,
            prompt_artifact_service,
            worker_service,
            path_service,
        )
        reference_service = ReferenceService(asset_repository, path_service)
        turnaround_service = TurnaroundService(
            asset_repository,
            pipeline_repository,
            turnaround_repository,
            path_service,
        )
        identity_key_service = IdentityKeyService(
            asset_repository,
            identity_key_repository,
            path_service,
        )
        costume_service = CostumeService(asset_repository, path_service)
        expression_service = ExpressionService(asset_repository, identity_key_repository, path_service)
        character_onboarding_service = CharacterOnboardingService(path_service)
        auxiliary_resource_service = AuxiliaryResourceService(auxiliary_resource_repository, path_service)
        phase_comparison_service = PhaseComparisonService(
            asset_repository,
            pipeline_repository,
            path_service,
            Path(__file__).resolve().parents[1],
        )
        story_service = StoryService(
            path_service,
            asset_repository,
            auxiliary_resource_repository,
            identity_key_repository,
            turnaround_repository,
        )
        app = cls(
            config,
            asset_repository,
            pipeline_repository,
            asset_service,
            prompt_review_service,
            reference_service,
            housekeeping_service,
            path_service,
            turnaround_service,
            identity_key_service,
            costume_service,
            expression_service,
            character_onboarding_service,
            auxiliary_resource_service,
            phase_comparison_service,
            story_service,
            config_path,
        )
        app.ai_proxy_service = ai_proxy_service
        return app

    def list_assets(self, character: str, phase: str) -> list[Asset]:
        return sorted(self.asset_repository.list_assets(character, phase), key=asset_sort_key)

    def character_workspace_summary(self, character: str, phase: str):
        """Return Character Development readiness for one phase."""
        return self.workspace_summary_service.character_summary(character, phase)

    def story_workspace_summary(self, story_slug: str):
        """Return Story Telling progress for one story."""
        return self.workspace_summary_service.story_summary(story_slug)

    def list_auxiliary_resources(self, category: str) -> list[AuxiliaryResource]:
        """List global auxiliary resources by category."""
        return self.auxiliary_resource_service.list_resources(category)

    def list_stories(self) -> list[StoryRecord]:
        """List story folders in the shared library."""
        return self.story_service.list_stories()

    def create_story(self, title: str) -> StoryDocument:
        """Create a story folder and main story markdown file."""
        return self.story_service.create_story(title)

    def load_story(self, story_slug: str) -> StoryDocument:
        """Load one story markdown document."""
        return self.story_service.load_story(story_slug)

    def save_story(self, story_slug: str, text: str) -> StoryDocument:
        """Save one story markdown document."""
        return self.story_service.save_story(story_slug, text)

    def rename_story(self, story_slug: str, title: str) -> StoryDocument:
        """Rename one story without changing its stable slug."""
        return self.story_service.rename_story(story_slug, title)

    def reorder_stories(self, story_slugs: list[str]) -> list[StoryRecord]:
        """Persist the display order for all stories."""
        return self.story_service.reorder_stories(story_slugs)

    def load_story_settings(self, story_slug: str) -> dict:
        """Load one story settings JSON document."""
        path = self.story_service.get_story_settings_path_from_story_md(self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug)))
        if not path.exists():
            self.story_service.save_story_settings(path, self.story_service.create_default_story_settings(self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug))))
        return self.story_service.load_story_settings(path)

    def save_story_settings(self, story_slug: str, data: dict) -> dict:
        """Save one story settings JSON document."""
        path = self.story_service.get_story_settings_path_from_story_md(self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug)))
        self.story_service.save_story_settings(path, data)
        return self.story_service.load_story_settings(path)

    def delete_story(self, story_slug: str) -> StoryGitResult:
        """Commit and delete one story folder."""
        return self.story_service.delete_story(story_slug)

    def story_git_has_changes(self) -> bool:
        """Return whether the Stories folder has uncommitted changes."""
        return self.story_service.story_git_has_changes()

    def story_git_status(self) -> StoryGitResult:
        """Fetch and return story git status."""
        return self.story_service.story_git_status()

    def story_git_pull(self) -> StoryGitResult:
        """Pull library changes and return story git output."""
        return self.story_service.story_git_pull()

    def story_git_commit(self) -> StoryGitResult:
        """Commit and push story changes."""
        return self.story_service.story_git_commit()

    def list_scenes(self, story_slug: str) -> list[SceneRecord]:
        """List scene markdown files for one story."""
        return self.story_service.list_scenes(story_slug)

    def create_scene(self, story_slug: str, scene_name: str) -> SceneDocument:
        """Create a new scene markdown file from template."""
        return self.story_service.create_scene(story_slug, scene_name)

    def load_scene(self, story_slug: str, scene_slug: str) -> SceneDocument:
        """Load one scene markdown document."""
        return self.story_service.load_scene(story_slug, scene_slug)

    def save_scene(self, story_slug: str, scene_slug: str, text: str) -> SceneDocument:
        """Save one scene markdown document."""
        return self.story_service.save_scene(story_slug, scene_slug, text)

    def rename_scene(self, story_slug: str, scene_slug: str, title: str) -> SceneDocument:
        """Rename one scene without changing its stable slug."""
        return self.story_service.rename_scene(story_slug, scene_slug, title)

    def reorder_scenes(self, story_slug: str, scene_slugs: list[str]) -> list[SceneRecord]:
        """Persist the display order for one story's scenes."""
        return self.story_service.reorder_scenes(story_slug, scene_slugs)

    def move_scene(self, story_slug: str, scene_slug: str, target_story_slug: str) -> SceneDocument:
        """Move one scene and its artifacts to another story."""
        return self.story_service.move_scene(story_slug, scene_slug, target_story_slug)

    def delete_scene(self, story_slug: str, scene_slug: str) -> StoryGitResult:
        """Commit and delete one scene markdown and image."""
        return self.story_service.delete_scene(story_slug, scene_slug)

    def scene_image_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the expected rendered scene image path."""
        return self.story_service.scene_image_path(story_slug, scene_slug)

    def scene_image_review_status(self, story_slug: str, scene_slug: str):
        return self.scene_image_review_service.status(story_slug, scene_slug)

    def list_pending_scene_image_reviews(self, story_slug: str = "", scene_slug: str = ""):
        return self.scene_image_review_service.list_pending(story_slug, scene_slug)

    def promote_scene_image(self, story_slug: str, scene_slug: str):
        return self.scene_image_review_service.promote(story_slug, scene_slug)

    def discard_scene_image_candidate(self, story_slug: str, scene_slug: str):
        return self.scene_image_review_service.discard(story_slug, scene_slug)

    def save_scene_image_review_comment(self, story_slug: str, scene_slug: str, comment: str):
        return self.scene_image_review_service.save_comment(story_slug, scene_slug, comment)

    def load_scene_builder(self, story_slug: str, scene_slug: str) -> SceneBuilderDocument:
        """Load Scene Builder JSON for one story scene."""
        return self.story_service.load_scene_builder_data(story_slug, scene_slug)

    def save_scene_builder(self, story_slug: str, scene_slug: str, data: dict) -> SceneBuilderDocument:
        """Save Scene Builder JSON for one story scene."""
        return self.story_service.save_scene_builder_data(story_slug, scene_slug, data)

    def continue_scene_builder_from(self, story_slug: str, scene_slug: str, source_scene_slug: str) -> SceneBuilderDocument:
        """Copy reusable visual setup from another scene in the same story."""
        return self.story_service.continue_scene_builder_from(story_slug, scene_slug, source_scene_slug)

    def generate_scene_builder(self, story_slug: str, scene_slug: str, data: dict) -> dict:
        """Generate Scene Builder outputs without saving."""
        return self.story_service.generate_scene_builder_outputs(story_slug, scene_slug, data)

    def export_scene_builder_markdown(self, story_slug: str, scene_slug: str, data: dict) -> SceneDocument:
        """Export Scene Builder-managed markdown into the scene file."""
        return self.story_service.export_scene_markdown(story_slug, scene_slug, data)

    def scene_builder_options(self) -> dict:
        """Return Scene Builder option lists."""
        return self.story_service.scene_builder_options()

    def stage_scene_render(self, story_slug: str, scene_slug: str) -> StoryRenderTask:
        """Compile and stage one story scene for the Render Console."""
        return self.story_service.stage_scene_render(story_slug, scene_slug)

    def queue_scene_prompt_analysis(self, story_slug: str, scene_slug: str) -> dict:
        return self.scene_prompt_analysis_service.queue(story_slug, scene_slug)

    def scene_prompt_analysis_status(self, story_slug: str, scene_slug: str) -> dict:
        return self.scene_prompt_analysis_service.status(story_slug, scene_slug)

    def scene_image_reference_rows(self, character: str = "", text_filter: str = "") -> list[ImageReferenceRow]:
        """List copyable image references for the scene editor."""
        return self.story_service.image_reference_rows(character, text_filter)

    def character_source_options(self, character: str = "", phase: str = "") -> dict:
        """Return safe dropdown options for a character-source consumer."""
        return self.character_source_service.options(character, phase)

    def image_reference_rows(
        self,
        character: str = "",
        phase: str = "",
        costume: str = "",
        text_filter: str = "",
        scope: str = "context",
        include_unavailable: bool = True,
    ) -> list[ImageReferenceRow]:
        """List reusable image-reference tags with contextual filters."""
        return self.story_service.image_reference_rows(
            character,
            text_filter,
            phase,
            costume,
            scope,
            include_unavailable,
        )

    def resolve_image_reference_tag(self, tag: str) -> dict:
        """Resolve one exact Zet image-reference tag."""
        return self.story_service.story_reference_service.resolve_image_tag(tag)

    def compile_character_source(
        self,
        *,
        character: str,
        phase: str,
        costume_slug: str | None,
        view_token: str,
        selected_sections: tuple[str, ...],
        reference_tags: tuple[str, ...],
    ) -> dict:
        """Compile one immutable character-source snapshot."""
        return self.character_source_service.compile(
            character=character,
            phase=phase,
            costume_slug=costume_slug,
            view_token=view_token,
            selected_sections=selected_sections,
            reference_tags=reference_tags,
        )

    def list_zines(self):
        """List saved zines."""
        return self.zine_service.list_zines()

    def load_zine(self, slug: str):
        """Load one saved zine."""
        return self.zine_service.load_zine(slug)

    def zine_story_scene_sources(self, story_slug: str):
        """List readable story scene images for zine auto-fill."""
        return self.zine_service.story_scene_sources(story_slug)

    def create_zine(self, payload: dict):
        """Create and render a zine."""
        return self.zine_service.create_zine(payload)

    def update_zine(self, slug: str, payload: dict):
        """Update, optionally rename, and render a zine."""
        return self.zine_service.update_zine(slug, payload)

    def regenerate_zine(self, slug: str):
        """Regenerate a zine from its saved image tags."""
        return self.zine_service.regenerate_zine(slug)

    def delete_zine(self, slug: str) -> None:
        """Delete one saved zine folder."""
        self.zine_service.delete_zine(slug)

    def phase_comparison(
        self,
        character: str,
        left_phase: str,
        right_phase: str,
        pipeline: str = "",
        selected_index: int = 0,
        selected_slot_key: str = "",
        left_costume: str = "",
        right_costume: str = "",
    ) -> PhaseComparisonResult:
        """Build a read-only comparison between two character phases."""
        return self.phase_comparison_service.compare(
            character,
            left_phase,
            right_phase,
            pipeline,
            selected_index,
            selected_slot_key,
            left_costume,
            right_costume,
        )

    def create_auxiliary_resource(
        self,
        category: str,
        label: str,
    ) -> AuxiliaryResource:
        """Create a global auxiliary resource."""
        return self.auxiliary_resource_service.create_resource(category, label)

    def update_auxiliary_resource(
        self,
        resource_id: str,
        label: str,
    ) -> AuxiliaryResource:
        """Update a global auxiliary resource."""
        return self.auxiliary_resource_service.update_resource(resource_id, label)

    def delete_auxiliary_resource(self, resource_id: str) -> AuxiliaryResource:
        """Delete a global auxiliary resource and its files."""
        return self.auxiliary_resource_service.delete_resource(resource_id)

    def save_auxiliary_resource_image(
        self,
        resource_id: str,
        image_label: str,
        image_bytes: bytes,
        content_type: str,
        original_image_id: str = "",
    ) -> AuxiliaryResource:
        """Save or update one image inside an auxiliary resource."""
        return self.auxiliary_resource_service.save_image(resource_id, image_label, image_bytes, content_type, original_image_id)

    def character_onboarding_options(self):
        """Return options used by new character and phase onboarding."""
        return self.character_onboarding_service.options()

    def character_onboarding_status(self, character: str, phase: str):
        """Return onboarding status for a character phase."""
        return self.character_onboarding_service.status(character, phase)

    def character_onboarding_prefill(self, character: str, source_phase: str = ""):
        """Return metadata defaults for a new character or phase."""
        return self.character_onboarding_service.prefill(character, source_phase)

    def save_character_onboarding_draft(self, payload: dict):
        """Create or update a draft character phase template."""
        return self.character_onboarding_service.save_draft(payload)

    def upload_character_template(self, character: str, phase: str, contents: str):
        """Install and validate an uploaded character image template."""
        return self.character_onboarding_service.upload_template(character, phase, contents)

    def initialize_character_foundation(self, character: str, phase: str) -> None:
        """Create foundation assets for a validated character phase."""
        self.character_onboarding_service.initialize_foundation(character, phase)

    def add_missing_head_image_foundation(self, character: str, phase: str):
        return self.character_onboarding_service.add_missing_head_image_foundation(character, phase)

    def asset(self, character: str, phase: str, asset_id: int) -> AssetRef:
        return AssetRef(self, character, phase, asset_id)

    def prompt_review_context(self, character: str, phase: str, asset_id: int) -> PromptReviewContext:
        return self.prompt_review_service.get_context(character, phase, asset_id)

    def generate_local_test_render(self, character: str, phase: str, asset_id: int):
        return self.prompt_review_service.generate_local_test_render(character, phase, asset_id)

    def stage_prompt_condense_ask(self, character: str, phase: str, asset_id: int, force: bool = False):
        return self.ai_proxy_service.stage_prompt_condense_ask_if_enabled(character, phase, asset_id, force)

    def stage_prompt_inspection_render_ask(self, character: str, phase: str, asset_id: int):
        return self.ai_proxy_service.stage_prompt_inspection_render_ask_if_enabled(character, phase, asset_id)

    def stage_render_task_prompt_condense_ask(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        force: bool = False,
    ):
        return self.ai_proxy_service.stage_render_task_prompt_condense_ask_if_enabled(manifest, prompt_path, target_output_dir, force)

    def stage_render_task_local_render_ask(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        *,
        allow_parallel: bool = False,
        seed: int | None = None,
        checkpoint: str | None = None,
    ):
        return self.ai_proxy_service.stage_render_task_local_render_ask(
            manifest,
            prompt_path,
            target_output_dir,
            allow_parallel=allow_parallel,
            seed=seed,
            checkpoint=checkpoint,
        )

    def stage_scene_local_render_ask(
        self,
        manifest: dict,
        workspace: Path,
        *,
        allow_parallel: bool = False,
        seed: int | None = None,
        checkpoint: str | None = None,
    ):
        return self.ai_proxy_service.stage_scene_local_render_ask(
            manifest,
            workspace,
            allow_parallel=allow_parallel,
            seed=seed,
            checkpoint=checkpoint,
        )

    def recompile_prompt_review(
        self,
        character: str,
        phase: str,
        asset_id: int,
        invalidate_review_artifacts: bool = False,
    ) -> PromptReviewContext:
        return self.prompt_review_service.recompile(character, phase, asset_id, invalidate_review_artifacts)

    def harvest_ai_answers(self):
        return self.asset_service.harvest_ai_answers()

    def run_available_workers(self, character: str, phase: str):
        return self.asset_service.run_available_workers(character, phase)

    def advance_assets(self, character: str, phase: str, asset_ids: list[int]) -> list[dict]:
        """Advance each requested non-locked asset as far as its current worker allows."""
        results = []
        for asset_id in asset_ids:
            try:
                asset = self.asset_repository.get_asset(character, phase, int(asset_id))
                if asset.asset_state == "LOCKED" or asset.pipeline_stage == "LOCKED":
                    results.append(
                        {
                            "asset_id": asset.asset_id,
                            "status": "SKIPPED",
                            "message": "Asset is locked.",
                            "before_stage": asset.pipeline_stage,
                            "after_stage": asset.pipeline_stage,
                        }
                    )
                    continue
                before_stage = asset.pipeline_stage
                before_actor = asset.actor
                result = self.asset_service.run_current_worker_chain(character, phase, asset.asset_id)
                progressed = result.asset.pipeline_stage != before_stage or result.asset.actor != before_actor
                if result.asset.pipeline_stage == "ERROR":
                    status = "ERROR"
                elif progressed:
                    status = "ADVANCED"
                else:
                    status = "WAITING" if result.worker_count else "SKIPPED"
                results.append(
                    {
                        "asset_id": result.asset.asset_id,
                        "status": status,
                        "message": " | ".join(result.messages) or "No worker ran.",
                        "worker_count": result.worker_count,
                        "before_stage": before_stage,
                        "before_actor": before_actor,
                        "after_stage": result.asset.pipeline_stage,
                        "after_actor": result.asset.actor,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "asset_id": int(asset_id),
                        "status": "ERROR",
                        "message": str(exc),
                    }
                )
        return results

    def reset_pipeline_assets_to_render(
        self,
        character: str,
        phase: str,
        pipeline_name: str,
        include_locked: bool = False,
    ) -> list[BatchRenderResetResult]:
        return self.asset_service.reset_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)

    def preview_pipeline_assets_to_render(
        self,
        character: str,
        phase: str,
        pipeline_name: str,
        include_locked: bool = False,
    ) -> list[BatchRenderResetPreviewResult]:
        return self.asset_service.preview_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)

    def fail_render_review_to_render(self, character: str, phase: str, asset_id: int, reason: str = "") -> Asset:
        return self.asset_service.fail_render_review_to_render(character, phase, asset_id, reason)

    def render_review_comment(self, character: str, phase: str, asset_id: int) -> str:
        """Read the render-review comment for an asset."""
        return self.asset_service.get_render_review_comment(character, phase, asset_id)

    def save_render_review_comment(self, character: str, phase: str, asset_id: int, comment: str) -> str:
        """Save the render-review comment for an asset."""
        return self.asset_service.save_render_review_comment(character, phase, asset_id, comment)

    def queue_snapshot(self):
        return self.ai_proxy_service.queue_snapshot()

    def archive_harvested_answers(self):
        """Archive harvested AI answer folders."""
        return self.ai_proxy_service.archive_harvested_answers()

    def harvested_answer_count(self) -> int:
        return self.ai_proxy_service.harvested_answer_count()

    def process_statuses(self):
        return self.process_service.statuses()

    def start_process(self, process_id: str):
        return self.process_service.start(process_id)

    def stop_process(self, process_id: str):
        return self.process_service.stop(process_id)

    def restart_process(self, process_id: str):
        return self.process_service.restart(process_id)

    def pipeline_control_snapshot(self, character: str, phase: str) -> PipelineControlSnapshot:
        return self.pipeline_control_service.snapshot(character, phase)

    def save_automation_settings(self, settings: AutomationSettings) -> None:
        self.pipeline_control_service.save_automation_settings(settings)

    def todo_text(self) -> str:
        path = Path(__file__).resolve().parents[1] / "Docs" / "ToDo.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def save_todo_text(self, text: str) -> None:
        path = Path(__file__).resolve().parents[1] / "Docs" / "ToDo.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def head_fitment_reference_context(self, character: str, phase: str, asset_id: int):
        return self.reference_service.head_fitment_context(character, phase, asset_id)

    def head_fitment_edit_context(self, character: str, phase: str, asset_id: int):
        return self.head_fitment_edit_service.context(character, phase, asset_id)

    def initialize_head_fitment_edit(self, character: str, phase: str, asset_id: int):
        return self.head_fitment_edit_service.initialize(character, phase, asset_id)

    def save_head_fitment_edit_mask(self, character: str, phase: str, asset_id: int, contents: bytes):
        return self.head_fitment_edit_service.save_mask(character, phase, asset_id, contents)

    def head_fitment_model_requirements(self):
        return self.head_fitment_edit_service.model_requirements()

    def head_image_reference_context(self, character: str, phase: str, asset_id: int):
        return self.reference_service.head_image_context(character, phase, asset_id)

    def character_assembly_reference_context(self, character: str, phase: str, asset_id: int):
        return self.reference_service.character_assembly_context(character, phase, asset_id)

    def save_head_image_source(self, character: str, phase: str, asset_id: int, source_path: str):
        return self.reference_service.save_head_image_source(character, phase, asset_id, source_path)

    def upload_head_image_source(self, character: str, phase: str, filename: str, contents: bytes):
        return self.reference_service.upload_head_image_source(character, phase, filename, contents)

    def save_head_fitment_references(
        self,
        character: str,
        phase: str,
        asset_id: int,
        body_reference_path: str,
        headshot_path: str,
    ) -> Asset:
        return self.reference_service.save_head_fitment_references(
            character,
            phase,
            asset_id,
            body_reference_path,
            headshot_path,
        )

    def save_character_assembly_references(
        self,
        character: str,
        phase: str,
        asset_id: int,
        body_reference_path: str,
        head_fitment_path: str,
    ) -> Asset:
        return self.reference_service.save_character_assembly_references(
            character,
            phase,
            asset_id,
            body_reference_path,
            head_fitment_path,
        )

    def upload_headshot_reference(self, character: str, phase: str, filename: str, contents: bytes) -> Path:
        return self.reference_service.upload_headshot(character, phase, filename, contents)

    def list_turnaround_rows(self, character: str, phase: str) -> list[TurnaroundRow]:
        """List dashboard rows for turnaround sheet generation."""
        return self.turnaround_service.list_rows(character, phase)

    def turnaround_row(self, character: str, phase: str, turnaround_id: str) -> TurnaroundRow:
        """Return one dashboard row for a turnaround sheet."""
        return self.turnaround_service.get_row(character, phase, turnaround_id)

    def generate_turnaround(
        self,
        character: str,
        phase: str,
        turnaround_id: str,
        detection_tolerance: float | None = None,
    ) -> TurnaroundRow:
        """Generate a candidate turnaround sheet for review."""
        return self.turnaround_service.generate_candidate(character, phase, turnaround_id, detection_tolerance)

    def promote_turnaround_to_locked(
        self,
        character: str,
        phase: str,
        turnaround_id: str,
        replace_existing: bool = False,
    ) -> TurnaroundRow:
        """Promote a reviewed turnaround candidate to the locked reference image."""
        return self.turnaround_service.promote_to_locked(character, phase, turnaround_id, replace_existing)

    def save_partial_turnaround(
        self,
        character: str,
        phase: str,
        parent_turnaround_id: str,
        label: str,
        crop_percent: float,
        detection_tolerance: float | None = None,
    ) -> TurnaroundRow:
        """Create or update a partial turnaround sheet under a full turnaround."""
        return self.turnaround_service.upsert_partial_sheet(
            character,
            phase,
            parent_turnaround_id,
            label,
            crop_percent,
            detection_tolerance,
        )

    def update_partial_turnaround(
        self,
        character: str,
        phase: str,
        partial_turnaround_id: str,
        label: str,
        crop_percent: float,
        detection_tolerance: float | None = None,
    ) -> TurnaroundRow:
        """Update and regenerate an existing partial turnaround sheet."""
        return self.turnaround_service.update_partial_sheet(
            character,
            phase,
            partial_turnaround_id,
            label,
            crop_percent,
            detection_tolerance,
        )

    def delete_partial_turnaround(self, character: str, phase: str, partial_turnaround_id: str) -> TurnaroundRow:
        """Delete an auxiliary partial turnaround sheet."""
        return self.turnaround_service.delete_partial_sheet(character, phase, partial_turnaround_id)

    def list_identity_keys(self, character: str, phase: str):
        """List saved identity keys for a character phase."""
        return self.identity_key_service.list_identity_keys(character, phase)

    def identity_key(self, character: str, phase: str, identity_key_id: str):
        """Return one saved identity key."""
        return self.identity_key_service.get_identity_key(character, phase, identity_key_id)

    def preview_identity_key(
        self,
        character: str,
        phase: str,
        source_asset_id: int,
        label: str,
        crop_percent: float,
        identity_key_id: str | None = None,
    ) -> IdentityKeyPreview:
        """Generate an identity key preview crop."""
        return self.identity_key_service.preview_identity_key(
            character,
            phase,
            source_asset_id,
            label,
            crop_percent,
            identity_key_id,
        )

    def save_identity_key(
        self,
        character: str,
        phase: str,
        source_asset_id: int,
        label: str,
        crop_percent: float,
        identity_key_id: str | None = None,
    ):
        """Save or update an identity key crop."""
        return self.identity_key_service.save_identity_key(
            character,
            phase,
            source_asset_id,
            label,
            crop_percent,
            identity_key_id,
        )

    def delete_identity_key(self, character: str, phase: str, identity_key_id: str):
        """Delete an identity key."""
        return self.identity_key_service.delete_identity_key(character, phase, identity_key_id)

    def list_costumes(self, character: str, phase: str):
        """List costume templates for a character phase."""
        return self.costume_service.list_costumes(character, phase)

    def create_costume(self, character: str, phase: str, costume_name: str, markdown: str) -> CostumeCreateResult:
        """Create a costume template and its Costume-Dressing assets."""
        return self.costume_service.create_costume(character, phase, costume_name, markdown)

    def update_costume(self, character: str, phase: str, costume_slug: str, costume_name: str) -> CostumeUpdateResult:
        """Update a costume template and its Costume-Dressing assets."""
        return self.costume_service.update_costume(character, phase, costume_slug, costume_name)

    def list_expression_assets(self, character: str, phase: str):
        """List Expression assets for a character phase."""
        return self.expression_service.list_expression_assets(character, phase)

    def list_expression_definitions(self, character: str, phase: str):
        """List expression definitions for a character phase."""
        return self.expression_service.list_expression_definitions(character, phase)

    def create_expression(
        self,
        character: str,
        phase: str,
        label: str,
        identity_key_id: str,
        markdown: str,
    ) -> ExpressionCreateResult:
        """Create an expression definition and its Expression asset."""
        return self.expression_service.create_expression(character, phase, label, identity_key_id, markdown)

    def update_expression(
        self,
        character: str,
        phase: str,
        asset_id: int,
        label: str,
        identity_key_id: str,
        regenerate: bool = False,
    ) -> ExpressionUpdateResult:
        """Update an expression definition and optionally reset it for regeneration."""
        result = self.expression_service.update_expression(character, phase, asset_id, label, identity_key_id)
        if regenerate:
            regenerated = self.asset_service.regenerate(character, phase, asset_id)
            return ExpressionUpdateResult(expression=result.expression, asset=regenerated)
        return result
