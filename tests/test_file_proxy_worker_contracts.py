import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import numpy as np
from PIL import Image

from AI_Manager import local_image_proxy_worker
from zet.app import ZetApp
from zet.services.head_fitment_edit_service import HeadFitmentEditService
from zet.services.head_fitment_mask_generation_service import HeadFitmentMaskGenerationService, HeadFitmentMaskResult


@pytest.mark.parametrize(
    ("backend", "artifact_name", "artifact_payload"),
    [
        (
            "stable_matrix",
            "Stable_Matrix_API_Call.json",
            {"api_path": "/sdapi/v1/txt2img"},
        ),
        (
            "comfyui",
            "ComfyUI_Compilation_Debug.json",
            {"workflow_kind": "ipadapter_scene_preview"},
        ),
    ],
)
def test_local_image_worker_outputs_remain_proxy_safe(
    tmp_path: Path,
    backend: str,
    artifact_name: str,
    artifact_payload: dict,
) -> None:
    job = tmp_path / "Running" / "zet" / f"{backend}-job"
    job.mkdir(parents=True)
    prompt = job / "prompt.md"
    prompt.write_text("prompt: test\nnegative: bad\n", encoding="utf-8")
    reference = job / "references" / "reference.png"
    reference.parent.mkdir()
    reference.write_bytes(b"reference")
    ask = {
        "version": 1,
        "ask_id": job.name,
        "worker_type": "local_image_render",
        "prompt_file": prompt.name,
        "expected_output": "result.png",
        "render_preset": "test",
        "image_generation": backend,
        "reference_files": [{"path": "references/reference.png"}],
    }
    (job / "ask_manifest.json").write_text(json.dumps(ask), encoding="utf-8")

    generated = job / "backend" / "generated.png"
    generated.parent.mkdir()
    generated.write_bytes(b"image")
    metadata = generated.parent / "metadata.json"
    metadata.write_text(
        json.dumps({"backend": backend, "final_prompt": str(prompt.resolve())}),
        encoding="utf-8",
    )
    artifact = generated.parent / artifact_name
    artifact_payload = dict(artifact_payload)
    artifact_payload["reference_path"] = str(reference.resolve())
    artifact.write_text(json.dumps(artifact_payload), encoding="utf-8")
    result = SimpleNamespace(
        image_path=generated,
        metadata_path=metadata,
        artifact_paths=[artifact],
        prompt_id="test-prompt",
    )

    with patch.object(local_image_proxy_worker, "render_image", return_value=result):
        status = local_image_proxy_worker.process_claimed(
            job,
            "test-worker",
        )

    assert status == "SUCCESS"
    assert (job / "result.png").read_bytes() == b"image"
    assert json.loads((job / "answer_manifest.json").read_text())["status"] == "SUCCESS"
    localized_artifact = json.loads((job / artifact_name).read_text())
    assert localized_artifact["reference_path"] == "references/reference.png"
    if backend == "stable_matrix":
        assert localized_artifact["api_path"] == "/sdapi/v1/txt2img"


def test_ollama_and_local_image_are_the_only_registered_proxy_workers(tmp_path: Path) -> None:
    from zet.services.file_proxy_client import FileProxyClient

    client = FileProxyClient(tmp_path)

    assert client.worker_names == {
        "ollama_generate": "ollama",
        "local_image_render": "local_image",
    }


def test_local_image_worker_accepts_registered_config_argument(tmp_path: Path) -> None:
    with patch.object(local_image_proxy_worker, "process_claimed", return_value="SUCCESS") as process:
        status = local_image_proxy_worker.main(
            ["--job-dir", str(tmp_path), "--config", str(tmp_path / "config.toml")]
        )

    assert status == 0
    process.assert_called_once()


def test_local_image_worker_processes_head_fitment_inpaint_inside_proxy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[BaseFolders]
BaseLibraryPath = "{tmp_path.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(tmp_path / 'Queue').as_posix()}"

[HeadFitment]
RenderMode = "masked_local"
""".lstrip(),
        encoding="utf-8",
    )
    job = tmp_path / "job"
    job.mkdir()
    (job / "Final_Image_Prompt.md").write_text("edit only the visible neck\n", encoding="utf-8")
    (job / "Head_Fitment_Init.png").write_bytes(b"init")
    (job / "Head_Fitment_Edit_Mask.png").write_bytes(b"mask")
    ask = {
        "version": 1,
        "ask_id": "head-fitment-test",
        "asset_id": 9,
        "worker_type": "local_image_render",
        "task_type": "head_fitment_inpaint",
        "prompt_file": "Final_Image_Prompt.md",
        "expected_output": "head_fitment.png",
        "render_preset": "head-fitment-inpaint",
        "head_fitment_init_file": "Head_Fitment_Init.png",
        "head_fitment_mask_file": "Head_Fitment_Edit_Mask.png",
        "image_generation": "comfyui",
        "checkpoint": "test-checkpoint",
        "mask_feather_pixels": 6,
    }
    (job / "ask_manifest.json").write_text(json.dumps(ask), encoding="utf-8")

    def render_artifacts(**kwargs):
        kwargs["output_path"].write_bytes(b"inpainted")
        requirements = job / "Head_Fitment_Model_Requirements.json"
        metadata = job / "Head_Fitment_Render_Metadata.json"
        requirements.write_text("{}\n", encoding="utf-8")
        metadata.write_text('{"backend": "comfyui"}\n', encoding="utf-8")
        return [kwargs["output_path"], requirements, metadata]

    with patch.object(HeadFitmentEditService, "render_artifacts", side_effect=render_artifacts) as render, patch.object(
        local_image_proxy_worker, "render_image"
    ) as txt2img:
        status = local_image_proxy_worker.process_claimed(job, "proxy-worker", config_path)

    assert status == "SUCCESS"
    txt2img.assert_not_called()
    assert render.call_args.kwargs["preset_name"] == "head-fitment-inpaint"
    assert render.call_args.kwargs["init_path"] == job / "Head_Fitment_Init.png"
    assert render.call_args.kwargs["mask_path"] == job / "Head_Fitment_Edit_Mask.png"
    assert (job / "head_fitment.png").read_bytes() == b"inpainted"
    assert "7860" not in "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in job.glob("*.json"))
    assert json.loads((job / "answer_manifest.json").read_text(encoding="utf-8"))["status"] == "SUCCESS"


@pytest.mark.skipif(os.environ.get("ZET_LIVE_COMFYUI") != "1", reason="requires live ComfyUI")
def test_live_head_fitment_inpaint_preserves_asset_11_protected_pixels(tmp_path: Path) -> None:
    config_path = Path(__file__).resolve().parents[1] / "config.toml"
    app = ZetApp.from_config(config_path)
    asset = app.asset_repository.get_asset("Tsaeytte", "Elder", 11)
    paths = app.head_fitment_edit_service.paths(asset)
    job = tmp_path / "asset-11-inpaint"
    job.mkdir()
    shutil.copy2(paths.init, job / "Head_Fitment_Init.png")
    shutil.copy2(paths.mask, job / "Head_Fitment_Edit_Mask.png")
    (job / "Final_Image_Prompt.md").write_text("Fit only the visible neck transition to the body reference.\n", encoding="utf-8")
    ask = {
        "version": 1,
        "ask_id": "live-head-fitment-asset-11",
        "asset_id": 11,
        "worker_type": "local_image_render",
        "task_type": "head_fitment_inpaint",
        "prompt_file": "Final_Image_Prompt.md",
        "expected_output": "Head_Fitment_Live_Test.png",
        "render_preset": "head-fitment-inpaint",
        "head_fitment_init_file": "Head_Fitment_Init.png",
        "head_fitment_mask_file": "Head_Fitment_Edit_Mask.png",
        "image_generation": "comfyui",
        "checkpoint": "perfectdeliberate_v90.safetensors",
        "mask_feather_pixels": 6,
    }
    (job / "ask_manifest.json").write_text(json.dumps(ask), encoding="utf-8")

    assert local_image_proxy_worker.process_claimed(job, "live-proxy-worker", config_path) == "SUCCESS"
    source = np.array(Image.open(paths.init).convert("RGBA"))
    semantic = np.array(Image.open(paths.mask).convert("L"))
    result = np.array(Image.open(job / "Head_Fitment_Live_Test.png").convert("RGBA"))
    assert np.array_equal(source[semantic == 255], result[semantic == 255])
    assert np.all(result[semantic == 0, 3] == 0)
    assert json.loads((job / "LOCAL_RENDER_METADATA.json").read_text(encoding="utf-8"))["image_generation"] == "comfyui"


def test_local_image_worker_generates_head_fitment_mask_inside_proxy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[BaseFolders]
BaseLibraryPath = "{tmp_path.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(tmp_path / 'Queue').as_posix()}"

[ComfyUI]
ServerURL = "http://comfy.test"
""".lstrip(),
        encoding="utf-8",
    )
    job = tmp_path / "job"
    refs = job / "references"
    refs.mkdir(parents=True)
    (job / "Head_Fitment_Mask_Task.md").write_text("generate mask\n", encoding="utf-8")
    (refs / "head.png").write_bytes(b"head")
    (refs / "body.png").write_bytes(b"body")
    (job / "ask_manifest.json").write_text(json.dumps({
        "version": 1,
        "ask_id": "mask-test",
        "asset_id": 2,
        "worker_type": "local_image_render",
        "task_type": "head_fitment_mask_generate",
        "prompt_file": "Head_Fitment_Mask_Task.md",
        "expected_output": "Head_Fitment_Edit_Mask.png",
        "head_view": "Front-Right-3-4",
        "reference_files": [
            {"role": "head_image", "path": "references/head.png"},
            {"role": "body_reference", "path": "references/body.png"},
        ],
    }), encoding="utf-8")

    def generate(**kwargs):
        mask = job / "Head_Fitment_Edit_Mask.png"
        report = job / "Head_Fitment_Mask_Score.json"
        overlay = job / "Head_Fitment_Mask_Overlay.png"
        workflow = job / "Head_Fitment_Mask_Workflow_API.json"
        mask.write_bytes(b"mask")
        report.write_text('{"backend":"comfyui","confidence_score":0.95}\n', encoding="utf-8")
        overlay.write_bytes(b"overlay")
        workflow.write_text("{}\n", encoding="utf-8")
        return HeadFitmentMaskResult(mask, report, overlay, workflow, [mask, report, overlay, workflow], "prompt-1")

    with patch.object(HeadFitmentMaskGenerationService, "generate", side_effect=generate) as generate_mask:
        status = local_image_proxy_worker.process_claimed(job, "proxy-worker", config_path)

    assert status == "SUCCESS"
    assert generate_mask.call_args.kwargs["server_url"] == "http://comfy.test"
    assert generate_mask.call_args.kwargs["view"] == "Front-Right-3-4"
    assert json.loads((job / "answer_manifest.json").read_text(encoding="utf-8"))["status"] == "SUCCESS"


@pytest.mark.skipif(os.environ.get("ZET_RUN_LIVE_COMFYUI") != "1", reason="live ComfyUI test is opt-in")
def test_live_elder_tsaeytte_asset_11_mask_through_ai_proxy_worker(tmp_path: Path) -> None:
    config_path = Path("config.toml").resolve()
    app = ZetApp.from_config(config_path)
    asset = app.asset_repository.get_asset("Tsaeytte", "Elder", 11)
    edit = app.head_fitment_edit_service
    head = Path(str(edit._reference(asset, "head_image", "headshot")["path"]))
    body = Path(str(edit._reference(asset, "body_reference")["path"]))
    job = tmp_path / "job"
    references = job / "references"
    references.mkdir(parents=True)
    shutil.copy2(head, references / head.name)
    shutil.copy2(body, references / body.name)
    (job / "Head_Fitment_Mask_Task.md").write_text("generate mask\n", encoding="utf-8")
    (job / "ask_manifest.json").write_text(json.dumps({
        "version": 1,
        "ask_id": "live-elder-tsaeytte-11",
        "asset_id": 11,
        "worker_type": "local_image_render",
        "task_type": "head_fitment_mask_generate",
        "prompt_file": "Head_Fitment_Mask_Task.md",
        "expected_output": "Head_Fitment_Edit_Mask.png",
        "head_view": "Front-Right-3-4",
        "reference_files": [
            {"role": "head_image", "path": f"references/{head.name}"},
            {"role": "body_reference", "path": f"references/{body.name}"},
        ],
    }), encoding="utf-8")

    assert local_image_proxy_worker.process_claimed(job, "live-test-worker", config_path) == "SUCCESS"
    report = json.loads((job / "Head_Fitment_Mask_Score.json").read_text(encoding="utf-8"))
    with Image.open(job / "Head_Fitment_Edit_Mask.png") as generated:
        mask = np.array(generated.convert("L"))
    protected_y, _ = np.where(mask == 255)
    assert len(protected_y) and protected_y.min() < mask.shape[0] * 0.10
    assert np.count_nonzero(mask[int(mask.shape[0] * 0.85):] == 255) == 0
    assert report["confidence_score"] >= app.config.head_fitment_mask_auto_confirm_threshold
    assert report["validation_failures"] == []
