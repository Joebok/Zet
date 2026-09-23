import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from zet.services.file_proxy_client import FileProxyClient
from zet.services.local_body_reference_service import (
    LocalBodyReferenceError,
    LocalBodyReferenceService,
    METHOD_FRONT_CONDITIONED,
    METHOD_TEXT_FIRST,
    ORIENTATION_VIEW_DEFINITIONS,
    _parse_orientation_gate_verdict,
    _parse_passing_gate_verdict,
)
from zet.services.candidate_review_contract import parse_rejection_verdict, validate_ranking
from zet.services.prompt_template_service import filter_prompt_variant_blocks
from zet.services.comfyui_workflow_registry import (
    QWEN_BODY_REFERENCE_EDIT_WORKFLOW,
    QWEN_BODY_REFERENCE_TEXT_WORKFLOW,
    compile_prompt_workflow,
)


def make_service(tmp_path: Path) -> LocalBodyReferenceService:
    project = tmp_path / "project"
    library = tmp_path / "library"
    (project / "Config").mkdir(parents=True)
    (project / "Config" / "Prompt_View_Text.json").write_text(
        json.dumps({"views": {key: {"label": key} for key in (
            "FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE",
            "RIGHT_PROFILE", "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK",
        )}}), encoding="utf-8"
    )
    app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(library)))
    return LocalBodyReferenceService(app, project)


def create_legacy_run(service: LocalBodyReferenceService, payload: dict) -> dict:
    """Create a version 1 fixture for tests that exercise the retained legacy path."""
    run = service.create_run(payload)
    root = Path(run["root"])
    spec_path = root / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec.update(schema_version=1, review_version=1)
    spec.pop("selected_views", None)
    spec.pop("rankings", None)
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return service.detail(run["run_id"])


def test_preview_has_eight_views_and_seventy_two_candidates(tmp_path):
    service = make_service(tmp_path)
    plan = service.preview({"character": "Tsaeytte", "phase": "Adult"})
    assert plan["views"][0] == "FRONT"
    assert len(plan["views"]) == 8
    assert plan["candidate_count"] == 44
    assert plan["methods"] == [METHOD_FRONT_CONDITIONED]


def test_new_run_uses_version_two_review_contract(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 2,
                              "other_count": 1, "seeds": list(range(9))})
    assert run["schema_version"] == run["review_version"] == 2
    assert run["selected_views"] == {}
    assert run["rankings"] == {}
    assert all(candidate["gates"] == {} for candidate in run["candidates"])
    assert service.gate_prompt(run["run_id"], "FRONT_LEFT_3_4", "orientation").startswith(
        "TARGET: FRONT_LEFT_3_4\n\nAuthoritative visual definition:\n\n"
    )


def test_gate_contracts_are_narrow_and_verdicts_are_exact():
    front = LocalBodyReferenceService.review_gates("FRONT")
    other = LocalBodyReferenceService.review_gates("LEFT_PROFILE")
    assert [gate.key for gate in front] == ["face", "proportion", "framing", "orientation"]
    assert [gate.key for gate in other] == ["face", "proportion", "framing", "orientation", "body_identity"]
    assert front[0].crop_head and other[-1].uses_anchor
    assert "LEFT_PROFILE" in other[3].prompt
    assert parse_rejection_verdict(" false \n") == "FALSE"
    with pytest.raises(ValueError):
        parse_rejection_verdict("FALSE because it looks fine")
    with pytest.raises(ValueError):
        validate_ranking({"ranking": [{"candidate_id": "c001", "reason": "best"}]}, ["c001", "c002"])


def test_body_reference_gates_use_their_ollama_settings(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    front = next(item for item in run["candidates"] if item["view"] == "FRONT")
    candidate = next(item for item in run["candidates"] if item["view"] == "FRONT_LEFT_3_4")
    image = Path(run["root"]) / "candidate.png"
    Image.new("RGB", (64, 64)).save(image)
    for item in (front, candidate):
        service._candidate_update(run["run_id"], item["candidate_id"], {"image_path": str(image)})
    state_path = Path(run["root"]) / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["front_anchor"] = front["candidate_id"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    client = FileProxyClient(tmp_path / "queue")
    service.app.ai_proxy_service = SimpleNamespace(
        ai_proxy_path_service=SimpleNamespace(file_proxy_client=client))

    for gate in service.review_gates(candidate["view"]):
        record = service._queue_review_gate(run["run_id"], candidate["candidate_id"], gate)
        manifest = json.loads((client.ready_path(record["ask_id"]) / "ask_manifest.json").read_text())
        if gate.key == "orientation":
            assert manifest["ollama_chat"] is True
            assert manifest["ollama_think"] is False
            assert manifest["ollama_temperature"] == 1.0
        else:
            assert manifest["ollama_think"] is True
            assert "ollama_chat" not in manifest
    service._run_face_gate(run["run_id"], front["candidate_id"])
    legacy_ask = service.detail(run["run_id"])["candidates"][0]["face_gate"]["ask_id"]
    manifest = json.loads((client.ready_path(legacy_ask) / "ask_manifest.json").read_text())
    assert manifest["ollama_think"] is True


def test_orientation_prompts_and_verdicts():
    assert len(ORIENTATION_VIEW_DEFINITIONS) == 8
    for view in ORIENTATION_VIEW_DEFINITIONS:
        prompt = next(gate.prompt for gate in LocalBodyReferenceService.review_gates(view)
                      if gate.key == "orientation")
        assert prompt.startswith(f"TARGET: {view}\n\nAuthoritative visual definition:\n\n- ")
        assert "Do not derive or reinterpret the view name." in prompt
        assert "Return TRUE when it matches. Return FALSE when it does not match." in prompt
        assert prompt.endswith("TRUE\nor\nFALSE: <brief visible reason>\n\nDo not explain your reasoning.")
    assert "- The near side of the body appears on IMAGE_RIGHT.\n" in ORIENTATION_VIEW_DEFINITIONS["FRONT_LEFT_3_4"]
    assert _parse_orientation_gate_verdict("TRUE\n") == ("FALSE", "")
    assert _parse_orientation_gate_verdict("FALSE: torso faces front\n") == ("TRUE", "torso faces front")
    assert _parse_orientation_gate_verdict("FALSE") == ("TRUE", "")
    with pytest.raises(ValueError):
        _parse_orientation_gate_verdict("TRUE: torso faces front")
    with pytest.raises(ValueError):
        _parse_orientation_gate_verdict("FALSE: torso faces front\nextra explanation")


def test_gate_prompts_use_true_for_positive_checks():
    gates = {gate.key: gate.prompt for gate in LocalBodyReferenceService.review_gates("LEFT_PROFILE")}
    assert "Answer TRUE only if obvious facial features are visibly rendered." in gates["face"]
    assert "Are the head-to-body proportions plausible" in gates["proportion"]
    assert "Answer TRUE if the proportions are plausible" in gates["proportion"]
    assert "Is the figure substantially complete" in gates["framing"]
    assert "Answer TRUE if the entire figure is substantially present" in gates["framing"]
    assert "could these plausibly represent the same underlying body?" in gates["body_identity"]
    assert "Answer TRUE if the physiques could plausibly be the same body" in gates["body_identity"]
    assert _parse_passing_gate_verdict(" TRUE\n") == ("FALSE", "")
    assert _parse_passing_gate_verdict("FALSE") == ("TRUE", "")


def test_gate_answer_polarity_at_review_boundary(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    output = Path(run["root"]) / "gate_answer.txt"
    for key, answer, expected in [
        ("face", "TRUE", ("TRUE", "")),
        ("proportion", "TRUE", ("FALSE", "")),
        ("framing", "FALSE", ("TRUE", "")),
        ("orientation", "FALSE: facing front", ("TRUE", "facing front")),
        ("body_identity", "TRUE", ("FALSE", "")),
    ]:
        output.write_text(answer, encoding="utf-8")
        service._candidate_update(run["run_id"], "c001", {
            "gates": {key: {"status": "QUEUED", "output_path": str(output)}}
        })
        assert service._wait_for_review_gate(run["run_id"], "c001", key) == expected


def test_gates_stop_on_first_obvious_defect_and_keep_rejected_render(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    image = Path(run["root"]) / "render.png"
    image.write_bytes(b"render")
    service._candidate_update(run["run_id"], "c001", {"status": "WAITING_FOR_GATES", "image_path": str(image)})
    queued = []
    verdicts = iter([("FALSE", ""), ("FALSE", ""), ("TRUE", "")])

    def queue(_run_id, _candidate_id, gate):
        queued.append(gate.key)
        record = {"status": "QUEUED", "input_hashes": {"candidate": service._hash(image), "front_anchor": ""}}
        service._candidate_update(run["run_id"], "c001", {"gates": {**(service.detail(run["run_id"])["candidates"][0].get("gates") or {}), gate.key: record}})
        return record

    monkeypatch.setattr(service, "_queue_review_gate", queue)
    monkeypatch.setattr(service, "_wait_for_review_gate", lambda *_args: next(verdicts))
    assert service._run_candidate_gates(run["run_id"], "c001") is True
    rejected = service.detail(run["run_id"])["candidates"][0]
    assert queued == ["face", "proportion", "framing"]
    assert rejected["status"] == "GATE_REJECTED"
    assert rejected["rejection_gate"] == "framing"
    assert rejected["image_path"] == str(image)
    assert image.is_file()


def test_orientation_gate_is_disabled_without_queuing_and_archives_old_failure(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    image = Path(run["root"]) / "render.png"
    image.write_bytes(b"render")
    service._candidate_update(run["run_id"], "c001", {
        "status": "WAITING_FOR_GATES", "image_path": str(image),
        "gates": {"orientation": {"status": "FAILED", "error": "Ollama returned no answer",
                                "ask_id": "old-ask", "prompt_sha256": "old-prompt",
                                "input_hashes": {"candidate": service._hash(image), "front_anchor": ""}}},
    })
    queued = []

    def queue(_run_id, _candidate_id, gate):
        queued.append(gate.key)
        return {"status": "QUEUED", "input_hashes": {"candidate": service._hash(image), "front_anchor": ""}}

    monkeypatch.setattr(service, "_queue_review_gate", queue)
    monkeypatch.setattr(service, "_wait_for_review_gate", lambda _run_id, _candidate_id, key:
                        ("FALSE", ""))
    assert service._run_candidate_gates(run["run_id"], "c001") is True
    assert queued == ["face", "proportion", "framing"]
    candidate = service.detail(run["run_id"])["candidates"][0]
    assert candidate["status"] == "WAITING_FOR_HUMAN_REVIEW"
    assert candidate["gates"]["orientation"]["status"] == "DISABLED"
    assert candidate["gates"]["orientation"]["verdict"] == "FALSE"
    assert "ask_id" not in candidate["gates"]["orientation"]
    assert candidate["gate_history"][-1]["gates"]["orientation"]["ask_id"] == "old-ask"


def test_old_orientation_rejection_is_reviewed_and_ranked(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    front = Path(run["root"]) / "front.png"
    image = Path(run["root"]) / "candidate.png"
    front.write_bytes(b"front")
    image.write_bytes(b"candidate")
    candidate = next(item for item in run["candidates"] if item["view"] == "FRONT_LEFT_3_4")
    candidate_id = candidate["candidate_id"]
    service._run_update(run["run_id"], front_anchor="c001")
    service._candidate_update(run["run_id"], "c001", {"image_path": str(front)})
    hashes = {"candidate": service._hash(image), "front_anchor": ""}
    gates = {key: {"status": "COMPLETE", "verdict": "FALSE", "input_hashes": hashes}
             for key in ("face", "proportion", "framing")}
    gates["orientation"] = {"status": "COMPLETE", "verdict": "TRUE", "reason": "IMAGE_RIGHT",
                            "ask_id": "old-orientation-ask", "input_hashes": hashes}
    service._candidate_update(run["run_id"], candidate_id, {
        "status": "GATE_REJECTED", "rejection_gate": "orientation",
        "image_path": str(image), "gates": gates,
    })
    queued = []

    def queue(_run_id, _candidate_id, gate):
        queued.append(gate.key)
        return {"status": "QUEUED", "input_hashes": {
            "candidate": service._hash(image), "front_anchor": service._hash(front)}}

    monkeypatch.setattr(service, "_queue_review_gate", queue)
    monkeypatch.setattr(service, "_wait_for_review_gate", lambda *_args: ("FALSE", ""))
    ranked = service.rank_view(run["run_id"], "FRONT_LEFT_3_4")
    reviewed = next(item for item in ranked["candidates"] if item["candidate_id"] == candidate_id)
    assert reviewed["status"] == "WAITING_FOR_HUMAN_REVIEW"
    assert reviewed["rejection_gate"] == ""
    assert reviewed["gates"]["orientation"]["status"] == "DISABLED"
    assert reviewed["gate_history"][-1]["gates"]["orientation"]["ask_id"] == "old-orientation-ask"
    assert queued == ["body_identity"]
    assert ranked["rankings"]["FRONT_LEFT_3_4"]["ordered_candidate_ids"] == [candidate_id]


def test_empty_ranking_and_rerun_failed_archive_gate_review(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    image = Path(run["root"]) / "rejected.png"
    image.write_bytes(b"rejected")
    service._candidate_update(run["run_id"], "c001", {
        "status": "GATE_REJECTED", "image_path": str(image), "rejection_gate": "face",
        "gates": {"face": {"status": "COMPLETE", "verdict": "TRUE"}},
    })
    empty = service.rank_view(run["run_id"], "FRONT")
    assert empty["rankings"]["FRONT"]["status"] == "EMPTY"
    rerun = service.rerun_failed_view(run["run_id"], "FRONT")
    candidate = next(item for item in rerun["candidates"] if item["candidate_id"] == "c001")
    assert candidate["status"] == "PENDING"
    assert candidate["image_path"] == ""
    assert candidate["review_history"][-1]["gates"]["face"]["verdict"] == "TRUE"
    assert image.is_file()


def test_single_survivor_is_ranked_without_luna_and_can_be_selected(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    image = Path(run["root"]) / "front.png"
    image.write_bytes(b"front image")
    image_hash = service._hash(image)
    gates = {gate.key: {"status": "COMPLETE", "verdict": "FALSE",
                        "input_hashes": {"candidate": image_hash, "front_anchor": ""}}
             for gate in service.review_gates("FRONT")}
    service._candidate_update(run["run_id"], "c001", {
        "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(image), "gates": gates,
    })
    ranked = service.rank_view(run["run_id"], "FRONT")
    assert ranked["rankings"]["FRONT"]["ordered_candidate_ids"] == ["c001"]
    assert ranked["rankings"]["FRONT"]["model"] == "deterministic-single-survivor"
    selected = service.select_view(run["run_id"], "FRONT", "c001")
    assert selected["front_anchor"] == "c001"
    assert selected["selected_views"] == {"FRONT": "c001"}


def test_luna_ranking_order_is_advisory_and_anchor_changes_invalidate_other_views(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 2,
                              "other_count": 1, "seeds": list(range(9))})
    image_paths = {}
    for candidate_id in ("c001", "c002"):
        image = Path(run["root"]) / f"{candidate_id}.png"
        image.write_bytes(candidate_id.encode())
        image_paths[candidate_id] = image
        image_hash = service._hash(image)
        gates = {gate.key: {"status": "COMPLETE", "verdict": "FALSE",
                            "input_hashes": {"candidate": image_hash, "front_anchor": ""}}
                 for gate in service.review_gates("FRONT")}
        service._candidate_update(run["run_id"], candidate_id, {
            "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(image), "gates": gates,
        })

    def fake_luna(command, **kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({"ranking": [
            {"candidate_id": "c001", "reason": "Sharper orientation."},
            {"candidate_id": "c002", "reason": "Better silhouette."},
        ]}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("zet.services.local_body_reference_service.subprocess.run", fake_luna)
    ranked = service.rank_view(run["run_id"], "FRONT")
    assert ranked["rankings"]["FRONT"]["ordered_candidate_ids"] == ["c001", "c002"]
    moved = service.move_candidate_rank(run["run_id"], "FRONT", "c002", "up")
    assert moved["rankings"]["FRONT"]["ordered_candidate_ids"] == ["c002", "c001"]
    assert moved["rankings"]["FRONT"]["luna_ordered_candidate_ids"] == ["c001", "c002"]
    service.update_candidate(run["run_id"], "c001", {"decision": "reject", "notes": ""})
    assert service.detail(run["run_id"])["rankings"]["FRONT"]["status"] == "COMPLETE"
    selected = service.select_view(run["run_id"], "FRONT", "c002")
    assert selected["front_anchor"] == "c002"

    other_image = Path(run["root"]) / "other.png"
    other_image.write_bytes(b"old anchor generation")
    service._candidate_update(run["run_id"], "c003", {
        "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(other_image),
    })
    root = Path(run["root"])
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    state.setdefault("selected_views", {})["FRONT_LEFT_3_4"] = "c003"
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    service.update_candidate(run["run_id"], "c001", {"decision": "undecided", "notes": ""})
    switched = service.select_view(run["run_id"], "FRONT", "c001")
    assert "FRONT_LEFT_3_4" not in switched["selected_views"]
    assert next(item for item in switched["candidates"] if item["candidate_id"] == "c003")["status"] == "PENDING"


def test_later_view_requires_current_front_anchor_hash(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "front_count": 1,
                              "other_count": 1, "seeds": list(range(8))})
    anchor_image = Path(run["root"]) / "anchor.png"
    anchor_image.write_bytes(b"accepted anchor")
    anchor_hash = service._hash(anchor_image)
    front_gates = {gate.key: {"status": "COMPLETE", "verdict": "FALSE",
                              "input_hashes": {"candidate": anchor_hash, "front_anchor": ""}}
                   for gate in service.review_gates("FRONT")}
    service._candidate_update(run["run_id"], "c001", {
        "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(anchor_image), "gates": front_gates,
    })
    service.rank_view(run["run_id"], "FRONT")
    service.select_view(run["run_id"], "FRONT", "c001")

    other_view = "FRONT_LEFT_3_4"
    candidate_image = Path(run["root"]) / "left.png"
    candidate_image.write_bytes(b"left view")
    candidate_hash = service._hash(candidate_image)
    gates = {gate.key: {"status": "COMPLETE", "verdict": "FALSE",
                        "input_hashes": {"candidate": candidate_hash,
                                         "front_anchor": anchor_hash if gate.uses_anchor else ""}}
             for gate in service.review_gates(other_view)}
    service._candidate_update(run["run_id"], "c002", {
        "status": "WAITING_FOR_HUMAN_REVIEW", "image_path": str(candidate_image), "gates": gates,
    })
    candidate = next(item for item in service.detail(run["run_id"])["candidates"] if item["candidate_id"] == "c002")
    assert candidate["view"] == other_view, candidate
    assert candidate["status"] == "WAITING_FOR_HUMAN_REVIEW", candidate
    assert not candidate.get("rejection_gate"), candidate
    assert candidate.get("human_review", {}).get("decision") == "undecided", candidate
    assert service.detail(run["run_id"])["front_anchor"] == "c001"
    assert candidate["gates"]["body_identity"]["input_hashes"]["front_anchor"] == anchor_hash
    assert candidate["gates"]["body_identity"]["input_hashes"]["candidate"] == candidate_hash
    assert all(candidate["gates"][gate.key]["verdict"] == "FALSE"
               and candidate["gates"][gate.key]["input_hashes"]["candidate"] == service._hash(candidate_image)
               and (not gate.uses_anchor or candidate["gates"][gate.key]["input_hashes"]["front_anchor"] == service._hash(anchor_image))
               for gate in service.review_gates(other_view))
    ranked = service.rank_view(run["run_id"], other_view)
    assert ranked["rankings"][other_view]["ordered_candidate_ids"] == ["c002"], {
        "candidate": candidate, "ranking": ranked["rankings"][other_view],
    }
    anchor_image.write_bytes(b"changed anchor")
    with pytest.raises(LocalBodyReferenceError, match="anchor changed"):
        service.select_view(run["run_id"], other_view, "c002")


def test_codex_jobs_report_pending_running_done_and_failed(tmp_path):
    service = make_service(tmp_path)
    root = service.runs_root / "Test" / "Adult" / "20260922_120000_000001"
    root.mkdir(parents=True)
    (root / "spec.json").write_text(json.dumps({
        "run_id": root.name, "character": "Test", "phase": "Adult",
        "created_at": "2026-09-22T12:00:00",
        "candidates": [{"candidate_id": f"c{i:03}", "view": "FRONT", "status": "PENDING"}
                       for i in range(1, 5)],
    }), encoding="utf-8")
    (root / "state.json").write_text(json.dumps({"candidates": {
        "c002": {"status": "COMPLETE", "luna_status": "RUNNING"},
        "c003": {"status": "COMPLETE", "analyses": {"luna": {"pass": True}}},
        "c004": {"status": "COMPLETE", "luna_status": "FAILED", "luna_error": "CLI unavailable"},
    }}), encoding="utf-8")

    jobs = service.list_codex_jobs()
    assert [item["status"] for item in jobs] == ["PENDING", "RUNNING", "COMPLETE", "FAILED"]
    assert jobs[0]["details"] == "Waiting for candidate image"
    assert jobs[3]["details"] == "CLI unavailable"


def test_render_completion_waits_for_face_gate(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    assert {item["method"] for item in run["candidates"]} == {"shared_front", METHOD_FRONT_CONDITIONED}
    assert all(item["method"] == METHOD_FRONT_CONDITIONED
               for item in run["candidates"] if item["view"] != "FRONT")
    image = Path(run["root"]) / "candidate.png"
    image.write_bytes(b"rendered image")
    service._candidate_update(run["run_id"], "c001", {
        "status": "RUNNING", "image_path": str(image), "ask_id": "render-ask",
    })

    assert service._wait_for_render(run["run_id"], "c001") is True
    candidate = service.detail(run["run_id"])["candidates"][0]
    assert candidate["status"] == "WAITING_FOR_GATES"
    assert candidate["completed_at"] == ""


def test_harvest_face_gate_advances_or_requeues_without_completing(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    root = Path(run["root"])
    image = root / "candidate.png"
    image.write_bytes(b"rendered image")
    output = root / "analyses" / "c001" / "face_gate_result.txt"
    output.parent.mkdir(parents=True)
    output.write_text("FALSE", encoding="utf-8")
    service._candidate_update(run["run_id"], "c001", {
        "status": "WAITING_FOR_FACE_GATE", "image_path": str(image),
        "face_gate": {"ask_id": "face-ask", "status": "QUEUED", "output_path": str(output)},
    })
    launched = []
    class CapturedThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args
        def start(self):
            launched.append(self.args[0])
    monkeypatch.setattr("zet.services.local_body_reference_service.threading.Thread", CapturedThread)

    assert service.harvest_face_gate_jobs() == [run["run_id"]]
    candidate = service.detail(run["run_id"])["candidates"][0]
    assert candidate["status"] == "WAITING_FOR_ANALYSIS"
    assert candidate["face_gate"]["verdict"] == "FALSE"
    assert launched == [run["run_id"]]

    output.write_text("TRUE", encoding="utf-8")
    service._candidate_update(run["run_id"], "c001", {
        "status": "WAITING_FOR_FACE_GATE",
        "face_gate": {"ask_id": "face-ask-2", "status": "QUEUED", "output_path": str(output)},
    })
    service.harvest_face_gate_jobs()
    candidate = service.detail(run["run_id"])["candidates"][0]
    assert candidate["status"] == "PENDING"
    assert candidate["face_gate"] == {}
    assert len(candidate["face_gate_history"]) == 1


def test_preexisting_gate_passed_candidates_wait_for_human_review(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    service._candidate_update(run["run_id"], "c001", {
        "status": "COMPLETE", "face_gate": {"status": "COMPLETE", "verdict": "FALSE"},
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
    })

    candidate = service.detail(run["run_id"])["candidates"][0]
    assert candidate["status"] == "WAITING_FOR_HUMAN_REVIEW"


def test_human_review_is_required_for_complete_status(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    service._candidate_update(run["run_id"], "c001", {
        "status": "WAITING_FOR_HUMAN_REVIEW",
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
    })

    pending = service.update_candidate(run["run_id"], "c001", {"decision": "undecided"})
    assert pending["candidates"][0]["status"] == "WAITING_FOR_HUMAN_REVIEW"
    reviewed = service.update_candidate(run["run_id"], "c001", {"decision": "keep"})
    assert reviewed["candidates"][0]["status"] == "COMPLETE"
    assert reviewed["candidates"][0]["completed_at"]


def test_workflow_reference_binding_is_only_present_for_conditioned_method():
    text = LocalBodyReferenceService.compile_qwen_workflow(
        "front", checkpoint="diffusion.safetensors", text_encoder="encoder.safetensors",
        vae="vae.safetensors", seed=1,
    )
    conditioned = LocalBodyReferenceService.compile_qwen_workflow(
        "<image1> edit", checkpoint="diffusion.safetensors", text_encoder="encoder.safetensors",
        vae="vae.safetensors", seed=1, anchor_path="front.png",
    )
    assert "LoadImage" not in {node["class_type"] for node in text.values()}
    assert sum(node["class_type"] == "LoadImage" for node in conditioned.values()) == 1
    assert conditioned["4"]["inputs"]["images.image_1"] == ["10", 0]


def test_registered_body_reference_compilers_enforce_reference_policy():
    nodes = {"UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21", "EmptyLatentImage",
             "KSampler", "VAEDecode", "SaveImage", "LoadImage"}
    profile = {"text_encoder": "encoder.safetensors", "vae": "vae.safetensors", "steps": 40, "cfg": 1}
    text = compile_prompt_workflow(QWEN_BODY_REFERENCE_TEXT_WORKFLOW, "body", "", profile,
                                   checkpoint="model.safetensors", seed=3, width=832, height=1216,
                                   output_prefix="body", available_node_types=nodes)
    assert "LoadImage" not in {node["class_type"] for node in text.workflow.values()}
    with pytest.raises(Exception):
        compile_prompt_workflow(QWEN_BODY_REFERENCE_TEXT_WORKFLOW, "body", "", profile,
                                checkpoint="model.safetensors", seed=3, width=832, height=1216,
                                output_prefix="body", reference_files=[{"path": "front.png"}],
                                available_node_types=nodes)
    edited = compile_prompt_workflow(QWEN_BODY_REFERENCE_EDIT_WORKFLOW, "<image1> body", "", profile,
                                     checkpoint="model.safetensors", seed=3, width=832, height=1216,
                                     output_prefix="body", reference_files=[{"path": "front.png"}],
                                     available_node_types=nodes)
    assert edited.workflow["4"]["inputs"]["images.image_1"] == ["10", 0]


def test_disposition_requires_two_independent_reviews():
    assert LocalBodyReferenceService.disposition({}, {}) == "pending"
    assert LocalBodyReferenceService.disposition({"pass": True}, {"pass": True}) == "joint_pass"
    assert LocalBodyReferenceService.disposition({"pass": False}, {"pass": False}) == "joint_fail"
    assert LocalBodyReferenceService.disposition({"pass": True}, {"pass": False}) == "human_triage"
    assert LocalBodyReferenceService.disposition({"pass": True}, {"pass": True, "uncertain": True}) == "human_triage"


def test_front_anchor_requires_completed_reviewed_front_candidate(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    prompts = []

    def compile_view(root, character, phase, view, index):
        prompts.append(view)
        return {"view": view, "view_index": index, "manual_prompt": view,
                "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                "source_map": "", "dependency_manifest": ""}

    monkeypatch.setattr(service, "_compile_view", compile_view)
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    assert prompts == run["views"]
    with pytest.raises(LocalBodyReferenceError):
        service.select_front_anchor(run["run_id"], "c001")
    root = Path(run["root"])
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    image = root / "front.png"
    image.write_bytes(b"front")
    image_hash = service._hash(image)
    state["candidates"]["c001"] = {
        "status": "COMPLETE", "image_path": str(image), "disposition": "human_keep",
        "human_review": {"decision": "keep", "notes": ""},
        "analyses": {provider: {"pass": True, "input_hashes": {"candidate": image_hash}}
                     for provider in ("local", "luna")},
    }
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    selected = service.select_front_anchor(run["run_id"], "c001")
    assert selected["front_anchor"] == "c001"
    assert selected["status"] == "READY_FOR_VIEWS"
    assert selected["candidates"][0]["status"] == "COMPLETE"
    assert selected["candidates"][0]["human_review"]["decision"] == "keep"


def test_lineup_rejects_missing_or_unreviewed_candidates(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    with pytest.raises(LocalBodyReferenceError):
        service.set_lineup(run["run_id"], METHOD_TEXT_FIRST, {"FRONT": "c001"})
    assert METHOD_FRONT_CONDITIONED in run["methods"]

def test_luna_schema_has_explicit_view_aware_criteria():
    schema = LocalBodyReferenceService.analysis_schema()
    criteria = schema["properties"]["criteria"]
    assert criteria["additionalProperties"] is False
    assert set(criteria["required"]) == set(criteria["properties"])
    assert "torso_leg_balance" in criteria["properties"]
    assert "uncertain" in criteria["properties"]["torso_leg_balance"]["properties"]["status"]["enum"]

def test_local_body_reference_harvest_uses_its_own_slot_when_proxy_omits_target_directory(tmp_path):
    service = make_service(tmp_path)
    run_id = "20260922_000000_000001"
    root = service.runs_root / "Tsaeytte" / "Adult" / run_id
    root.mkdir(parents=True)
    (root / "spec.json").write_text("{}", encoding="utf-8")
    answers = tmp_path / "answers"
    service.app.ai_proxy_service = SimpleNamespace(
        ai_proxy_path_service=SimpleNamespace(answer_root=lambda: answers)
    )
    ask_id = "local-review"
    answer_dir = answers / ask_id
    answer_dir.mkdir(parents=True)
    (answer_dir / "ask_manifest.json").write_text(json.dumps({
        "ask_id": ask_id, "local_body_reference_run_id": run_id, "candidate_id": "c001",
        "task_type": "local_body_reference_analysis", "expected_output": "response.json",
        "target_output_file": "local.json",
    }), encoding="utf-8")
    (answer_dir / "answer_manifest.json").write_text(json.dumps({
        "ask_id": ask_id, "status": "SUCCESS", "expected_output": "response.json",
    }), encoding="utf-8")
    (answer_dir / "response.json").write_text("{}", encoding="utf-8")
    target = root / "analyses" / "c001" / "local.json"
    service._harvest_local_body_reference_answer(run_id, "c001", ask_id, target)
    assert target.read_text(encoding="utf-8") == "{}"
    render_id = "render-job"
    render_dir = answers / render_id
    render_dir.mkdir()
    (render_dir / "ask_manifest.json").write_text(json.dumps({
        "ask_id": render_id, "source_ask_id": f"BodyReference_{run_id}_c001_0",
        "task_type": "local_test_render", "expected_output": "image.png",
        "target_output_file": "image.png",
    }), encoding="utf-8")
    (render_dir / "answer_manifest.json").write_text(json.dumps({
        "ask_id": render_id, "status": "SUCCESS", "expected_output": "image.png",
    }), encoding="utf-8")
    (render_dir / "image.png").write_bytes(b"image")
    render_target = root / "renders" / "c001" / "Local_Test_Renders" / "image.png"
    service._harvest_local_body_reference_answer(run_id, "c001", render_id, render_target)
    assert render_target.read_bytes() == b"image"


def test_analysis_prompt_uses_saved_facts_and_prioritizes_proportions():
    prompt = LocalBodyReferenceService.analysis_prompt(
        {"view": "FRONT"}, facts="Olive tube top and compression shorts. Petite adult with a featureless mannequin head."
    )
    assert "Authoritative Body-Reference specification" in prompt
    assert "Olive tube top and compression shorts" in prompt
    assert prompt.index("head-to-body scale") < prompt.index("fitment clothing")
    assert "uncertain=false" in prompt


def test_review_prompt_is_view_specific(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": f"generation for {view}",
                         "analysis_specification": f"facts for {view}",
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = service.create_run({"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})

    front = service.review_prompt(run["run_id"], "FRONT")
    side = service.review_prompt(run["run_id"], "FRONT_LEFT_3_4")

    assert "Judge the candidate image against the requested view" in front
    assert "anchor" not in front.lower()
    assert "Image 1" not in front
    assert "Image 1 is the accepted front anchor; Image 2 is the candidate." in side
    assert "facts for FRONT" in front
    assert "facts for FRONT_LEFT_3_4" in side
    assert "generation for FRONT" not in front
    assert "generation for FRONT_LEFT_3_4" not in side


def test_existing_run_refreshes_analysis_when_template_changes(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index,
                         "manual_prompt": f"saved generation for {view}",
                         "analysis_specification": "old analysis with no cast shadow, contact shadow",
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    template = service.project_root / "Config" / "Prompt_Templates" / "body_reference_v2.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        "Shared fact.\n<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->\n"
        "no cast shadow, contact shadow\n<!-- ZET:END IMAGE_PROMPT_ONLY -->\n"
        "<!-- ZET:BEGIN ANALYSIS_PROMPT_ONLY -->\nCurrent review rule.\n"
        "<!-- ZET:END ANALYSIS_PROMPT_ONLY -->\n", encoding="utf-8"
    )
    calls = []
    def compile_analysis(job, project_root, *, prompt_variant):
        assert prompt_variant == "analysis"
        calls.append(job["Body View"])
        path = Path(job["Output Directory"]) / "Final_Image_Prompt.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(filter_prompt_variant_blocks(template.read_text(encoding="utf-8"), prompt_variant), encoding="utf-8")
        return {"final_prompt": str(path)}
    monkeypatch.setattr("zet.services.local_body_reference_service.compile_body_reference_job", compile_analysis)

    first = service.review_prompt(run["run_id"], "FRONT")
    second = service.review_prompt(run["run_id"], "FRONT")
    assert "Current review rule." in first
    assert second == first
    assert "no cast shadow, contact shadow" not in first
    assert calls == ["FRONT"]
    saved = json.loads((Path(run["root"]) / "spec.json").read_text(encoding="utf-8"))
    assert saved["prompt_snapshots"][0]["manual_prompt"] == "saved generation for FRONT"

    template.write_text(template.read_text(encoding="utf-8").replace("Current review rule.", "Updated review rule."), encoding="utf-8")
    updated = service.review_prompt(run["run_id"], "FRONT")
    assert "Updated review rule." in updated
    assert calls == ["FRONT", "FRONT"]

    image = Path(run["root"]) / "front.png"
    image.write_bytes(b"image")
    state_path = Path(run["root"]) / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["candidates"]["c001"] = {"status": "COMPLETE", "image_path": str(image)}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    template.write_text(template.read_text(encoding="utf-8").replace("Updated review rule.", "Reevaluation rule."), encoding="utf-8")
    service.reevaluate(run["run_id"])
    saved = json.loads((Path(run["root"]) / "spec.json").read_text(encoding="utf-8"))
    assert all("Reevaluation rule." in item["analysis_specification"] for item in saved["prompt_snapshots"])
    assert all("no cast shadow, contact shadow" not in item["analysis_specification"] for item in saved["prompt_snapshots"])


def test_reevaluate_preserves_render_and_human_review(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    root = Path(run["root"])
    image = root / "front.png"
    image.write_bytes(b"original image")
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    state["candidates"]["c001"] = {
        "status": "COMPLETE", "image_path": str(image),
        "analyses": {"local": {"pass": True}, "luna": {"pass": False}},
        "human_review": {"decision": "keep", "notes": "Good proportions"},
        "disposition": "human_keep",
    }
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    updated = service.reevaluate(run["run_id"])
    candidate = updated["candidates"][0]
    assert updated["status"] == "REEVALUATING"
    assert updated["review_only"] is True
    assert candidate["image_path"] == str(image)
    assert image.read_bytes() == b"original image"
    assert candidate["analyses"] == {}
    assert candidate["analysis_history"][0]["analyses"]["luna"]["pass"] is False
    assert candidate["human_review"] == {"decision": "keep", "notes": "Good proportions"}
    assert candidate["disposition"] == "human_keep"
    restarted = service.reevaluate(run["run_id"])
    assert restarted["status"] == "REEVALUATING"




def test_view_actions_scope_rerun_and_reevaluation(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    root = Path(run["root"])
    front_image = root / "front.png"
    other_image = root / "other.png"
    front_image.write_bytes(b"front image")
    other_image.write_bytes(b"other image")
    state_path = root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["front_anchor"] = "c001"
    state["status"] = "COMPLETE"
    state["candidates"]["c001"] = {
        "status": "COMPLETE", "image_path": str(front_image),
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
        "human_review": {"decision": "keep", "notes": "Front"},
    }
    state["candidates"]["c017"] = {
        "status": "COMPLETE", "image_path": str(other_image),
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
        "human_review": {"decision": "keep", "notes": "Other"},
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    rerun = service.rerun_view(run["run_id"], "FRONT")
    front = next(item for item in rerun["candidates"] if item["candidate_id"] == "c001")
    other = next(item for item in rerun["candidates"] if item["candidate_id"] == "c017")
    assert rerun["status"] == "RUNNING"
    assert rerun["front_anchor"] is None
    assert json.loads((root / "state.json").read_text(encoding="utf-8"))["target_views"] == ["FRONT"]
    assert front["status"] == "PENDING"
    assert front["human_review"] == {"decision": "undecided", "notes": ""}
    assert other["status"] == "COMPLETE"
    assert other["image_path"] == str(other_image)
    assert not front_image.exists()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "COMPLETE"
    state["candidates"]["c001"] = {
        "status": "COMPLETE", "image_path": str(other_image),
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
        "human_review": {"decision": "keep", "notes": "Keep front"},
    }
    state["candidates"]["c017"] = {
        "status": "COMPLETE", "image_path": str(other_image),
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
        "human_review": {"decision": "reject", "notes": "Keep other review"},
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    reevaluated = service.reevaluate(run["run_id"], view="FRONT")
    front = next(item for item in reevaluated["candidates"] if item["candidate_id"] == "c001")
    other = next(item for item in reevaluated["candidates"] if item["candidate_id"] == "c017")
    assert reevaluated["status"] == "REEVALUATING"
    assert json.loads(state_path.read_text(encoding="utf-8"))["target_views"] == ["FRONT"]
    assert front["analyses"] == {}
    assert front["human_review"] == {"decision": "keep", "notes": "Keep front"}
    assert other["analyses"] == {"local": {"pass": True}, "luna": {"pass": True}}

def test_interrupted_run_is_recoverable(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    root = Path(run["root"])
    image = root / "front.png"
    image.write_bytes(b"front image")
    state_path = root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(status="RUNNING", candidates={"c001": {
        "status": "COMPLETE", "image_path": str(image),
        "local_job": {"status": "RUNNING"}, "luna_status": "RUNNING",
    }})
    state_path.write_text(json.dumps(state), encoding="utf-8")

    interrupted = service.detail(run["run_id"])
    candidate = interrupted["candidates"][0]
    assert interrupted["status"] == "INTERRUPTED"
    assert interrupted["interrupted"] is True
    assert candidate["local_job"]["status"] == "INTERRUPTED"
    assert candidate["luna_status"] == "INTERRUPTED"

    restarted = service.reevaluate(run["run_id"], view="FRONT")
    assert restarted["status"] == "REEVALUATING"

def test_luna_environment_drops_desktop_context(monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "test-auth")
    monkeypatch.setenv("CODEX_SESSION_ID", "desktop-session")
    monkeypatch.setenv("CODEX_APP_TOOLS_PIPE_PATH", "desktop-pipe")
    monkeypatch.setenv("NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S", "browser")
    env = LocalBodyReferenceService._luna_environment()
    assert env["CODEX_HOME"] == "test-auth"
    assert "CODEX_SESSION_ID" not in env
    assert "CODEX_APP_TOOLS_PIPE_PATH" not in env
    assert "NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S" not in env


def test_reevaluation_runner_only_reviews_existing_images(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {"character": "Tsaeytte", "phase": "Adult", "seeds": list(range(44))})
    root = Path(run["root"])
    image = root / "front.png"
    image.write_bytes(b"front image")
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    state["candidates"]["c001"] = {"status": "COMPLETE", "image_path": str(image)}
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    service.reevaluate(run["run_id"])
    def unexpected(*_args, **_kwargs):
        pytest.fail("Re-evaluation called a render path")
    monkeypatch.setattr(service, "_preflight", unexpected)
    monkeypatch.setattr(service, "queue_render_candidate", unexpected)
    monkeypatch.setattr(service, "_wait_for_render", unexpected)
    def local(run_id, candidate_id):
        service._candidate_update(run_id, candidate_id, {"analyses": {"local": {"pass": True}}})
    def luna(run_id, candidate_id):
        service._candidate_update(run_id, candidate_id, {
            "status": "WAITING_FOR_HUMAN_REVIEW",
            "analyses": {"local": {"pass": True}, "luna": {"pass": True}}
        })
    monkeypatch.setattr(service, "queue_local_analysis", local)
    monkeypatch.setattr(service, "run_luna_analysis", luna)
    service.execute_run(run["run_id"])
    completed = service.detail(run["run_id"])
    assert completed["status"] == "WAITING_FOR_HUMAN_REVIEW"
    assert completed["review_only"] is False
    assert image.read_bytes() == b"front image"


def test_runner_batches_images_before_reviews_for_each_view(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    monkeypatch.setattr(service, "_compile_view", lambda root, character, phase, view, index:
                        {"view": view, "view_index": index, "manual_prompt": view,
                         "qwen_prompt": view, "prompt_path": "", "prompt_sha256": view,
                         "source_map": "", "dependency_manifest": ""})
    run = create_legacy_run(service, {
        "character": "Tsaeytte", "phase": "Adult",
        "front_count": 2, "other_count": 1, "seeds": list(range(9)),
    })
    root = Path(run["root"])
    anchor = root / "anchor.png"
    anchor.write_bytes(b"front anchor")
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    state["front_anchor"] = "c001"
    state["candidates"]["c001"] = {
        "status": "COMPLETE", "image_path": str(anchor),
        "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
    }
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(service, "_preflight", lambda: None)
    events = []

    def queue_render(run_id, candidate_id):
        events.append(("queue", candidate_id))
        image = root / "renders" / candidate_id / "image.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(candidate_id.encode())
        service._candidate_update(run_id, candidate_id, {
            "status": "QUEUED", "image_path": str(image),
        })

    def wait_for_render(run_id, candidate_id):
        events.append(("wait", candidate_id))
        service._candidate_update(run_id, candidate_id, {"status": "COMPLETE"})
        return True

    def queue_local(run_id, candidate_id):
        events.append(("local", candidate_id))
        service._candidate_update(run_id, candidate_id, {
            "analyses": {"local": {"pass": True}},
            "local_job": {"status": "COMPLETE"},
        })

    def run_luna(run_id, candidate_id):
        events.append(("luna", candidate_id))
        service._candidate_update(run_id, candidate_id, {
            "analyses": {"local": {"pass": True}, "luna": {"pass": True}},
        })

    monkeypatch.setattr(service, "queue_render_candidate", queue_render)
    monkeypatch.setattr(service, "_wait_for_render", wait_for_render)
    monkeypatch.setattr(service, "queue_local_analysis", queue_local)
    monkeypatch.setattr(service, "run_luna_analysis", run_luna)
    service.execute_run(run["run_id"])

    other_views = [view for view in run["views"] if view != "FRONT"]
    first_view_ids = [
        item["candidate_id"] for item in run["candidates"]
        if item["view"] == other_views[0]
    ]
    first_view_events = [
        (index, event) for index, event in enumerate(events)
        if event[1] in first_view_ids
    ]
    assert [event[1] for _, event in first_view_events if event[0] == "queue"] == first_view_ids
    assert max(index for index, event in first_view_events if event[0] == "wait") < min(
        index for index, event in first_view_events if event[0] in {"local", "luna"}
    )
    next_view_ids = [
        item["candidate_id"] for item in run["candidates"]
        if item["view"] == other_views[1]
    ]
    assert max(index for index, event in first_view_events) < min(
        index for index, event in enumerate(events) if event[1] in next_view_ids
    )


def test_legacy_run_and_queue_metadata_migrates_once(tmp_path):
    service = make_service(tmp_path)
    run_id = "20260922_010203_000004"
    run_root = service.runs_root / "Test" / "Adult" / run_id
    run_root.mkdir(parents=True)
    (run_root / "spec.json").write_text(json.dumps({
        "kind": "body_reference_qwen_experiment", "run_id": run_id,
        "job": "BodyReferenceExperiment_" + run_id,
    }), encoding="utf-8")
    queue_root = tmp_path / "queue"
    answer_dir = queue_root / f"Ask_BodyReference_{run_id}_c001_FACE"
    answer_dir.mkdir(parents=True)
    (answer_dir / "ask_manifest.json").write_text(json.dumps({
        "pipeline": "Character-Pipeline-Experiment",
        "task_type": "body_reference_face_gate",
        "body_reference_run_id": run_id,
        "ask_id": answer_dir.name,
    }), encoding="utf-8")
    service.app.config.base_ai_queue_path = str(queue_root)
    marker = service.runs_root / ".local_body_reference_migration_v1"
    marker.unlink()

    service._migrate_legacy_runs()

    spec = json.loads((run_root / "spec.json").read_text(encoding="utf-8"))
    ask = json.loads((answer_dir / "ask_manifest.json").read_text(encoding="utf-8"))
    assert spec["kind"] == "local_body_reference"
    assert spec["job"] == f"LocalBodyReference_{run_id}"
    assert ask["pipeline"] == "Local-Body-Reference"
    assert ask["task_type"] == "local_body_reference_face_gate"
    assert ask["local_body_reference_run_id"] == run_id
    assert ask["ask_id"] == answer_dir.name
    assert marker.exists()

    (run_root / "already_local.json").write_text(json.dumps({
        "task_type": "local_body_reference_analysis",
    }), encoding="utf-8")
    service._migrate_legacy_runs()
    already_local = json.loads((run_root / "already_local.json").read_text(encoding="utf-8"))
    assert already_local["task_type"] == "local_body_reference_analysis"
