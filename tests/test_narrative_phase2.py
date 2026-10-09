"""Phase 2 contracts: model provenance, durable reruns and protected assembly."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image, ImageDraw
import pytest

from tests.test_narrative_generation import rig, complete, latest_job
from zet.models.narrative import new_id
from zet.services.narrative_assembly_service import png_bytes
from zet.services.narrative_generation_service import NarrativeGenerationService
from zet.services.narrative_prompt_service import llm_request
from zet.web.narrative_router import create_narrative_router


PROSE = {"scene": "Create a new illustration of a hopeful traveler.", "rendering": "Soft daylight."}
DRAFT = {"narrative": "An uncertain traveler arrives.", "staging": "Facing inward.",
         "physical_context": "Stone paving.", "framing": "Full body", "questions": []}


@pytest.mark.parametrize("action,payload", [("interview", DRAFT), ("synthesize", PROSE)])
def test_assembly_text_jobs_queue_before_sources_are_added(rig, action, payload):
    app, author, service, source_ids = rig
    target = author.create_target(*source_ids[:2], {"title": "Final assembly", "kind": "assembly"})
    ids = (*source_ids[:2], target["id"])
    detail = service.start(*ids, {"action": action, "message": "Plan the final scene"})
    job = latest_job(detail, action)
    assert job["status"] == "QUEUED"
    manifest = json.loads((service.proxy.client.ask_root / job["id"] / "ask_manifest.json").read_text())
    assert manifest["ollama_model"] == "general:latest"
    assert job["references"] == []
    completed = complete(service, ids, job["id"], payload)
    assert completed["jobs"][job["id"]]["status"] == "COMPLETE"
    with pytest.raises(ValueError, match="visible base backdrop"):
        service.start(*ids, {"action": "generate"})


def test_assembly_text_jobs_skip_cutout_and_freeze_sources(assembly_rig, monkeypatch):
    app, author, service, ids, record, _ = assembly_rig
    def unexpected_composition(*args):
        raise AssertionError("Text jobs must not prepare image cutouts")
    monkeypatch.setattr(app.narrative_assembly_service, "compose", unexpected_composition)
    detail = service.start(*ids, {"action": "synthesize"})
    job = latest_job(detail, "synthesize")
    assert job["status"] == "QUEUED"
    for original, frozen in zip(record["layers"], job["detail"]["layers"]):
        folder = author.repository.folder(*ids)
        assert (folder / frozen["source_file"]).read_bytes() == (folder / original["source_file"]).read_bytes()
        assert frozen["source_file"] != original["source_file"]


def test_models_are_independent_and_snapshotted(rig):
    app, author, service, ids = rig
    author.update_target(*ids, {"interview_model": "interview-a:latest", "prompt_model": "prompt-b:latest"})
    interviewed = service.start(*ids, {"action": "interview", "message": "Make him uncertain"})
    job = latest_job(interviewed, "interview")
    manifest = json.loads((service.proxy.client.ask_root / job["id"] / "ask_manifest.json").read_text())
    assert manifest["ollama_model"] == "interview-a:latest"
    assert manifest["ollama_allow_unmanaged_model"] is True
    author.update_target(*ids, {"interview_model": "new:latest"})
    detail = complete(service, ids, job["id"], DRAFT)
    assert detail["interview"][-1]["provenance"]["model"] == "interview-a:latest"
    written = service.start(*ids, {"action": "synthesize"})
    prompt_job = latest_job(written, "synthesize")
    assert prompt_job["model"] == "prompt-b:latest"
    detail = complete(service, ids, prompt_job["id"], PROSE)
    assert detail["prompt_provenance"]["model"] == "prompt-b:latest"
    assert detail["effective_models"]["interview_model"] == "new:latest"


@pytest.mark.parametrize("action,replay_action,payload", [("interview", "rerun_interview", DRAFT),
                                                         ("synthesize", "rerun_prompt", PROSE)])
def test_reruns_replay_exact_request_and_preserve_outputs(rig, action, replay_action, payload):
    app, author, service, ids = rig
    detail = service.start(*ids, {"action": action, "message": "A specific direction"})
    first = latest_job(detail, action)
    complete(service, ids, first["id"], payload)
    author.update_target(*ids, {"narrative": "Completely different now", "prompt_model": "other:latest",
                               "interview_model": "other:latest"})
    replay = service.start(*ids, {"action": replay_action, "job_id": first["id"]})
    second = latest_job(replay, action)
    assert second["request"] == first["request"]
    assert second["detail"]["narrative"] == first["detail"]["narrative"]
    assert second["model"] == "other:latest"
    changed = {**payload, "narrative": "Other interview output"} if action == "interview" else {**payload, "scene": "Other prompt output"}
    detail = complete(service, ids, second["id"], changed)
    assert detail["jobs"][first["id"]]["result"] != detail["jobs"][second["id"]]["result"]
    if action == "interview":
        assert len([entry for entry in detail["interview"] if entry["role"] == "assistant"]) == 2
        assert detail["narrative"] == "Other interview output"
    else:
        restored = author.update_target(*ids, {"use_prompt_job": first["id"]})
        assert restored["prompt"] == detail["jobs"][first["id"]]["result"]
        assert restored["prompt_provenance"]["model"] == first["model"]


def test_prompt_edits_candidates_and_legacy_defaults(rig):
    app, author, service, ids = rig
    detail = service.start(*ids, {"action": "synthesize"})
    job = latest_job(detail, "synthesize")
    detail = complete(service, ids, job["id"], PROSE)
    author.update_target(*ids, {"prompt": "My exact edited prompt", "prompt_model": "codex:new-model"})
    detail = service.start(*ids, {"action": "render"})
    candidate = detail["candidates"][detail["slots"][0]]
    assert candidate["prompt"] == "My exact edited prompt"
    assert candidate["prompt_provenance"]["model"] == "general:latest"
    assert candidate["prompt_provenance"]["edited"] is True
    assert not any(item["provider"] == "codex" and item["kind"] != "render" for item in detail["jobs"].values() if "provider" in item)
    stored = author.repository.read(*ids)
    for key in ("interview_model", "prompt_model", "prompt_provenance", "layers"):
        stored.pop(key)
    author.repository.write(stored, *ids)
    legacy = author.target(*ids)
    assert legacy["prompt_provenance"] == {}
    assert legacy["effective_models"]["prompt_model"] == app.config.ai_narrative_scene_model


def test_explicit_prompt_restore_is_not_overwritten_by_pending_output(rig):
    app, author, service, ids = rig
    first = latest_job(service.start(*ids, {"action": "synthesize"}), "synthesize")
    detail = complete(service, ids, first["id"], PROSE)
    chosen = detail["prompt"]
    second = latest_job(service.start(*ids, {"action": "synthesize"}), "synthesize")
    author.update_target(*ids, {"use_prompt_job": first["id"]})
    detail = complete(service, ids, second["id"], {**PROSE, "scene": "A later output"})
    assert detail["prompt"] == chosen
    assert "A later output" in detail["jobs"][second["id"]]["result"]


def test_repository_reads_coordinate_with_background_writes(rig):
    app, author, service, ids = rig
    started, finished = threading.Event(), threading.Event()
    result = []
    def reader():
        started.set()
        result.append(author.repository.read(*ids)["prompt"])
        finished.set()
    with author.repository.lock():
        thread = threading.Thread(target=reader)
        thread.start()
        assert started.wait(2)
        assert not finished.is_set()
        record = author.repository.read(*ids)
        record["prompt"] = "Updated under the workflow lock"
        author.repository.write(record, *ids)
    thread.join(timeout=2)
    assert finished.is_set() and result == ["Updated under the workflow lock"]


@pytest.mark.parametrize("model", ["codex:", "has spaces", 123])
def test_invalid_model_identifiers(rig, model):
    app, author, service, ids = rig
    with pytest.raises(ValueError):
        author.update_target(*ids, {"prompt_model": model})


def poll_until_done(service, ids, kind="synthesize"):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        detail = service.detail(*ids)
        if latest_job(detail, kind)["status"] in {"COMPLETE", "FAILED"}:
            return detail
        time.sleep(.01)
    pytest.fail("Local text job did not finish")


def fake_codex(service, monkeypatch, payload=PROSE, returncode=0):
    commands = []
    monkeypatch.setattr(service.codex, "executable", lambda: "codex-test")
    def runner(command, **kwargs):
        commands.append((command, kwargs))
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload), encoding="utf-8")
        return SimpleNamespace(returncode=returncode, stdout="", stderr="Unavailable model" if returncode else "")
    service.codex.runner = runner
    return commands


def test_codex_dispatch_provenance_and_custom_models(rig, monkeypatch):
    app, author, service, ids = rig
    commands = fake_codex(service, monkeypatch)
    author.update_target(*ids, {"prompt_model": "codex:a-new-model"})
    service.start(*ids, {"action": "synthesize"})
    detail = poll_until_done(service, ids)
    assert latest_job(detail, "synthesize")["status"] == "COMPLETE"
    assert detail["prompt_provenance"]["model"] == "codex:a-new-model"
    command, kwargs = commands[0]
    assert command[command.index("-m") + 1] == "a-new-model"
    assert command[command.index("-s") + 1] == "read-only"
    assert '--output-schema' in command and '--ignore-user-config' in command
    assert kwargs["input"] == latest_job(detail, "synthesize")["request"]
    assert not list(service.proxy.client.ask_root.glob("*/ask_manifest.json"))


@pytest.mark.parametrize("action,payload", [("interview", DRAFT), ("generate", PROSE)])
def test_codex_interview_and_generate_share_normal_lifecycle(rig, monkeypatch, action, payload):
    app, author, service, ids = rig
    fake_codex(service, monkeypatch, payload)
    author.update_target(*ids, {"interview_model": "codex:gpt-6-luna", "prompt_model": "codex:gpt-6-sol"})
    service.start(*ids, {"action": action})
    detail = poll_until_done(service, ids, action)
    assert latest_job(detail, action)["status"] == "COMPLETE"
    if action == "interview":
        assert detail["interview"][-1]["provenance"]["model"] == "codex:gpt-6-luna"
    else:
        candidate = detail["candidates"][detail["slots"][0]]
        assert candidate["status"] == "QUEUED"
        assert candidate["prompt_provenance"]["model"] == "codex:gpt-6-sol"
        assert (service.proxy.client.ask_root / latest_job(detail, "image")["id"]).exists()


def test_ollama_runtime_and_recoverable_legacy_model(rig):
    app, author, service, ids = rig
    detail = service.start(*ids, {"action": "synthesize"})
    job = latest_job(detail, "synthesize")
    stored = author.repository.read(*ids)
    for key in ("model", "provider", "provenance"):
        stored["jobs"][job["id"]].pop(key)
    author.repository.write(stored, *ids)
    refresh = service.detail
    service.detail = lambda *args: None
    try:
        complete(service, ids, job["id"], PROSE)
    finally:
        service.detail = refresh
    path = service.proxy.client.answer_root / job["id"] / "answer_manifest.json"
    answer = json.loads(path.read_text())
    answer["ollama_runtime"] = {"requested_alias": "general:latest", "effective_alias": "general:latest", "digest": "actual-digest"}
    path.write_text(json.dumps(answer))
    detail = service.detail(*ids)
    assert detail["prompt_provenance"]["model"] == "general:latest"
    assert detail["prompt_provenance"]["runtime"]["digest"] == "actual-digest"


@pytest.mark.parametrize("payload,code", [("not an object", 0), ({"scene": 42, "rendering": "light"}, 0),
                                        ({"scene": "", "rendering": "light"}, 0), (PROSE, 1)])
def test_codex_failures_are_inline_without_fallback(rig, monkeypatch, payload, code):
    app, author, service, ids = rig
    fake_codex(service, monkeypatch, payload, code)
    author.update_target(*ids, {"prompt_model": "codex:unavailable"})
    service.start(*ids, {"action": "synthesize"})
    detail = poll_until_done(service, ids)
    assert latest_job(detail, "synthesize")["status"] == "FAILED"
    assert latest_job(detail, "synthesize")["error"]
    assert detail["prompt"] == ""


def test_codex_restart_attempt_rejects_late_completion(rig, monkeypatch):
    app, author, service, ids = rig
    started, release = threading.Event(), threading.Event()
    monkeypatch.setattr(service.codex, "executable", lambda: "codex-test")
    def old_runner(command, **kwargs):
        started.set()
        release.wait(5)
        Path(command[command.index("--output-last-message")+1]).write_text(json.dumps({**PROSE, "scene": "Old output"}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    service.codex.runner = old_runner
    author.update_target(*ids, {"prompt_model": "codex:gpt-6-luna"})
    service.start(*ids, {"action": "synthesize"})
    service.detail(*ids)
    assert started.wait(2)
    old_attempt = latest_job(author.repository.read(*ids), "synthesize")["codex_attempt"]
    restarted = NarrativeGenerationService(author)
    fake_codex(restarted, monkeypatch, {**PROSE, "scene": "New output"})
    try:
        detail = poll_until_done(restarted, ids)
        assert latest_job(detail, "synthesize")["codex_attempt"] != old_attempt
        assert "New output" in detail["prompt"]
    finally:
        release.set()
        service.codex._attempts[old_attempt].join(timeout=2)
    assert "New output" in restarted.detail(*ids)["prompt"]


@pytest.fixture
def assembly_rig(rig):
    app, author, generation, ids = rig
    author.update_target(*ids, {"width": 256, "height": 256, "prompt": "Source group"})
    group = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    ImageDraw.Draw(group).rectangle((64, 32, 191, 223), fill=(220, 20, 30, 255))
    detail = generation.start(*ids, {"action": "render"})
    detail = complete(generation, ids, latest_job(detail, "image")["id"], png_bytes(group))
    group_id = detail["slots"][0]
    generation.candidate_action(*ids, group_id, {"action": "select"})
    backdrop = author.create_target(*ids[:2], {"title": "Blue courtyard", "kind": "backdrop", "prompt": "Source backdrop"})
    backdrop_ids = (*ids[:2], backdrop["id"])
    detail = generation.start(*backdrop_ids, {"action": "render"})
    detail = complete(generation, backdrop_ids, latest_job(detail, "image")["id"], png_bytes(Image.new("RGB", (512, 256), "blue")))
    background_id = detail["slots"][0]
    assembly = author.create_target(*ids[:2], {"title": "Final assembly", "kind": "assembly", "width": 256, "height": 256})
    assembly_ids = (*ids[:2], assembly["id"])
    record = author.update_target(*assembly_ids, {"layers": [
        {"target_id": backdrop["id"], "candidate_id": background_id, "role": "base"},
        {"target_id": ids[2], "candidate_id": group_id, "role": "group", "x": .2, "y": .2, "scale": .5},
    ]})
    return app, author, generation, assembly_ids, record, ids


def test_scene_reuses_its_existing_final_assembly(assembly_rig):
    _, author, _, assembly_ids, _, _ = assembly_rig
    existing_id = assembly_ids[2]
    before = author.repository.read(*assembly_ids[:2])["target_ids"]

    duplicate = author.create_target(*assembly_ids[:2], {"title": "Final assembly", "kind": "assembly"})

    assert duplicate["id"] == existing_id
    assert author.repository.read(*assembly_ids[:2])["target_ids"] == before


def test_concurrent_requests_create_only_one_final_assembly(rig):
    from concurrent.futures import ThreadPoolExecutor

    _, author, _, ids = rig
    barrier = threading.Barrier(2)

    def create_assembly():
        barrier.wait(timeout=5)
        return author.create_target(*ids[:2], {"title": "Final assembly", "kind": "assembly"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(create_assembly) for _ in range(2)]
        targets = [request.result(timeout=10) for request in requests]

    assert targets[0]["id"] == targets[1]["id"]
    assert [target["id"] for target in author.list_targets(*ids[:2])
            if target["kind"] == "assembly"] == [targets[0]["id"]]


def test_assembly_mode_defaults_validation_and_legacy_records(assembly_rig):
    _, author, _, ids, record, source_ids = assembly_rig
    assert record["assembly_mode"] == "finish_composite"
    record.pop("assembly_mode")
    author.repository.write(record, *ids)
    assert author.target(*ids)["assembly_mode"] == "finish_composite"
    for mode in ("unknown", None, []):
        with pytest.raises(ValueError, match="Choose finish_composite|assembly_mode must be text"):
            author.update_target(*ids, {"assembly_mode": mode})
    with pytest.raises(ValueError, match="Only final assemblies"):
        author.update_target(*source_ids, {"assembly_mode": "assemble_references"})
    assert author.update_target(*ids, {"assembly_mode": "assemble_references"})["assembly_mode"] == "assemble_references"


@pytest.mark.parametrize("action,payload", [("interview", DRAFT), ("synthesize", PROSE)])
def test_reference_assembly_text_jobs_without_sources(rig, action, payload):
    _, author, service, source_ids = rig
    target = author.create_target(*source_ids[:2], {"title": "Assembly", "kind": "assembly", "assembly_mode": "assemble_references"})
    ids = (*source_ids[:2], target["id"])
    detail = service.start(*ids, {"action": action})
    job = latest_job(detail, action)
    assert job["references"] == []
    assert '"reference_images": []' in job["request"]
    assert "Placed final scene" not in job["request"]
    result = complete(service, ids, job["id"], payload)
    assert result["jobs"][job["id"]]["status"] == "COMPLETE"


def test_reference_manifest_geometry_order_and_original_bytes(assembly_rig, monkeypatch):
    app, author, service, ids, record, _ = assembly_rig
    layers = deepcopy(record["layers"])
    first = {**layers[1], "z": 4, "x": -.25, "y": .75, "scale": .5}
    second = {**layers[1], "id": new_id(), "z": 4}
    back = {**layers[1], "id": new_id(), "z": -1}
    hidden = {**layers[1], "id": new_id(), "visible": False}
    record = author.update_target(*ids, {"assembly_mode": "assemble_references",
                                         "layers": [first, {**layers[0], "fit": "contain"}, second, back, hidden]})
    def forbidden(*args, **kwargs):
        raise AssertionError("Reference assembly must not compose or extract")
    monkeypatch.setattr(app.narrative_assembly_service, "compose", forbidden)
    monkeypatch.setattr(app.narrative_assembly_service, "cutout", forbidden)
    detail = service.start(*ids, {"action": "generate"})
    job = latest_job(detail, "generate")
    refs = job["references"]
    assert [ref["layer_id"] for ref in refs] == [layers[0]["id"], back["id"], first["id"], second["id"]]
    assert [ref["image_index"] for ref in refs] == [1, 2, 3, 4]
    assert refs[0]["fit"] == "contain"
    assert (refs[0]["source_width"], refs[0]["source_height"]) == (512, 256)
    assert (refs[2]["x"], refs[2]["y"], refs[2]["width"], refs[2]["height"]) == (-64, 192, 128, 128)
    folder = author.repository.folder(*ids)
    original = {layer["id"]: layer for layer in record["layers"]}
    for ref in refs:
        assert Path(ref["path"]).read_bytes() == (folder / original[ref["layer_id"]]["source_file"]).read_bytes()
    assert not (folder / job["assembly_snapshot"]["folder"] / "composite.png").exists()
    completed = complete(service, ids, job["id"], PROSE)
    prompt = completed["prompt"]
    assert "(-64, 192)" in prompt and "128 × 128" in prompt
    assert "<image2>, <image3>, <image4>" in prompt
    assert "canvas boundary" in prompt and "white margins" in prompt
    assert "assembled final scene" not in prompt
    image_job = latest_job(completed, "image")
    manifest = json.loads((service.proxy.client.ask_root / image_job["id"] / "ask_manifest.json").read_text())
    for supplied, frozen in zip(manifest["reference_files"], refs):
        assert {key: value for key, value in supplied.items() if key != "path"} == {key: value for key, value in frozen.items() if key != "path"}
        assert (service.proxy.client.ask_root / image_job["id"] / supplied["path"]).read_bytes() == Path(frozen["path"]).read_bytes()


@pytest.mark.parametrize("count", [10, 11])
def test_reference_limit_checked_before_slots_or_dispatch(assembly_rig, count):
    _, author, service, ids, record, _ = assembly_rig
    layers = [record["layers"][0]] + [{**record["layers"][1], "id": new_id()} for _ in range(count - 1)]
    author.update_target(*ids, {"assembly_mode": "assemble_references", "layers": layers, "prompt": "Assemble sources."})
    before = author.target(*ids)
    if count == 10:
        detail = service.start(*ids, {"action": "render"})
        assert len(latest_job(detail, "render")["references"]) == 10
    else:
        with pytest.raises(ValueError, match="ten visible"):
            service.start(*ids, {"action": "render"})
        after = author.target(*ids)
        assert after["slots"] == before["slots"] and after["jobs"] == before["jobs"]


def test_reference_render_requires_visible_base_before_slot_replacement(assembly_rig):
    _, author, service, ids, record, _ = assembly_rig
    author.update_target(*ids, {"assembly_mode": "assemble_references", "prompt": "Assemble.",
                                "layers": [{**layer, "visible": layer["role"] != "base"} for layer in record["layers"]]})
    with pytest.raises(ValueError, match="visible base backdrop"):
        service.start(*ids, {"action": "render"})
    assert author.target(*ids)["slots"] == [None] * 8


def test_reference_geometry_uses_full_non_square_source_aspect_ratio(assembly_rig):
    app, author, _, ids, record, _ = assembly_rig
    group = record["layers"][1]
    source = author.repository.folder(*ids) / group["source_file"]
    Image.new("RGBA", (400, 200), (220, 20, 30, 255)).save(source)
    record = author.update_target(*ids, {"assembly_mode": "assemble_references"})
    refs = app.narrative_assembly_service.reference_manifest(*ids[:2], record, required=True)
    assert (refs[1]["width"], refs[1]["height"]) == (128, 64)
    assert (refs[1]["source_width"], refs[1]["source_height"]) == (400, 200)


def test_reference_output_restart_retry_and_deleted_sources(assembly_rig):
    _, author, service, ids, record, source_ids = assembly_rig
    author.update_target(*ids, {"assembly_mode": "assemble_references", "prompt": "Assemble the original sources."})
    detail = service.start(*ids, {"action": "render"})
    candidate_id = detail["slots"][0]
    job = latest_job(detail, "image")
    parent = latest_job(detail, "render")
    author.update_target(*ids, {"assembly_mode": "finish_composite", "width": 512, "prompt": "Changed prompt", "layers": []})
    author.delete(*source_ids, confirmed=[record["layers"][1]["candidate_id"]])
    restarted = NarrativeGenerationService(author)
    detail = complete(restarted, ids, job["id"], png_bytes(Image.new("RGB", (32, 32), "green")))
    assert detail["candidates"][candidate_id]["status"] == "FAILED"
    assert "dimensions" in detail["candidates"][candidate_id]["error"]
    retried = restarted.candidate_action(*ids, candidate_id, {"action": "retry"})
    retry = latest_job(retried, "image")
    assert retry["assembly_mode"] == "assemble_references"
    manifest = json.loads((restarted.proxy.client.ask_root / retry["id"] / "ask_manifest.json").read_text())
    for supplied, frozen in zip(manifest["reference_files"], parent["references"]):
        assert {key: value for key, value in supplied.items() if key != "path"} == {key: value for key, value in frozen.items() if key != "path"}
        assert (restarted.proxy.client.ask_root / retry["id"] / supplied["path"]).read_bytes() == Path(frozen["path"]).read_bytes()
    assert manifest["render_overrides"]["width"] == 256
    assert (restarted.proxy.client.ask_root / retry["id"] / "prompt.md").read_text() == "Assemble the original sources."
    output = png_bytes(Image.new("RGBA", (256, 256), (10, 200, 30, 128)))
    complete(restarted, ids, retry["id"], output)
    assert restarted.image(*ids, candidate_id).read_bytes() == output
    with pytest.raises(KeyError, match="no assembly snapshot"):
        author.app.narrative_assembly_service.candidate_composite(*ids, candidate_id)


def test_mode_switch_stale_prompt_history_and_inflight_results(assembly_rig):
    _, author, service, ids, _, _ = assembly_rig
    detail = service.start(*ids, {"action": "synthesize"})
    old = latest_job(detail, "synthesize")
    completed = complete(service, ids, old["id"], PROSE)
    old_prompt = completed["prompt"]
    author.update_target(*ids, {"assembly_mode": "assemble_references"})
    assert author.target(*ids)["prompt"] == old_prompt
    with pytest.raises(ValueError, match="another assembly mode"):
        service.start(*ids, {"action": "render"})
    detail = service.start(*ids, {"action": "synthesize"})
    ref_job = latest_job(detail, "synthesize")
    author.update_target(*ids, {"assembly_mode": "finish_composite"})
    result = complete(service, ids, ref_job["id"], PROSE)
    assert result["prompt"] == old_prompt
    restored = author.update_target(*ids, {"use_prompt_job": ref_job["id"]})
    assert restored["assembly_mode"] == restored["prompt_provenance"]["assembly_mode"] == "assemble_references"
    assert restored["prompt"] == result["jobs"][ref_job["id"]]["result"]
    author.update_target(*ids, {"assembly_mode": "finish_composite", "prompt": "Manually rewritten."})
    assert author.target(*ids)["prompt_provenance"]["assembly_mode"] == "finish_composite"


def test_reference_prompt_rerun_uses_frozen_layout_after_source_deletion(assembly_rig):
    _, author, service, ids, record, source_ids = assembly_rig
    author.update_target(*ids, {"assembly_mode": "assemble_references"})
    detail = service.start(*ids, {"action": "synthesize"})
    original = latest_job(detail, "synthesize")
    complete(service, ids, original["id"], PROSE)
    author.delete(*source_ids, confirmed=[record["layers"][1]["candidate_id"]])
    author.update_target(*ids, {"assembly_mode": "finish_composite", "layers": []})
    replay = service.start(*ids, {"action": "rerun_prompt", "job_id": original["id"]})
    job = latest_job(replay, "synthesize")
    assert job["request"] == original["request"]
    assert job["assembly_mode"] == "assemble_references"
    assert [{key: value for key, value in ref.items() if key != "path"} for ref in job["references"]] == [
        {key: value for key, value in ref.items() if key != "path"} for ref in original["references"]]


def test_failed_reference_prompt_retry_keeps_original_mode_and_layout(assembly_rig):
    _, author, service, ids, record, source_ids = assembly_rig
    author.update_target(*ids, {"assembly_mode": "assemble_references"})
    detail = service.start(*ids, {"action": "generate", "count": 4})
    original = latest_job(detail, "generate")
    complete(service, ids, original["id"], PROSE, failed=True)
    author.delete(*source_ids, confirmed=[record["layers"][1]["candidate_id"]])
    author.update_target(*ids, {"assembly_mode": "finish_composite", "layers": []})
    detail = service.start(*ids, {"action": "generate", "count": 4, "retry_job_id": original["id"]})
    retry = latest_job(detail, "generate")
    assert retry["request"] == original["request"]
    assert retry["assembly_mode"] == "assemble_references"
    assert len(retry["references"]) == 2
    assert all(detail["candidates"][identifier]["assembly_mode"] == "assemble_references" for identifier in retry["candidate_ids"])
    result = complete(service, ids, retry["id"], PROSE)
    assert len([job for job in result["jobs"].values() if job["kind"] == "image"]) == 4
    assert result["assembly_mode"] == "finish_composite" and result["prompt"] == ""


def test_pinned_sources_survive_source_selection_and_deletion(assembly_rig):
    app, author, generation, ids, record, source_ids = assembly_rig
    before = app.narrative_assembly_service.preview(*ids)
    changed = generation.start(*source_ids, {"action": "render"})
    changed = complete(generation, source_ids, latest_job(changed, "image")["id"], png_bytes(Image.new("RGB", (256, 256), "yellow")))
    new_id = changed["slots"][1]
    generation.candidate_action(*source_ids, new_id, {"action": "select"})
    assert app.narrative_assembly_service.preview(*ids) == before
    author.delete(*source_ids, confirmed=[new_id])
    assert app.narrative_assembly_service.preview(*ids) == before
    author.update_target(*ids, {"layers": record["layers"]})
    assert app.narrative_assembly_service.preview(*ids) == before


@pytest.mark.parametrize("field,value", [("scale", 0), ("x", float("inf")), ("visible", "yes"),
                                        ("cutout", "invented"), ("fit", "stretch")])
def test_invalid_layer_controls(assembly_rig, field, value):
    app, author, generation, ids, record, _ = assembly_rig
    layers = deepcopy(record["layers"])
    layers[1][field] = value
    with pytest.raises(ValueError):
        author.update_target(*ids, {"layers": layers})


def test_no_cross_scene_sources_or_assembly_cycles(assembly_rig):
    app, author, generation, ids, record, _ = assembly_rig
    other = author.create_scene(ids[0], {"title": "Other scene"})
    source = author.create_target(ids[0], other["id"], {"title": "Other target"})
    for source_id in (source["id"], ids[2]):
        with pytest.raises(ValueError):
            author.update_target(*ids, {"layers": [{"target_id": source_id, "candidate_id": new_id()}]})


def test_alpha_and_opaque_cutout_corrections(assembly_rig):
    app, author, generation, ids, record, _ = assembly_rig
    service = app.narrative_assembly_service
    layer = record["layers"][1]
    image = Image.new("RGBA", (40, 30), (12, 34, 56, 128))
    assert png_bytes(service.cutout(image, layer)) == png_bytes(image)
    image = Image.new("RGB", (40, 30), "white")
    ImageDraw.Draw(image).rectangle((10, 5, 29, 24), fill="red")
    cut = service.cutout(image, layer)
    assert cut.getchannel("A").getpixel((0, 0)) == 0
    assert cut.getchannel("A").getpixel((20, 15)) == 255
    # Qwen can return RGBA with near-opaque alpha noise across a neutral background.
    noisy = image.convert("RGBA")
    noisy.putalpha(Image.new("L", image.size, 254))
    extracted = service.cutout(noisy, layer)
    assert extracted.getchannel("A").getpixel((0, 0)) == 0
    assert extracted.getchannel("A").getpixel((20, 15)) == 255
    layer = {**layer, "strokes": [{"mode": "remove", "x": .5, "y": .5, "radius": .1},
                                   {"mode": "keep", "x": .05, "y": .05, "radius": .05}]}
    corrected = service.cutout(image, layer)
    assert corrected.getchannel("A").getpixel((20, 15)) == 0
    assert corrected.getchannel("A").getpixel((2, 1)) == 255
    with pytest.raises(ValueError, match="empty mask"):
        service.cutout(Image.new("RGB", (40, 30), "white"), {**layer, "strokes": []})


def test_auto_extraction_is_repeatable_for_textured_sources(assembly_rig):
    app, author, generation, ids, record, _ = assembly_rig
    pixels = np.random.default_rng(17).integers(80, 240, (180, 260, 3), dtype=np.uint8)
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 259, 20), fill="white")
    draw.rectangle((0, 0, 20, 179), fill="white")
    draw.rectangle((240, 0, 259, 179), fill="white")
    draw.rectangle((80, 30, 179, 165), fill="darkgreen")
    layer = record["layers"][1]
    outputs = [png_bytes(app.narrative_assembly_service.cutout(image, layer)) for _ in range(3)]
    assert outputs[0] == outputs[1] == outputs[2]


def test_fit_clipping_depth_visibility_and_mask_protection(assembly_rig):
    app, author, generation, ids, record, _ = assembly_rig
    service = app.narrative_assembly_service
    raw, mask, protected = service.compose(*ids[:2], record)
    assert raw.getpixel((0, 0)) == (0, 0, 255)
    assert np.all(np.asarray(mask)[np.asarray(protected) > 0] == 0)
    layers = deepcopy(record["layers"])
    layers[0]["fit"] = "contain"
    layers[1]["visible"] = False
    updated = author.update_target(*ids, {"layers": layers})
    contained, _, _ = service.compose(*ids[:2], updated)
    assert contained.getpixel((0, 0)) == (255, 255, 255)
    layers[1].update(visible=True, x=-.3, y=-.1)
    updated = author.update_target(*ids, {"layers": layers})
    clipped, _, _ = service.compose(*ids[:2], updated)
    assert clipped.size == (256, 256)


def test_overlapping_layers_obey_authored_depth(assembly_rig):
    app, author, generation, ids, record, _ = assembly_rig
    other = author.create_target(*ids[:2], {"title": "Translucent blue group", "prompt": "Blue group"})
    other_ids = (*ids[:2], other["id"])
    detail = generation.start(*other_ids, {"action": "render"})
    detail = complete(generation, other_ids, latest_job(detail, "image")["id"],
                      png_bytes(Image.new("RGBA", (256, 256), (0, 0, 200, 128))))
    layers = deepcopy(record["layers"])
    layers.append({"target_id": other["id"], "candidate_id": detail["slots"][0], "role": "group",
                   "x": .2, "y": .2, "scale": .5, "z": 9})
    record = author.update_target(*ids, {"layers": layers})
    above, _, _ = app.narrative_assembly_service.compose(*ids[:2], record)
    layers = deepcopy(record["layers"])
    layers[-1]["z"] = -9
    record = author.update_target(*ids, {"layers": layers})
    below, _, _ = app.narrative_assembly_service.compose(*ids[:2], record)
    assert above.getpixel((115, 100)) != below.getpixel((115, 100))
    assert below.getpixel((115, 100)) == (220, 20, 30)


def test_extreme_scale_only_allocates_visible_pixels(assembly_rig, monkeypatch):
    app, author, generation, ids, record, _ = assembly_rig
    layers = deepcopy(record["layers"])
    layers[1].update(scale=4, x=-.5, y=-.5)
    record = author.update_target(*ids, {"layers": layers})
    resize = Image.Image.resize
    def bounded_resize(image, size, *args, **kwargs):
        assert size[0] <= 256 and size[1] <= 256
        return resize(image, size, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "resize", bounded_resize)
    canvas, _, _ = app.narrative_assembly_service.compose(*ids[:2], record)
    assert canvas.size == (256, 256)


def test_finishing_uses_immutable_snapshot_and_preserves_pixels(assembly_rig):
    app, author, generation, ids, record, source_ids = assembly_rig
    author.update_target(*ids, {"prompt": "Blend joins only."})
    detail = generation.start(*ids, {"action": "render", "count": 4})
    candidate = detail["candidates"][detail["slots"][0]]
    snapshot = candidate["assembly_snapshot"]
    root = author.repository.folder(*ids) / snapshot["folder"]
    raw = np.array(Image.open(root / "composite.png"))
    mask = np.array(Image.open(root / "edit-mask.png"))
    protected = np.array(Image.open(root / "protected.png")) > 0
    layers = deepcopy(record["layers"])
    layers[1]["x"] = .6
    author.update_target(*ids, {"layers": layers})
    author.delete(*source_ids, confirmed=[record["layers"][1]["candidate_id"]])
    for job in [item for item in detail["jobs"].values() if item["kind"] == "image"]:
        detail = complete(generation, ids, job["id"], png_bytes(Image.new("RGB", (256, 256), "green")))
    final = np.array(Image.open(generation.image(*ids, candidate["id"])))
    assert np.array_equal(final[protected], raw[protected])
    assert np.array_equal(final[mask == 0], raw[mask == 0])
    assert np.any(final[mask > 0] != raw[mask > 0])
    assert sum(item["status"] == "COMPLETE" for item in detail["candidates"].values()) == 4


def test_finishing_rejects_wrong_dimensions_and_replays_deleted_sources(assembly_rig):
    app, author, generation, ids, record, source_ids = assembly_rig
    detail = generation.start(*ids, {"action": "generate"})
    job = latest_job(detail, "generate")
    request, _ = llm_request(author.target(*ids), "generate")
    assert "source_groups" in request and "plain neutral background" not in request
    detail = complete(generation, ids, job["id"], PROSE)
    assert "No people" not in detail["prompt"] and "<image1>" in detail["prompt"]
    image_job = latest_job(detail, "image")
    detail = complete(generation, ids, image_job["id"], png_bytes(Image.new("RGB", (32, 32), "green")))
    assert detail["candidates"][detail["slots"][0]]["status"] == "FAILED"
    assert "dimensions" in detail["candidates"][detail["slots"][0]]["error"]
    author.delete(*source_ids, confirmed=[record["layers"][1]["candidate_id"]])
    author.update_target(*ids, {"prompt_model": "other:latest"})
    replay = generation.start(*ids, {"action": "rerun_prompt", "job_id": job["id"]})
    assert latest_job(replay, "synthesize")["request"] == job["request"]


def test_assembly_routes_and_protected_deletion(assembly_rig):
    app, author, generation, ids, record, _ = assembly_rig
    api = FastAPI()
    api.include_router(create_narrative_router(lambda: app))
    client = TestClient(api)
    base = f"/api/narrative/stories/{ids[0]}/scenes/{ids[1]}/targets/{ids[2]}"
    assert client.get(base + "/composite?download=true").headers["content-disposition"].startswith("attachment")
    layer = record["layers"][1]["id"]
    for kind in ("source", "cutout", "overlay"):
        assert client.get(base + f"/layers/{layer}/image?kind={kind}").status_code == 200
    author.update_target(*ids, {"prompt": "Blend joins"})
    detail = generation.start(*ids, {"action": "render"})
    detail = complete(generation, ids, latest_job(detail, "image")["id"], png_bytes(Image.new("RGB", (256, 256), "green")))
    candidate = detail["slots"][0]
    generation.candidate_action(*ids, candidate, {"action": "select"})
    assert client.get(base + f"/candidates/{candidate}/composite").status_code == 200
    assert client.request("DELETE", base).status_code == 409
