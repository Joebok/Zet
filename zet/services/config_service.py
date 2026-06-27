from dataclasses import dataclass
from pathlib import Path
import tomllib


class ConfigServiceError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    base_character_path: str
    base_asset_path: str
    base_pipeline_path: str
    base_ai_queue_path: str


class ConfigService:
    @staticmethod
    def load(config_path: str | Path) -> Config:
        path = Path(config_path)
        if not path.exists():
            raise ConfigServiceError(f"Config file not found: {path}")
        try:
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigServiceError(f"Config file is invalid TOML at {path}: {exc}") from exc
        try:
            base_folders = payload["BaseFolders"]
            return Config(
                base_character_path=base_folders["BaseCharacterPath"],
                base_asset_path=base_folders["BaseAssetPath"],
                base_pipeline_path=base_folders["BasePipelinePath"],
                base_ai_queue_path=base_folders["BaseAIQueuePath"],
            )
        except Exception as exc:
            raise ConfigServiceError(f"Config file is missing required BaseFolders entries: {path}") from exc

