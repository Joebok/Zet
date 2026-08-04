from __future__ import annotations

import json
from pathlib import Path

from zet.app import ZetApp
from zet.services.checkpoint_lab_service import CheckpointLabService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_fixture(tmp_path: Path) -> tuple[ZetApp, CheckpointLabService, Path]:
    library = tmp_path / "Library"
    character = library / "Characters" / "Ada" / "Adult"
    image = library / "Assets" / "Ada" / "Adult" / "Costume-Dressing_Front_Field-Gear.png"
    character.mkdir(parents=True)
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    (character / "Assets.json").write_text(json.dumps({
        "next_asset_id": 2,
        "assets": [{
            "asset_id": 1,
            "character": "Ada",
            "phase": "Adult",
            "pipeline": "Costume-Dressing",
            "body_view": "Front",
            "costume": "Field Gear",
            "asset_state": "LOCKED",
            "pipeline_stage": "LOCKED",
            "final_image_output": image.name,
        }],
    }), encoding="utf-8")
    (character / "Character_Image_Template.md").write_text(
        "<!-- ZET:BEGIN IDENTITY_PRESERVATION_SCENE -->\n"
        "Ada has unmistakable silver hair and green eyes.\n"
        "<!-- ZET:END IDENTITY_PRESERVATION_SCENE -->\n",
        encoding="utf-8",
    )
    (character / "Costume_Field_Gear.md").write_text(
        "<!-- ZET:BEGIN IDENTITY_PRESERVATION_COSTUME_SCENE -->\n"
        "Brown field jacket and sturdy boots.\n"
        "<!-- ZET:END IDENTITY_PRESERVATION_COSTUME_SCENE -->\n",
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[BaseFolders]
BaseLibraryPath = "{library.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(tmp_path / 'Queue').as_posix()}"

[StableMatrix]
Profile = "scene-preview-sd15"
PositivePromptGlobals = "stable global"
NegativePromptGlobals = "stable negative"
Checkpoint = "stable.safetensors"

[ComfyUI]
Profile = "comfyui-core-preview"
Checkpoint = "comfy.safetensors"
PositivePromptGlobals = "comfy global"
NegativePromptGlobals = "comfy negative"
""".lstrip(),
        encoding="utf-8",
    )
    app = ZetApp.from_config(config)
    return app, CheckpointLabService(app, PROJECT_ROOT), image


def test_costume_reference_image_returns_tag_and_absolute_path(tmp_path: Path) -> None:
    _app, service, image = _write_fixture(tmp_path)

    result = service.costume_reference_image(
        character="Ada",
        phase="Adult",
        view="front",
        costume="Field Gear",
    )

    assert result["image_tag"] == "{{ASSET:Ada:Adult:1:Costume | Front | Field Gear}}"
    assert result["image_path"] == str(image.resolve())


def test_local_image_recipe_compiles_comfyui_api_without_running_zet(tmp_path: Path) -> None:
    _app, service, _image = _write_fixture(tmp_path)
    output = tmp_path / "ComfyUI_Workflow_API.json"

    result = service.local_image_recipe(
        character="Ada",
        phase="Adult",
        view="Front",
        costume="Field Gear",
        image_generation="comfyui",
        render_profile="comfyui-core-preview",
        output_path=output,
        seed=42,
    )

    workflow = json.loads(output.read_text(encoding="utf-8"))
    assert result["api_json_path"] == str(output.resolve())
    assert result["prompts"]["global"].endswith("comfy global")
    assert "silver hair and green eyes" in result["prompts"]["regions"][0]
    assert result["prompts"]["negative"].endswith("comfy negative")
    assert workflow["1"]["inputs"]["ckpt_name"] == "comfy.safetensors"


def test_local_image_recipe_compiles_stable_matrix_api_without_backend(tmp_path: Path) -> None:
    _app, service, _image = _write_fixture(tmp_path)
    output = tmp_path / "Stable_Matrix_API_Call.json"

    result = service.local_image_recipe(
        character="Ada",
        phase="Adult",
        view="Front",
        costume="Field Gear",
        image_generation="stable_matrix",
        render_profile="scene-preview-sd15",
        output_path=output,
        seed=42,
    )

    recipe = json.loads(output.read_text(encoding="utf-8"))
    assert result["api_json_path"] == str(output.resolve())
    assert recipe["payload"]["prompt"].endswith("stable global")
    assert "silver hair" in recipe["payload"]["prompt"]
    assert recipe["payload"]["negative_prompt"].endswith("stable negative")
    assert recipe["payload"]["override_settings"]["sd_model_checkpoint"] == "stable.safetensors"
