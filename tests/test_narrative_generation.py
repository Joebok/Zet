import json
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tests.support.project_fixture import write_project_fixture
from tests.support.image_fixture import png_bytes
from zet.app import ZetApp
from zet.services.atomic_file_service import write_json_atomic
from zet.services.narrative_generation_service import NarrativeGenerationService
from zet.services.narrative_scene_service import ProtectedNarrativeImages
from zet.web.narrative_router import create_narrative_router


@pytest.fixture
def rig(tmp_path, monkeypatch):
    app = ZetApp.from_config(write_project_fixture(tmp_path, library_root=True), validate_catalog=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy scene workflow called")
    for name in ("create_story", "create_scene", "load_scene_builder", "stage_scene_render"):
        monkeypatch.setattr(app, name, forbidden)
    author = app.narrative_scene_service
    story = author.create_story({"title": "Fresh narrative story"})["id"]
    scene = author.create_scene(story, {"title": "Encounter", "style": "Painterly fantasy"})["id"]
    element = author.save_element(story, scene, {"name": "Traveler", "appearance": "A cloaked traveler"})
    target = author.create_target(story, scene, {"title": "Traveler's arrival", "narrative": "A traveler arrives",
                                               "element_ids": [element["id"]]})["id"]
    return app, author, app.narrative_generation_service, (story, scene, target)


def complete(service, ids, job_id, output, *, failed=False, foreign=False):
    proxy = service.proxy.client
    ask = proxy.ask_root / job_id
    answer = proxy.answer_root / job_id
    answer.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ask / "ask_manifest.json").read_text(encoding="utf-8"))
    if foreign:
        manifest["narrative_target_id"] = "other"
    write_json_atomic(answer / "ask_manifest.json", manifest)
    write_json_atomic(answer / "answer_manifest.json", {"ask_id": job_id, "expected_output": manifest["expected_output"],
                       "status": "ERROR" if failed else "SUCCESS", "error_message": "Test worker failure"})
    (answer / manifest["expected_output"]).write_bytes(output if isinstance(output, bytes) else json.dumps(output).encode("utf-8"))
    write_json_atomic(answer / "harvest_manifest.json", {})
    shutil.rmtree(ask)
    return service.detail(*ids)


def latest_job(detail, kind):
    return [item for item in detail["jobs"].values() if item["kind"] == kind][-1]


def test_interview_edits_and_concurrent_fields(rig):
    app, author, service, ids = rig
    draft = service.start(*ids, {"action": "interview", "message": "Give him an uncertain expression."})
    job = latest_job(draft, "interview")
    ask = json.loads((service.proxy.client.ask_root / job["id"] / "ask_manifest.json").read_text())
    assert ask["ollama_model"] == "general:latest"
    assert ask["consumer"] == "zet-narrative-scenes"
    assert ask["response_schema"]["properties"]["questions"]["maxItems"] == 2
    author.update_target(*ids, {"narrative": "My newer direction"})
    result = complete(service, ids, job["id"], {"narrative": "Old generated direction", "staging": "Facing left",
                    "physical_context": "Stone ground", "framing": "Full body", "questions": ["Question one?", "Question two?", "Extra?"]})
    assert result["narrative"] == "My newer direction"
    assert result["staging"] == "Facing left"
    assert result["interview"][-1]["text"] == "Question one?\nQuestion two?"
    assert not any(key in result for key in ("approved", "stale", "needs_review"))


def test_generate_synthesis_one_prompt_and_four_images(rig):
    app, author, service, ids = rig
    draft = service.start(*ids, {"action": "generate", "count": 4})
    job = latest_job(draft, "generate")
    detail = complete(service, ids, job["id"], {"scene": "Create an illustration of a traveler arriving with uncertainty.",
                                             "rendering": "Painterly fantasy, eye level, soft daylight."})
    assert all(part in detail["prompt"] for part in ("Scene\n", "References\n", "Rendering\n", "Constraints\n"))
    assert "Exactly 1 named subjects: Traveler" in detail["prompt"]
    image_jobs = [item for item in detail["jobs"].values() if item["kind"] == "image"]
    assert len(image_jobs) == 4
    assert len({item["seed"] for item in detail["candidates"].values()}) == 4
    for image_job in image_jobs:
        ask = service.proxy.client.ask_root / image_job["id"]
        manifest = json.loads((ask / "ask_manifest.json").read_text())
        assert manifest["render_preset"] == "comfyui-qwen-narrative"
        assert manifest["render_overrides"]["disable_prompt_globals"] is True
        assert "scene_render_ir_file" not in manifest
        assert (ask / "prompt.md").read_text(encoding="utf-8") == detail["prompt"]
    assert not (Path(app.config.base_library_path) / "Stories").exists()


def test_manual_prompt_restart_selection_and_protected_cascade(rig):
    app, author, service, ids = rig
    prompt = "Scene\nMy exact text.\nNegative constraints: keep these literal words."
    author.update_target(*ids, {"prompt": prompt})
    draft = service.start(*ids, {"action": "render", "count": 1})
    job = latest_job(draft, "image")
    ask = service.proxy.client.ask_root / job["id"]
    assert (ask / "prompt.md").read_text(encoding="utf-8") == prompt
    service = NarrativeGenerationService(author)
    detail = complete(service, ids, job["id"], png_bytes("red"))
    candidate = detail["slots"][0]
    service.candidate_action(*ids, candidate, {"action": "select"})
    author.update_target(*ids, {"narrative": "Completely changed"})
    assert service.detail(*ids)["selected_id"] == candidate
    with pytest.raises(ValueError, match="protected"):
        service.start(*ids, {"action": "render", "slot": 1})
    with pytest.raises(ProtectedNarrativeImages):
        service.candidate_action(*ids, candidate, {"action": "clear"})
    for depth in (1, 2, 3):
        with pytest.raises(ProtectedNarrativeImages):
            author.delete(*ids[:depth])
    assert service.image(*ids, candidate).is_file()
    author.delete(*ids, confirmed=[candidate])
    assert author.scene(*ids[:2])["targets"] == []


def test_late_answers_never_replace_new_slots(rig):
    app, author, service, ids = rig
    author.update_target(*ids, {"prompt": "A traveler."})
    draft = service.start(*ids, {"action": "render"})
    old_job = latest_job(draft, "image")
    old_candidate = draft["slots"][0]
    new = service.start(*ids, {"action": "render", "slot": 1})
    new_candidate = new["slots"][0]
    assert old_candidate != new_candidate
    after = complete(service, ids, old_job["id"], png_bytes("red"))
    assert after["slots"][0] == new_candidate
    assert after["candidates"][new_candidate]["image"] == ""
    assert old_candidate not in after["candidates"]


def test_partial_failure_retry_and_foreign_answer(rig):
    app, author, service, ids = rig
    author.update_target(*ids, {"prompt": "A traveler."})
    detail = service.start(*ids, {"action": "render", "count": 4})
    jobs = [item for item in detail["jobs"].values() if item["kind"] == "image"]
    for i, job in enumerate(jobs):
        detail = complete(service, ids, job["id"], png_bytes("red"), failed=(i == 1))
    assert sum(item["status"] == "COMPLETE" for item in detail["candidates"].values()) == 3
    retry = service.start(*ids, {"action": "render", "slot": 2})
    job = latest_job(retry, "image")
    detail = complete(service, ids, job["id"], png_bytes("red"), foreign=True)
    assert detail["candidates"][detail["slots"][1]]["status"] == "FAILED"
    assert (service.proxy.client.answer_root / job["id"]).exists()


def test_selection_does_not_delete_previous_and_lock_survives(rig):
    app, author, service, ids = rig
    author.update_target(*ids, {"prompt": "A traveler."})
    detail = service.start(*ids, {"action": "render", "count": 4})
    for job in [item for item in detail["jobs"].values() if item["kind"] == "image"]:
        detail = complete(service, ids, job["id"], png_bytes("red"))
    first, second = detail["slots"][:2]
    service.candidate_action(*ids, first, {"action": "select"})
    service.candidate_action(*ids, first, {"action": "lock"})
    service.candidate_action(*ids, second, {"action": "select"})
    assert service.image(*ids, first).exists()
    with pytest.raises(ValueError, match="protected"):
        service.start(*ids, {"action": "render", "slot": 1})
    detail = service.start(*ids, {"action": "render", "count": 4})
    assert detail["slots"][0] == first and detail["slots"][1] == second


def test_router_confirmation_and_target_isolation(rig):
    app, author, service, ids = rig
    api = FastAPI()
    api.include_router(create_narrative_router(lambda: app))
    client = TestClient(api)
    base = f"/api/narrative/stories/{ids[0]}/scenes/{ids[1]}/targets/{ids[2]}"
    response = client.patch(base, json={"prompt": "My prompt"})
    assert response.status_code == 200
    detail = client.post(base + "/jobs", json={"action": "render"}).json()
    job = latest_job(detail, "image")
    detail = complete(service, ids, job["id"], png_bytes("red"))
    candidate = detail["slots"][0]
    assert client.post(base + f"/candidates/{candidate}", json={"action": "select"}).status_code == 200
    response = client.request("DELETE", base)
    assert response.status_code == 409
    assert response.json()["detail"]["protected_images"][0]["id"] == candidate
    assert client.get(base + f"/candidates/{candidate}/image").status_code == 200
    assert client.get("/api/narrative/stories/not-an-id").status_code == 400
    assert client.request("DELETE", base, json={"confirm_ids": [candidate]}).status_code == 200


def test_backdrop_uses_no_automatic_subjects(rig):
    app, author, service, ids = rig
    backdrop = author.create_target(*ids[:2], {"title": "Academy courtyard", "kind": "backdrop", "narrative": "A stone courtyard"})
    target_ids = (*ids[:2], backdrop["id"])
    detail = service.start(*target_ids, {"action": "generate"})
    job = latest_job(detail, "generate")
    detail = complete(service, target_ids, job["id"], {"scene": "Create a stone courtyard with no people.", "rendering": "Soft daylight."})
    assert "No people" in detail["prompt"]
    assert detail["elements"] == []
    image_job = latest_job(detail, "image")
    manifest = json.loads((service.proxy.client.ask_root / image_job["id"] / "ask_manifest.json").read_text())
    assert manifest["reference_files"] == []
    assert manifest["render_overrides"]["width"] == 1344


def test_background_sweep_dispatches_images_without_open_page(rig):
    app, author, service, ids = rig
    detail = service.start(*ids, {"action": "generate"})
    job = latest_job(detail, "generate")
    original = service.detail
    # Prepare the answer without polling the target page.
    service.detail = lambda *args: None
    complete(service, ids, job["id"], {"scene": "A hopeful traveler.", "rendering": "Soft daylight."})
    service.detail = original
    restarted = NarrativeGenerationService(author)
    restarted.poll_pending()
    stored = author.repository.read(*ids)
    assert latest_job(stored, "image")["status"] == "QUEUED"


def test_library_bindings_and_prompt_order_without_metadata_injection(rig, monkeypatch):
    app, author, service, ids = rig
    first = app.entity_library_service.import_asset("First appearance", "image/png", png_bytes("red"), prompt="OLD TEMPLATE MUST NOT LEAK")
    second = app.entity_library_service.import_asset("Second appearance", "image/png", png_bytes("blue"))
    a = author.save_element(*ids[:2], {"name": "A", "asset_id": first["asset_id"]})
    b = author.save_element(*ids[:2], {"name": "B", "asset_id": second["asset_id"]})
    author.update_target(*ids, {"element_ids": [b["id"], a["id"]]})
    monkeypatch.setattr(app.entity_library_service, "get_asset", lambda *args: pytest.fail("Full metadata read"))
    detail = service.start(*ids, {"action": "generate"})
    job = latest_job(detail, "generate")
    detail = complete(service, ids, job["id"], {"scene": "A and B talk together.", "rendering": "Daylight."})
    assert "<image1> depicts B" in detail["prompt"]
    assert "<image2> depicts A" in detail["prompt"]
    assert "OLD TEMPLATE" not in detail["prompt"]
    manifest = json.loads((service.proxy.client.ask_root / latest_job(detail, "image")["id"] / "ask_manifest.json").read_text())
    assert [ref["label"] for ref in manifest["reference_files"]] == ["B", "A"]
    assert all(not Path(ref["path"]).is_absolute() for ref in manifest["reference_files"])


def test_dispatch_recovers_between_image_submissions(rig, monkeypatch):
    app, author, service, ids = rig
    author.update_target(*ids, {"prompt": "A traveler."})
    publish = service.proxy.publish
    calls = []
    def interrupt(*args, **kwargs):
        calls.append(args[3]["id"])
        if len(calls) == 2:
            raise KeyboardInterrupt("Simulated crash")
        return publish(*args, **kwargs)
    monkeypatch.setattr(service.proxy, "publish", interrupt)
    with pytest.raises(KeyboardInterrupt):
        service.start(*ids, {"action": "render", "count": 4})
    restarted = NarrativeGenerationService(author)
    detail = restarted.detail(*ids)
    # The interrupted job fails visibly; existing asks are reused and remaining
    # slots are submitted once rather than silently disappearing.
    images = [job for job in detail["jobs"].values() if job["kind"] == "image"]
    assert len(images) == 4
    assert len(list(restarted.proxy.client.ask_root.glob('*/job.json'))) == 3
    assert sum(candidate["status"] == "FAILED" for candidate in detail["candidates"].values()) == 1


def test_alpha_bytes_preserved_and_manual_prompt_not_overwritten(rig):
    from io import BytesIO
    from PIL import Image
    app, author, service, ids = rig
    detail = service.start(*ids, {"action": "generate"})
    job = latest_job(detail, "generate")
    author.update_target(*ids, {"prompt": "A concurrent manual edit"})
    detail = complete(service, ids, job["id"], {"scene": "A traveler arrives.", "rendering": "Soft light."})
    assert detail["prompt"] == "A concurrent manual edit"
    buffer = BytesIO()
    Image.new('RGBA', (4,4), (0,100,0,128)).save(buffer, format='PNG')
    detail = complete(service, ids, latest_job(detail, "image")["id"], buffer.getvalue())
    assert service.image(*ids, detail["slots"][0]).read_bytes() == buffer.getvalue()


def test_target_llm_never_receives_unassigned_scene_action(rig):
    from zet.services.narrative_prompt_service import llm_request
    app, author, service, ids = rig
    author.update_scene(*ids[:2], {"intent": "Traveler and UnassignedSpectator exchange a parchment."})
    for kind in ("subscene", "backdrop"):
        backdrop = author.create_target(*ids[:2], {"title": "Quiet courtyard", "kind": kind, "narrative": "An empty courtyard"})
        detail = author.target(*ids[:2], backdrop["id"])
        for action in ("interview", "generate"):
            request, _ = llm_request(detail, action)
            assert "Traveler" not in request and "UnassignedSpectator" not in request
            assert "exchange a parchment" not in request
            assert "An empty courtyard" in request
    # Deliberate assignments remain available for a backdrop with people.
    element = author.save_element(*ids[:2], {"name": "Deliberate guard"})
    author.update_target(*ids[:2], backdrop["id"], {"element_ids": [element["id"]]})
    request, _ = llm_request(author.target(*ids[:2], backdrop["id"]), "generate")
    assert "Deliberate guard" in request


def test_prop_reference_never_receives_character_clothing_instructions(rig):
    app, author, service, ids = rig
    asset = app.entity_library_service.import_asset("Parchment", "image/png", png_bytes("red"))
    prop = author.save_element(*ids[:2], {"name": "Parchment", "kind": "prop", "asset_id": asset["asset_id"]})
    author.update_target(*ids, {"element_ids": [prop["id"]]})
    detail = service.start(*ids, {"action": "generate"})
    detail = complete(service, ids, latest_job(detail, "generate")["id"], {"scene": "A rolled parchment.", "rendering": "Soft daylight."})
    assert "defining physical appearance" in detail["prompt"]
    assert "clothing" not in detail["prompt"]


def test_full_grid_bulk_iteration_replaces_only_unprotected_images(rig):
    app, author, service, ids = rig
    author.update_target(*ids, {"prompt": "A traveler."})
    for _ in range(2):
        detail = service.start(*ids, {"action": "render", "count": 4})
        for job in [item for item in detail["jobs"].values() if item["kind"] == "image" and item["status"] == "QUEUED"]:
            detail = complete(service, ids, job["id"], png_bytes("red"))
    first, second = detail["slots"][:2]
    service.candidate_action(*ids, first, {"action": "select"})
    service.candidate_action(*ids, second, {"action": "lock"})
    previous_slots = detail["slots"][:]
    detail = service.start(*ids, {"action": "render", "count": 4})
    assert detail["slots"][:2] == [first, second]
    assert service.image(*ids, first).exists() and service.image(*ids, second).exists()
    assert sum(before != after for before, after in zip(previous_slots, detail["slots"])) == 4
