from __future__ import annotations

import base64
import json
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from tests.support.image_fixture import png_bytes
from tests.support.project_fixture import write_project_fixture
from zet.app import ZetApp
from zet.services.ai_answer_harvester import AIAnswerHarvester
from zet.services.ad_hoc_image_generation_service import (
    AdHocImageGenerationError,
    AdHocImageGenerationService,
)
from zet.services.stable_matrix_api_compiler import split_labeled_prompt
from zet.web.app import create_app


def _service(tmp_path: Path) -> tuple[AdHocImageGenerationService, Path]:
    config_path = write_project_fixture(tmp_path)
    app = ZetApp.from_config(config_path, validate_catalog=False)
    service = AdHocImageGenerationService(app, Path(__file__).resolve().parents[1])
    return service, config_path


def test_default_count_dimensions_and_proxy_staging(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)

    assert service.options()["default_count"] == 4
    assert service.options()["default_width"] == 1024
    assert service.options()["default_height"] == 1024

    result = service.submit({"mode": "txt2img", "prompt": "A brass dragon egg", "negative_prompt": "blurred"})

    assert result["status"] == "QUEUED"
    assert result["requested"] == 4
    paths = service.proxy_paths
    asks = [
        json.loads((paths.ask_root() / child["ask_id"] / "ask_manifest.json").read_text(encoding="utf-8"))
        for child in service._jobs[result["request_id"]]["children"]
    ]
    assert len({ask["seed"] for ask in asks}) == 4
    assert {ask["consumer"] for ask in asks} == {"zet-image-generation"}
    assert {ask["ad_hoc_request_id"] for ask in asks} == {result["request_id"]}
    assert {ask["render_preset"] for ask in asks} == {"comfyui-qwen-head-image-text"}
    assert all(ask["render_overrides"] == {
        "width": 1024, "height": 1024, "disable_prompt_globals": True,
    } for ask in asks)
    assert object.__new__(AIAnswerHarvester)._has_external_consumer(
        paths.ask_root() / asks[0]["ask_id"]
    )
    prompts = [
        split_labeled_prompt((paths.ask_root() / ask["ask_id"] / ask["prompt_file"]).read_text(encoding="utf-8"))
        for ask in asks
    ]
    assert prompts == [("A brass dragon egg", "blurred")] * 4

    for ask in asks:
        shutil_path = paths.ask_root() / ask["ask_id"]
        service.proxy_client.remove_route(ask["ask_id"])
        shutil.rmtree(shutil_path)
    assert service.status(result["request_id"])["status"] == "FAILED"
    service.clear(result["request_id"])


def test_img2img_stages_reference_and_explicit_dimensions(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)
    result = service.submit({
        "mode": "img2img",
        "prompt": "Turn the prop into carved jade",
        "count": 1,
        "width": 1280,
        "height": 768,
        "reference_image": base64.b64encode(png_bytes()).decode("ascii"),
    })

    child = service._jobs[result["request_id"]]["children"][0]
    ask_dir = service.proxy_paths.ask_root() / child["ask_id"]
    ask = json.loads((ask_dir / "ask_manifest.json").read_text(encoding="utf-8"))
    reference = ask["reference_files"][0]
    assert ask["render_preset"] == "comfyui-qwen-head-image-edit"
    assert ask["render_overrides"] == {
        "width": 1280, "height": 768, "disable_prompt_globals": True,
    }
    assert (ask_dir / reference["path"]).is_file()
    assert result["requested"] == 1
    service.proxy_client.remove_route(child["ask_id"])
    shutil.rmtree(ask_dir)
    assert service.status(result["request_id"])["status"] == "FAILED"
    service.clear(result["request_id"])


@pytest.mark.parametrize(
    ("mode", "expected_preset"),
    [
        ("img2img", "comfyui-qwen-head-image-edit"),
        ("txt2img", "comfyui-qwen-head-image-text"),
    ],
)
def test_inventory_generation_binds_source_and_carries_prompts_into_import_and_update(
    tmp_path: Path, mode: str, expected_preset: str,
) -> None:
    service, _config_path = _service(tmp_path)
    source_bytes = png_bytes()
    source = service.zet_app.entity_library_import(
        "Source image", "image/png", source_bytes, prompt="A pale blue house",
        negative_prompt="extra windows",
    )
    payload = {
        "mode": mode, "prompt": "Night version of the house", "negative_prompt": "text",
        "count": 1, "source_asset_id": source["asset_id"], "source_checksum": source["checksum"],
    }
    if mode == "img2img":
        payload["reference_image"] = base64.b64encode(source_bytes).decode("ascii")
    result = service.submit(payload)
    job = service._jobs[result["request_id"]]
    child = job["children"][0]
    ask = json.loads((service.proxy_paths.ask_root() / child["ask_id"] / "ask_manifest.json").read_text(encoding="utf-8"))
    assert ask["render_preset"] == expected_preset
    assert bool(ask["reference_files"]) is (mode == "img2img")
    if mode == "img2img":
        assert ask["reference_files"][0]["label"] == "source image"
        staged_prompt, staged_negative = split_labeled_prompt(
            (service.proxy_paths.ask_root() / child["ask_id"] / ask["prompt_file"]).read_text(encoding="utf-8")
        )
        expected_staged_prompt = (
            "Night version of the house\n\n"
            "Reference image labels (images are supplied in this order):\n"
            "Image 1: source image"
        )
        assert staged_prompt == " ".join(expected_staged_prompt.split())
        assert staged_negative == "text"
    assert result["source_asset_id"] == source["asset_id"]
    assert result["prompt"] == "Night version of the house"
    job["images"].append((png_bytes() + b"new render", "image/png"))
    service._save_job(job)

    restarted = AdHocImageGenerationService(
        ZetApp.from_config(_config_path, validate_catalog=False), Path(__file__).resolve().parents[1],
    )
    assert restarted.library_result(result["request_id"], 0)[2]["prompt"] == "Night version of the house"
    imported = restarted.import_into_library(result["request_id"], 0, {"label": "Night house"})
    assert imported["asset"]["prompt"] == "Night version of the house"
    assert imported["asset"]["negative_prompt"] == "text"

    updated = restarted.apply_to_source(result["request_id"], 0)
    assert updated["asset_id"] == source["asset_id"]
    assert updated["prompt"] == "Night version of the house"
    assert updated["negative_prompt"] == "text"
    assert restarted.status(result["request_id"])["source_asset_id"] == source["asset_id"]


def test_inventory_generation_rejects_unrelated_reference_bytes(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)
    source = service.zet_app.entity_library_import("Source", "image/png", png_bytes())
    with pytest.raises(AdHocImageGenerationError, match="does not match"):
        service.submit({
            "mode": "img2img", "prompt": "Modify", "count": 1,
            "reference_image": base64.b64encode(png_bytes() + b"different").decode("ascii"),
            "source_asset_id": source["asset_id"], "source_checksum": source["checksum"],
        })


def test_txt2img_inventory_generation_rejects_stale_source_checksum(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)
    source = service.zet_app.entity_library_import("Source", "image/png", png_bytes())
    with pytest.raises(AdHocImageGenerationError, match="source image changed"):
        service.submit({
            "mode": "txt2img", "prompt": "Regenerate", "count": 1,
            "source_asset_id": source["asset_id"], "source_checksum": "stale-checksum",
        })


@pytest.mark.parametrize("field,value", [("width", 255), ("width", 1025), ("height", 4097), ("height", True)])
def test_invalid_dimensions_are_rejected(tmp_path: Path, field: str, value) -> None:
    service, _config_path = _service(tmp_path)
    with pytest.raises(AdHocImageGenerationError, match="divisible by 32"):
        service.submit({"mode": "txt2img", "prompt": "A stone key", field: value})


def test_img2img_requires_valid_image_data(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)
    with pytest.raises(AdHocImageGenerationError, match="reference image"):
        service.submit({"mode": "img2img", "prompt": "Edit it"})
    with pytest.raises(AdHocImageGenerationError, match="invalid or incomplete"):
        service.submit({"mode": "img2img", "prompt": "Edit it", "reference_image": base64.b64encode(b"bad").decode()})


def _finish_proxy_child(service: AdHocImageGenerationService, child: dict, *, success: bool) -> Path:
    ask_path = service.proxy_paths.ask_root() / child["ask_id"]
    answer_path = service.proxy_paths.answer_root() / child["ask_id"]
    answer_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(ask_path, answer_path)
    ask = json.loads((answer_path / "ask_manifest.json").read_text(encoding="utf-8"))
    expected = str(ask["expected_output"])
    if success:
        (answer_path / expected).write_bytes(png_bytes())
    (answer_path / "answer_manifest.json").write_text(json.dumps({
        "ask_id": child["ask_id"],
        "expected_output": expected,
        "status": "SUCCESS" if success else "ERROR",
        "error_message": "synthetic render failure" if not success else "",
    }), encoding="utf-8")
    output_files = service.proxy_client._file_inventory(answer_path)
    (answer_path / "proxy_result.json").write_text(json.dumps({"output_files": output_files}), encoding="utf-8")
    return answer_path


def test_progressive_answer_collection_preserves_partial_success_and_cleans_queue(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)
    result = service.submit({"mode": "txt2img", "prompt": "A glass forest spirit", "count": 2})
    job = service._jobs[result["request_id"]]
    successful = _finish_proxy_child(service, job["children"][0], success=True)
    failed = _finish_proxy_child(service, job["children"][1], success=False)

    status = service.status(result["request_id"])

    assert status["status"] == "PARTIAL"
    assert status["completed"] == 1
    assert status["failed"] == 1
    assert "synthetic render failure" in status["error"]
    image, media_type = service.image(result["request_id"], 0)
    assert image == png_bytes()
    assert media_type == "image/png"
    assert not successful.exists()
    assert not failed.exists()
    service.clear(result["request_id"])
    assert result["request_id"] not in service._jobs


def test_foreign_answer_is_rejected_and_preserved(tmp_path: Path) -> None:
    service, _config_path = _service(tmp_path)
    result = service.submit({"mode": "txt2img", "prompt": "An ivory lantern", "count": 1})
    job = service._jobs[result["request_id"]]
    child = job["children"][0]
    answer_path = _finish_proxy_child(service, child, success=True)
    ask_path = answer_path / "ask_manifest.json"
    ask = json.loads(ask_path.read_text(encoding="utf-8"))
    ask["ad_hoc_request_id"] = "another-request"
    ask_path.write_text(json.dumps(ask), encoding="utf-8")
    (answer_path / "proxy_result.json").unlink()
    proxy_result = {"output_files": service.proxy_client._file_inventory(answer_path)}
    (answer_path / "proxy_result.json").write_text(json.dumps(proxy_result), encoding="utf-8")

    status = service.status(result["request_id"])

    assert status["status"] == "FAILED"
    assert "ownership" in status["error"]
    assert answer_path.is_dir()
    service.proxy_client.remove_answer(child["ask_id"])
    service.proxy_client.remove_route(child["ask_id"])
    service.clear(result["request_id"])


def test_completed_results_survive_service_restart_until_cleared(tmp_path: Path) -> None:
    service, config_path = _service(tmp_path)
    result = service.submit({"mode": "txt2img", "prompt": "A red marble mask", "count": 1})
    job = service._jobs[result["request_id"]]
    child = job["children"][0]
    answer_path = _finish_proxy_child(service, child, success=True)
    status = service.status(result["request_id"])
    assert not answer_path.exists()

    restarted = AdHocImageGenerationService(
        ZetApp.from_config(config_path, validate_catalog=False), Path(__file__).resolve().parents[1],
    )
    assert restarted.status(result["request_id"]) == status
    assert restarted.image(result["request_id"], 0) == (png_bytes(), "image/png")
    restarted.clear(result["request_id"])
    with pytest.raises(KeyError, match="not found"):
        restarted.status(result["request_id"])


def test_clearing_one_result_preserves_other_indexes_and_prompts(tmp_path: Path) -> None:
    service, config_path = _service(tmp_path)
    result = service.submit({"mode": "txt2img", "prompt": "A silver lantern", "count": 2})
    request_id = result["request_id"]
    for child in service._jobs[request_id]["children"]:
        _finish_proxy_child(service, child, success=True)
    assert service.status(request_id)["completed"] == 2

    cleared = service.clear_image(request_id, 0)
    assert cleared["completed"] == 1
    assert cleared["images"] == [{"index": 1, "url": f"/api/image-generation/jobs/{request_id}/images/1"}]
    with pytest.raises(KeyError, match="not found"):
        service.image(request_id, 0)
    assert service.library_result(request_id, 1)[2]["prompt"] == "A silver lantern"

    restarted = AdHocImageGenerationService(
        ZetApp.from_config(config_path, validate_catalog=False), Path(__file__).resolve().parents[1],
    )
    assert restarted.status(request_id)["images"] == cleared["images"]
    assert restarted.image(request_id, 1) == (png_bytes(), "image/png")
    restarted.clear(request_id)


def test_image_generation_api_exposes_defaults_and_validates_dimensions(tmp_path: Path) -> None:
    config_path = write_project_fixture(tmp_path)
    with TestClient(create_app(config_path, validate_catalog_on_create=False)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert 'id="image-generation-page"' in page.text
        defaults = client.get("/api/image-generation/options").json()
        assert defaults["default_count"] == 4
        assert defaults["default_width"] == 1024
        assert defaults["default_height"] == 1024
        invalid = client.post("/api/image-generation/jobs", json={
            "mode": "txt2img", "prompt": "A stone moon", "width": 1025,
        })
        assert invalid.status_code == 400
        assert "divisible by 32" in invalid.json()["detail"]
