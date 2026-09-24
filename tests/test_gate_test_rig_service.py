import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from zet.services.candidate_review_contract import ReviewGate
from zet.services.file_proxy_client import FileProxyClient
from zet.services.gate_test_rig_service import GateTestRigService


class FakeBodyReferenceService:
    def __init__(self, image: Path):
        self.image = image
        self.run = {
            "run_id": "20260923_014156_870344", "character": "Tsaeytte", "phase": "Adult",
            "views": ["FRONT", "FRONT_LEFT_3_4"], "front_anchor": "c001",
            "candidates": [
                {"candidate_id": "c001", "view": "FRONT", "status": "COMPLETE", "image_path": str(image)},
                {"candidate_id": "c009", "view": "FRONT_LEFT_3_4", "status": "GATE_REJECTED", "image_path": str(image)},
                {"candidate_id": "c010", "view": "FRONT_LEFT_3_4", "status": "PENDING", "image_path": ""},
            ],
        }

    @staticmethod
    def review_gates(view):
        gates = [ReviewGate("orientation", f"TARGET: {view}", crop_head=False)]
        if view != "FRONT":
            gates.append(ReviewGate("body_identity", "Compare anchor and candidate", uses_anchor=True))
        return gates

    def list_runs(self):
        return [{"run_id": self.run["run_id"]}]

    def detail(self, run_id):
        assert run_id == self.run["run_id"]
        return self.run


class FakeHeadImageService:
    def __init__(self, image: Path):
        self.run = {
            "run_id": "20260924_062129_472332", "character": "Tsaeytte", "phase": "Adult",
            "views": ["FRONT", "FRONT_LEFT_3_4"], "front_anchor": "c001", "front_source": "",
            "candidates": [
                {"candidate_id": "c001", "view": "FRONT", "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(image)},
                {"candidate_id": "c009", "view": "FRONT_LEFT_3_4", "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(image)},
            ],
        }

    @staticmethod
    def review_gates(view, *, has_front_source=False):
        return [ReviewGate("gaze", f"TARGET: {view}; gaze follows the nose. Reply exactly TRUE or FALSE.",
                           uses_anchor=view != "FRONT")]

    def list_runs(self):
        return [{"run_id": self.run["run_id"]}]

    def detail(self, run_id):
        assert run_id == self.run["run_id"]
        return self.run

def make_service(tmp_path, monkeypatch):
    library = tmp_path / "library"
    queue = tmp_path / "queue"
    image = tmp_path / "candidate.png"
    Image.new("RGB", (64, 96), "white").save(image)
    app = SimpleNamespace(
        config=SimpleNamespace(base_library_path=str(library), base_ai_queue_path=str(queue)),
    )
    client = FileProxyClient(queue)
    path_service = SimpleNamespace(
        file_proxy_client=client,
        ask_root=lambda: client.ask_root,
        running_root=lambda: client.running_root,
        answer_root=lambda: client.answer_root,
        harvested_archive_root=lambda: queue / "Zet_File_Proxy_State" / "Archive" / "Harvested",
    )
    app.ai_proxy_service = SimpleNamespace(ai_proxy_path_service=path_service)
    fake_body = FakeBodyReferenceService(image)
    monkeypatch.setattr(GateTestRigService, "_body", lambda self: fake_body)
    return GateTestRigService(app, tmp_path), fake_body, client


def test_selection_exposes_disabled_orientation_and_only_existing_images(tmp_path, monkeypatch):
    service, _, _ = make_service(tmp_path, monkeypatch)
    value = service.selection("20260923_014156_870344", "FRONT_LEFT_3_4")
    assert [gate["key"] for gate in value["gates"]] == ["orientation", "body_identity"]
    assert [candidate["candidate_id"] for candidate in value["candidates"]] == ["c009"]
    assert value["front_anchor"] == "c001"


def test_gaze_gate_can_be_selected_and_queued_in_test_rig(tmp_path, monkeypatch):
    service, _, client = make_service(tmp_path, monkeypatch)
    image = tmp_path / "candidate.png"
    Image.new("RGB", (64, 96), "white").save(image)
    head = FakeHeadImageService(image)
    monkeypatch.setattr(GateTestRigService, "_head", lambda self: head)

    selection = service.selection(head.run["run_id"], "FRONT_LEFT_3_4", "head-image")
    assert [gate["key"] for gate in selection["gates"]] == ["gaze"]
    test = service.start_test({"pipeline": "head-image", "run_id": head.run["run_id"], "view": "FRONT_LEFT_3_4",
                              "config": {"gate": "gaze", "api": "generate", "model": "gemma4:12b",
                                         "think": False, "temperature": 0.1, "request_options": {}}})
    assert test["status"] == "RUNNING"
    manifest = json.loads((client.ready_path(test["attempts"][0]["ask_id"]) / "ask_manifest.json").read_text(encoding="utf-8"))
    assert manifest["gate"] == "gaze"
    assert manifest["image_files"] == ["front_anchor.png", "candidate.png"]


def test_named_configuration_round_trips_call_setup(tmp_path, monkeypatch):
    service, _, _ = make_service(tmp_path, monkeypatch)
    saved = service.save_config({"name": "Orientation chat", "config": {
        "gate": "orientation", "prompt": "Custom", "api": "chat", "model": "gemma4:12b",
        "think": None, "temperature": 1, "keep_alive": "30m",
        "options": {"num_predict": 42, "top_k": 20}, "request_options": {"logprobs": True},
    }})
    assert saved["config"]["api"] == "chat"
    assert service.configs() == [saved]


def test_gate_test_queues_isolated_work_and_records_each_input_hash(tmp_path, monkeypatch):
    service, body, client = make_service(tmp_path, monkeypatch)
    run_id = body.run["run_id"]
    test = service.start_test({"run_id": run_id, "view": "FRONT_LEFT_3_4", "config": {
        "gate": "body_identity", "api": "generate", "model": "gemma4:12b",
        "think": False, "temperature": 0.4, "keep_alive": "0",
        "options": {"num_ctx": 32768, "top_p": 0.8}, "request_options": {},
    }})
    assert test["status"] == "RUNNING"
    assert [item["candidate_id"] for item in test["attempts"]] == ["c009"]
    assert body.run["candidates"][1].get("gates") is None
    ask_id = test["attempts"][0]["ask_id"]
    manifest = json.loads((client.ready_path(ask_id) / "ask_manifest.json").read_text(encoding="utf-8"))
    assert manifest["pipeline"] == "Gate-Test-Rig"
    assert manifest["ollama_force_generate"] is True
    assert manifest["image_files"] == ["front_anchor.png", "candidate.png"]
    assert manifest["ollama_options"] == {"num_ctx": 32768, "top_p": 0.8, "temperature": 0.4}
    assert set(manifest["input_hashes"]) == {"front_anchor.png", "candidate.png"}
    assert set(manifest["source_image_hashes"]) == {"candidate", "front_anchor"}
    Path(test["attempts"][0]["output_path"]).write_text("TRUE", encoding="utf-8")
    finished = service.status(test["test_id"])
    assert finished["status"] == "COMPLETE"
    assert finished["attempts"][0]["result"] == "PASS"
    listed = service.list_tests()
    assert listed[0]["test_id"] == test["test_id"]
    assert listed[0]["status"] == "COMPLETE"
    assert listed[0]["complete_count"] == 1
