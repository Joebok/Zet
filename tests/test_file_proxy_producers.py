import json
from pathlib import Path

from zet.app import ZetApp
from zet.services.config_service import Config
from zet.services.scene_prompt_analysis_service import ScenePromptAnalysisService


def test_render_task_prompt_condense_publishes_ollama_job(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[BaseFolders]
BaseLibraryPath = "{tmp_path.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(tmp_path / 'Queue').as_posix()}"

[PromptCondense]
Enabled = true
PromptFile = "Config/Prompt_Condense_Tasks/Condense_Zet.md"
""".lstrip(),
        encoding="utf-8",
    )
    prompt = tmp_path / "Final_Image_Prompt.md"
    prompt.write_text("test prompt", encoding="utf-8")
    output_dir = tmp_path / "output"

    app = ZetApp.from_config(config_path)
    ask = app.ai_proxy_service.stage_render_task_prompt_condense_ask_if_enabled(
        {"ask_id": "Ask_Test", "pipeline": "Story", "pipeline_stage": "RENDER"},
        prompt,
        output_dir,
    )

    assert ask is not None
    job = json.loads((ask / "job.json").read_text(encoding="utf-8"))
    manifest = json.loads((ask / "ask_manifest.json").read_text(encoding="utf-8"))
    assert job["worker"] == "ollama"
    assert manifest["task_type"] == "prompt_condense"
    assert "target_output_dir" not in manifest
    route = app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.load_route(ask.name)
    assert route["target_output_dir"] == str(output_dir.resolve())


def test_scene_prompt_analysis_publishes_ollama_job(tmp_path: Path) -> None:
    class StoryService:
        def compile_scene_prompt(self, story_slug: str, scene_slug: str) -> Path:
            prompt = tmp_path / "Final_Image_Prompt.md"
            prompt.write_text("compiled scene prompt", encoding="utf-8")
            return prompt

        def scene_pipeline_path(self, story_slug: str, scene_slug: str) -> Path:
            return tmp_path / "Stories" / story_slug / scene_slug

    config = Config(
        base_library_path=str(tmp_path),
        base_character_path=str(tmp_path / "Characters"),
        base_asset_path=str(tmp_path / "Assets"),
        base_pipeline_path=str(tmp_path / "Pipelines"),
        base_ai_queue_path=str(tmp_path / "Queue"),
    )
    service = ScenePromptAnalysisService(config, StoryService())

    status = service.queue("Story", "Scene")

    asks = list(service.path_service.file_proxy_client.task_paths("ask"))
    assert status["pending"] is True
    assert len(asks) == 1
    job = json.loads((asks[0] / "job.json").read_text(encoding="utf-8"))
    manifest = json.loads((asks[0] / "ask_manifest.json").read_text(encoding="utf-8"))
    assert job["worker"] == "ollama"
    assert manifest["task_type"] == "scene_prompt_analysis"
    assert "target_output_dir" not in manifest
    route = service.path_service.file_proxy_client.load_route(asks[0].name)
    assert route["target_output_dir"] == str((tmp_path / "Stories" / "Story" / "Scene").resolve())
