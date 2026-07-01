from dataclasses import dataclass
import os
import platform
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
    def _platform_name() -> str:
        return platform.system() or "Unknown"

    @staticmethod
    def _normalize_path_value(value) -> str:
        text = str(value)
        return os.path.expandvars(os.path.expanduser(text))

    @staticmethod
    def _base_folders_for_platform(payload: dict) -> dict:
        base_folders = dict(payload["BaseFolders"])
        platform_overrides = payload.get("BaseFoldersByPlatform", {})
        if isinstance(platform_overrides, dict):
            current_platform = ConfigService._platform_name()
            override = platform_overrides.get(current_platform, {})
            if isinstance(override, dict):
                base_folders.update({key: value for key, value in override.items() if value is not None})
        return base_folders

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
            base_folders = ConfigService._base_folders_for_platform(payload)
            return Config(
                base_character_path=ConfigService._normalize_path_value(base_folders["BaseCharacterPath"]),
                base_asset_path=ConfigService._normalize_path_value(base_folders["BaseAssetPath"]),
                base_pipeline_path=ConfigService._normalize_path_value(base_folders["BasePipelinePath"]),
                base_ai_queue_path=ConfigService._normalize_path_value(base_folders["BaseAIQueuePath"]),
            )
        except Exception as exc:
            raise ConfigServiceError(f"Config file is missing required BaseFolders entries: {path}") from exc

