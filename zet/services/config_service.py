from dataclasses import dataclass
import os
import platform
from pathlib import Path
import tomllib
from zet.services.local_render_policy import configured_qwen_profile, configured_qwen_checkpoint, SCENE_PROFILE
from zet.services.task_service import TaskServiceError, validate_kanban_settings


class ConfigServiceError(Exception):
    pass


@dataclass(frozen=True)
class SceneCandidateSourceConfig:
    key: str
    label: str
    path: str
    default_story_slug: str = ""
    read_only: bool = True


@dataclass(frozen=True)
class Config:
    base_library_path: str
    base_character_path: str
    base_asset_path: str
    base_pipeline_path: str
    base_ai_queue_path: str
    prompt_condense_enabled: bool = False
    prompt_condense_model: str = "general:latest"
    prompt_condense_file: str = "Config/Prompt_Condense_Tasks/body_reference_condense.md"
    ai_asset_workflow_model: str = "general:latest"
    codex_default_model: str = "gpt-6-luna"
    ai_scene_builder_model: str = "general:latest"
    ai_narrative_scene_model: str = "general:latest"
    local_body_reference_face_gate_model: str = "image-analysis-alt:latest"
    local_body_reference_review_model: str = "image-analysis:latest"
    local_render_auto_queue_after_condense: bool = False
    local_render_backend: str = "comfyui"
    local_render_preset: str = SCENE_PROFILE
    local_render_positive_prompt_globals: str = ""
    local_render_negative_prompt_globals: str = ""
    local_render_layout_backend: str = "forge_couple_basic"
    local_render_checkpoint: str = ""
    local_render_strict_primary_subject_count: bool = True
    local_render_forge_couple_debug_base_pass: bool = True
    comfyui_profile: str = SCENE_PROFILE
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
    ai_harvest_archive_path: str = ""
    ai_queue_debug: bool = False
    ai_queue_debug_retention_days: int = 7
    ai_queue_debug_max_bytes: int = 1073741824
    render_backend: str = "local_image"
    ai_prompt_analysis_model: str = "general:latest"
    ai_image_description_model: str = "image-analysis:latest"
    ai_image_prompt_generation_model: str = "image-analysis:latest"
    ai_costume_wizard_model: str = "codex:gpt-6-luna"
    ai_quick_character_wizard_model: str = "codex:gpt-6-luna"
    ai_prompt_analysis_instructions_file: str = "Config/AI_Prompt_Analysis_Instructions.md"
    ai_prompt_analysis_auto_queue_on_render: bool = False
    scene_candidate_sources: tuple[SceneCandidateSourceConfig, ...] = ()
    universe_id: str = "Moonsea"
    universe_is_legacy: bool = True
    library_container_path: str = ""
    kanban_base_url: str = "http://127.0.0.1:8000"
    kanban_project_id: str = ""
    kanban_timeout_seconds: float = 5.0


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
    def _scene_candidate_sources(payload: dict) -> tuple[SceneCandidateSourceConfig, ...]:
        records = payload.get("SceneCandidateSources", [])
        if not isinstance(records, list):
            raise ConfigServiceError("SceneCandidateSources must be an array of tables.")
        sources = []
        for record in records:
            if not isinstance(record, dict):
                continue
            key = str(record.get("Key") or "").strip()
            label = str(record.get("Label") or key).strip()
            path = ConfigService._normalize_path_value(record.get("Path") or "")
            if not key or not path:
                raise ConfigServiceError("Each scene candidate source requires Key and Path.")
            sources.append(SceneCandidateSourceConfig(
                key=key,
                label=label,
                path=path,
                default_story_slug=str(record.get("DefaultStorySlug") or "").strip(),
                read_only=bool(record.get("ReadOnly", True)),
            ))
        if len({source.key for source in sources}) != len(sources):
            raise ConfigServiceError("Scene candidate source keys must be unique.")
        return tuple(sources)

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
            kanban = payload.get("Kanban", {})
            if not isinstance(kanban, dict) or set(kanban) - {"BaseURL", "ProjectID", "TimeoutSeconds"}:
                raise ConfigServiceError("Kanban settings must be a table containing BaseURL, ProjectID, and TimeoutSeconds only.")
            try:
                kanban_url, kanban_project, kanban_timeout = validate_kanban_settings(
                    kanban.get("BaseURL", "http://127.0.0.1:8000"), kanban.get("ProjectID", ""), kanban.get("TimeoutSeconds", 5.0),
                )
            except TaskServiceError as exc:
                raise ConfigServiceError(str(exc)) from exc
            base_folders = ConfigService._base_folders_for_platform(payload)
            prompt_condense = ConfigService._prompt_condense_config(payload)
            ai_models = ConfigService._ai_models_config(payload)
            local_render = ConfigService._local_render_config(payload)
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
                    ai_models.get("PromptCondense", prompt_condense.get("Model", "general:latest"))
                ),
                prompt_condense_file=str(
                    prompt_condense.get("PromptFile", "Config/Prompt_Condense_Tasks/body_reference_condense.md")
                ),
                ai_asset_workflow_model=str(ai_models.get("AssetWorkflow", "general:latest")),
                codex_default_model=str(ai_models.get("CodexDefault", "gpt-6-luna")),
                ai_scene_builder_model=str(ai_models.get("SceneBuilder", "general:latest")),
                ai_narrative_scene_model=str(ai_models.get("NarrativeScene", "general:latest")),
                local_body_reference_face_gate_model=str(
                    ai_models.get("LocalBodyReferenceFaceGate", "image-analysis-alt:latest")
                ),
                local_body_reference_review_model=str(
                    ai_models.get("LocalBodyReferenceReview", "image-analysis:latest")
                ),
                local_render_auto_queue_after_condense=bool(local_render.get("AutoQueueAfterCondense", False)),
                local_render_backend="comfyui",
                local_render_preset=configured_qwen_profile(str(comfyui.get("Profile", SCENE_PROFILE))),
                comfyui_profile=configured_qwen_profile(str(comfyui.get("Profile", SCENE_PROFILE))),
                comfyui_server_url=str(comfyui.get("ServerURL", "http://127.0.0.1:8188")),
                comfyui_checkpoint=configured_qwen_checkpoint(str(comfyui.get("Checkpoint", ""))),
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
                ai_harvest_archive_path=ConfigService._normalize_path_value(
                    ai_harvest.get("ArchivePath", "Zet_File_Proxy_State/Archive/Harvested")
                ),
                ai_queue_debug=bool(ai_harvest.get("Debug", False)) or os.environ.get("ZET_AI_QUEUE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"},
                ai_queue_debug_retention_days=max(1, int(ai_harvest.get("DebugRetentionDays", 7))),
                ai_queue_debug_max_bytes=max(1, int(ai_harvest.get("DebugMaxBytes", 1073741824))),
                render_backend=str(render.get("Backend", "local_image")),
                ai_prompt_analysis_model=str(
                    ai_models.get(
                        "PromptAnalysis", ai_prompt_analysis.get("Model", "general:latest")
                    )
                ),
                ai_image_description_model=str(ai_models.get("ImageDescription", "image-analysis:latest")),
                ai_image_prompt_generation_model=str(ai_models.get("ImagePromptGeneration", "image-analysis:latest")),
                ai_costume_wizard_model=str(ai_models.get("CostumeWizard", "codex:gpt-6-luna")),
                ai_quick_character_wizard_model=str(ai_models.get("QuickCharacterWizard", "codex:gpt-6-luna")),
                ai_prompt_analysis_instructions_file=str(
                    ai_prompt_analysis.get("InstructionsFile", "Config/AI_Prompt_Analysis_Instructions.md")
                ),
                ai_prompt_analysis_auto_queue_on_render=bool(ai_prompt_analysis.get("AutoQueueOnRender", False)),
                scene_candidate_sources=ConfigService._scene_candidate_sources(payload),
                kanban_base_url=kanban_url,
                kanban_project_id=kanban_project,
                kanban_timeout_seconds=kanban_timeout,
            )
        except ConfigServiceError:
            raise
        except Exception as exc:
            raise ConfigServiceError(f"Config file is missing required BaseFolders entries: {path}") from exc

