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
    prompt_condense_enabled: bool = False
    prompt_condense_model: str = "llama3.2-vision:11b"
    prompt_condense_file: str = "Config/Prompt_Condense_Tasks/body_reference_condense.md"
    local_render_auto_queue_after_condense: bool = False
    local_render_preset: str = "body-reference-preview"
    ai_harvest_auto_enabled: bool = True
    ai_harvest_interval_seconds: int = 300
    render_backend: str = "local_image"
    ai_prompt_review_model: str = "qwen3.5:9b-instruct"
    ai_prompt_review_instructions_file: str = "Config/AI_Prompt_Review_Instructions.md"


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
    def _prompt_condense_config(payload: dict) -> dict:
        prompt_condense = payload.get("PromptCondense", {})
        return prompt_condense if isinstance(prompt_condense, dict) else {}

    @staticmethod
    def _local_render_config(payload: dict) -> dict:
        local_render = payload.get("LocalRender", {})
        return local_render if isinstance(local_render, dict) else {}

    @staticmethod
    def _ai_harvest_config(payload: dict) -> dict:
        ai_harvest = payload.get("AIHarvest", {})
        return ai_harvest if isinstance(ai_harvest, dict) else {}

    @staticmethod
    def _render_config(payload: dict) -> dict:
        render = payload.get("Render", {})
        return render if isinstance(render, dict) else {}

    @staticmethod
    def _ai_prompt_review_config(payload: dict) -> dict:
        review = payload.get("AIPromptReview", {})
        return review if isinstance(review, dict) else {}

    @staticmethod
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
            prompt_condense = ConfigService._prompt_condense_config(payload)
            local_render = ConfigService._local_render_config(payload)
            ai_harvest = ConfigService._ai_harvest_config(payload)
            render = ConfigService._render_config(payload)
            ai_prompt_review = ConfigService._ai_prompt_review_config(payload)
            return Config(
                base_character_path=ConfigService._normalize_path_value(base_folders["BaseCharacterPath"]),
                base_asset_path=ConfigService._normalize_path_value(base_folders["BaseAssetPath"]),
                base_pipeline_path=ConfigService._normalize_path_value(base_folders["BasePipelinePath"]),
                base_ai_queue_path=ConfigService._normalize_path_value(base_folders["BaseAIQueuePath"]),
                prompt_condense_enabled=bool(prompt_condense.get("Enabled", False)),
                prompt_condense_model=str(prompt_condense.get("Model", "llama3.2-vision:11b")),
                prompt_condense_file=str(
                    prompt_condense.get("PromptFile", "Config/Prompt_Condense_Tasks/body_reference_condense.md")
                ),
                local_render_auto_queue_after_condense=bool(local_render.get("AutoQueueAfterCondense", False)),
                local_render_preset=str(local_render.get("Preset", "body-reference-preview")),
                ai_harvest_auto_enabled=bool(ai_harvest.get("AutoEnabled", True)),
                ai_harvest_interval_seconds=int(ai_harvest.get("IntervalSeconds", 300)),
                render_backend=str(render.get("Backend", "local_image")),
                ai_prompt_review_model=str(ai_prompt_review.get("Model", "qwen3.5:9b-instruct")),
                ai_prompt_review_instructions_file=str(
                    ai_prompt_review.get("InstructionsFile", "Config/AI_Prompt_Review_Instructions.md")
                ),
            )
        except Exception as exc:
            raise ConfigServiceError(f"Config file is missing required BaseFolders entries: {path}") from exc

