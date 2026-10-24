from dataclasses import dataclass, field
import os
import platform
from pathlib import Path
import tomllib
from zet.services.local_render_policy import configured_qwen_profile, configured_qwen_checkpoint, SCENE_PROFILE
from zet.services.task_report_service import validate_repository
from zet.services.github_client import TaskServiceError
from zet.services.runtime_state_service import state_file


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
    llm_role_models: dict[str, str] = field(default_factory=dict)
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
    ai_harvest_interval_seconds: int = 2
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
    github_repository: str = ""
    github_timeout_seconds: float = 20.0
    task_state_path: str = ""
    runtime_state_path: str = ""
    runtime_root: str = ""
    runtime_role: str = "local"
    codex_usage_reserve_percent: float = 10.0
    codex_trusted_users: tuple[str, ...] = ("Joebok",)
    storage_root: str = ""
    storage_indexes_path: str = "Indexes"
    storage_queue_state_path: str = "AI_Queue"
    storage_migration_state_path: str = "LibraryReferenceUpdates"
    storage_workflow_state_path: str = "TaskWorkflow"
    storage_completed_retention_days: int = 7
    storage_maintenance_interval_hours: int = 24

    def state_file(self, project_root, filename: str) -> Path:
        return state_file(self, project_root, filename)


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
    def _storage_config(payload: dict) -> dict:
        storage = payload.get("Storage", {})
        if not isinstance(storage, dict):
            raise ConfigServiceError("Storage settings must be a TOML table.")
        override = payload.get("StorageByPlatform", {}).get(ConfigService._platform_name(), {})
        if not isinstance(override, dict):
            raise ConfigServiceError("Storage platform settings must be a TOML table.")
        return {**storage, **override}

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
    def load(config_path: str | Path, *, worker_render_root: str | Path | None = None) -> Config:
        """Load settings; worker render opt-in redirects creative paths to a private root.

        The caller remains responsible for validating frozen asks and render budgets.
        """
        path = Path(config_path)
        if not path.exists():
            raise ConfigServiceError(f"Config file not found: {path}")
        try:
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigServiceError(f"Config file is invalid TOML at {path}: {exc}") from exc
        try:
            github = payload.get("GitHub", {})
            runtime = payload.get("Runtime", {})
            if not isinstance(github, dict) or not isinstance(runtime, dict):
                raise ConfigServiceError("GitHub and Runtime settings must be TOML tables.")
            for name, settings in (("GitHub", github), ("Runtime", runtime)):
                overrides = payload.get(name + "ByPlatform", {}).get(ConfigService._platform_name(), {})
                if not isinstance(overrides, dict):
                    raise ConfigServiceError(f"{name} platform settings must be a TOML table.")
                settings.update(overrides)
            github_repository = validate_repository(github.get("Repository", ""))
            timeout = float(github.get("TimeoutSeconds", 20))
            reserve = float(github.get("UsageReservePercent", 10))
            if not 0 < timeout <= 60 or not 0 <= reserve <= 100:
                raise ConfigServiceError("GitHub timeout must be 0–60 seconds and usage reserve 0–100 percent.")
            role = runtime.get("Role", "local")
            if role not in {"local", "development", "production"}:
                raise ConfigServiceError("Runtime.Role must be local, development or production.")
            trusted = github.get("TrustedUsers", ["Joebok"])
            if not isinstance(trusted, list) or any(not isinstance(user, str) or not user.strip() for user in trusted):
                raise ConfigServiceError("GitHub.TrustedUsers must be a list of GitHub account names.")
            base_folders = ConfigService._base_folders_for_platform(payload)
            prompt_condense = ConfigService._prompt_condense_config(payload)
            ai_models = ConfigService._ai_models_config(payload)
            from zet.services.llm_role_service import validate_overrides
            try:
                role_models = validate_overrides(payload.get("LLMRoles", {}).get("Models", {}))
            except (ValueError, AttributeError) as exc:
                raise ConfigServiceError(f"Invalid LLM role settings: {exc}") from exc
            local_render = ConfigService._local_render_config(payload)
            comfyui = ConfigService._comfyui_config(payload)
            zine = ConfigService._zine_config(payload)
            turnaround = ConfigService._turnaround_config(payload)
            ai_harvest = ConfigService._ai_harvest_config(payload)
            storage = ConfigService._storage_config(payload)
            render = ConfigService._render_config(payload)
            ai_prompt_analysis = ConfigService._ai_prompt_analysis_config(payload)
            preset_path = Path(ConfigService._normalize_path_value(runtime.get("StatePath", ""))) / "Local_Render_Presets.json" if runtime.get("StatePath") else None
            library_base = ConfigService._normalize_path_value(base_folders.get("BaseLibraryPath", ""))
            configured_storage_root = storage.get("Root", "")
            if configured_storage_root:
                storage_root = Path(ConfigService._normalize_path_value(configured_storage_root))
                if not storage_root.is_absolute():
                    storage_root = path.resolve().parent / storage_root
            else:
                local_storage = os.environ.get("LOCALAPPDATA")
                if not local_storage:
                    local_storage = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
                storage_root = Path(local_storage) / "Zet"
            retention_days = int(storage.get("CompletedRetentionDays", 7))
            maintenance_hours = int(storage.get("MaintenanceIntervalHours", 24))
            if retention_days < 1 or maintenance_hours < 1:
                raise ConfigServiceError("Storage retention and maintenance intervals must be at least one.")
            for configured_state in (github.get("StatePath", ""), runtime.get("StatePath", "")):
                if configured_state:
                    state_root = Path(ConfigService._normalize_path_value(configured_state)).resolve()
                    for authored_path in (library_base, base_folders.get("BaseAIQueuePath", "")):
                        authored = Path(ConfigService._normalize_path_value(authored_path)).resolve()
                        if state_root == authored or authored in state_root.parents:
                            raise ConfigServiceError("Runtime/task state must be outside the creative library and queue.")
            render_root = None
            if worker_render_root is not None:
                checkout = Path(__file__).resolve().parents[2]
                private_root = (checkout / "test-results").resolve()
                render_root = Path(worker_render_root).resolve()
                if (os.environ.get("ZET_WORKER_MODE") != "1" or role != "local"
                        or path.resolve() != checkout / "config.toml"
                        or not render_root.is_dir() or not render_root.is_relative_to(private_root)
                        or render_root == private_root):
                    raise ConfigServiceError(
                        "Worker render access requires the local config and an existing private test-results directory."
                    )
            if os.environ.get("ZET_WORKER_MODE") == "1" and role != "development" and render_root is None:
                raise ConfigServiceError("Issue workers may load only a development fixture configuration, never production config.toml.")
            if role == "development":
                fixture_root = path.resolve().parent
                for candidate in (library_base, base_folders.get("BaseAIQueuePath", "")):
                    resolved = Path(ConfigService._normalize_path_value(candidate)).resolve()
                    if fixture_root not in resolved.parents:
                        raise ConfigServiceError("Development library and queue must be inside the fixture config directory.")
                if ConfigService._scene_candidate_sources(payload):
                    raise ConfigServiceError("Development fixtures cannot attach external candidate source documents.")
            creative_root = str(render_root) if render_root else library_base
            config = Config(
                base_library_path=creative_root,
                base_character_path=(str(render_root / "Characters") if render_root else
                                     ConfigService._resolve_base_folder(library_base, base_folders["BaseCharacterPath"])),
                base_asset_path=(str(render_root / "Assets") if render_root else
                                 ConfigService._resolve_base_folder(library_base, base_folders["BaseAssetPath"])),
                base_pipeline_path=(str(render_root / "PipelineCandidates") if render_root else
                                    ConfigService._resolve_base_folder(library_base, base_folders["BasePipelinePath"])),
                base_ai_queue_path=ConfigService._normalize_path_value(base_folders["BaseAIQueuePath"]),
                prompt_condense_enabled=bool(prompt_condense.get("Enabled", False)),
                prompt_condense_model=str(
                    ai_models.get("PromptCondense", prompt_condense.get("Model", "general:latest"))
                ),
                prompt_condense_file=str(
                    prompt_condense.get("PromptFile", "Config/Prompt_Condense_Tasks/body_reference_condense.md")
                ),
                llm_role_models=role_models,
                ai_asset_workflow_model=str(ai_models.get("AssetWorkflow", "general:latest")),
                codex_default_model=str(ai_models.get("CodexDefault", "gpt-6-luna")),
                ai_scene_builder_model=str(ai_models.get("SceneBuilder", "general:latest")),
                ai_narrative_scene_model=str(ai_models.get("NarrativeScene", "general:latest")),
                local_body_reference_review_model=str(
                    ai_models.get("LocalBodyReferenceReview", "image-analysis:latest")
                ),
                local_render_auto_queue_after_condense=bool(local_render.get("AutoQueueAfterCondense", False)),
                local_render_backend="comfyui",
                local_render_preset=configured_qwen_profile(str(comfyui.get("Profile", SCENE_PROFILE)), presets_path=preset_path),
                comfyui_profile=configured_qwen_profile(str(comfyui.get("Profile", SCENE_PROFILE)), presets_path=preset_path),
                comfyui_server_url=str(comfyui.get("ServerURL", "http://127.0.0.1:8188")),
                comfyui_checkpoint=configured_qwen_checkpoint(str(comfyui.get("Checkpoint", "")), presets_path=preset_path),
                comfyui_positive_prompt_globals=str(comfyui.get("PositivePromptGlobals", "")),
                comfyui_negative_prompt_globals=str(comfyui.get("NegativePromptGlobals", "")),
                comfyui_poll_seconds=float(comfyui.get("PollSeconds", 1.0)),
                comfyui_timeout_seconds=float(comfyui.get("TimeoutSeconds", 300.0)),
                zine_print_scale=float(zine.get("PrintScale", 0.978)),
                zine_page_margin=int(zine.get("PageMargin", 4)),
                zine_width=int(zine.get("Width", 3300)),
                turnaround_width=int(turnaround.get("Width", 3960)),
                ai_harvest_auto_enabled=bool(ai_harvest.get("AutoEnabled", True)),
                ai_harvest_interval_seconds=int(ai_harvest.get("IntervalSeconds", 2)),
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
                scene_candidate_sources=() if render_root else ConfigService._scene_candidate_sources(payload),
                github_repository=github_repository,
                github_timeout_seconds=timeout,
                task_state_path=ConfigService._normalize_path_value(github.get("StatePath", "")),
                runtime_state_path=ConfigService._normalize_path_value(runtime.get("StatePath", "")),
                runtime_root=ConfigService._normalize_path_value(runtime.get("Root", "")),
                runtime_role=role,
                codex_usage_reserve_percent=reserve,
                codex_trusted_users=tuple(trusted),
                storage_root=str(storage_root.resolve()),
                storage_indexes_path=str(storage.get("Indexes", "Indexes")),
                storage_queue_state_path=str(storage.get("QueueState", "AI_Queue")),
                storage_migration_state_path=str(storage.get("MigrationState", "LibraryReferenceUpdates")),
                storage_workflow_state_path=str(storage.get("WorkflowState", "TaskWorkflow")),
                storage_completed_retention_days=retention_days,
                storage_maintenance_interval_hours=maintenance_hours,
            )
            from zet.services.storage_path_service import StoragePathError, StoragePathService
            paths = StoragePathService(config)
            try:
                for area in StoragePathService.CHILDREN:
                    paths.child(area)
            except StoragePathError as exc:
                raise ConfigServiceError(str(exc)) from exc
            if paths.root == Path(config.base_library_path).expanduser().resolve():
                raise ConfigServiceError("Machine-local storage must be outside the creative library.")
            return config
        except ConfigServiceError:
            raise
        except TaskServiceError as exc:
            raise ConfigServiceError(str(exc)) from exc
        except Exception as exc:
            raise ConfigServiceError(f"Config file is missing required BaseFolders entries: {path}") from exc

