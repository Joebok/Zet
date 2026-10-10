from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService
from zet.services.path_service import PathService
from zet.services.quick_character_wizard_service import QuickCharacterWizardConflict, QuickCharacterWizardError, QuickCharacterWizardService


def png(color="red"):
    output = BytesIO()
    Image.new("RGB", (32, 48), color=color).save(output, "PNG")
    return output.getvalue()


class Generation:
    def __init__(self):
        self.requests = []
        self.jobs = {}

    def submit(self, payload):
        self.requests.append(payload)
        rid = str(len(self.requests))
        self.jobs[rid] = {"request_id": rid, "status": "QUEUED", "images": [], "error": ""}
        return self.jobs[rid]

    def status(self, rid):
        return self.jobs[rid]

    def image(self, rid, index):
        return png(), "image/png"

    def finish(self, rid, *, failed=False):
        self.jobs[rid].update(status="FAILED" if failed else "COMPLETE",
                              images=[] if failed else [{"index": 0}], error="Proxy render failed" if failed else "")


@pytest.fixture
def wizard(tmp_path):
    config = SimpleNamespace(base_library_path=str(tmp_path), ai_quick_character_wizard_model="codex:gpt-6-luna")
    paths = PathService(config)
    repository = EntityLibraryRepository(paths.entity_library_database_path())
    repository.initialize()
    library = EntityLibraryService(paths, repository)
    refreshes = []
    app = SimpleNamespace(path_service=paths, config=config, entity_library_service=library,
                          refresh_library_index=lambda: refreshes.append(True))
    generation = Generation()
    service = QuickCharacterWizardService(app, Path(__file__).resolve().parents[1], generation)
    service._submit = lambda sid, target, *args: target(sid, *args)
    service._ask = lambda prompt, schema, images: (
        {"description": "A warrior with white hair and brown armor.", "identity": "White-haired warrior",
         "observations": ["White hair"], "proposals": ["Plain matching rear armor"], "questions": []}
        if "description" in schema["properties"] else {"review": "Identity and angle match.", "refinements": []})
    return service, library, generation, refreshes


def create(service, **extra):
    payload = {"name": "Freydis", "references": [{"image": base64.b64encode(png()).decode(), "caption": "Primary identity"}], **extra}
    sid = service.create_session(payload)["session_id"]
    return service.get_session(sid)


def approve(service, session):
    return service.update_draft(session["session_id"], session["revision_id"], {
        "description": session["description"], "identity": session["identity"], "proposals_approved": True})


def render_ready(service, generation, session, view="FRONT"):
    queued = service.render(session["session_id"], session["revision_id"], view)
    generation.finish(queued["candidates"][-1]["request_id"])
    # Review completes in our synchronous worker; re-read its persisted result.
    service.get_session(session["session_id"])
    return service.get_session(session["session_id"])


def select_latest(service, session):
    return service.select(session["session_id"], session["revision_id"], session["candidates"][-1]["candidate_id"])


def all_views(service, generation, session):
    session = approve(service, session)
    for view in session["views"]:
        session = select_latest(service, render_ready(service, generation, session, view))
    return session


def test_reference_validation_and_no_partial_session(wizard):
    service, _, _, _ = wizard
    for refs, error in [([], "one to three"), ([{"image": "bad", "caption": ""}], "each reference"),
                        ([{"image": "bad", "caption": "front"}], "invalid"),
                        ([{"image": base64.b64encode(b"not an image").decode(), "caption": "front"}], "readable")]:
        with pytest.raises(QuickCharacterWizardError, match=error):
            service.create_session({"name": "Test", "references": refs})
    assert not service.root.exists()
    with pytest.raises(QuickCharacterWizardError, match="not found"):
        create(service, references=[{"asset_id": "missing", "caption": "identity"}])


def test_primary_reference_reorders_snapshots_and_is_immutable(wizard):
    service, library, _, _ = wizard
    source = library.import_asset("Source", "image/png", png("blue"))
    session = create(service, primary_index=1, references=[
        {"image": base64.b64encode(png()).decode(), "caption": "outfit"},
        {"asset_id": source["asset_id"], "caption": "identity"}])
    assert session["references"][0]["asset_id"] == source["asset_id"]
    Path(source["image_path"]).write_bytes(png("green"))
    assert service.image_path(session["session_id"], reference_index=0).read_bytes() == png("blue")
    with pytest.raises(QuickCharacterWizardError):
        service.image_path("../../", reference_index=0)


def test_proposals_revision_and_front_prerequisites(wizard):
    service, _, generation, _ = wizard
    session = create(service)
    with pytest.raises(QuickCharacterWizardConflict, match="approve"):
        service.render(session["session_id"], session["revision_id"], "FRONT")
    with pytest.raises(QuickCharacterWizardConflict, match="changed"):
        service.update_draft(session["session_id"], "old", {})
    session = approve(service, session)
    with pytest.raises(QuickCharacterWizardConflict, match="front"):
        service.render(session["session_id"], session["revision_id"], "LEFT_PROFILE")
    session = select_latest(service, render_ready(service, generation, session))
    assert generation.requests[0]["count"] == 1
    assert (generation.requests[0]["width"], generation.requests[0]["height"]) == (832, 1216)
    session = render_ready(service, generation, session, "LEFT_PROFILE")
    assert len(generation.requests[-1]["reference_images"]) == 2
    assert generation.requests[-1]["reference_images"][0]["label"].startswith("Approved front")


def test_questions_require_answers(wizard):
    service, _, _, _ = wizard
    ask = service._ask
    service._ask = lambda *args: {**ask(*args), "questions": ["Which outfit should be used?"]}
    session = create(service)
    assert session["status"] == "NEEDS_INPUT"
    with pytest.raises(QuickCharacterWizardError, match="Answer each"):
        service.generate_draft(session["session_id"], session["revision_id"], [])
    service._ask = ask
    result = service.generate_draft(session["session_id"], session["revision_id"],
                                    [{"question": session["questions"][0], "answer": "The brown armor"}])
    assert service.get_session(result["session_id"])["questions"] == []


def test_new_front_and_changed_description_invalidate_dependents(wizard):
    service, _, generation, _ = wizard
    session = all_views(service, generation, create(service))
    old_profile = session["selected"]["LEFT_PROFILE"]
    session = select_latest(service, render_ready(service, generation, session))
    assert set(session["selected"]) == {"FRONT"}
    assert next(c for c in session["candidates"] if c["candidate_id"] == old_profile)["stale"]
    with pytest.raises(QuickCharacterWizardConflict):
        service.select(session["session_id"], session["revision_id"], old_profile)
    session = service.update_draft(session["session_id"], session["revision_id"],
        {"description": "New outfit", "identity": session["identity"], "proposals_approved": True})
    assert session["selected"] == {}
    assert all(c["stale"] for c in session["candidates"])


def test_portrait_right_side_and_partial_failure(wizard):
    service, _, generation, _ = wizard
    session = approve(service, create(service, framing="portrait", side="right"))
    assert session["views"] == ["FRONT", "FRONT_RIGHT_3_4", "RIGHT_PROFILE"]
    session = select_latest(service, render_ready(service, generation, session))
    assert generation.requests[0]["width"] == generation.requests[0]["height"] == 1024
    selected_front = session["selected"]["FRONT"]
    queued = service.render(session["session_id"], session["revision_id"], "RIGHT_PROFILE")
    generation.finish(queued["candidates"][-1]["request_id"], failed=True)
    failed = service.get_session(session["session_id"])
    assert failed["selected"]["FRONT"] == selected_front
    assert failed["candidates"][-1]["error"] == "Proxy render failed"
    assert render_ready(service, generation, failed, "RIGHT_PROFILE")["candidates"][-1]["status"] == "READY"


def test_restart_reconciles_without_resubmission_and_abandon_ignores_results(wizard):
    service, _, generation, _ = wizard
    session = approve(service, create(service))
    queued = service.render(session["session_id"], session["revision_id"], "FRONT")
    restarted = QuickCharacterWizardService(service.app, service.project_root, generation)
    restarted._ask, restarted._submit = service._ask, service._submit
    assert restarted.get_session(session["session_id"])["busy"]
    generation.finish(queued["candidates"][-1]["request_id"])
    restarted.get_session(session["session_id"])
    assert restarted.get_session(session["session_id"])["candidates"][-1]["status"] == "READY"
    assert len(generation.requests) == 1
    queued = restarted.render(session["session_id"], session["revision_id"], "FRONT")
    restarted.abandon(session["session_id"], session["revision_id"])
    generation.finish(queued["candidates"][-1]["request_id"])
    assert restarted.get_session(session["session_id"])["status"] == "ABANDONED"
    with pytest.raises(QuickCharacterWizardConflict):
        restarted.accept(session["session_id"], session["revision_id"])


@pytest.mark.parametrize("has_variant", [True, False])
def test_publication_source_links_and_retry(wizard, has_variant):
    service, library, generation, refreshes = wizard
    entity = library.create_entity({"name": "Freydis", "entity_type": "character"})
    variant = library.create_variant(entity["entity_id"], {"name": "Adult", "variant_type": "life_stage"})
    source = library.import_asset("Freydis", "image/png", png("blue"))
    variant_id = variant["variant_id"] if has_variant else None
    library.update_asset(source["asset_id"], {"entity_links": [{"entity_id": entity["entity_id"],
                         "variant_id": variant_id, "role": "primary_subject"}]})
    before = Path(source["image_path"]).read_bytes()
    session = all_views(service, generation, create(service, references=[{"asset_id": source["asset_id"], "caption": "identity"}]))
    # Simulate a crash after commit but before index refresh/session update.
    service.app.refresh_library_index = lambda: (_ for _ in ()).throw(RuntimeError("Index unavailable"))
    with pytest.raises(RuntimeError, match="Index unavailable"):
        service.accept(session["session_id"], session["revision_id"])
    service.app.refresh_library_index = lambda: refreshes.append(True)
    accepted = service.accept(session["session_id"], session["revision_id"])
    assert accepted["status"] == "ACCEPTED"
    assert service.accept(session["session_id"], session["revision_id"])["publication"] == accepted["publication"]
    rows = library.repository.fetchall("SELECT * FROM assets")
    assert len(rows) == 4
    assert len(library.get_set(accepted["publication"]["set_id"])["assets"]) == 4
    for aid in accepted["publication"]["asset_ids"].values():
        asset = library.get_asset(aid)
        assert asset["derived_from_asset_id"] == source["asset_id"]
        assert len(asset["entities"]) == 1
        assert asset["entities"][0]["variant_id"] == variant_id
        assert asset["provenance"][0]["source_asset_id"] == source["asset_id"]
        assert asset["descriptors"][0]["text"] == session["identity"]
    assert Path(source["image_path"]).read_bytes() == before
    assert len(refreshes) == 1


def test_upload_only_publication_and_source_change_guard(wizard):
    service, library, generation, _ = wizard
    session = all_views(service, generation, create(service))
    accepted = service.accept(session["session_id"], session["revision_id"])
    source = library.get_asset(accepted["publication"]["source_asset_id"])
    assert Path(source["image_path"]).read_bytes() == png()
    assert hashlib.sha256(Path(source["image_path"]).read_bytes()).hexdigest() == session["references"][0]["checksum"]
    session = all_views(service, generation, create(service, references=[{"asset_id": source["asset_id"], "caption": "identity"}]))
    Path(source["image_path"]).write_bytes(png("blue"))
    with pytest.raises(QuickCharacterWizardConflict, match="changed outside"):
        service.accept(session["session_id"], session["revision_id"])


def test_universe_sessions_are_isolated(wizard, tmp_path):
    service, _, _, _ = wizard
    session = create(service)
    app = SimpleNamespace(path_service=PathService(SimpleNamespace(base_library_path=str(tmp_path / "Other"))))
    other = QuickCharacterWizardService(app, service.project_root)
    assert other.list_sessions() == []
    with pytest.raises(QuickCharacterWizardError, match="not found"):
        other.get_session(session["session_id"])


def test_interrupted_analysis_and_failed_review_are_recoverable(wizard):
    service, _, generation, _ = wizard
    session = approve(service, create(service))
    service._submit = lambda *args: None
    queued = service.render(session["session_id"], session["revision_id"], "FRONT")
    generation.finish(queued["candidates"][-1]["request_id"])
    service.get_session(session["session_id"])
    interrupted = service.get_session(session["session_id"])
    assert interrupted["candidates"][-1]["status"] == "REVIEW_FAILED"
    assert not interrupted["busy"]
    service._submit = lambda sid, target, *args: target(sid, *args)
    service.retry_review(session["session_id"], session["revision_id"], interrupted["candidates"][-1]["candidate_id"])
    assert service.get_session(session["session_id"])["candidates"][-1]["status"] == "READY"


def test_busy_rejection_and_late_review_does_not_revive_abandoned_session(wizard):
    service, _, generation, _ = wizard
    session = approve(service, create(service))
    queued = service.render(session["session_id"], session["revision_id"], "FRONT")
    with pytest.raises(QuickCharacterWizardConflict, match="running"):
        service.render(session["session_id"], session["revision_id"], "FRONT")
    generation.finish(queued["candidates"][-1]["request_id"])
    original_submit = service._submit
    service._submit = lambda *args: None
    reviewing = service.get_session(session["session_id"])
    service.abandon(session["session_id"], session["revision_id"])
    service._review_job(session["session_id"], reviewing["candidates"][-1]["candidate_id"])
    assert service.get_session(session["session_id"])["status"] == "ABANDONED"
    service._submit = original_submit


def test_refinement_uses_the_displayed_candidate(wizard):
    service, _, generation, _ = wizard
    session = approve(service, create(service))
    ready = render_ready(service, generation, session)
    previous = ready["candidates"][-1]["candidate_id"]
    refined = service.render(session["session_id"], session["revision_id"], "FRONT", "Keep the boots unchanged", previous)
    assert refined["candidates"][-1]["refinement_base_id"] == previous
    assert generation.requests[-1]["reference_images"][0]["label"].startswith("Edit this previous candidate")


def test_corrected_proposals_are_used_and_invalidate_prior_views(wizard):
    service, _, generation, _ = wizard
    session = all_views(service, generation, create(service))
    updated = service.update_draft(session["session_id"], session["revision_id"], {
        "description": session["description"], "identity": session["identity"],
        "proposals": ["Keep the cloak back unadorned"], "proposals_approved": True})
    assert updated["revision_id"] != session["revision_id"]
    assert updated["selected"] == {}
    service.render(updated["session_id"], updated["revision_id"], "FRONT")
    assert "Keep the cloak back unadorned" in generation.requests[-1]["prompt"]
    assert "Plain matching rear armor" not in generation.requests[-1]["prompt"]


def test_http_routes_validate_revision_and_publish(wizard):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from zet.web.quick_character_wizard_router import create_quick_character_wizard_router
    service, _, generation, _ = wizard
    app = FastAPI()
    app.include_router(create_quick_character_wizard_router(lambda: service))
    client = TestClient(app)
    assert client.post("/api/quick-character-wizard", content="no json").status_code == 400
    assert client.post("/api/quick-character-wizard", json={"name": "Missing images"}).status_code == 400
    response = client.post("/api/quick-character-wizard", json={"name": "Route test",
        "references": [{"image": base64.b64encode(png()).decode(), "caption": "identity"}]})
    assert response.status_code == 200
    sid = response.json()["session"]["session_id"]
    base = f"/api/quick-character-wizard/{sid}"
    session = client.get(base).json()["session"]
    assert client.get(base + "/references/0").content == png()
    assert client.post(base + "/render", json={"revision_id": "old", "view": "FRONT"}).status_code == 409
    assert client.post(base + "/refine", json={"revision_id": session["revision_id"], "instructions": ""}).status_code == 400
    session = all_views(service, generation, session)
    accepted = client.post(base + "/accept", json={"revision_id": session["revision_id"]})
    assert accepted.status_code == 200
    assert len(accepted.json()["session"]["publication"]["asset_ids"]) == 3
    assert client.post(base + "/abandon", json={"revision_id": session["revision_id"]}).status_code == 409
