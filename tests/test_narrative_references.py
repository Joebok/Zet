import json
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from tests import test_narrative_generation as generation_tests
from tests.support.image_fixture import png_bytes
from tests.test_narrative_generation import complete, latest_job
from zet.models.narrative import NarrativeCandidate, new_id
from zet.services.narrative_generation_service import (
    NarrativeGenerationService,
    detail_without_jobs,
)
from zet.services.narrative_prompt_service import assemble_prompt, llm_request
from zet.web.narrative_router import create_narrative_router

rig = generation_tests.rig


def add_image(author, ids, payload=None, *, selected=True, history=True):
    record = author.repository.read(*ids)
    slot = record["slots"].index(None)
    candidate = asdict(NarrativeCandidate(ids[2], slot + 1, 23, status="COMPLETE"))
    candidate["image"] = f"images/{candidate['id']}.png"
    path = author.repository.folder(*ids) / candidate["image"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload or png_bytes("red"))
    record["candidates"][candidate["id"]] = candidate
    record["slots"][slot] = candidate["id"]
    if history:
        job_id = new_id()
        record["jobs"][job_id] = {"id": job_id, "kind": "render", "status": "COMPLETE",
                                  "candidate_ids": [candidate["id"]], "result": "Original exact prompt",
                                  "detail": detail_without_jobs(author.target(*ids))}
    if selected:
        record["selected_id"] = candidate["id"]
    author.repository.write(record, *ids)
    return candidate["id"]


@pytest.fixture
def pair(rig):
    app, author, generation, original = rig
    story, scene, _ = original
    source_target = author.create_target(story, scene, {"title": "Arrival courtyard", "kind": "backdrop",
                                                       "narrative": "An empty courtyard", "width": 512, "height": 256})
    source_ids = (story, scene, source_target["id"])
    candidate = add_image(author, source_ids)
    author.update_target(*source_ids, {"narrative": "Current source text differs"})
    destination = author.create_scene(story, {"title": "Second scene", "lighting": "Night"})["id"]
    source = dict(zip(("story_id", "scene_id", "target_id"), source_ids)) | {"candidate_id": candidate}
    return app, author, generation, source_ids, destination, source


def referenced(pair):
    app, _, _, ids, scene, source = pair
    target = app.narrative_reference_service.create(ids[0], scene, {"source": source})
    return ids[0], scene, target["id"]


def test_discovery_and_recovery_distinguish_generation_from_current_text(pair):
    app, author, _, ids, _, source = pair
    refs = app.narrative_reference_service
    assert refs.sources("backdrop")[0]["selected_id"] == source["candidate_id"]
    preview = refs.preview(source)
    assert preview["prompt"] == "Original exact prompt"
    assert preview["generation_inputs"]["narrative"] == "An empty courtyard"
    assert preview["current_inputs"]["narrative"] == "Current source text differs"
    record = author.repository.read(*ids)
    record["jobs"] = {}
    author.repository.write(record, *ids)
    preview = refs.preview(source)
    assert preview["generation_inputs"] is None and preview["prompt"] == ""
    with pytest.raises(ValueError):
        refs.sources("assembly")


def test_pin_refresh_reuse_and_deletion_preserve_destination(pair):
    app, author, generation, source_ids, _, _ = pair
    refs = app.narrative_reference_service
    ids = referenced(pair)
    original = refs.image(*ids).read_bytes()
    first = refs.backdrop_action(*ids, {"action": "reuse"})
    selected = first["selected_id"]
    assert generation.image(*ids, selected).read_bytes() == original
    assert not first["jobs"]
    author.update_target(*ids, {"narrative": "Destination edit"})
    new_source = add_image(author, source_ids, png_bytes("blue"))
    assert refs.image(*ids).read_bytes() == original
    refreshed = refs.backdrop_action(*ids, {"action": "refresh"})
    assert refreshed["source_snapshot"]["candidate_id"] == new_source
    assert refreshed["narrative"] == "Destination edit"
    assert refreshed["selected_id"] == selected
    assert refs.image(*ids).read_bytes() == png_bytes("blue")
    reused = refs.backdrop_action(*ids, {"action": "reuse"})
    assert reused["selected_id"] == selected and reused["slots"][0] == selected
    author.delete(*source_ids, confirmed=[new_source])
    assert generation.image(*ids, selected).read_bytes() == original
    assert refs.image(*ids).read_bytes() == png_bytes("blue")
    with pytest.raises((KeyError, ValueError)):
        refs.backdrop_action(*ids, {"action": "refresh"})


def test_attach_and_copy_are_explicit_and_local_slots_never_replace_images(pair):
    app, author, _, _, scene, source = pair
    refs = app.narrative_reference_service
    record = author.create_target(source["story_id"], scene, {"title": "Existing", "kind": "backdrop", "narrative": "Keep my edits"})
    ids = (source["story_id"], scene, record["id"])
    refs.backdrop_action(*ids, {"action": "attach", "source": source})
    assert author.target(*ids)["narrative"] == "Keep my edits"
    copied = refs.backdrop_action(*ids, {"action": "copy_inputs", "basis": "generation"})
    assert copied["narrative"] == "An empty courtyard"
    for _ in range(8):
        refs.backdrop_action(*ids, {"action": "reuse"})
    before = author.repository.read(*ids)
    with pytest.raises(ValueError, match="Clear a slot"):
        refs.backdrop_action(*ids, {"action": "reuse"})
    assert author.repository.read(*ids) == before


def test_crop_keeps_aspect_bounds_and_requested_dimensions(pair):
    app, author, _, source_ids, _, source = pair
    image = Image.new("RGBA", (512, 256), "red")
    image.paste("blue", (256, 0, 512, 256))
    stream = BytesIO()
    image.save(stream, format="PNG")
    source["candidate_id"] = add_image(author, source_ids, stream.getvalue())
    ids = referenced(pair)
    author.update_target(*ids, {"width": 256, "height": 256,
                               "backdrop_adaptation": {"operation": "crop", "crop": {"center_x": 1, "center_y": 1, "zoom": 1}}})
    payload = app.narrative_reference_service.crop(*ids)
    with Image.open(BytesIO(payload)) as cropped:
        assert cropped.size == (256, 256)
        assert cropped.getpixel((128, 128)) == (0, 0, 255, 255)
    result = app.narrative_reference_service.backdrop_action(*ids, {"action": "crop"})
    assert result["candidates"][result["selected_id"]]["backdrop_adaptation"]["operation"] == "crop"


@pytest.mark.parametrize("settings", [{"crop": {"zoom": 0}}, {"crop": {"center_x": float("nan")}},
                                      {"operation": "invalid"}, {"operation": []}, {"direction": []}, {"expand_side": "diagonal"}, {"expand_side": []}])
def test_invalid_crop_and_adaptation_do_not_save(pair, settings):
    _, author, _, _, _, _ = pair
    ids = referenced(pair)
    before = author.repository.read(*ids)
    with pytest.raises(ValueError):
        author.update_target(*ids, {"backdrop_adaptation": settings})
    assert author.repository.read(*ids) == before


def test_subscene_import_copies_only_assigned_elements_and_keeps_destination_context(rig):
    app, author, _, ids = rig
    source = {"story_id": ids[0], "scene_id": ids[1], "target_id": ids[2]}
    author.update_target(*ids, {"prompt": "Source prompt for inspection"})
    unrelated = author.save_element(*ids[:2], {"name": "Unrelated"})
    destination = author.create_scene(ids[0], {"title": "Night scene", "lighting": "Moonlight"})["id"]
    imported = app.narrative_reference_service.create(ids[0], destination, {"source": source})
    assert imported["context"]["lighting"] == "Moonlight"
    assert len(imported["elements"]) == 1
    assert imported["elements"][0]["id"] != author.target(*ids)["elements"][0]["id"]
    assert unrelated["id"] not in imported["element_ids"]
    assert imported["prompt"] == "" and imported["interview"] == [] and imported["jobs"] == {}
    assert imported["source_snapshot"]["current_inputs"]["prompt"] == "Source prompt for inspection"
    assert imported["selected_id"] is None and imported["slots"] == [None] * 8
    assert author.references(imported) == []
    author.update_target(*ids, {"narrative": "Changed original"})
    assert author.target(ids[0], destination, imported["id"])["narrative"] == "A traveler arrives"


def test_import_preserves_library_bindings_and_supports_explicit_mapping(rig, monkeypatch):
    app, author, _, ids = rig
    source_element = author.target(*ids)["elements"][0]
    monkeypatch.setattr(author, "library_asset", lambda asset: {"asset_id": asset, "image_path": str(Path(__file__)), "label": "Traveler"})
    author.save_element(*ids[:2], {"asset_id": "identity-binding"}, source_element["id"])
    destination = author.create_scene(ids[0], {"title": "Other"})["id"]
    existing = author.save_element(ids[0], destination, {"name": "Traveler", "appearance": "Destination appearance"})
    source = {"story_id": ids[0], "scene_id": ids[1], "target_id": ids[2]}
    copied = app.narrative_reference_service.create(ids[0], destination, {"source": source, "copy_visual_context": True})
    assert copied["elements"][0]["asset_id"] == "identity-binding"
    assert copied["visual_overrides"] == author.target(*ids)["context"]
    mapped = app.narrative_reference_service.create(ids[0], destination, {"source": source, "element_mappings": {source_element["id"]: existing["id"]}})
    assert mapped["element_ids"] == [existing["id"]]
    assert mapped["elements"][0]["appearance"] == "Destination appearance"


def test_import_validation_and_write_failure_leave_no_partial_target(pair, monkeypatch):
    app, author, _, ids, scene, source = pair
    before = author.repository.read(ids[0], scene)
    with pytest.raises(ValueError):
        app.narrative_reference_service.create(ids[0], scene, {"source": source, "element_mappings": {"unknown": "invalid"}})
    write = author.repository.write
    def fail_parent(record, story, scene_id="", target=""):
        if scene_id == scene and not target:
            raise OSError("disk unavailable")
        return write(record, story, scene_id, target)
    monkeypatch.setattr(author.repository, "write", fail_parent)
    with pytest.raises(OSError):
        app.narrative_reference_service.create(ids[0], scene, {"source": source})
    assert author.repository.read(ids[0], scene) == before
    assert list(author.repository.folder(ids[0], scene).glob("*/target.json")) == []


def test_adaptation_reference_order_and_prompt_roles(pair, monkeypatch):
    app, author, _, _, _, _ = pair
    ids = referenced(pair)
    asset = app.narrative_reference_service.image(*ids)
    monkeypatch.setattr(author, "library_asset", lambda value: {"asset_id": value, "image_path": str(asset), "label": "Prop"})
    prop = author.save_element(*ids[:2], {"name": "Fountain", "kind": "prop", "asset_id": "fountain"})
    author.update_target(*ids, {"element_ids": [prop["id"]], "backdrop_adaptation": {"operation": "expand", "expand_side": "left", "direction": "Add another arch"}})
    detail = author.target(*ids)
    refs = author.references(detail)
    assert [ref["role"] for ref in refs] == ["backdrop source", "appearance"]
    assert [ref["image_index"] for ref in refs] == [1, 2]
    prompt = assemble_prompt(detail, {"scene": "Extend the courtyard", "rendering": "Moonlight"}, refs)
    assert "<image1> is the original backdrop" in prompt and "<image2> depicts Fountain" in prompt
    assert "toward left" in prompt
    request, _ = llm_request(detail, "interview", "Change viewpoint")
    assert '"role": "backdrop source"' in request and "Add another arch" in request
    request, _ = llm_request(detail, "generate")
    assert "Begin with an instruction to adapt the supplied backdrop" in request
    assert "Adapt the supplied environment-only backdrop" in prompt
    author.update_target(*ids, {"element_ids": [author.save_element(*ids[:2], {"name": str(i), "asset_id": "fountain"})["id"] for i in range(10)]})
    with pytest.raises(ValueError, match="ten"):
        author.references(author.target(*ids))


def test_frozen_render_retry_after_refresh_restart_and_source_deletion(pair):
    app, author, generation, source_ids, _, _ = pair
    ids = referenced(pair)
    author.update_target(*ids, {"prompt": "My literal edit", "width": 512, "height": 256,
                               "backdrop_adaptation": {"operation": "viewpoint", "direction": "Look from the arch"}})
    started = generation.start(*ids, {"action": "render"})
    candidate_id = started["slots"][0]
    job = latest_job(started, "image")
    parent = latest_job(started, "render")
    frozen = Path(parent["references"][0]["path"]).read_bytes()
    complete(generation, ids, job["id"], b"", failed=True)
    updated_source = add_image(author, source_ids, png_bytes("blue"))
    app.narrative_reference_service.backdrop_action(*ids, {"action": "refresh"})
    author.update_target(*ids, {"prompt": "New prompt", "width": 1024, "backdrop_adaptation": {"operation": "expand"}})
    author.delete(*source_ids, confirmed=[updated_source])
    restarted = NarrativeGenerationService(author)
    retried = restarted.candidate_action(*ids, candidate_id, {"action": "retry"})
    retried_job = latest_job(retried, "image")
    ask = restarted.proxy.client.ask_root / retried_job["id"]
    assert (ask / "prompt.md").read_text() == "My literal edit"
    manifest = json.loads((ask / "ask_manifest.json").read_text())
    assert manifest["render_overrides"]["width"] == 512 and manifest["render_overrides"]["height"] == 256
    assert manifest["seed"] == started["candidates"][candidate_id]["seed"]
    assert Path(parent["references"][0]["path"]).read_bytes() == frozen
    assert retried["candidates"][candidate_id]["backdrop_adaptation"]["operation"] == "viewpoint"
    result = complete(restarted, ids, retried_job["id"], png_bytes("green"))
    assert result["candidates"][candidate_id]["status"] == "COMPLETE"


def test_late_interview_and_prompt_do_not_override_changed_adaptation(pair):
    _, author, generation, _, _, _ = pair
    ids = referenced(pair)
    started = generation.start(*ids, {"action": "interview"})
    job = latest_job(started, "interview")
    author.update_target(*ids, {"backdrop_adaptation": {"operation": "viewpoint", "direction": "New view"}})
    result = complete(generation, ids, job["id"], {"narrative": "Late old view", "staging": "Old staging", "physical_context": "Old", "framing": "Wide", "questions": []})
    assert result["narrative"] != "Late old view" and result["interview"][-1]["draft"]["narrative"] == "Late old view"
    started = generation.start(*ids, {"action": "synthesize"})
    job = latest_job(started, "synthesize")
    author.update_target(*ids, {"backdrop_adaptation": {"operation": "expand"}})
    result = complete(generation, ids, job["id"], {"scene": "Old view", "rendering": "Old light"})
    assert result["prompt"] == "" and result["jobs"][job["id"]]["result"]


def test_http_source_actions_and_assembly_use_local_candidates(pair):
    app, author, _, source_ids, scene, source = pair
    web = FastAPI()
    web.include_router(create_narrative_router(lambda: app))
    client = TestClient(web)
    assert client.get("/api/narrative/sources?kind=backdrop").status_code == 200
    assert client.post("/api/narrative/sources/preview", json=source).json()["prompt"] == "Original exact prompt"
    base = f"/api/narrative/stories/{source_ids[0]}/scenes/{scene}"
    target = client.post(base + "/references", json={"source": source}).json()
    target_base = base + "/targets/" + target["id"]
    reused = client.post(target_base + "/backdrop-source", json={"action": "reuse"}).json()
    assert client.get(target_base + "/source-image").content == png_bytes("red")
    assert client.get(target_base + "/crop-preview").status_code == 200
    assembly = author.create_target(source_ids[0], scene, {"title": "Final", "kind": "assembly"})
    updated = author.update_target(source_ids[0], scene, assembly["id"], {"layers": [{"target_id": target["id"], "candidate_id": reused["selected_id"], "role": "base"}]})
    pinned = author.repository.folder(source_ids[0], scene, assembly["id"]) / updated["layers"][0]["source_file"]
    author.delete(*source_ids, confirmed=[source["candidate_id"]])
    assert pinned.read_bytes() == png_bytes("red")


def test_unselected_source_requires_explicit_candidate_and_rejects_foreign_paths(pair):
    app, author, _, ids, scene, source = pair
    record = author.repository.read(*ids)
    record["selected_id"] = None
    author.repository.write(record, *ids)
    choice = {key: source[key] for key in ("story_id", "scene_id", "target_id")}
    with pytest.raises(ValueError, match="explicitly"):
        app.narrative_reference_service.create(ids[0], scene, {"source": choice})
    assert author.repository.read(ids[0], scene)["target_ids"] == []
    app.narrative_reference_service.create(ids[0], scene, {"source": source})
    record["candidates"][source["candidate_id"]]["image"] = "../../outside.png"
    author.repository.write(record, *ids)
    with pytest.raises(ValueError, match="inside"):
        app.narrative_reference_service.create(ids[0], scene, {"source": source})


def test_source_picker_can_import_from_another_story_in_current_universe(pair):
    app, author, _, ids, _, source = pair
    story = author.create_story({"title": "Another story"})
    scene = author.create_scene(story["id"], {"title": "A different scene"})
    copied = app.narrative_reference_service.create(story["id"], scene["id"], {"source": source})
    assert copied["source_snapshot"]["story_id"] == ids[0]
    assert app.narrative_reference_service.image(story["id"], scene["id"], copied["id"]).read_bytes() == png_bytes("red")
