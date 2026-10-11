import time
import json
import subprocess
from dataclasses import replace
import threading

from tests.support.image_fixture import png_bytes
from tests.support.project_fixture import write_project_fixture
from zet.app import ZetApp
from zet.services.image_prompt_generation_service import ImagePromptGenerationService


class ModelResponse:
    def __init__(self, value):
        self.value = value

    def generate_json(self, model, system, prompt, schema, *, images):
        assert images
        return self.value


def _asset(tmp_path, *, prompt="", negative_prompt=""):
    config_path = write_project_fixture(tmp_path)
    app = ZetApp.from_config(config_path, validate_catalog=False)
    asset = app.entity_library_import("Prompt analysis", "image/png", png_bytes(),
                                      prompt=prompt, negative_prompt=negative_prompt)
    return app, asset


def test_local_vision_model_returns_structured_editable_draft(tmp_path):
    app, asset = _asset(tmp_path)
    service = ImagePromptGenerationService(app, tmp_path, ModelResponse({
        "prompt": "A painted red boat at dawn", "negative_prompt": "text, extra boats",
    }))
    started = service.start(asset["asset_id"])
    for _ in range(100):
        status = service.status(started["job_id"])
        if status["status"] != "RUNNING":
            break
        time.sleep(0.01)
    assert status["status"] == "COMPLETE"
    assert status["draft"] == {"prompt": "A painted red boat at dawn", "negative_prompt": "text, extra boats"}
    assert app.entity_library_asset(asset["asset_id"])["prompt"] == ""


def test_invalid_vision_model_response_fails_without_saving_metadata(tmp_path):
    app, asset = _asset(tmp_path)
    service = ImagePromptGenerationService(app, tmp_path, ModelResponse({"prompt": "", "negative_prompt": ""}))
    started = service.start(asset["asset_id"])
    for _ in range(100):
        status = service.status(started["job_id"])
        if status["status"] != "RUNNING":
            break
        time.sleep(0.01)
    assert status["status"] == "FAILED"
    assert app.entity_library_asset(asset["asset_id"])["prompt"] == ""


def test_codex_model_returns_structured_image_draft(tmp_path):
    app, asset = _asset(tmp_path)

    def runner(command, **kwargs):
        assert "--image" in command
        assert command[command.index("--image") + 1] == asset["image_path"]
        output = command[command.index("--output-last-message") + 1]
        with open(output, "w", encoding="utf-8") as stream:
            json.dump({"prompt": "A blue ceramic vase", "negative_prompt": "text"}, stream)
        return subprocess.CompletedProcess(command, 0, "", "")

    service = ImagePromptGenerationService(app, tmp_path, runner=runner)
    service._codex_executable = lambda: "codex"
    app.config = replace(app.config, ai_image_prompt_generation_model="codex:gpt-6-luna")
    started = service.start(asset["asset_id"])
    for _ in range(100):
        status = service.status(started["job_id"])
        if status["status"] != "RUNNING":
            break
        time.sleep(0.01)
    assert status["status"] == "COMPLETE"
    assert status["draft"] == {"prompt": "A blue ceramic vase", "negative_prompt": "text"}


def test_identity_generation_uses_luna_and_returns_unsaved_visual_facts(tmp_path):
    app, asset = _asset(tmp_path)

    def runner(command, **kwargs):
        assert command[command.index("-m") + 1] == "gpt-6-luna"
        assert command[command.index("--image") + 1] == asset["image_path"]
        assert "scene builder" in kwargs["input"]
        assert "image generation prompt" in kwargs["input"]
        with open(command[command.index("--output-schema") + 1], encoding="utf-8") as stream:
            assert json.load(stream)["required"] == ["identity"]
        output = command[command.index("--output-last-message") + 1]
        with open(output, "w", encoding="utf-8") as stream:
            json.dump({"identity": "  Blue ceramic vase with a narrow neck and two loop handles.  "}, stream)
        return subprocess.CompletedProcess(command, 0, "", "")

    service = ImagePromptGenerationService(app, tmp_path, runner=runner)
    service._codex_executable = lambda: "codex"
    started = service.start_identity(asset["asset_id"])
    for _ in range(100):
        status = service.status(started["job_id"])
        if status["status"] != "RUNNING":
            break
        time.sleep(0.01)
    assert status["status"] == "COMPLETE"
    assert status["draft"] == {"identity": "Blue ceramic vase with a narrow neck and two loop handles."}
    assert app.entity_library_asset(asset["asset_id"])["descriptors"] == []


def test_analysis_result_is_rejected_after_image_content_changes(tmp_path):
    app, asset = _asset(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    class SlowModel:
        def generate_json(self, model, system, prompt, schema, *, images):
            entered.set()
            release.wait(timeout=2)
            return {"prompt": "A painted red boat", "negative_prompt": "text"}

    service = ImagePromptGenerationService(app, tmp_path, SlowModel())
    started = service.start(asset["asset_id"])
    assert entered.wait(timeout=1)
    app.entity_library_apply_generated_image(
        asset["asset_id"], asset["checksum"], "image/png", png_bytes() + b"revision",
        "Updated image", "text", "update-job", 0,
    )
    release.set()
    for _ in range(100):
        status = service.status(started["job_id"])
        if status["status"] != "RUNNING":
            break
        time.sleep(0.01)
    assert status["status"] == "FAILED"
    assert "changed" in status["error"]
