from dataclasses import dataclass
import os
import platform
from pathlib import Path
import tomllib


class ConfigServiceError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    base_library_path: str
    base_character_path: str
    base_asset_path: str
    base_pipeline_path: str
    base_ai_queue_path: str
    prompt_condense_enabled: bool = False
    prompt_condense_model: str = "structured-reasoning:latest"
    prompt_condense_file: str = "Config/Prompt_Condense_Tasks/body_reference_condense.md"
    ai_asset_workflow_model: str = "general-purpose:latest"
    ai_scene_builder_model: str = "structured-reasoning:latest"
    ai_prompt_evolution_critic_model_a: str = "vision-analysis:latest"
    ai_prompt_evolution_critic_model_b: str = "vision-analysis-alt:latest"
    ai_prompt_evolution_analysis_model: str = "vision-analysis:latest"
    ai_prompt_evolution_check_model: str = "vision-analysis-alt:latest"
    local_render_auto_queue_after_condense: bool = False
    local_render_backend: str = "stable_matrix"
    local_render_preset: str = "body-reference-preview"
    local_render_positive_prompt_globals: str = ""
    local_render_negative_prompt_globals: str = ""
    local_render_layout_backend: str = "forge_couple_basic"
    local_render_checkpoint: str = ""
    local_render_strict_primary_subject_count: bool = True
    local_render_forge_couple_debug_base_pass: bool = True
    comfyui_profile: str = "comfyui-core-preview"
    comfyui_server_url: str = "http://127.0.0.1:8188"
    comfyui_checkpoint: str = ""
    comfyui_positive_prompt_globals: str = ""
    comfyui_negative_prompt_globals: str = ""
    comfyui_poll_seconds: float = 1.0
    comfyui_timeout_seconds: float = 300.0
    zine_print_scale: float = 0.978
    zine_page_margin: int = 4
    zine_width: int = 3300
    turnaround_width: int = 3960
    ai_harvest_auto_enabled: bool = True
    ai_harvest_interval_seconds: int = 300
    render_backend: str = "local_image"
    ai_prompt_analysis_model: str = "structured-reasoning:latest"
    ai_prompt_analysis_instructions_file: str = "Config/AI_Prompt_Analysis_Instructions.md"


class ConfigService:
    @staticmethod
    def _platform_name() -> str:
        return platform.system() or "Unknown"

    @staticmethod
    def _normalize_path_value(value) -> str:
        text = str(value)
        return os.path.expandvars(os.path.expanduser(text))

    @staticmethod
    def _resolve_base_folder(base_path: str, value) -> str:
        """Resolve a base folder value against the configured library root when relative."""
        path_text = ConfigService._normalize_path_value(value)
        if not base_path:
            return path_text
        path = Path(path_text)
        if path.is_absolute():
            return str(path)
        return str(Path(base_path) / path)

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
    def _ai_models_config(payload: dict) -> dict:
        ai_models = payload.get("AIModels", {})
        return ai_models if isinstance(ai_models, dict) else {}

    @staticmethod
    def _local_render_config(payload: dict) -> dict:
        local_render = payload.get("LocalRender", {})
        return local_render if isinstance(local_render, dict) else {}

    @staticmethod
    def _stable_matrix_config(payload: dict) -> dict:
        stable_matrix = payload.get("StableMatrix", {})
        return stable_matrix if isinstance(stable_matrix, dict) else {}

    @staticmethod
    def _comfyui_config(payload: dict) -> dict:
        comfyui = payload.get("ComfyUI", {})
        return comfyui if isinstance(comfyui, dict) else {}

    @staticmethod
    def _ai_harvest_config(payload: dict) -> dict:
        ai_harvest = payload.get("AIHarvest", {})
        return ai_harvest if isinstance(ai_harvest, dict) else {}

    @staticmethod
    def _zine_config(payload: dict) -> dict:
        zine = payload.get("Zine", {})
        return zine if isinstance(zine, dict) else {}

    @staticmethod
    def _render_config(payload: dict) -> dict:
        render = payload.get("Render", {})
        return render if isinstance(render, dict) else {}

    @staticmethod
    def _turnaround_config(payload: dict) -> dict:
        turnaround = payload.get("Turnaround", {})
        return turnaround if isinstance(turnaround, dict) else {}

    @staticmethod
    def _ai_prompt_analysis_config(payload: dict) -> dict:
        analysis = payload.get("AIPromptAnalysis", {})
        return analysis if isinstance(analysis, dict) else {}

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
            ai_models = ConfigService._ai_models_config(payload)
            local_render = ConfigService._local_render_config(payload)
            stable_matrix = ConfigService._stable_matrix_config(payload)
            comfyui = ConfigService._comfyui_config(payload)
            zine = ConfigService._zine_config(payload)
            turnaround = ConfigService._turnaround_config(payload)
            ai_harvest = ConfigService._ai_harvest_config(payload)
            render = ConfigService._render_config(payload)
            ai_prompt_analysis = ConfigService._ai_prompt_analysis_config(payload)
            library_base = ConfigService._normalize_path_value(base_folders.get("BaseLibraryPath", ""))
            return Config(
                base_library_path=library_base,
                base_character_path=ConfigService._resolve_base_folder(library_base, base_folders["BaseCharacterPath"]),
                base_asset_path=ConfigService._resolve_base_folder(library_base, base_folders["BaseAssetPath"]),
                base_pipeline_path=ConfigService._resolve_base_folder(library_base, base_folders["BasePipelinePath"]),
                base_ai_queue_path=ConfigService._normalize_path_value(base_folders["BaseAIQueuePath"]),
                prompt_condense_enabled=bool(prompt_condense.get("Enabled", False)),
                prompt_condense_model=str(
                    ai_models.get("PromptCondense", prompt_condense.get("Model", "structured-reasoning:latest"))
                ),
                prompt_condense_file=str(
                    prompt_condense.get("PromptFile", "Config/Prompt_Condense_Tasks/body_reference_condense.md")
                ),
                ai_asset_workflow_model=str(ai_models.get("AssetWorkflow", "general-purpose:latest")),
                ai_scene_builder_model=str(ai_models.get("SceneBuilder", "structured-reasoning:latest")),
                ai_prompt_evolution_critic_model_a=str(
                    ai_models.get("PromptEvolutionCriticA", "vision-analysis:latest")
                ),
                ai_prompt_evolution_critic_model_b=str(
                    ai_models.get("PromptEvolutionCriticB", "vision-analysis-alt:latest")
                ),
                ai_prompt_evolution_analysis_model=str(
                    ai_models.get("PromptEvolutionAnalysis", "vision-analysis:latest")
                ),
                ai_prompt_evolution_check_model=str(
                    ai_models.get("PromptEvolutionCheck", "vision-analysis-alt:latest")
                ),
                local_render_auto_queue_after_condense=bool(local_render.get("AutoQueueAfterCondense", False)),
                local_render_backend=str(local_render.get("Backend", "stable_matrix")).strip().lower(),
                local_render_preset=str(stable_matrix.get("Profile", local_render.get("Preset", "body-reference-preview"))),
                local_render_positive_prompt_globals=str(
                    stable_matrix.get("PositivePromptGlobals", local_render.get("PositivePromptGlobals", ""))
                ),
                local_render_negative_prompt_globals=str(
                    stable_matrix.get("NegativePromptGlobals", local_render.get("NegativePromptGlobals", ""))
                ),
                local_render_layout_backend=str(
                    stable_matrix.get("LayoutBackend", local_render.get("LayoutBackend", "forge_couple_basic"))
                ),
                local_render_checkpoint=str(stable_matrix.get("Checkpoint", local_render.get("Checkpoint", ""))),
                local_render_strict_primary_subject_count=bool(
                    stable_matrix.get("StrictPrimarySubjectCount", local_render.get("StrictPrimarySubjectCount", True))
                ),
                local_render_forge_couple_debug_base_pass=bool(
                    stable_matrix.get("ForgeCoupleDebugBasePass", local_render.get("ForgeCoupleDebugBasePass", True))
                ),
                comfyui_profile=str(comfyui.get("Profile", "comfyui-core-preview")),
                comfyui_server_url=str(comfyui.get("ServerURL", "http://127.0.0.1:8188")),
                comfyui_checkpoint=str(comfyui.get("Checkpoint", "")),
                comfyui_positive_prompt_globals=str(comfyui.get("PositivePromptGlobals", "")),
                comfyui_negative_prompt_globals=str(comfyui.get("NegativePromptGlobals", "")),
                comfyui_poll_seconds=float(comfyui.get("PollSeconds", 1.0)),
                comfyui_timeout_seconds=float(comfyui.get("TimeoutSeconds", 300.0)),
                zine_print_scale=float(zine.get("PrintScale", 0.978)),
                zine_page_margin=int(zine.get("PageMargin", 4)),
                zine_width=int(zine.get("Width", 3300)),
                turnaround_width=int(turnaround.get("Width", 3960)),
                ai_harvest_auto_enabled=bool(ai_harvest.get("AutoEnabled", True)),
                ai_harvest_interval_seconds=int(ai_harvest.get("IntervalSeconds", 300)),
                render_backend=str(render.get("Backend", "local_image")),
                ai_prompt_analysis_model=str(
                    ai_models.get(
                        "PromptAnalysis", ai_prompt_analysis.get("Model", "structured-reasoning:latest")
                    )
                ),
                ai_prompt_analysis_instructions_file=str(
                    ai_prompt_analysis.get("InstructionsFile", "Config/AI_Prompt_Analysis_Instructions.md")
                ),
            )
        except Exception as exc:
            raise ConfigServiceError(f"Config file is missing required BaseFolders entries: {path}") from exc

