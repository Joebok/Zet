import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from zet.services.ai_queue_lifecycle_service import AIQueueLifecycleService
from zet.services.config_service import Config
from zet.services.file_proxy_client import FileProxyClient


def _service(tmp_path: Path, monkeypatch) -> tuple[AIQueueLifecycleService, FileProxyClient]:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    queue = tmp_path / "Dropbox" / "AI_Queue"
    config = Config("library", "characters", "assets", "pipelines", str(queue))
    service = AIQueueLifecycleService(config)
    return service, service.file_proxy_client()


def _ready_answer(client: FileProxyClient, job_id: str, *, contents: bytes = b"image") -> Path:
    answer = client.answer_root / job_id
    answer.mkdir(parents=True)
    (answer / "ask_manifest.json").write_text(json.dumps({"ask_id": job_id, "consumer": "zet"}), encoding="utf-8")
    (answer / "answer_manifest.json").write_text(json.dumps({"ask_id": job_id, "status": "SUCCESS"}), encoding="utf-8")
    (answer / "job.json").write_text(json.dumps({"producer_id": socket.gethostname(), "route_required": False}), encoding="utf-8")
    (answer / "output.png").write_bytes(contents)
    record = {"path": "output.png", "size": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
    (answer / "proxy_result.json").write_text(json.dumps({"output_files": [record]}), encoding="utf-8")
    return answer


def test_verified_answer_moves_from_shared_queue_and_completion_purges_payload(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    shared = _ready_answer(client, "Ask_1")

    local = service.drain_answer(shared, client)

    assert not shared.exists()
    assert (local / "output.png").read_bytes() == b"image"
    service.finish_answer(local, {"status": "APPLIED", "answer_status": "SUCCESS"})
    assert not local.exists()
    assert service.read_receipt("Ask_1")["status"] == "APPLIED"


def test_incomplete_answer_is_left_on_shared_queue(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    shared = _ready_answer(client, "Ask_2")
    (shared / "output.png").write_bytes(b"partial")

    assert service.drain_ready_answers(client) == []
    assert shared.is_dir()


def test_debug_retains_completed_payload_locally(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    monkeypatch.setenv("ZET_AI_QUEUE_DEBUG", "1")
    local = _ready_answer(client, "Ask_3")
    local = service.drain_answer(local, client)

    service.finish_answer(local, {"status": "APPLIED", "answer_status": "SUCCESS"})

    assert not local.exists()
    assert (service.debug_root / "Ask_3" / "output.png").read_bytes() == b"image"


def test_foreign_producer_and_missing_route_stay_on_shared_queue(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    foreign = _ready_answer(client, "Ask_Foreign")
    job = json.loads((foreign / "job.json").read_text(encoding="utf-8"))
    job["producer_id"] = "OtherMachine"
    (foreign / "job.json").write_text(json.dumps(job), encoding="utf-8")
    unrouted = _ready_answer(client, "Ask_Unrouted")
    job = json.loads((unrouted / "job.json").read_text(encoding="utf-8"))
    job["route_required"] = True
    (unrouted / "job.json").write_text(json.dumps(job), encoding="utf-8")

    assert service.drain_ready_answers(client) == []
    assert foreign.is_dir() and unrouted.is_dir()


def test_copy_error_preserves_source_for_a_later_retry(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    shared = _ready_answer(client, "Ask_CopyError")

    with patch("zet.services.ai_queue_lifecycle_service.shutil.copytree", side_effect=OSError("Dropbox busy")):
        assert service.drain_ready_answers(client) == []

    assert shared.is_dir()
    assert not (service.inbox_root / shared.name).exists()


def test_durable_receipt_cleans_a_leftover_shared_duplicate(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    shared = _ready_answer(client, "Ask_Duplicate")
    service.write_receipt("Ask_Duplicate", {"status": "APPLIED", "answer_status": "SUCCESS"})

    service.drain_ready_answers(client)

    assert not shared.exists()


def test_stale_terminal_gate_is_recorded_as_failed_before_purge(tmp_path, monkeypatch):
    service, client = _service(tmp_path, monkeypatch)
    job_id = "Ask_LocalHeadImage_20260930_103450_335104_PR-002_framing_20260930_112006_221888"
    answer = client.answer_root / job_id
    answer.mkdir(parents=True)
    target = tmp_path / "deleted-run" / "analyses" / "PR-002"
    route = {"target_output_dir": str(target), "_producer_id": socket.gethostname(), "universe_id": "Moonsea"}
    (client.route_root).mkdir(parents=True, exist_ok=True)
    (client.route_root / f"{job_id}.json").write_text(json.dumps(route), encoding="utf-8")
    (answer / "job.json").write_text(json.dumps({"producer_id": socket.gethostname()}), encoding="utf-8")
    (answer / "ask_manifest.json").write_text(json.dumps({
        "ask_id": job_id, "task_type": "local_head_image_gate", "universe_id": "Moonsea",
        "local_head_image_run_id": "20260930_103450_335104", "candidate_id": "PR-002", "gate": "framing",
    }), encoding="utf-8")
    (answer / "answer_manifest.json").write_text(json.dumps({
        "status": "SUCCESS", "expected_output": "gate.txt", "completed_at": "2026-09-30T11:20:40",
    }), encoding="utf-8")
    (answer / "proxy_result.json").write_text(json.dumps({"status": "SUCCEEDED"}), encoding="utf-8")
    (answer / "gate.txt").write_text("FALSE\n", encoding="utf-8")
    (answer / "candidate.png").write_bytes(b"candidate evidence")
    (answer / "OLLAMA_PROMPT.md").write_text("gate prompt", encoding="utf-8")

    receipt = service.fail_stale_gate_answer(answer, client)

    assert receipt["status"] == "FAILED"
    assert receipt["gate_verdict"] == "FALSE"
    assert not answer.exists()
    assert not (client.route_root / f"{job_id}.json").exists()
    assert service.read_receipt(job_id)["failure_code"] == "STALE_GATE_DESTINATION"
    assert (Path(receipt["evidence_path"]) / "candidate.png").read_bytes() == b"candidate evidence"
