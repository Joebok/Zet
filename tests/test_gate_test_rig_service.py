import base64
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

from PIL import Image

from zet.services.file_proxy_client import FileProxyClient
from zet.services.gate_test_rig_service import GateTestRigService
from zet.services.local_gate_registry_service import LocalGatePipeline, LocalGateRegistryService
from zet.services.candidate_review_contract import ReviewGate


def make_service(tmp_path):
    library = tmp_path / "library"
    queue = tmp_path / "queue"
    app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(library)))
    client = FileProxyClient(queue)
    paths = SimpleNamespace(file_proxy_client=client, ask_root=lambda: client.ask_root,
                            running_root=lambda: client.running_root, answer_root=lambda: client.answer_root,
                            harvested_archive_root=lambda: queue / "Zet_File_Proxy_State" / "Archive" / "Harvested")
    app.ai_proxy_service = SimpleNamespace(ai_proxy_path_service=paths)
    return GateTestRigService(app, tmp_path), app, client


def image_data(color):
    import io
    stream = io.BytesIO()
    Image.new("RGB", (64, 96), color).save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def add_case(service, *, view, expected="PASS", color="white"):
    return service.registry.save_case({"pipeline": "body-reference", "gate": "proportion", "view": view,
                                       "expected": expected, "image_data": image_data(color)})


def test_registry_catalog_lists_views_and_default_statuses(tmp_path):
    service, app, _ = make_service(tmp_path)
    catalog = LocalGateRegistryService(app, tmp_path).catalog()
    assert {item["key"] for item in catalog["pipelines"]} == {
        "body-reference", "head-image", "local-character-assembly", "local-costume-dressing",
    }
    assert set(LocalGateRegistryService(app, tmp_path).catalog("local-character-assembly")["statuses"].values()) == {"Disabled"}
    assert set(LocalGateRegistryService(app, tmp_path).catalog("local-costume-dressing")["statuses"].values()) == {"Disabled"}
    body = service.catalog("body-reference")
    assert body["statuses"]["orientation"] == "Disabled"
    assert body["statuses"]["face"] == "Active"
    assert set(body["views"]) == set(body["gates_by_view"])


def test_gate_status_is_persisted_and_validated(tmp_path):
    service, app, _ = make_service(tmp_path)
    registry = LocalGateRegistryService(app, tmp_path)
    updated = registry.set_status("head-image", "gaze", "Warning")
    assert updated["statuses"]["gaze"] == "Warning"
    assert LocalGateRegistryService(app, tmp_path).status("head-image", "gaze") == "Warning"


def test_mixed_view_cases_run_with_per_view_prompts_and_snapshot_answers(tmp_path):
    service, _, client = make_service(tmp_path)
    front = add_case(service, view="FRONT", expected="PASS")
    side = add_case(service, view="LEFT_PROFILE", expected="FAIL", color="gray")
    started = service.start_test({"pipeline": "body-reference", "gate": "proportion",
                                  "config": {"model": "gemma4:12b", "api": "chat", "think": None},
                                  "prompt_overrides": {"FRONT": "Custom front-only prompt"}})
    assert started["status"] == "RUNNING"
    assert {item["case_id"] for item in started["attempts"]} == {front["case_id"], side["case_id"]}
    prompts = {item["view"]: (Path(item["case_snapshot"]) / "prompt.md").read_text(encoding="utf-8")
               for item in started["attempts"]}
    assert prompts["FRONT"] == "Custom front-only prompt"
    expected_prompt = next(item["prompt"] for item in service.registry.catalog("body-reference")["gates_by_view"]["LEFT_PROFILE"]
                           if item["key"] == "proportion")
    assert prompts["LEFT_PROFILE"] == expected_prompt
    for attempt in started["attempts"]:
        manifest = json.loads((client.ready_path(attempt["ask_id"]) / "ask_manifest.json").read_text(encoding="utf-8"))
        assert manifest["ollama_model"] == "gemma4:12b"
        assert "ollama_temperature" not in manifest and "ollama_keep_alive" not in manifest
        Path(attempt["output_path"]).write_text("TRUE", encoding="utf-8")
    finished = service.status(started["run_id"])
    assert finished["status"] == "COMPLETE"
    assert {item["result"] for item in finished["attempts"]} == {"PASS", "FAIL"}


def test_saved_test_packet_keeps_images_after_curated_case_deletion(tmp_path):
    service, _, _ = make_service(tmp_path)
    case = add_case(service, view="FRONT")
    run = service.start_test({"pipeline": "body-reference", "gate": "proportion",
                              "config": {"model": "gemma4:12b", "api": "generate", "think": False}})
    for attempt in run["attempts"]:
        Path(attempt["output_path"]).write_text("TRUE", encoding="utf-8")
    saved = service.save_test(run["run_id"], "Proportion baseline")
    service.registry.delete_case("body-reference", "proportion", case["case_id"])
    packet = service.review_packet(saved["test_id"])
    with zipfile.ZipFile(packet) as archive:
        names = archive.namelist()
        assert any(name.endswith("candidate.png") for name in names)
        assert any(name.endswith("run.json") for name in names)
    assert service.list_tests()[0]["name"] == "Proportion baseline"


def test_registered_future_pipeline_can_supply_custom_reference_roles(tmp_path):
    service, _, client = make_service(tmp_path)
    adapter = LocalGatePipeline(
        key="future-local", label="Future Local", views=("SIDE",),
        service_factory=lambda *_args: None,
        gates_for_view=lambda _service, _view: [ReviewGate("style", "Compare style.", input_roles=("style_reference",))],
        interpret=lambda _gate, _response: {"result": "PASS", "reason": ""},
    )
    service.registry.register_pipeline(adapter)
    try:
        case = service.registry.save_case({"pipeline": "future-local", "gate": "style", "view": "SIDE",
                                           "expected": "PASS", "image_data": image_data("white"),
                                           "reference_data": {"style_reference": image_data("blue")}})
        run = service.start_test({"pipeline": "future-local", "gate": "style",
                                  "config": {"model": "gemma4:12b", "api": "generate", "think": False}})
        attempt = run["attempts"][0]
        manifest = json.loads((client.ready_path(attempt["ask_id"]) / "ask_manifest.json").read_text(encoding="utf-8"))
        assert set(manifest["image_files"]) == {"candidate.png", "style_reference.png"}
        assert attempt["case_id"] == case["case_id"]
    finally:
        service.registry.pipelines.pop("future-local", None)
