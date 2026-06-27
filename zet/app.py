from pathlib import Path

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.services.config_service import ConfigService
from zet.services.path_service import PathService


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

    def move_next(self) -> None:
        raise NotImplementedError("Milestone 3+ only: move_next is not implemented yet")

    def regenerate(self) -> None:
        raise NotImplementedError("Milestone 3+ only: regenerate is not implemented yet")

    def retry_ai(self) -> None:
        raise NotImplementedError("Milestone 3+ only: retry_ai is not implemented yet")

    def promote_to_locked(self) -> None:
        raise NotImplementedError("Milestone 3+ only: promote_to_locked is not implemented yet")


class ZetApp:
    def __init__(self, config, asset_repository: AssetRepository, path_service: PathService):
        self.config = config
        self.asset_repository = asset_repository
        self.path_service = path_service

    @classmethod
    def from_config(cls, config_path: str | Path) -> "ZetApp":
        config = ConfigService.load(config_path)
        path_service = PathService(config)
        asset_repository = AssetRepository(path_service)
        return cls(config, asset_repository, path_service)

    def list_assets(self, character: str, phase: str) -> list[Asset]:
        return self.asset_repository.list_assets(character, phase)

    def asset(self, character: str, phase: str, asset_id: int) -> AssetRef:
        return AssetRef(self, character, phase, asset_id)

