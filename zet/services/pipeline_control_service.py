from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re

from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.config_service import Config, ConfigService


class PipelineControlServiceError(Exception):
    pass


@dataclass(frozen=True)
class AutomationSettings:
    prompt_condense_enabled: bool
    prompt_condense_model: str
    prompt_condense_file: str
    local_render_auto_queue_after_condense: bool
    local_render_preset: str
    ai_harvest_auto_enabled: bool
    ai_harvest_interval_seconds: int
    render_backend: str


@dataclass(frozen=True)
class PipelineStageControlRow:
    pipeline: str
    step: int
    stage: str
    actor: str
    worker: str
    asset_count: int


@dataclass(frozen=True)
class PipelineControlSnapshot:
    config_path: Path
    pipelines_path: Path
    automation: AutomationSettings
    pipeline_rows: list[PipelineStageControlRow]
    project_config_rows: list[dict]


class PipelineControlService:
    SAFE_RENDER_BACKENDS = {"local_image", "manual_chatgpt"}

    def __init__(
        self,
        config_path: str | Path,
        config: Config,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
    ):
        self.config_path = Path(config_path)
        self.config = config
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository

    def snapshot(self, character: str, phase: str) -> PipelineControlSnapshot:
        pipelines = self.pipeline_repository.list_pipelines(character, phase)
        assets = self.asset_repository.list_assets(character, phase)
        asset_counts: dict[tuple[str, str], int] = {}
        for asset in assets:
            key = (asset.pipeline, asset.pipeline_stage)
            asset_counts[key] = asset_counts.get(key, 0) + 1

        pipeline_rows: list[PipelineStageControlRow] = []
        for pipeline in pipelines:
            for index, stage in enumerate(pipeline.stages, start=1):
                pipeline_rows.append(
                    PipelineStageControlRow(
                        pipeline=pipeline.name,
                        step=index,
                        stage=stage,
                        actor=str(pipeline.actor_by_stage.get(stage) or ""),
                        worker=str(pipeline.worker_by_stage.get(stage) or ""),
                        asset_count=asset_counts.get((pipeline.name, stage), 0),
                    )
                )

        return PipelineControlSnapshot(
            config_path=self.config_path,
            pipelines_path=Path(self.config.base_character_path) / character / phase / "Pipelines.json",
            automation=self.automation_settings(),
            pipeline_rows=pipeline_rows,
            project_config_rows=self.project_config_rows(),
        )

    def automation_settings(self) -> AutomationSettings:
        return AutomationSettings(
            prompt_condense_enabled=bool(self.config.prompt_condense_enabled),
            prompt_condense_model=str(self.config.prompt_condense_model),
            prompt_condense_file=str(self.config.prompt_condense_file),
            local_render_auto_queue_after_condense=bool(self.config.local_render_auto_queue_after_condense),
            local_render_preset=str(self.config.local_render_preset),
            ai_harvest_auto_enabled=bool(self.config.ai_harvest_auto_enabled),
            ai_harvest_interval_seconds=int(self.config.ai_harvest_interval_seconds),
            render_backend=str(self.config.render_backend),
        )

    def project_config_rows(self) -> list[dict]:
        return [
            {"Scope": "Project config", "Setting": "PromptCondense.Enabled", "Value": self.config.prompt_condense_enabled},
            {"Scope": "Project config", "Setting": "PromptCondense.Model", "Value": self.config.prompt_condense_model},
            {"Scope": "Project config", "Setting": "PromptCondense.PromptFile", "Value": self.config.prompt_condense_file},
            {
                "Scope": "Project config",
                "Setting": "LocalRender.AutoQueueAfterCondense",
                "Value": self.config.local_render_auto_queue_after_condense,
            },
            {"Scope": "Project config", "Setting": "LocalRender.Preset", "Value": self.config.local_render_preset},
            {"Scope": "Project config", "Setting": "AIHarvest.AutoEnabled", "Value": self.config.ai_harvest_auto_enabled},
            {"Scope": "Project config", "Setting": "AIHarvest.IntervalSeconds", "Value": self.config.ai_harvest_interval_seconds},
            {"Scope": "Project config", "Setting": "Render.Backend", "Value": self.config.render_backend},
            {"Scope": "Project config", "Setting": "RenderConsole.Host", "Value": self.config.render_console_host},
            {"Scope": "Project config", "Setting": "RenderConsole.Port", "Value": self.config.render_console_port},
        ]

    def save_automation_settings(self, settings: AutomationSettings) -> None:
        self._validate_settings(settings)
        updates = {
            ("PromptCondense", "Enabled"): settings.prompt_condense_enabled,
            ("PromptCondense", "Model"): settings.prompt_condense_model,
            ("PromptCondense", "PromptFile"): settings.prompt_condense_file,
            ("LocalRender", "AutoQueueAfterCondense"): settings.local_render_auto_queue_after_condense,
            ("LocalRender", "Preset"): settings.local_render_preset,
            ("AIHarvest", "AutoEnabled"): settings.ai_harvest_auto_enabled,
            ("AIHarvest", "IntervalSeconds"): settings.ai_harvest_interval_seconds,
            ("Render", "Backend"): settings.render_backend,
        }
        self._update_config_values(updates)
        ConfigService.load(self.config_path)

    def _validate_settings(self, settings: AutomationSettings) -> None:
        render_backend = settings.render_backend.strip()
        if render_backend not in self.SAFE_RENDER_BACKENDS:
            choices = ", ".join(sorted(self.SAFE_RENDER_BACKENDS))
            raise PipelineControlServiceError(f"Render backend must be one of: {choices}.")
        if not settings.prompt_condense_model.strip():
            raise PipelineControlServiceError("Prompt condense model cannot be blank.")
        if not settings.prompt_condense_file.strip():
            raise PipelineControlServiceError("Prompt condense file cannot be blank.")
        if not settings.local_render_preset.strip():
            raise PipelineControlServiceError("Local render preset cannot be blank.")
        if settings.ai_harvest_interval_seconds < 0:
            raise PipelineControlServiceError("Auto harvest interval cannot be negative.")
        if settings.ai_harvest_interval_seconds > 86400:
            raise PipelineControlServiceError("Auto harvest interval must be 86400 seconds or less.")

    def _update_config_values(self, updates: dict[tuple[str, str], object]) -> None:
        if not self.config_path.exists():
            raise PipelineControlServiceError(f"Config file not found: {self.config_path}")
        original = self.config_path.read_text(encoding="utf-8")
        updated = original
        for (section, key), value in updates.items():
            updated = self._set_section_value(updated, section, key, value)

        if updated == original:
            return

        backup_path = self.config_path.with_name(
            f"{self.config_path.stem}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{self.config_path.suffix}"
        )
        temp_path = self.config_path.with_name(f"{self.config_path.name}.tmp")
        backup_path.write_text(original, encoding="utf-8")
        try:
            temp_path.write_text(updated, encoding="utf-8")
            ConfigService.load(temp_path)
            temp_path.replace(self.config_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _set_section_value(self, text: str, section: str, key: str, value: object) -> str:
        rendered_value = self._render_toml_value(value)
        section_pattern = re.compile(rf"(?ms)^(\[{re.escape(section)}\]\s*$)(.*?)(?=^\[|\Z)")
        match = section_pattern.search(text)
        if not match:
            suffix = "" if text.endswith("\n") else "\n"
            return f"{text}{suffix}\n[{section}]\n{key} = {rendered_value}\n"

        section_body = match.group(2)
        key_pattern = re.compile(rf"(?m)^({re.escape(key)}\s*=\s*).*$")
        if key_pattern.search(section_body):
            new_body = key_pattern.sub(rf"\g<1>{rendered_value}", section_body, count=1)
        else:
            body_suffix = "" if section_body.endswith("\n") or not section_body else "\n"
            new_body = f"{section_body}{body_suffix}{key} = {rendered_value}\n"
        return text[: match.start(2)] + new_body + text[match.end(2) :]

    def _render_toml_value(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        return json.dumps(str(value))
