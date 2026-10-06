import copy
import hashlib
import json
from pathlib import Path
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tests.support.project_fixture import write_project_fixture
from tests.support.image_fixture import png_bytes
from zet.app import ZetApp
from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_render_policy import require_qwen_profile
from zet.web.local_scene_batch_router import create_local_scene_batch_router
import zet.services.local_scene_batch_service as scene_batch_module


@pytest.fixture(autouse=True)
def stable_scene_ranking(monkeypatch):
    monkeypatch.setattr(scene_batch_module, "rank_images_with_luna",
        lambda **kwargs: ([{"candidate_id": item, "reason": "Test ranking"} for item in kwargs["candidate_ids"]], "test"))


@pytest.fixture
def batches(tmp_path):
    app = ZetApp.from_config(write_project_fixture(tmp_path, library_root=True), validate_catalog=False)
    for path, text in [(app.path_service.shared_story_template_path(), "Title: Story\n"),
                       (app.path_service.shared_scene_template_path(), "Title: Scene\n")]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    app.create_story("Story")
    app.create_scene("Story", "Scene")
    data = app.load_scene_builder("Story", "Scene").data
    data["setup"]["environment"]["general_background_notes"] = "A quiet forest clearing"
    data["subscenes"] = [{"id": "background", "name": "Background", "kind": "background", "enabled": True}]
    app.save_scene_builder("Story", "Scene", data)
    return app.local_scene_batch_service


def create(batches, count=1):
    return batches.create("Story", "Scene", {"count": count})


def action(batches, run, name, **payload):
    return batches.action("Story", "Scene", run["run_id"], name, payload)


def finish(batches, run, target, *, failed=False, foreign=False, index=0, wait=True, color="red"):
    candidate = run["groups"][target]["candidates"][index]
    ask = batches.proxy.ask_root() / candidate["ask_id"]
    answer = batches.proxy.answer_root() / candidate["ask_id"]
    answer.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ask / "ask_manifest.json").read_text(encoding="utf-8"))
    if foreign:
        manifest["source_ask_id"] = "foreign"
    write_json_atomic(answer / "ask_manifest.json", manifest)
    write_json_atomic(answer / "answer_manifest.json", {"ask_id": candidate["ask_id"], "status": "ERROR" if failed else "SUCCESS",
                      "expected_output": "render.png", "error_message": "Test render failure"})
    (answer / "render.png").write_bytes(png_bytes(color))
    run = batches.detail("Story", "Scene", run["run_id"])
    if wait:
        for _ in range(100):
            slot = run["groups"][target]["candidates"][index]
            active = any(item["status"] in {"SUBMITTING", "QUEUED", "RUNNING"}
                         for item in run["groups"][target]["candidates"])
            if slot["status"] in {"COMPLETE", "FAILED"} and not active:
                break
            time.sleep(.01)
            run = batches.detail("Story", "Scene", run["run_id"])
    return run


def finish_group(batches, run, target, *, failed_index=None):
    for index, slot in enumerate(run["groups"][target]["candidates"]):
        if slot["status"] in {"SUBMITTING", "QUEUED", "RUNNING"}:
            run = finish(batches, run, target, failed=index == failed_index, index=index, wait=False)
    for _ in range(500):
        run = batches.detail("Story", "Scene", run["run_id"])
        if run["rankings"].get(target, {}).get("status") in {"COMPLETE", "FAILED"}:
            return run
        time.sleep(.01)
    raise AssertionError("Rating did not finish")


def test_selection_checkpoints_and_canonical_publication(batches):
    run = create(batches)
    assert run["views"] == ["background", "main"]
    with pytest.raises(ValueError, match="prerequisite"):
        action(batches, run, "render", target_id="main")
    run = action(batches, run, "start")
    assert len(run["groups"]["main"]["candidates"]) == 8
    assert all(item["status"] == "EMPTY" for item in run["groups"]["main"]["candidates"])
    run = finish_group(batches, run, "background")
    run = action(batches, run, "select", target_id="background", candidate_id="background-001")
    assert not batches.targets.review_paths("Story", "Scene", "background")["locked"].exists()
    run = action(batches, run, "start")
    main = run["groups"]["main"]
    assert main["reference_images"][0]["image_index"] == 1
    assert "<image1>" in Path(main["prompt_path"]).read_text(encoding="utf-8")
    run = finish_group(batches, run, "main")
    run = action(batches, run, "select", target_id="main", candidate_id="main-001")
    assert run["status"] == "READY_TO_PUBLISH"
    run = action(batches, run, "stop")
    assert run["status"] == "STOPPED"
    run = action(batches, run, "resume")
    assert run["status"] == "READY_TO_PUBLISH"
    run = action(batches, run, "publish")
    assert run["status"] == "COMPLETE"
    assert batches.story.scene_image_path("Story", "Scene").is_file()
    metadata = json.loads(batches.targets.review_paths("Story", "Scene", "main")["metadata"].read_text())
    assert metadata["batch_id"] == run["run_id"]
    action(batches, run, "publish")


@pytest.mark.parametrize("count", [0, 1, 10])
def test_dynamic_groups_and_disabled_targets(batches, count):
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["subscenes"] = [{"id": f"group_{i}", "name": str(i), "kind": "background", "enabled": True} for i in range(count)]
    data["subscenes"].append({"id": "off", "kind": "background", "enabled": False})
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = create(batches)
    assert len(run["views"]) == count + 1
    assert "off" not in run["views"]


def test_selected_subscene_previews_match_prompt_order_and_submitted_images(batches):
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    for element_id, label in [("schoolboys", "Kaeldor and the Schoolboys"), ("friends", "Tsaeytte and Valindia")]:
        data["scene_elements"].append({"id": element_id, "display_name": label,
            "resource_type": "Scene-Only", "element_type": "Prop", "fallback_visual_description": label})
        data["placements"].append({"id": f"p_{element_id}", "scene_element_id": element_id,
            "depth": "midground", "position_within_cell": "center"})
        data["subscenes"].append({"id": f"{element_id}_view", "kind": "element", "enabled": True,
            "name": label, "anchor_element_id": element_id})
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = create(batches)
    colors = {"background": "blue", "schoolboys_view": "green", "friends_view": "red"}
    for target, color in colors.items():
        run = action(batches, run, "render", target_id=target)
        for index in range(4):
            run = finish(batches, run, target, index=index, wait=False,
                         color="yellow" if index == 1 else color)
        run = action(batches, run, "select", target_id=target, candidate_id=f"{target}-001")

    run = action(batches, run, "render", target_id="main")
    main = run["groups"]["main"]
    assert [item["tag"] for item in main["next_reference_images"]] == [item["tag"] for item in main["reference_images"]]
    for preview, reference in zip(main["next_reference_images"], main["reference_images"], strict=True):
        assert preview["image_index"] == reference["image_index"]
        assert preview["prompt_role"] == reference["prompt_role"]
        assert preview["sha256"] == reference["sha256"]
        target = reference["tag"].split(":")[-1].removesuffix("}}")
        assert Path(preview["path"]).read_bytes() == png_bytes(colors[target])
    ask = batches.proxy.ask_root() / main["candidates"][0]["ask_id"] / "ask_manifest.json"
    manifest = json.loads(ask.read_text(encoding="utf-8"))
    assert [(ask.parent / item["path"]).read_bytes() for item in manifest["reference_files"]] == [
        Path(item["path"]).read_bytes() for item in main["next_reference_images"]]

    api = FastAPI()
    api.include_router(create_local_scene_batch_router(lambda: batches.app))
    client = TestClient(api)
    url = f"/api/stories/Story/scenes/Scene/local-batches/{run['run_id']}/targets/main/next-references/0"
    response = client.get(url)
    assert response.content == png_bytes("blue")
    assert response.headers["cache-control"] == "no-store"
    previous_hash = main["next_reference_images"][0]["sha256"]
    run = action(batches, run, "select", target_id="background", candidate_id="background-002")
    assert run["groups"]["main"]["next_reference_images"][0]["sha256"] != previous_hash
    assert client.get(url).content == png_bytes("yellow")
    # Existing slots retain their original inputs; a new attempt uses the new selection.
    assert main["reference_images"][0]["sha256"] == previous_hash
    run = action(batches, run, "compile", target_id="main")
    assert Path(run["groups"]["main"]["reference_images"][0]["path"]).read_bytes() == png_bytes("yellow")


def test_saved_target_changes_reconcile_without_showing_inactive_targets(batches):
    run = action(batches, create(batches), "start")
    run = finish_group(batches, run, "background")
    old_image = Path(run["groups"]["background"]["active_candidates"][0]["image_path"])
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["subscenes"][0]["enabled"] = False
    data["subscenes"].append({"id": "new_view", "name": "New View", "kind": "background", "enabled": True})
    batches.story.save_scene_builder_data("Story", "Scene", data)
    reconciled = batches.detail("Story", "Scene", run["run_id"])
    assert reconciled["views"] == ["new_view", "main"]
    assert "background" not in [item["target_id"] for item in reconciled["targets"]]
    assert "historical_targets" not in reconciled
    assert old_image.is_file()
    selected = action(batches, reconciled, "select", target_id="background", candidate_id="background-001")
    assert selected["selected_views"]["background"] == "background-001"


def test_same_asset_id_with_replaced_bytes_is_captured_for_next_attempt(batches, monkeypatch, tmp_path):
    reference = tmp_path / "spire.png"
    reference.write_bytes(b"old archway bytes")
    asset_id = "cb9087bb-7b38-4a04-9c2b-7a04a395cb5a"
    monkeypatch.setattr(batches.story.story_reference_service, "resolve_scene_references", lambda *_: [{
        "asset_id": asset_id, "tag": f"{{{{LIB:ASSET:{asset_id}}}}}", "path": str(reference), "label": "Spire Archway",
    }])
    monkeypatch.setattr(batches.story.story_render_service, "compile_batch_target", lambda scene, settings, sections, refs, target, selected: {
        "prompt": "Fresh reference prompt", "references": refs,
        "ir": {"image_inputs": [{"tag": refs[0]["tag"], "image_index": 1}], "elements": [], "placements": []},
        "render_input_hash": hashlib.sha256(Path(refs[0]["path"]).read_bytes()).hexdigest(),
    })
    run = create(batches)
    reference.write_bytes(b"new archway bytes")
    run = action(batches, run, "render", target_id="background")
    group = run["groups"]["background"]
    attempt = group["attempts"][group["attempt_id"]]
    captured = Path(attempt["reference_images"][0]["path"])
    assert attempt["reference_images"][0]["asset_id"] == asset_id
    assert captured.read_bytes() == b"new archway bytes"
    assert attempt["reference_images"][0]["sha256"] == hashlib.sha256(b"new archway bytes").hexdigest()
    preview = Path(group["next_reference_images"][0]["path"])
    assert preview.read_bytes() == b"new archway bytes"


def test_each_group_has_eight_slots_but_initial_render_queues_four(batches):
    run = create(batches)
    for group in run["groups"].values():
        assert [slot["slot"] for slot in group["candidates"]] == list(range(1, 9))
        assert all(slot["status"] == "EMPTY" for slot in group["candidates"])
    run = action(batches, run, "start")
    slots = run["groups"]["background"]["candidates"]
    assert all(slot["status"] in {"SUBMITTING", "QUEUED"} for slot in slots[:4])
    assert all(slot["status"] == "EMPTY" for slot in slots[4:])


def test_fill_slots_renders_only_empty_slots_and_preserves_images(batches):
    run = action(batches, create(batches), "start")
    run = finish_group(batches, run, "background")
    run = action(batches, run, "select", target_id="background", candidate_id="background-002")
    preserved = {item["slot"]: (item["candidate_id"], Path(item["image_path"]))
                 for item in run["groups"]["background"]["active_candidates"][1:4]}
    first = run["groups"]["background"]["active_candidates"][0]
    run = action(batches, run, "clear", target_id="background", candidate_id=first["candidate_id"])

    run = action(batches, run, "fill", target_id="background")
    slots = run["groups"]["background"]["active_candidates"]
    assert [item["slot"] for item in slots] == list(range(1, 9))
    assert all(slots[index - 1]["status"] == "QUEUED" for index in (1, 5, 6, 7, 8))
    assert all(slots[index - 1]["candidate_id"] == candidate_id and image.is_file()
               for index, (candidate_id, image) in preserved.items())
    assert run["selected_views"]["background"] == "background-002"
    with pytest.raises(ValueError, match="no empty render slots"):
        action(batches, run, "fill", target_id="background")


def test_fill_slots_queues_all_eight_when_empty(batches):
    run = action(batches, create(batches), "fill", target_id="background")
    assert len(run["groups"]["background"]["active_candidates"]) == 8
    assert all(item["status"] == "QUEUED" for item in run["groups"]["background"]["active_candidates"])


def test_existing_batch_discards_earlier_slot_images_and_observations(batches):
    run = create(batches)
    root = Path(run["root"])
    state_path = root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    old_image = root / "slots" / "main" / "main-old.png"
    old_image.parent.mkdir(parents=True, exist_ok=True)
    old_image.write_bytes(png_bytes())
    state["groups"]["main"]["candidates"].append({
        "candidate_id": "main-old", "slot": 1, "status": "COMPLETE", "image_path": str(old_image),
    })
    state["selected_views"]["main"] = "main-old"
    state["view_reviews"] = {"main": {"observations": "Old note"}}
    write_json_atomic(state_path, state)

    current = batches.detail("Story", "Scene", run["run_id"])
    assert len(current["groups"]["main"]["candidates"]) == 8
    assert "main-old" not in {item["candidate_id"] for item in current["groups"]["main"]["candidates"]}
    assert not old_image.exists()
    assert "main" not in current["selected_views"]
    assert "view_reviews" not in current


@pytest.mark.parametrize("name,count", [("render", 4), ("rerender", 8)])
def test_new_render_withdraws_pending_asks_but_preserves_running_work(batches, name, count):
    run = action(batches, create(batches), "start")
    old = run["groups"]["background"]["active_candidates"][:4]
    running = old[0]
    (batches.proxy.ask_root() / running["ask_id"]).rename(batches.proxy.running_root() / running["ask_id"])
    run = action(batches, run, name, target_id="background")

    assert len(run["groups"]["background"]["candidates"]) == 8
    assert running["candidate_id"] not in {item["candidate_id"] for item in run["groups"]["background"]["candidates"]}
    assert (batches.proxy.running_root() / running["ask_id"]).is_dir()
    for item in old[1:]:
        assert item["candidate_id"] not in {candidate["candidate_id"] for candidate in run["groups"]["background"]["candidates"]}
        assert not (batches.proxy.ask_root() / item["ask_id"]).exists()
    active = run["groups"]["background"]["active_candidates"]
    assert sum(item["status"] == "QUEUED" for item in active) == count
    assert all((batches.proxy.ask_root() / item["ask_id"]).is_dir() for item in active if item["status"] == "QUEUED")


def test_render_withdraws_pending_asks_from_another_scene_target(batches):
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["subscenes"].append({"id": "other", "name": "Other", "kind": "background", "enabled": True})
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = action(batches, create(batches), "start")
    run = action(batches, run, "rerender", target_id="background")
    pending = [item["ask_id"] for item in run["groups"]["background"]["active_candidates"]]

    run = action(batches, run, "render", target_id="other")
    assert all(item["status"] == "STOPPED" for item in run["groups"]["background"]["active_candidates"])
    assert all(not (batches.proxy.ask_root() / ask_id).exists() for ask_id in pending)
    assert all(item["status"] == "QUEUED" for item in run["groups"]["other"]["active_candidates"][:4])


def test_render_captures_scene_edits_without_a_recompile_action(batches):
    run = create(batches)
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["scene"]["story_beat"] = "The archway glows with a new blue light."
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = action(batches, run, "render", target_id="background")
    group = run["groups"]["background"]
    attempt = group["attempts"][group["attempt_id"]]
    snapshot = json.loads(Path(attempt["snapshot_path"]).read_text(encoding="utf-8"))
    assert snapshot["scene"]["scene"]["story_beat"] == "The archway glows with a new blue light."
    assert all(item["status"] in {"SUBMITTING", "QUEUED"} for item in group["active_candidates"][:4])


def test_retry_replaces_filled_slot_and_clear_removes_image(batches):
    run = action(batches, create(batches), "start")
    run = finish_group(batches, run, "background")
    filled = run["groups"]["background"]["candidates"][0]
    image_path, old_seed = Path(filled["image_path"]), filled["seed"]
    run = action(batches, run, "retry", target_id="background", candidate_id=filled["candidate_id"])
    assert not image_path.exists()
    assert run["groups"]["background"]["active_candidates"][0]["seed"] != old_seed
    assert len(run["groups"]["background"]["candidates"]) == 8
    assert filled["candidate_id"] not in {item["candidate_id"] for item in run["groups"]["background"]["candidates"]}
    run = finish(batches, run, "background", index=0, wait=False)
    run = finish_group(batches, run, "background")
    candidate = run["groups"]["background"]["active_candidates"][0]
    image_path = Path(candidate["image_path"])
    run = action(batches, run, "clear", target_id="background", candidate_id=candidate["candidate_id"])
    assert not image_path.exists()
    assert len(run["groups"]["background"]["candidates"]) == 8
    assert candidate["candidate_id"] not in {item["candidate_id"] for item in run["groups"]["background"]["candidates"]}


def test_late_answer_cannot_restore_a_cleared_slot(batches):
    run = action(batches, create(batches), "start")
    slot = run["groups"]["background"]["candidates"][0]
    ask = batches.proxy.ask_root() / slot["ask_id"]
    answer = batches.proxy.answer_root() / slot["ask_id"]
    manifest = json.loads((ask / "ask_manifest.json").read_text(encoding="utf-8"))
    run = action(batches, run, "clear", target_id="background", candidate_id=slot["candidate_id"])
    answer.mkdir(parents=True, exist_ok=True)
    write_json_atomic(answer / "ask_manifest.json", manifest)
    write_json_atomic(answer / "answer_manifest.json", {"ask_id": slot["ask_id"], "status": "SUCCESS", "expected_output": "render.png"})
    (answer / "render.png").write_bytes(png_bytes())
    run = batches.detail("Story", "Scene", run["run_id"])
    cleared = run["groups"]["background"]["candidates"][0]
    assert cleared["status"] == "EMPTY" and "image_path" not in cleared
    assert slot["candidate_id"] not in {item["candidate_id"] for item in run["groups"]["background"]["candidates"]}


def test_clearing_selected_slot_preserves_dependent_images(batches):
    run = complete_run(batches)
    main_image = Path(run["groups"]["main"]["candidates"][0]["image_path"])
    run = action(batches, run, "clear", target_id="background", candidate_id="background-001")
    assert "background" not in run["selected_views"]
    assert run["selected_views"]["main"] == "main-001"
    assert main_image.exists()


def test_rejecting_a_slot_keeps_the_image_selectable(batches):
    run = action(batches, create(batches), "start")
    run = finish_group(batches, run, "background")
    image = Path(run["groups"]["background"]["candidates"][0]["image_path"])
    run = action(batches, run, "review", target_id="background", candidate_id="background-001", decision="reject")
    slot = run["groups"]["background"]["candidates"][0]
    assert slot["status"] == "COMPLETE" and Path(slot["image_path"]).exists()
    assert slot["human_review"]["decision"] == "reject" and image.exists()
    run = action(batches, run, "select", target_id="background", candidate_id=slot["candidate_id"])
    assert run["selected_views"]["background"] == slot["candidate_id"]


def test_legacy_batches_convert_images_and_preserve_older_history(batches):
    run = create(batches)
    root = Path(run["root"])
    backup_dir = batches.targets.review_paths("Story", "Scene", "background")["backups"]
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "old.png").write_bytes(png_bytes())
    render_attempts = batches.targets.pipeline_path("Story", "Scene", "background") / "Render_Attempts"
    render_attempts.mkdir(parents=True, exist_ok=True)
    (render_attempts / "old.png").write_bytes(png_bytes())
    legacy_image = root / "targets" / "background" / "legacy" / "background-001.png"
    legacy_image.parent.mkdir(parents=True, exist_ok=True)
    legacy_image.write_bytes(png_bytes())
    spec_path, state_path = root / "spec.json", root / "state.json"
    spec = json.loads(spec_path.read_text())
    spec.pop("slot_count")
    spec["schema_version"] = 1
    spec["batch_name"] = "Old run"
    state = json.loads(state_path.read_text())
    for target, group in state["groups"].items():
        if target == "background":
            group["candidates"] = [{"candidate_id": "background-001", "seed": 3, "status": "COMPLETE",
                "image_path": str(legacy_image), "sha256": hashlib.sha256(legacy_image.read_bytes()).hexdigest(),
                "human_review": {"decision": "undecided"}}]
        else:
            group["candidates"] = []
        group["attempts"] = []
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    state_path.write_text(json.dumps(state), encoding="utf-8")
    older_id = "0" * 32
    older = root.parent / older_id
    older.mkdir()
    old_spec = {**spec, "run_id": older_id, "created_at": "2000-01-01T00:00:00+00:00"}
    (older / "spec.json").write_text(json.dumps(old_spec), encoding="utf-8")
    (older / "state.json").write_text(json.dumps(state), encoding="utf-8")

    listing = batches.list_runs("Story", "Scene")
    converted = batches.detail("Story", "Scene", run["run_id"])
    slots = converted["groups"]["background"]["candidates"]
    assert len(listing) == 1 and listing[0]["slot_count"] == 8
    assert slots[0]["status"] == "COMPLETE" and Path(slots[0]["image_path"]).is_file()
    assert all(slot["status"] == "EMPTY" for slot in slots[1:])
    assert older.exists()
    assert (backup_dir / "old.png").is_file() and (render_attempts / "old.png").is_file()


def test_failed_foreign_and_late_answers_are_isolated(batches):
    run = action(batches, create(batches), "start")
    run = finish(batches, run, "background", foreign=True)
    assert run["groups"]["background"]["candidates"][0]["status"] == "FAILED"
    old_ask = run["groups"]["background"]["candidates"][0]["ask_id"]
    run = action(batches, run, "retry", target_id="background", candidate_id="background-001")
    assert run["groups"]["background"]["active_candidates"][0]["ask_id"] != old_ask
    run = finish_group(batches, run, "background")
    assert run["groups"]["background"]["active_candidates"][0]["status"] == "COMPLETE"
    assert "render_attempts" not in run["groups"]["background"]["active_candidates"][0]


def test_source_changes_do_not_block_publication_or_rewrite_existing_attempts(batches):
    run = complete_run(batches)
    root = Path(run["root"])
    original = json.loads((root / "snapshot.json").read_text())
    settings = batches.story._library_absolute_path(original["scene"]["scene"]["story_settings_path"])
    settings.write_text(settings.read_text() + "\n")
    second = create(batches)
    assert run["run_id"] == second["run_id"]
    assert len(batches.list_runs("Story", "Scene")) == 1
    assert json.loads((root / "snapshot.json").read_text()) == original
    run = action(batches, run, "publish")
    assert run["status"] == "COMPLETE"


def test_stop_resume_and_rerender_keep_only_eight_current_slots(batches):
    run = action(batches, create(batches), "start")
    run = action(batches, run, "stop")
    assert run["status"] == "STOPPED"
    run = action(batches, run, "resume")
    run = finish_group(batches, run, "background")
    candidate = run["groups"]["background"]["active_candidates"][0]
    run = action(batches, run, "select", target_id="background", candidate_id=candidate["candidate_id"])
    run = action(batches, run, "start")
    run = action(batches, run, "stop")
    run = action(batches, run, "rerender", target_id="background")
    assert len(run["groups"]["background"]["candidates"]) == 8
    active = run["groups"]["background"]["active_candidates"]
    assert all(item["status"] in {"QUEUED", "SUBMITTING"} for item in active), [
        (item["status"], item.get("error")) for item in active
    ]
    assert all(item["status"] in {"EMPTY", "STOPPED"} for item in run["groups"]["main"]["active_candidates"])
    assert "background" not in run["selected_views"]


def test_batch_api_without_observations(batches):
    app = FastAPI()
    app.include_router(create_local_scene_batch_router(lambda: batches.app))
    client = TestClient(app)
    base = "/api/stories/Story/scenes/Scene/local-batches"
    response = client.post(base, json={"count": 1})
    assert response.status_code == 200, response.text
    run = response.json()
    assert client.post(f"{base}/{run['run_id']}/actions/compile", json={"target_id": "background"}).status_code == 200
    assert client.get(f"{base}/{run['run_id']}/targets/background/prompt").status_code == 200
    assert client.get(f"{base}/{run['run_id']}/prompt-improvement-package").status_code == 404
    assert client.post(f"{base}/{run['run_id']}/actions/save-observations", json={"target_id": "background", "observations": "Preserve the horizon"}).status_code == 400
    assert client.get(f"{base}/{'f'*32}").status_code == 400


def test_prompt_link_compiles_current_scene_before_render_without_changing_attempts(batches):
    app = FastAPI()
    app.include_router(create_local_scene_batch_router(lambda: batches.app))
    client = TestClient(app)
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["subscenes"][0]["enabled"] = False
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = create(batches)
    base = f"/api/stories/Story/scenes/Scene/local-batches/{run['run_id']}"
    prompt_url = f"{base}/targets/main/prompt"

    first = client.get(prompt_url)
    assert first.status_code == 200, first.text
    assert "A quiet forest clearing" in first.text
    assert not run["groups"]["main"].get("attempt_id")

    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["setup"]["environment"]["general_background_notes"] = "A bright stone courtyard"
    batches.story.save_scene_builder_data("Story", "Scene", data)
    second = client.get(prompt_url)
    assert second.status_code == 200, second.text
    assert "A bright stone courtyard" in second.text
    assert "A quiet forest clearing" not in second.text
    current = batches.detail("Story", "Scene", run["run_id"])
    assert not current["groups"]["main"].get("attempt_id")
    assert all(item["status"] == "EMPTY" for item in current["groups"]["main"]["candidates"])


@pytest.mark.parametrize("profile,backend", [("scene-preview-sd15", "stable_matrix"), ("comfyui-core-preview", "comfyui"), ("image-recipe-lab-qwen-image-edit-2511", "comfyui")])
def test_retired_local_renderers_cannot_be_submitted(profile, backend):
    with pytest.raises(ValueError, match="only ComfyUI"):
        require_qwen_profile(Path(__file__).resolve().parents[1], profile, backend)


def complete_run(batches):
    run = create(batches)
    for target in run["views"]:
        run = action(batches, run, "start")
        run = finish_group(batches, run, target)
        run = action(batches, run, "select", target_id=target, candidate_id=f"{target}-001")
    return run


def test_partial_publication_recovers_without_creating_locked_backups(batches, monkeypatch):
    run = complete_run(batches)
    locked = batches.story.scene_image_path("Story", "Scene")
    locked.parent.mkdir(parents=True, exist_ok=True)
    locked.write_bytes(b"previous locked output")
    reviews = {target["target_id"]: {**target, "decision": "promote"}
               for target in batches.publication_review("Story", "Scene", run["run_id"])["targets"]}
    promote = batches.app.scene_image_review_service.promote
    def fail_main(story, scene, target, **kwargs):
        if target == "main":
            raise RuntimeError("publication interrupted")
        return promote(story, scene, target, **kwargs)
    monkeypatch.setattr(batches.app.scene_image_review_service, "promote", fail_main)
    with pytest.raises(RuntimeError, match="interrupted"):
        action(batches, run, "publish", reviews=reviews)
    state = json.loads((Path(run["root"]) / "state.json").read_text())
    assert list(state["publication"]["targets"]) == ["background"]
    monkeypatch.setattr(batches.app.scene_image_review_service, "promote", promote)
    run = action(batches, run, "publish", reviews=reviews)
    assert run["status"] == "COMPLETE"
    backups = list(batches.targets.review_paths("Story", "Scene", "main")["backups"].glob("*.png"))
    assert len(backups) == 1
    action(batches, run, "publish")


def publication_reviews(batches, run, **decisions):
    review = batches.publication_review("Story", "Scene", run["run_id"])
    return {target["target_id"]: {**target, "decision": decisions.get(target["target_id"], "promote")}
            for target in review["targets"]}


def test_publication_review_keeps_existing_lock_and_rejects_selected_candidate(batches):
    run = complete_run(batches)
    paths = batches.targets.review_paths("Story", "Scene", "main")
    paths["locked"].parent.mkdir(parents=True, exist_ok=True)
    paths["locked"].write_bytes(b"previous locked scene")
    paths["metadata"].parent.mkdir(parents=True, exist_ok=True)
    paths["metadata"].write_text('{"previous": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="Compare the candidate"):
        action(batches, run, "publish")
    assert not batches.targets.review_paths("Story", "Scene", "background")["locked"].exists()
    reviews = publication_reviews(batches, run, main="keep-current")
    candidate_path = Path(run["groups"]["main"]["candidates"][0]["image_path"])
    run = action(batches, run, "publish", reviews=reviews)
    assert run["status"] == "COMPLETE"
    assert run["groups"]["main"]["status"] == "CURRENT_LOCK_KEPT"
    assert run["groups"]["main"]["candidates"][0]["human_review"]["decision"] == "reject"
    assert paths["locked"].read_bytes() == b"previous locked scene"
    assert paths["metadata"].read_text() == '{"previous": true}'
    assert candidate_path.is_file()
    assert not list(paths["backups"].glob("*.png"))
    # Retrying publication must not promote a candidate that was rejected.
    run = action(batches, run, "publish")
    assert paths["locked"].read_bytes() == b"previous locked scene"
    run = action(batches, run, "select", target_id="main", candidate_id="main-002")
    assert run["status"] == "READY_TO_PUBLISH"


def test_publication_review_promotes_with_backup_and_exposes_comparison_images(batches):
    run = complete_run(batches)
    paths = batches.targets.review_paths("Story", "Scene", "main")
    paths["locked"].parent.mkdir(parents=True, exist_ok=True)
    paths["locked"].write_bytes(png_bytes())
    app = FastAPI()
    app.include_router(create_local_scene_batch_router(lambda: batches.app))
    client = TestClient(app)
    base = f"/api/stories/Story/scenes/Scene/local-batches/{run['run_id']}"
    response = client.get(base + "/publication-review")
    assert response.status_code == 200
    target = next(item for item in response.json()["targets"] if item["target_id"] == "main")
    assert target["locked_exists"]
    assert target["locked_sha256"] == hashlib.sha256(png_bytes()).hexdigest()
    assert client.get(base + "/targets/main/locked").content == png_bytes()
    reviews = publication_reviews(batches, run)
    response = client.post(base + "/actions/publish", json={"reviews": reviews})
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETE"
    assert len(list(paths["backups"].glob("*.png"))) == 1
    metadata = json.loads(paths["metadata"].read_text())
    assert metadata["batch_id"] == run["run_id"]


@pytest.mark.parametrize("change", ["locked", "selection", "incomplete", "missing-lock"])
def test_publication_review_validates_all_decisions_before_replacing_any_lock(batches, change):
    run = complete_run(batches)
    reviews = publication_reviews(batches, run)
    if change == "locked":
        locked = batches.targets.review_paths("Story", "Scene", "main")["locked"]
        locked.parent.mkdir(parents=True, exist_ok=True)
        locked.write_bytes(b"lock changed while dialog was open")
    elif change == "selection":
        run = action(batches, run, "select", target_id="main", candidate_id="main-002")
    elif change == "incomplete":
        reviews.pop("main")
    else:
        reviews["main"]["decision"] = "keep-current"
    with pytest.raises(ValueError):
        action(batches, run, "publish", reviews=reviews)
    assert not batches.targets.review_paths("Story", "Scene", "background")["locked"].exists()


def test_partial_candidates_retry_and_source_changes_only_invalidate_descendants(batches, monkeypatch):
    monkeypatch.setattr("zet.services.local_scene_batch_service.rank_images_with_luna",
        lambda **kwargs: ([{"candidate_id": item, "reason": "Good composition"} for item in kwargs["candidate_ids"]], "test"))
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["subscenes"].append({"id": "other", "kind": "background", "enabled": True})
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = batches.create("Story", "Scene", {"counts": {"background": 2, "other": 1, "main": 1}})
    run = action(batches, run, "start")
    run = finish(batches, run, "background", wait=False)
    first = run["groups"]["background"]["candidates"][0]["image_path"]
    run = finish(batches, run, "background", index=1, failed=True)
    run = action(batches, run, "retry", target_id="background", candidate_id="background-002")
    assert run["groups"]["background"]["candidates"][0]["image_path"] == first
    run = finish(batches, run, "background", index=1, wait=False)
    for index in (2, 3):
        run = finish(batches, run, "background", index=index, wait=False)
    run = finish_group(batches, run, "background")
    assert run["selected_views"] == {}
    run = action(batches, run, "select", target_id="background", candidate_id="background-001")
    run = action(batches, run, "start")
    run = finish_group(batches, run, "other")
    run = action(batches, run, "select", target_id="other", candidate_id="other-001")
    run = action(batches, run, "start")
    run = finish_group(batches, run, "main")
    old_main_image = Path(run["groups"]["main"]["candidates"][0]["image_path"])
    newer = next(item for item in run["groups"]["background"]["candidates"]
                 if item["status"] == "COMPLETE" and item["candidate_id"] != "background-001")
    run = action(batches, run, "select", target_id="background", candidate_id=newer["candidate_id"])
    assert run["selected_views"]["other"] == "other-001"
    assert all(item["status"] == "COMPLETE" for item in run["groups"]["main"]["active_candidates"][:4])
    assert "main" in run["rankings"] and old_main_image.exists()


def test_submission_restart_recovers_existing_queue_job(batches):
    from zet.services.local_scene_batch_service import LocalSceneBatchService
    run = action(batches, create(batches), "start")
    state_path = Path(run["root"]) / "state.json"
    state = json.loads(state_path.read_text())
    state["groups"]["background"]["candidates"][0].update(status="SUBMITTING", ask_id="")
    write_json_atomic(state_path, state)
    restored = LocalSceneBatchService(batches.app, batches.project_root).detail("Story", "Scene", run["run_id"])
    assert restored["groups"]["background"]["candidates"][0]["ask_id"] == run["groups"]["background"]["candidates"][0]["ask_id"]


def test_prompt_analysis_exact_prompt_and_attempt_fence(batches):
    run = action(batches, create(batches), "compile", target_id="background")
    run = batches.analyze_prompt("Story", "Scene", run["run_id"], "background")
    group = run["groups"]["background"]
    record = group["analysis"]
    ask = batches.proxy.ask_root() / record["ask_id"]
    assert Path(group["prompt_path"]).read_text(encoding="utf-8") in (ask / "OLLAMA_PROMPT.md").read_text(encoding="utf-8")
    answer = batches.proxy.answer_root() / record["ask_id"]
    answer.mkdir(parents=True)
    manifest = json.loads((ask / "ask_manifest.json").read_text())
    manifest["attempt_id"] = "old-attempt"
    write_json_atomic(answer / "ask_manifest.json", manifest)
    write_json_atomic(answer / "answer_manifest.json", {"ask_id": record["ask_id"], "status": "SUCCESS", "expected_output": "Analysis.md"})
    (answer / "Analysis.md").write_text("late analysis")
    run = batches.detail("Story", "Scene", run["run_id"])
    assert run["groups"]["background"]["analysis"]["status"] == "FAILED"
    assert not Path(record["result_path"]).exists()


def test_analysis_submission_restart_and_saved_prompt_validation(batches):
    run = action(batches, create(batches), "compile", target_id="background")
    run = batches.analyze_prompt("Story", "Scene", run["run_id"], "background")
    state_path = Path(run["root"]) / "state.json"
    state = json.loads(state_path.read_text())
    state["groups"]["background"]["analysis"]["status"] = "SUBMITTING"
    write_json_atomic(state_path, state)
    restored = batches.detail("Story", "Scene", run["run_id"])
    assert restored["groups"]["background"]["analysis"]["status"] == "QUEUED"
    state = json.loads(state_path.read_text())
    state["groups"]["background"]["analysis"].update(status="SUBMITTING", ask_id="not-published")
    write_json_atomic(state_path, state)
    restored = batches.detail("Story", "Scene", run["run_id"])
    assert restored["groups"]["background"]["analysis"]["status"] == "FAILED"
    prompt = Path(restored["groups"]["background"]["prompt_path"])
    prompt.write_text("An altered prompt", encoding="utf-8")
    analyzed = batches.analyze_prompt("Story", "Scene", run["run_id"], "background")
    assert analyzed["groups"]["background"]["attempt_id"] != restored["groups"]["background"]["attempt_id"]


def test_reference_cap_is_preflight_without_dropping_inputs(batches):
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["subscenes"] = [{"id": f"back{i}", "kind": "background", "enabled": True} for i in range(11)]
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = complete_run_until_main(batches)
    with pytest.raises(ValueError, match="ten"):
        action(batches, run, "compile", target_id="main")
    assert len(run["selected_views"]) == 11


def complete_run_until_main(batches):
    run = create(batches)
    for target in run["views"][:-1]:
        run = action(batches, run, "start")
        run = finish_group(batches, run, target)
        run = action(batches, run, "select", target_id=target, candidate_id=f"{target}-001")
    return run


def test_nested_graph_dependency_order_and_invalid_graph(batches, monkeypatch):
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["scene_elements"] = [{"id": "parent", "display_name": "Parent", "subscene_id": "", "element_type": "object"},
                              {"id": "child", "display_name": "Child", "subscene_id": "parent_view", "element_type": "object"}]
    data["subscenes"] += [{"id": "parent_view", "kind": "element", "enabled": True, "anchor_element_id": "parent"},
                          {"id": "child_view", "kind": "element", "enabled": True, "anchor_element_id": "child"}]
    monkeypatch.setattr(batches.story, "load_scene_builder_data", lambda *_: type("Document", (), {
        "blocked": False, "data": data, "story": type("Story", (), {"slug": "Story"}), "scene": type("Scene", (), {"slug": "Scene"})})())
    preview = batches.preview("Story", "Scene", {})
    assert [item["target_id"] for item in preview["targets"]] == ["background", "child_view", "parent_view", "main"]
    assert preview["targets"][2]["dependencies"] == ["child_view"]
    data["scene_elements"][0]["subscene_id"] = "child_view"
    with pytest.raises(Exception, match="cycle"):
        batches.preview("Story", "Scene", {})


def test_retired_model_override_and_adapter_dispatch(tmp_path):
    from Scripts.Local_Render_Adapters.local_render import render_image
    from zet.services.local_render_types import LocalRenderError
    with pytest.raises(LocalRenderError, match="Qwen Image 2.1"):
        render_image(project_root=Path(__file__).resolve().parents[1], final_prompt_path=tmp_path / "unused.md",
                     job_output_dir=tmp_path, checkpoint="sdxl.safetensors")


def test_nested_scene_compilation_uses_batch_selected_references(batches):
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["scene_elements"] = [{"id": "parent", "display_name": "Party", "resource_type": "Scene-Only", "element_type": "Prop", "fallback_visual_description": "A group of travelers"},
                              {"id": "child", "display_name": "Child", "resource_type": "Scene-Only", "element_type": "Prop", "fallback_visual_description": "A small cart", "subscene_id": "parent_view"}]
    data["placements"] = [{"id": "p1", "scene_element_id": "parent", "depth": "midground", "position_within_cell": "center"},
                          {"id": "p2", "scene_element_id": "child", "depth": "midground", "position_within_cell": "center"}]
    data["subscenes"] += [{"id": "parent_view", "kind": "element", "enabled": True, "anchor_element_id": "parent"},
                          {"id": "child_view", "kind": "element", "enabled": True, "anchor_element_id": "child"}]
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = complete_run(batches)
    references = run["groups"]["parent_view"]["reference_images"]
    assert references[0]["tag"] == "{{SCENE_RENDER:Story:Scene:child_view}}"
    assert references[0]["path"] == run["groups"]["child_view"]["candidates"][0]["image_path"]
    assert all(not batches.targets.review_paths("Story", "Scene", target)["locked"].exists() for target in run["views"])
    run = action(batches, run, "publish")
    assert run["status"] == "COMPLETE"


def test_legacy_recompile_refreshes_prompt_and_preserves_images_and_selections(batches):
    run = complete_run(batches)
    old_prompt = Path(run["groups"]["main"]["prompt_path"])
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["scene"]["story_beat"] = "A red kite flies overhead."
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = action(batches, run, "recompile")
    assert run["selected_views"]["background"] == "background-001"
    assert run["selected_views"]["main"] == "main-001"
    assert run["groups"]["background"].get("prompt_path")
    assert old_prompt.exists()
    assert any(item["status"] == "COMPLETE" for item in run["groups"]["background"]["active_candidates"])
    assert run["groups"]["main"].get("prompt_path")


def test_storytelling_pages_load_with_unassociated_approved_image(batches, monkeypatch):
    import importlib
    web = importlib.import_module("zet.web.app")
    monkeypatch.setattr(web, "_app", lambda *_: batches.app)
    monkeypatch.setattr(batches.app.entity_library_service, "list_assets", lambda: [{"asset_id": "orphan", "status": "approved", "label": "Orphan",
        "entities": [], "file_name": "orphan.png", "image_path": "orphan.png", "thumbnail_path": "orphan.png", "origin": "uploaded"}])
    client = TestClient(web.create_app(batches.app.config_path, validate_catalog_on_create=False))
    for url in ["/api/stories/Story/scenes/Scene", "/api/stories/Story/scenes/Scene/builder", "/api/scene-image-picker"]:
        response = client.get(url)
        assert response.status_code == 200, response.text


def test_ad_hoc_retired_choices_are_rejected(batches):
    from zet.services.ad_hoc_image_generation_service import AdHocImageGenerationService
    service = AdHocImageGenerationService(batches.app, batches.project_root)
    for retired in [{"backend": "stable_matrix"}, {"profile": "comfyui-core-preview"}, {"checkpoint": "sdxl.safetensors"}]:
        with pytest.raises(ValueError, match="Qwen Image 2.1"):
            service.submit({"prompt": "A quiet lake", **retired})


def test_manual_smoke_harness_through_publication_and_zine(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from tests import manual_scene_batch_smoke as smoke
    from zet.services.local_render_types import LocalRenderResult
    monkeypatch.setattr(scene_batch_module, "rank_images_with_luna",
        lambda **kwargs: ([{"candidate_id": item, "reason": "Smoke ranking"} for item in kwargs["candidate_ids"]], "test"))
    root = tmp_path / "Smoke"
    root.mkdir()
    monkeypatch.setattr(smoke.tempfile, "mkdtemp", lambda **_: str(root))
    @contextmanager
    def node_info(*_, **__):
        from io import StringIO
        yield StringIO('{"TextEncodeQwenImage21": {}}')
    monkeypatch.setattr(smoke, "urlopen", node_info)
    def render(**kwargs):
        image = kwargs["job_output_dir"] / "smoke.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(png_bytes())
        return LocalRenderResult(image, image.with_suffix(".json"), None, "test")
    monkeypatch.setattr(smoke, "render_image", render)
    smoke.main()
    assert (root / "Stories/Smoke/Clearing.png").is_file()
    assert (root / "Assets/Zines/Smoke/Smoke.png").is_file()
