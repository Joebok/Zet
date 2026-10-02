import copy
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


def finish(batches, run, target, *, failed=False, foreign=False, index=0, wait=True):
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
    (answer / "render.png").write_bytes(png_bytes())
    for _ in range(100):
        run = batches.detail("Story", "Scene", run["run_id"])
        if not wait or failed or foreign or run["rankings"].get(target, {}).get("status") == "COMPLETE":
            return run
        time.sleep(.01)
    raise AssertionError("Rating did not finish")


def test_selection_checkpoints_and_canonical_publication(batches):
    run = create(batches)
    assert run["views"] == ["background", "main"]
    with pytest.raises(ValueError, match="Select prerequisite"):
        action(batches, run, "render", target_id="main")
    run = action(batches, run, "start")
    assert not run["groups"]["main"]["candidates"]
    run = finish(batches, run, "background")
    run = action(batches, run, "select", target_id="background", candidate_id="background-001")
    assert not batches.targets.review_paths("Story", "Scene", "background")["locked"].exists()
    run = action(batches, run, "start")
    main = run["groups"]["main"]
    assert main["reference_images"][0]["image_index"] == 1
    assert "<image1>" in Path(main["prompt_path"]).read_text(encoding="utf-8")
    run = finish(batches, run, "main")
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


def test_failed_foreign_and_late_answers_are_isolated(batches):
    run = action(batches, create(batches), "start")
    run = finish(batches, run, "background", foreign=True)
    assert run["groups"]["background"]["candidates"][0]["status"] == "FAILED"
    assert run["groups"]["background"]["candidates"][0]["render_attempts"][0]["status"] == "FAILED"
    old_ask = run["groups"]["background"]["candidates"][0]["ask_id"]
    run = action(batches, run, "retry", target_id="background")
    assert run["groups"]["background"]["candidates"][0]["ask_id"] != old_ask
    run = finish(batches, run, "background")
    assert run["groups"]["background"]["candidates"][0]["status"] == "COMPLETE"
    attempts = run["groups"]["background"]["candidates"][0]["render_attempts"]
    assert [entry["status"] for entry in attempts] == ["FAILED", "COMPLETE"]


def test_source_changes_block_publication_and_batches_keep_history(batches):
    run = complete_run(batches)
    root = Path(run["root"])
    original = json.loads((root / "snapshot.json").read_text())
    settings = batches.story._library_absolute_path(original["scene"]["scene"]["story_settings_path"])
    settings.write_text(settings.read_text() + "\n")
    second = create(batches)
    assert run["run_id"] != second["run_id"]
    assert len(batches.list_runs("Story", "Scene")) == 2
    assert json.loads((root / "snapshot.json").read_text()) == original
    with pytest.raises(ValueError, match="Source inputs changed"):
        action(batches, run, "publish")


def test_stop_resume_and_rerender_keep_attempts(batches):
    run = action(batches, create(batches), "start")
    run = action(batches, run, "stop")
    assert run["status"] == "STOPPED"
    run = action(batches, run, "resume")
    run = finish(batches, run, "background")
    run = action(batches, run, "select", target_id="background", candidate_id="background-001")
    run = action(batches, run, "start")
    run = action(batches, run, "stop")
    run = action(batches, run, "rerender", target_id="background")
    assert run["groups"]["background"]["attempts"]
    assert not run["groups"]["main"]["candidates"]
    assert "background" not in run["selected_views"]


def test_batch_api_and_prompt_package(batches):
    app = FastAPI()
    app.include_router(create_local_scene_batch_router(lambda: batches.app))
    client = TestClient(app)
    base = "/api/stories/Story/scenes/Scene/local-batches"
    response = client.post(base, json={"count": 1})
    assert response.status_code == 200, response.text
    run = response.json()
    assert client.post(f"{base}/{run['run_id']}/actions/compile", json={"target_id": "background"}).status_code == 200
    assert client.get(f"{base}/{run['run_id']}/targets/background/prompt").status_code == 200
    assert client.get(f"{base}/{run['run_id']}/prompt-improvement-package").status_code == 200
    assert client.post(f"{base}/{run['run_id']}/actions/save-observations", json={"target_id": "background", "observations": "Preserve the horizon"}).status_code == 200
    assert client.get(f"{base}/{'f'*32}").status_code == 400


@pytest.mark.parametrize("profile,backend", [("scene-preview-sd15", "stable_matrix"), ("comfyui-core-preview", "comfyui"), ("image-recipe-lab-qwen-image-edit-2511", "comfyui")])
def test_retired_local_renderers_cannot_be_submitted(profile, backend):
    with pytest.raises(ValueError, match="only ComfyUI"):
        require_qwen_profile(Path(__file__).resolve().parents[1], profile, backend)


def complete_run(batches):
    run = create(batches)
    for target in run["views"]:
        run = action(batches, run, "start")
        run = finish(batches, run, target)
        run = action(batches, run, "select", target_id=target, candidate_id=f"{target}-001")
    return run


def test_partial_publication_recovers_and_preserves_locked_backups(batches, monkeypatch):
    run = complete_run(batches)
    locked = batches.story.scene_image_path("Story", "Scene")
    locked.parent.mkdir(parents=True, exist_ok=True)
    locked.write_bytes(b"previous locked output")
    promote = batches.app.scene_image_review_service.promote
    def fail_main(story, scene, target):
        if target == "main":
            raise RuntimeError("publication interrupted")
        return promote(story, scene, target)
    monkeypatch.setattr(batches.app.scene_image_review_service, "promote", fail_main)
    with pytest.raises(RuntimeError, match="interrupted"):
        action(batches, run, "publish")
    state = json.loads((Path(run["root"]) / "state.json").read_text())
    assert list(state["publication"]["targets"]) == ["background"]
    monkeypatch.setattr(batches.app.scene_image_review_service, "promote", promote)
    run = action(batches, run, "publish")
    assert run["status"] == "COMPLETE"
    backups = list(batches.targets.review_paths("Story", "Scene", "main")["backups"].glob("*.png"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"previous locked output"
    action(batches, run, "publish")
    assert len(list(backups[0].parent.glob("*.png"))) == 1


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
    run = action(batches, run, "retry", target_id="background")
    assert run["groups"]["background"]["candidates"][0]["image_path"] == first
    run = finish(batches, run, "background", index=1)
    assert run["selected_views"] == {}
    run = action(batches, run, "select", target_id="background", candidate_id="background-001")
    run = action(batches, run, "start")
    run = finish(batches, run, "other")
    run = action(batches, run, "select", target_id="other", candidate_id="other-001")
    run = action(batches, run, "start")
    run = finish(batches, run, "main")
    old_attempt = run["groups"]["main"]["attempt_id"]
    run = action(batches, run, "select", target_id="background", candidate_id="background-002")
    assert run["selected_views"]["other"] == "other-001"
    assert not run["groups"]["main"]["candidates"] and "main" not in run["rankings"]
    assert batches.artifact("Story", "Scene", run["run_id"], "main", "image", "main-001", old_attempt).is_file()


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
    with pytest.raises(ValueError, match="Saved prompt"):
        batches.analyze_prompt("Story", "Scene", run["run_id"], "background")


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
        run = finish(batches, run, target)
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


def test_recompile_refreshes_inputs_but_keeps_original_attempts(batches):
    run = complete_run(batches)
    old_prompt = Path(run["groups"]["main"]["prompt_path"])
    old_text = old_prompt.read_text(encoding="utf-8")
    data = batches.story.load_scene_builder_data("Story", "Scene").data
    data["scene"]["story_beat"] = "A red kite flies overhead."
    batches.story.save_scene_builder_data("Story", "Scene", data)
    run = action(batches, run, "recompile")
    assert not run["selected_views"]
    assert run["groups"]["background"]["status"] == "COMPILED"
    assert old_prompt.read_text(encoding="utf-8") == old_text
    assert run["groups"]["main"]["attempts"][0]["prompt_path"] == str(old_prompt)


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
