from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from zet.services.ai_proxy_service import AIProxyService, AIProxyServiceError
from zet.services.config_service import ConfigService, ConfigServiceError
from zet.services.prompt_evolution_service import PromptEvolutionError, PromptEvolutionService


BASE_FOLDERS = """
[BaseFolders]
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "Queue"
""".lstrip()


def test_config_round_trip_covers_every_selectable_role(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    role_values = {
        "AssetWorkflow": "asset",
        "PromptCondense": "condense",
        "PromptAnalysis": "prompt-analysis",
        "ImageDescription": "image-description",
        "SceneBuilder": "scene-builder",
        "PromptEvolutionCriticA": "critic-a",
        "PromptEvolutionCriticB": "critic-b",
        "PromptEvolutionVision": "evolution-vision",
        "PromptEvolutionText": "evolution-text",
        "PromptEvolutionCheck": "evolution-check",
    }
    config_path.write_text(
        BASE_FOLDERS + "\n[AIModels]\n" + "".join(f'{key} = "{value}"\n' for key, value in role_values.items()),
        encoding="utf-8",
    )

    config = ConfigService.load(config_path)

    assert config.ai_asset_workflow_model == "asset"
    assert config.prompt_condense_model == "condense"
    assert config.ai_prompt_analysis_model == "prompt-analysis"
    assert config.ai_image_description_model == "image-description"
    assert config.ai_scene_builder_model == "scene-builder"
    assert config.ai_prompt_evolution_critic_model_a == "critic-a"
    assert config.ai_prompt_evolution_critic_model_b == "critic-b"
    assert config.ai_prompt_evolution_vision_model == "evolution-vision"
    assert config.ai_prompt_evolution_text_model == "evolution-text"
    assert config.ai_prompt_evolution_check_model == "evolution-check"


def test_explicit_config_migration_copies_shared_assignment_and_is_idempotent(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        BASE_FOLDERS + '\n[AIModels]\nPromptEvolutionAnalysis = "managed:latest"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigServiceError, match="migrate_wp13_config"):
        ConfigService.load(config_path)

    backup = ConfigService.migrate_prompt_evolution_roles(config_path)
    config = ConfigService.load(config_path)

    assert backup is not None and backup.read_text(encoding="utf-8").find("PromptEvolutionAnalysis") >= 0
    assert config.ai_prompt_evolution_vision_model == "managed:latest"
    assert config.ai_prompt_evolution_text_model == "managed:latest"
    assert "PromptEvolutionAnalysis" not in config_path.read_text(encoding="utf-8")
    assert ConfigService.migrate_prompt_evolution_roles(config_path) is None


def test_prompt_evolution_routes_repair_and_directed_refinement_to_split_roles(tmp_path: Path) -> None:
    malformed = tmp_path / "response.json"
    malformed.write_text("not json", encoding="utf-8")
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"image")
    (tmp_path / "prompt_core.json").write_text(
        json.dumps({"positive_core": "blue coat", "negative_core": "blur"}), encoding="utf-8"
    )
    run = {
        "run_id": "run-1", "root": str(tmp_path), "status": "COMPLETE",
        "selected_prompt_version": "prompt-1", "reference_image": str(reference),
        "vision_model": "vision-managed", "text_model": "text-managed", "check_model": "check-managed",
    }
    service = object.__new__(PromptEvolutionService)
    service._find_run = Mock(return_value=run)
    service._format_template = Mock(return_value="task prompt")
    service._queue_ollama = Mock(return_value="ask-1")
    service._save_run = Mock()
    service.detail = Mock(return_value=run)
    service._log = Mock()

    with pytest.raises(Exception, match="Waiting for JSON repair"):
        service._llm_json(run, malformed)
    assert service._queue_ollama.call_args.kwargs["model"] == "text-managed"

    service._queue_ollama.reset_mock(return_value=True)
    service._queue_ollama.return_value = "ask-2"
    service.start_directed_refinement("run-1", "change only blue coat to red")
    assert service._queue_ollama.call_args.kwargs["model"] == "vision-managed"
    assert service._queue_ollama.call_args.kwargs["images"] == [reference]


def test_prompt_evolution_unsupported_fallback_fails_explicitly(tmp_path: Path) -> None:
    response = tmp_path / "bootstrap.json"
    response.write_text("{}", encoding="utf-8")
    run = {"current_batch": 0, "validation_retries": {"0:BOOTSTRAPPING": 1}}
    service = object.__new__(PromptEvolutionService)

    with pytest.raises(PromptEvolutionError, match="unsupported fallback generation was not run"):
        service._prompt_json(run, response)


def test_asset_workflow_unsupported_stage_fails_before_inference() -> None:
    service = object.__new__(AIProxyService)
    asset = SimpleNamespace(
        asset_id=7, character="Hero", phase="Adult", pipeline="Unknown-Workflow",
        pipeline_stage="ANALYZE", body_view=None, head_view=None, final_image_output="output.png",
    )

    with pytest.raises(AIProxyServiceError, match="no production prompt contract is registered"):
        service._prompt_contents(asset)
