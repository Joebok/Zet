from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re

from zet.repositories.asset_repository import AssetRepository, AssetRepositoryError
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.config_service import Config, ConfigService


class PipelineControlServiceError(Exception):
    pass


@dataclass(frozen=True)
class AutomationSettings:
    local_render_preset: str
    local_render_positive_prompt_globals: str
    local_render_negative_prompt_globals: str
    local_render_use_forge_couple: bool
    local_render_checkpoint: str
    ai_harvest_auto_enabled: bool
    ai_harvest_interval_seconds: int
    render_backend: str
    head_fitment_render_mode: str = "prompt"
    head_fitment_masked_local_preset: str = "head-fitment-inpaint"
    head_fitment_masked_local_checkpoint: str = ""
    head_fitment_mask_feather_pixels: int = 6
    local_render_backend: str = "stable_matrix"
    stable_matrix_profile: str = ""
    stable_matrix_positive_prompt_globals: str = ""
    stable_matrix_negative_prompt_globals: str = ""
    stable_matrix_use_forge_couple: bool | None = None
    stable_matrix_checkpoint: str = ""
    comfyui_profile: str = "comfyui-core-preview"
    comfyui_server_url: str = "http://127.0.0.1:8188"
    comfyui_checkpoint: str = ""
    comfyui_positive_prompt_globals: str = ""
    comfyui_negative_prompt_globals: str = ""
    comfyui_poll_seconds: float = 1.0
    comfyui_timeout_seconds: float = 300.0
    ai_prompt_analysis_model: str = "qwen3.5:9b-instruct"
    ai_prompt_analysis_instructions_file: str = "Config/AI_Prompt_Analysis_Instructions.md"
    zine_print_scale: float = 0.978
    zine_page_margin: int = 4
    zine_width: int = 3300
    turnaround_width: int = 3960


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
    render_profiles: dict[str, list[str]]


class PipelineControlService:
    SAFE_RENDER_BACKENDS = {"local_image", "manual_chatgpt"}
    SAFE_LOCAL_RENDER_BACKENDS = {"stable_matrix", "comfyui"}

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
        try:
            assets = self.asset_repository.list_assets(character, phase)
        except AssetRepositoryError:
            assets = []
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
            render_profiles=self.render_profiles(),
        )

    def automation_settings(self) -> AutomationSettings:
        return AutomationSettings(
            local_render_preset=str(self.config.local_render_preset),
            local_render_positive_prompt_globals=str(self.config.local_render_positive_prompt_globals),
            local_render_negative_prompt_globals=str(self.config.local_render_negative_prompt_globals),
            local_render_use_forge_couple=str(self.config.local_render_layout_backend) == "forge_couple_basic",
            local_render_checkpoint=str(self.config.local_render_checkpoint),
            ai_harvest_auto_enabled=bool(self.config.ai_harvest_auto_enabled),
            ai_harvest_interval_seconds=int(self.config.ai_harvest_interval_seconds),
            render_backend=str(self.config.render_backend),
            head_fitment_render_mode=str(self.config.head_fitment_render_mode),
            head_fitment_masked_local_preset=str(self.config.head_fitment_masked_local_preset),
            head_fitment_masked_local_checkpoint=str(self.config.head_fitment_masked_local_checkpoint),
            head_fitment_mask_feather_pixels=int(self.config.head_fitment_mask_feather_pixels),
            local_render_backend=str(self.config.local_render_backend),
            stable_matrix_profile=str(self.config.local_render_preset),
            stable_matrix_positive_prompt_globals=str(self.config.local_render_positive_prompt_globals),
            stable_matrix_negative_prompt_globals=str(self.config.local_render_negative_prompt_globals),
            stable_matrix_use_forge_couple=str(self.config.local_render_layout_backend) == "forge_couple_basic",
            stable_matrix_checkpoint=str(self.config.local_render_checkpoint),
            comfyui_profile=str(self.config.comfyui_profile),
            comfyui_server_url=str(self.config.comfyui_server_url),
            comfyui_checkpoint=str(self.config.comfyui_checkpoint),
            comfyui_positive_prompt_globals=str(self.config.comfyui_positive_prompt_globals),
            comfyui_negative_prompt_globals=str(self.config.comfyui_negative_prompt_globals),
            comfyui_poll_seconds=float(self.config.comfyui_poll_seconds),
            comfyui_timeout_seconds=float(self.config.comfyui_timeout_seconds),
            ai_prompt_analysis_model=str(self.config.ai_prompt_analysis_model),
            ai_prompt_analysis_instructions_file=str(self.config.ai_prompt_analysis_instructions_file),
            zine_print_scale=float(self.config.zine_print_scale),
            zine_page_margin=int(self.config.zine_page_margin),
            zine_width=int(self.config.zine_width),
            turnaround_width=int(self.config.turnaround_width),
        )

    def render_profiles(self) -> dict[str, list[str]]:
        path = self.config_path.resolve().parent / "Config" / "Local_Render_Presets.json"
        try:
            profiles = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            profiles = {}
        result = {"stable_matrix": [], "comfyui": []}
        for name, profile in profiles.items() if isinstance(profiles, dict) else []:
            backend = str(profile.get("backend") or "") if isinstance(profile, dict) else ""
            if backend in result and profile.get("enabled", True):
                result[backend].append(str(name))
        return {backend: sorted(names) for backend, names in result.items()}

    def project_config_rows(self) -> list[dict]:
        return [
            {"Scope": "Project config", "Setting": "LocalRender.Backend", "Value": self.config.local_render_backend},
            {"Scope": "Project config", "Setting": "StableMatrix.Profile", "Value": self.config.local_render_preset},
            {
                "Scope": "Project config",
                "Setting": "StableMatrix.PositivePromptGlobals",
                "Value": self.config.local_render_positive_prompt_globals,
            },
            {
                "Scope": "Project config",
                "Setting": "StableMatrix.NegativePromptGlobals",
                "Value": self.config.local_render_negative_prompt_globals,
            },
            {"Scope": "Project config", "Setting": "StableMatrix.LayoutBackend", "Value": self.config.local_render_layout_backend},
            {"Scope": "Project config", "Setting": "StableMatrix.Checkpoint", "Value": self.config.local_render_checkpoint},
            {"Scope": "Project config", "Setting": "ComfyUI.Profile", "Value": self.config.comfyui_profile},
            {"Scope": "Project config", "Setting": "ComfyUI.ServerURL", "Value": self.config.comfyui_server_url},
            {"Scope": "Project config", "Setting": "ComfyUI.Checkpoint", "Value": self.config.comfyui_checkpoint},
            {"Scope": "Project config", "Setting": "Zine.PrintScale", "Value": self.config.zine_print_scale},
            {"Scope": "Project config", "Setting": "Zine.PageMargin", "Value": self.config.zine_page_margin},
            {"Scope": "Project config", "Setting": "Zine.Width", "Value": self.config.zine_width},
            {"Scope": "Project config", "Setting": "Turnaround.Width", "Value": self.config.turnaround_width},
            {"Scope": "Project config", "Setting": "AIHarvest.AutoEnabled", "Value": self.config.ai_harvest_auto_enabled},
            {"Scope": "Project config", "Setting": "AIHarvest.IntervalSeconds", "Value": self.config.ai_harvest_interval_seconds},
            {"Scope": "Project config", "Setting": "Render.Backend", "Value": self.config.render_backend},
            {"Scope": "Project config", "Setting": "HeadFitment.RenderMode", "Value": self.config.head_fitment_render_mode},
            {"Scope": "Project config", "Setting": "HeadFitment.MaskedLocalPreset", "Value": self.config.head_fitment_masked_local_preset},
            {"Scope": "Project config", "Setting": "HeadFitment.MaskedLocalCheckpoint", "Value": self.config.head_fitment_masked_local_checkpoint},
            {"Scope": "Project config", "Setting": "AIPromptAnalysis.Model", "Value": self.config.ai_prompt_analysis_model},
            {"Scope": "Project config", "Setting": "AIPromptAnalysis.InstructionsFile", "Value": self.config.ai_prompt_analysis_instructions_file},
        ]

    def save_automation_settings(self, settings: AutomationSettings) -> None:
        """Persist project-level automation settings."""
        self._validate_settings(settings)
        stable_profile = settings.stable_matrix_profile or settings.local_render_preset
        stable_positive = settings.stable_matrix_positive_prompt_globals or settings.local_render_positive_prompt_globals
        stable_negative = settings.stable_matrix_negative_prompt_globals or settings.local_render_negative_prompt_globals
        stable_checkpoint = settings.stable_matrix_checkpoint or settings.local_render_checkpoint
        stable_forge = (
            settings.local_render_use_forge_couple
            if settings.stable_matrix_use_forge_couple is None
            else settings.stable_matrix_use_forge_couple
        )
        updates = {
            ("LocalRender", "Backend"): settings.local_render_backend,
            ("StableMatrix", "Profile"): stable_profile,
            ("StableMatrix", "PositivePromptGlobals"): stable_positive,
            ("StableMatrix", "NegativePromptGlobals"): stable_negative,
            ("StableMatrix", "LayoutBackend"): "forge_couple_basic" if stable_forge else "plain_txt2img",
            ("StableMatrix", "Checkpoint"): stable_checkpoint,
            ("ComfyUI", "Profile"): settings.comfyui_profile,
            ("ComfyUI", "ServerURL"): settings.comfyui_server_url,
            ("ComfyUI", "Checkpoint"): settings.comfyui_checkpoint,
            ("ComfyUI", "PositivePromptGlobals"): settings.comfyui_positive_prompt_globals,
            ("ComfyUI", "NegativePromptGlobals"): settings.comfyui_negative_prompt_globals,
            ("ComfyUI", "PollSeconds"): settings.comfyui_poll_seconds,
            ("ComfyUI", "TimeoutSeconds"): settings.comfyui_timeout_seconds,
            ("Zine", "PrintScale"): settings.zine_print_scale,
            ("Zine", "PageMargin"): settings.zine_page_margin,
            ("Zine", "Width"): settings.zine_width,
            ("Turnaround", "Width"): settings.turnaround_width,
            ("AIHarvest", "AutoEnabled"): settings.ai_harvest_auto_enabled,
            ("AIHarvest", "IntervalSeconds"): settings.ai_harvest_interval_seconds,
            ("Render", "Backend"): settings.render_backend,
            ("HeadFitment", "RenderMode"): settings.head_fitment_render_mode,
            ("HeadFitment", "MaskedLocalPreset"): settings.head_fitment_masked_local_preset,
            ("HeadFitment", "MaskedLocalCheckpoint"): settings.head_fitment_masked_local_checkpoint,
            ("HeadFitment", "MaskFeatherPixels"): settings.head_fitment_mask_feather_pixels,
            ("AIPromptAnalysis", "Model"): settings.ai_prompt_analysis_model,
            ("AIPromptAnalysis", "InstructionsFile"): settings.ai_prompt_analysis_instructions_file,
        }
        self._update_config_values(updates)
        ConfigService.load(self.config_path)

    def _validate_settings(self, settings: AutomationSettings) -> None:
        render_backend = settings.render_backend.strip()
        if render_backend not in self.SAFE_RENDER_BACKENDS:
            choices = ", ".join(sorted(self.SAFE_RENDER_BACKENDS))
            raise PipelineControlServiceError(f"Render backend must be one of: {choices}.")
        if settings.head_fitment_render_mode not in {"prompt", "masked_local"}:
            raise PipelineControlServiceError("Head-Fitment render mode must be prompt or masked_local.")
        if not settings.head_fitment_masked_local_preset.strip():
            raise PipelineControlServiceError("Head-Fitment masked-local preset cannot be blank.")
        if settings.head_fitment_mask_feather_pixels < 0 or settings.head_fitment_mask_feather_pixels > 64:
            raise PipelineControlServiceError("Head-Fitment mask feather must be between 0 and 64 pixels.")
        local_backend = settings.local_render_backend.strip()
        if local_backend not in self.SAFE_LOCAL_RENDER_BACKENDS:
            choices = ", ".join(sorted(self.SAFE_LOCAL_RENDER_BACKENDS))
            raise PipelineControlServiceError(f"Local render backend must be one of: {choices}.")
        if not (settings.stable_matrix_profile or settings.local_render_preset).strip():
            raise PipelineControlServiceError("Stable Matrix profile cannot be blank.")
        if not settings.comfyui_profile.strip():
            raise PipelineControlServiceError("ComfyUI profile cannot be blank.")
        if not settings.comfyui_server_url.strip():
            raise PipelineControlServiceError("ComfyUI server URL cannot be blank.")
        if settings.comfyui_poll_seconds < 0 or settings.comfyui_timeout_seconds <= 0:
            raise PipelineControlServiceError("ComfyUI polling must be non-negative and timeout must be positive.")
        if settings.ai_harvest_interval_seconds < 0:
            raise PipelineControlServiceError("Auto harvest interval cannot be negative.")
        if settings.ai_harvest_interval_seconds > 86400:
            raise PipelineControlServiceError("Auto harvest interval must be 86400 seconds or less.")
        if settings.zine_print_scale <= 0 or settings.zine_print_scale > 1:
            raise PipelineControlServiceError("Zine print scale must be greater than 0 and no greater than 1.")
        if settings.zine_width <= 0 or settings.zine_width % 44:
            raise PipelineControlServiceError("Zine width must be a positive multiple of 44 pixels.")
        if settings.turnaround_width <= 0 or settings.turnaround_width % 44:
            raise PipelineControlServiceError("Turnaround width must be a positive multiple of 44 pixels.")
        max_page_margin = (settings.zine_width // 4 - 1) // 2
        if settings.zine_page_margin < 0 or settings.zine_page_margin > max_page_margin:
            raise PipelineControlServiceError(
                f"Zine page margin must be between 0 and {max_page_margin} pixels."
            )
        if not settings.ai_prompt_analysis_model.strip():
            raise PipelineControlServiceError("AI prompt analysis model cannot be blank.")
        if not settings.ai_prompt_analysis_instructions_file.strip():
            raise PipelineControlServiceError("AI prompt analysis instructions file cannot be blank.")

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
            new_body = key_pattern.sub(lambda match: f"{match.group(1)}{rendered_value}", section_body, count=1)
        else:
            body_suffix = "" if section_body.endswith("\n") or not section_body else "\n"
            new_body = f"{section_body}{body_suffix}{key} = {rendered_value}\n"
        return text[: match.start(2)] + new_body + text[match.end(2) :]

    def _render_toml_value(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(value)
        return json.dumps(str(value))
