from pathlib import Path

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.asset_service import AssetService
from zet.services.config_service import ConfigService
from zet.services.housekeeping_service import HousekeepingService
from zet.services.path_service import PathService
from zet.services.state_machine import StateMachine


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

    def run_housekeeping(self) -> Path:
        return self._app.asset_service.run_housekeeping(self._character, self._phase, self._asset_id)

    def regenerate(self) -> Asset:
        return self._app.asset_service.regenerate(self._character, self._phase, self._asset_id)

    def retry_ai(self) -> Asset:
        return self._app.asset_service.retry_ai(self._character, self._phase, self._asset_id)

    def promote_to_locked(self) -> Asset:
        return self._app.asset_service.promote_to_locked(self._character, self._phase, self._asset_id)


class ZetApp:
    def __init__(
        self,
        config,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        asset_service: AssetService,
        housekeeping_service: HousekeepingService,
        path_service: PathService,
    ):
        self.config = config
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.asset_service = asset_service
        self.housekeeping_service = housekeeping_service
        self.path_service = path_service

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ZetApp":
        config = ConfigService.load(config_path)
        path_service = PathService(config)
        asset_repository = AssetRepository(path_service)
        pipeline_repository = PipelineRepository(path_service)
        state_machine = StateMachine()
        housekeeping_service = HousekeepingService(path_service)
        asset_service = AssetService(
            asset_repository,
            pipeline_repository,
            state_machine,
            housekeeping_service,
            path_service,
        )
        return cls(
            config,
            asset_repository,
            pipeline_repository,
            asset_service,
            housekeeping_service,
            path_service,
        )

    def list_assets(self, character: str, phase: str) -> list[Asset]:
        return self.asset_repository.list_assets(character, phase)

    def asset(self, character: str, phase: str, asset_id: int) -> AssetRef:
        return AssetRef(self, character, phase, asset_id)
