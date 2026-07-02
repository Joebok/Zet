from pathlib import Path
from datetime import datetime

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.asset_service import AssetService, BatchRenderResetResult
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.ai_proxy_service import AIProxyService
from zet.services.ai_answer_harvester import AIAnswerHarvester
from zet.services.config_service import ConfigService
from zet.services.housekeeping_service import HousekeepingService
from zet.services.path_service import PathService
from zet.services.process_service import ProcessService
from zet.services.pipeline_control_service import AutomationSettings, PipelineControlService, PipelineControlSnapshot
from zet.services.prompt_review_service import PromptReviewContext, PromptReviewService
from zet.services.reference_service import ReferenceService
from zet.services.state_machine import StateMachine
from zet.services.worker_service import WorkerService


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

    def approve_prompt_review(self) -> Asset:
        return self._app.prompt_review_service.approve(self._character, self._phase, self._asset_id)

    def fail_prompt_review(self, reason: str = "") -> Asset:
        return self._app.prompt_review_service.fail(self._character, self._phase, self._asset_id, reason)

    def prompt_review_context(self) -> PromptReviewContext:
        return self._app.prompt_review_service.get_context(self._character, self._phase, self._asset_id)

    def generate_local_test_render(self):
        return self._app.prompt_review_service.generate_local_test_render(self._character, self._phase, self._asset_id)

    def run_housekeeping(self) -> Path:
        return self._app.asset_service.run_housekeeping(self._character, self._phase, self._asset_id)

    def regenerate(self) -> Asset:
        return self._app.asset_service.regenerate(self._character, self._phase, self._asset_id)

    def retry_ai(self) -> Asset:
        return self._app.asset_service.retry_ai(self._character, self._phase, self._asset_id)

    def promote_to_locked(self) -> Asset:
        return self._app.asset_service.promote_to_locked(self._character, self._phase, self._asset_id)

    def fail_render_review_to_render(self, reason: str = "") -> Asset:
        return self._app.asset_service.fail_render_review_to_render(
            self._character,
            self._phase,
            self._asset_id,
            reason,
        )

    def run_current_worker(self) -> Asset:
        return self._app.asset_service.run_current_worker(self._character, self._phase, self._asset_id)

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
        config_path: str | Path = "config.toml",
    ):
        self.config = config
        self.config_path = Path(config_path)
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.asset_service = asset_service
        self.prompt_review_service = prompt_review_service
        self.reference_service = reference_service
        self.housekeeping_service = housekeeping_service
        self.path_service = path_service
        self.process_service = ProcessService(Path(__file__).resolve().parents[1])
        self.pipeline_control_service = PipelineControlService(
            self.config_path,
            config,
            asset_repository,
            pipeline_repository,
        )

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ZetApp":
        config = ConfigService.load(config_path)
        path_service = PathService(config)
        asset_repository = AssetRepository(path_service)
        pipeline_repository = PipelineRepository(path_service)
        state_machine = StateMachine()
        housekeeping_service = HousekeepingService(path_service)
        worker_service = WorkerService(asset_repository, pipeline_repository, path_service)
        ai_proxy_path_service = AIProxyPathService(config)
        ai_proxy_service = AIProxyService(
            asset_repository,
            pipeline_repository,
            path_service,
            ai_proxy_path_service,
            housekeeping_service,
        )
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
            worker_service,
            ai_proxy_service,
            ai_answer_harvester,
        )
        prompt_review_service = PromptReviewService(
            asset_repository,
            asset_service,
            path_service,
        )
        reference_service = ReferenceService(asset_repository, path_service)
        ai_proxy_service.prompt_review_service = prompt_review_service
        app = cls(
            config,
            asset_repository,
            pipeline_repository,
            asset_service,
            prompt_review_service,
            reference_service,
            housekeeping_service,
            path_service,
            config_path,
        )
        app.ai_proxy_service = ai_proxy_service
        return app

    def list_assets(self, character: str, phase: str) -> list[Asset]:
        return self.asset_repository.list_assets(character, phase)

    def asset(self, character: str, phase: str, asset_id: int) -> AssetRef:
        return AssetRef(self, character, phase, asset_id)

    def prompt_review_context(self, character: str, phase: str, asset_id: int) -> PromptReviewContext:
        return self.prompt_review_service.get_context(character, phase, asset_id)

    def approve_prompt_review(self, character: str, phase: str, asset_id: int) -> Asset:
        return self.prompt_review_service.approve(character, phase, asset_id)

    def fail_prompt_review(self, character: str, phase: str, asset_id: int, reason: str = "") -> Asset:
        return self.prompt_review_service.fail(character, phase, asset_id, reason)

    def generate_local_test_render(self, character: str, phase: str, asset_id: int):
        return self.prompt_review_service.generate_local_test_render(character, phase, asset_id)

    def harvest_ai_answers(self):
        return self.asset_service.harvest_ai_answers()

    def run_available_workers(self, character: str, phase: str):
        return self.asset_service.run_available_workers(character, phase)

    def reset_pipeline_assets_to_render(
        self,
        character: str,
        phase: str,
        pipeline_name: str,
        include_locked: bool = False,
    ) -> list[BatchRenderResetResult]:
        return self.asset_service.reset_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)

    def fail_render_review_to_render(self, character: str, phase: str, asset_id: int, reason: str = "") -> Asset:
        return self.asset_service.fail_render_review_to_render(character, phase, asset_id, reason)

    def issue_monitor_test(self, instruction: str = ""):
        return self.ai_proxy_service.issue_monitor_test(instruction)

    def activate_proxy_stop(self):
        return self.ai_proxy_service.activate_stop()

    def resume_proxy_stop(self):
        return self.ai_proxy_service.resume_stop()

    def proxy_stop_state(self):
        return self.ai_proxy_service.stop_state()

    def queue_snapshot(self):
        return self.ai_proxy_service.queue_snapshot()

    def list_monitor_responses(self):
        return self.ai_proxy_service.list_monitor_responses()

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

    def head_fitment_reference_context(self, character: str, phase: str, asset_id: int):
        return self.reference_service.head_fitment_context(character, phase, asset_id)

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

    def upload_headshot_reference(self, character: str, phase: str, filename: str, contents: bytes) -> Path:
        return self.reference_service.upload_headshot(character, phase, filename, contents)
