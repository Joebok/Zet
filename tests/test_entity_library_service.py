import json
from types import SimpleNamespace

import pytest

from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService, EntityLibraryServiceError
from zet.services.path_service import PathService
from zet.services.story_reference_service import StoryReferenceService
from support.project_fixture import write_project_fixture
from fastapi.testclient import TestClient
from zet.web.app import create_app


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + b"\x00\x00\x00\x20\x00\x00\x00\x10" + b"\x08\x06\x00\x00\x00"


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "Zet_Library_v5"
    config = SimpleNamespace(base_library_path=str(root))
    paths = PathService(config, tmp_path)
    repository = EntityLibraryRepository(paths.entity_library_database_path())
    repository.initialize()
    return root, EntityLibraryService(paths, repository)


def test_assets_entities_sets_facets_descriptors_and_logical_references(library):
    root, service = library
    entity = service.create_entity({"name": "Tsaeytte", "entity_type": "character"})
    variant = service.create_variant(entity["entity_id"], {"name": "Adult", "variant_type": "life_stage"})
    reference_set = service.create_set({"name": "Adult Head References", "set_type": "identity", "entity_id": entity["entity_id"]})
    asset = service.import_asset("Front Portrait", "image/png", PNG)
    asset = service.update_asset(asset["asset_id"], {
        "entity_links": [{"entity_id": entity["entity_id"], "variant_id": variant["variant_id"], "role": "primary_subject"}],
        "set_ids": [reference_set["set_id"]],
        "facets": [{"namespace": "view", "value": "front"}, {"namespace": "framing", "value": "head"}],
    })
    service.save_descriptor({"owner_type": "entity", "owner_id": entity["entity_id"], "descriptor_type": "prompt_identity", "text": "High elf with violet eyes."})
    service.save_descriptor({"owner_type": "set", "owner_id": reference_set["set_id"], "descriptor_type": "prompt_identity", "text": "Adult head reference."})
    service.save_descriptor({"owner_type": "asset", "owner_id": asset["asset_id"], "descriptor_type": "prompt_identity", "text": "Direct front portrait."})
    assert [item["text"] for item in service.effective_descriptors(asset["asset_id"], reference_set["set_id"]) if item["descriptor_type"] == "prompt_identity"] == ["Direct front portrait."]
    service.save_logical_reference({"reference_key": "tsaeytte.adult.head", "label": "Adult head", "asset_id": asset["asset_id"]})
    assert service.resolve_reference("tsaeytte.adult.head")["asset_id"] == asset["asset_id"]
    filtered = service.search_picker(entity_id=entity["entity_id"], variant_id=variant["variant_id"], facet_namespace="view", facet_value="front")
    assert [item["asset_id"] for item in filtered] == [asset["asset_id"]]
    assert filtered[0]["descriptor_ready"] is True
    assert (root / "images" / asset["file_name"]).is_file()


def test_locked_costume_image_has_searchable_classification_and_stable_reference(library):
    _, service = library
    asset = service.import_asset("Generated image", "image/png", PNG, origin="pipeline")

    classified = service.classify_costume_image(asset["asset_id"], character="Tsaeytte", phase="Youth",
                                                costume="Woodland_outfit", view="FRONT_LEFT_3_4")

    assert classified["label"] == "Tsaeytte · Youth · Woodland outfit · Front Left 3 4"
    assert classified["logical_reference"]["reference_key"] == "tsaeytte.youth.costume-dressing.woodland-outfit.front-left-3-4"
    results = service.search_picker(q="TSAEYTTE youth woodland outfit")
    assert [item["asset_id"] for item in results] == [asset["asset_id"]]
    assert any(item["role"] == "worn_costume" for item in classified["entities"])
    assert {item["namespace"] for item in classified["facets"]} == {"pipeline", "view"}


def test_costume_reference_backfill_converts_exact_legacy_scene_tag_once(library):
    root, service = library
    asset = service.import_asset("Generated image", "image/png", PNG, origin="pipeline")
    store = root / "_state" / "LocalAssets" / "Tsaeytte" / "Youth" / "local_assets.json"
    store.parent.mkdir(parents=True)
    store.write_text(json.dumps({"assets": {"costume-dressing:woodland_outfit:FRONT": {
        "pipeline": "Costume-Dressing", "qualifier": "Woodland_outfit", "view": "FRONT",
        "locked": True, "stale": False, "entity_library_asset_id": asset["asset_id"],
    }}}), encoding="utf-8")
    scene = root / "Stories" / "FirstDay" / "Chapter-01.scene.json"
    scene.parent.mkdir(parents=True)
    original = {"scene_elements": [{"character": "Tsaeytte", "phase": "Youth", "costume": "Woodland outfit",
                                    "reference_images": [{"tag": "{{ASSET:Tsaeytte:Youth:28:Costume | Front | Woodland outfit}}",
                                                         "roles": ["visual reference"], "notes": "Keep the pose."}]}]}
    scene.write_text(json.dumps(original), encoding="utf-8")

    assert service.backfill_costume_references(dry_run=True)["scene_references"] == 1
    report = service.backfill_costume_references(dry_run=False)
    assert report["scene_references"] == 1
    migrated = json.loads(scene.read_text(encoding="utf-8"))["scene_elements"][0]["reference_images"][0]
    assert migrated == {"roles": ["visual reference"], "notes": "Keep the pose.",
                        "reference_key": "tsaeytte.youth.costume-dressing.woodland-outfit.front"}
    assert service.backfill_costume_references(dry_run=True)["scene_references"] == 0


def test_usage_blocks_archival_and_image_replacement_updates_logical_reference(library):
    root, service = library
    asset = service.import_asset("Reference", "image/png", PNG)
    service.save_logical_reference({"reference_key": "reference.current", "asset_id": asset["asset_id"]})
    scene = root / "Stories" / "Story" / "Scene.scene.json"
    scene.parent.mkdir(parents=True)
    scene.write_text(json.dumps({"scene_elements": [{"reference_images": [{"asset_id": asset["asset_id"]}, {"reference_key": "reference.current"}]}]}), encoding="utf-8")
    report = service.refresh_usages(root)
    assert report["current"] == 2
    assert len(service.usage_for_asset(asset["asset_id"])) == 2
    with pytest.raises(EntityLibraryServiceError, match="current consumer"):
        service.delete_asset(asset["asset_id"])
    replacement = service.replace_asset(asset["asset_id"], "image/png", PNG + b"replacement")
    assert replacement["asset_id"] != asset["asset_id"]
    assert service.get_asset(asset["asset_id"])["status"] == "approved"
    assert service.resolve_reference("reference.current")["asset_id"] == replacement["asset_id"]


def test_archive_deactivates_logical_references_and_keeps_them_on_asset_details(library):
    _, service = library
    asset = service.import_asset("Reference to archive", "image/png", PNG)
    service.save_logical_reference({"reference_key": "reference.to_archive", "asset_id": asset["asset_id"]})

    archived = service.delete_asset(asset["asset_id"])

    assert archived["status"] == "archived"
    assert archived["logical_references"] == [{
        "reference_key": "reference.to_archive",
        "label": "reference.to_archive",
        "set_id": None,
        "status": "inactive",
    }]
    with pytest.raises(EntityLibraryServiceError, match="missing or inactive"):
        service.resolve_reference("reference.to_archive")


def test_obsolete_assets_are_hidden_from_inventory_search_by_default(library):
    _, service = library
    obsolete = service.import_asset("Obsolete image", "image/png", PNG)
    service.set_asset_status(obsolete["asset_id"], "obsolete")
    approved = service.import_asset("Approved image", "image/png", PNG)

    assert {item["asset_id"] for item in service.list_assets(hide_obsolete=True)} == {approved["asset_id"]}
    assert {item["asset_id"] for item in service.list_assets()} == {approved["asset_id"], obsolete["asset_id"]}
    assert [item["asset_id"] for item in service.list_assets(status="obsolete")] == [obsolete["asset_id"]]


def test_locked_pipeline_sync_registers_only_pipeline_rows(library, tmp_path):
    _, service = library
    source = tmp_path / "locked.png"
    source.write_bytes(PNG)
    service.pipeline_provider = lambda: [
        SimpleNamespace(source_type="pipeline", available=True, image_path=str(source), tag="{{ASSET:Tsaeytte:Adult:1}}", mime_type="image/png", label="Locked front", character="", costume=""),
        SimpleNamespace(source_type="pipeline", available=True, candidate_pending=True, image_path=str(source), tag="candidate", mime_type="image/png", label="Candidate", character="", costume=""),
    ]
    rows = service.search_picker()
    assert len(rows) == 1
    assert rows[0]["origin"] == "pipeline"


def test_scene_reference_resolution_records_library_asset_and_checksum(library):
    _, service = library
    entity = service.create_entity({"name": "Morrow", "entity_type": "creature"})
    reference_set = service.create_set({"name": "Morrow forms", "set_type": "identity", "entity_id": entity["entity_id"]})
    asset = service.import_asset("Raven form", "image/png", PNG)
    service.update_asset(asset["asset_id"], {
        "entity_links": [{"entity_id": entity["entity_id"], "role": "primary_subject"}],
        "set_ids": [reference_set["set_id"]],
    })
    service.save_logical_reference({
        "reference_key": "morrow.raven",
        "asset_id": asset["asset_id"],
        "set_id": reference_set["set_id"],
    })
    resolver = StoryReferenceService(service.path_service, None, None, None, Exception)
    resolver.entity_library_service = service

    references = resolver.resolve_scene_references(json.dumps({
        "scene_elements": [{"reference_images": [
            {"asset_id": asset["asset_id"]}, {"reference_key": "morrow.raven"},
        ]}],
    }))

    assert {item["asset_id"] for item in references} == {asset["asset_id"]}
    assert all(item["checksum"] == asset["checksum"] for item in references)
    logical = next(item for item in references if item.get("reference_key"))
    assert logical["set_id"] == reference_set["set_id"]


def test_inventory_search_matches_labels_variants_and_active_reference_keys(library):
    _, service = library
    entity = service.create_entity({"name": "Morrow", "entity_type": "creature"})
    variant = service.create_variant(entity["entity_id"], {"name": "Raven Form", "variant_type": "form"})
    asset = service.import_asset("Black-winged portrait", "image/png", PNG)
    service.update_asset(asset["asset_id"], {"entity_links": [{"entity_id": entity["entity_id"], "variant_id": variant["variant_id"], "role": "primary_subject"}]})
    service.save_logical_reference({"reference_key": "morrow.raven.front", "asset_id": asset["asset_id"]})

    for query in ("black-winged", "raven form", "morrow.raven.front"):
        assert [item["asset_id"] for item in service.list_assets(q=query)] == [asset["asset_id"]]


def test_entity_merge_preserves_assets_descriptors_and_reuses_pipeline_names(library, tmp_path):
    _, service = library
    source = service.create_entity({"name": "Old Name", "entity_type": "character", "description": "Old description"})
    target = service.create_entity({"name": "New Name", "entity_type": "character", "description": "New description"})
    source_variant = service.create_variant(source["entity_id"], {"name": "Adult", "variant_type": "life_stage", "description": "Source stage"})
    target_variant = service.create_variant(target["entity_id"], {"name": "Adult", "variant_type": "life_stage", "description": "Target stage"})
    source_asset = service.import_asset("Old portrait", "image/png", PNG)
    target_asset = service.import_asset("New portrait", "image/png", PNG + b"target")
    service.update_asset(source_asset["asset_id"], {"entity_links": [{"entity_id": source["entity_id"], "variant_id": source_variant["variant_id"], "role": "primary_subject"}]})
    service.update_asset(target_asset["asset_id"], {"entity_links": [{"entity_id": source["entity_id"], "role": "primary_subject"}, {"entity_id": target["entity_id"], "role": "primary_subject"}]})
    service.save_descriptor({"owner_type": "entity", "owner_id": source["entity_id"], "descriptor_type": "prompt_identity", "text": "Source identity"})
    service.save_descriptor({"owner_type": "entity", "owner_id": target["entity_id"], "descriptor_type": "prompt_identity", "text": "Target identity"})
    image = tmp_path / "pipeline.png"
    image.write_bytes(PNG)
    service.pipeline_provider = lambda: [SimpleNamespace(source_type="pipeline", available=True, candidate_pending=False, asset_state="LOCKED", image_path=str(image), tag="old-name-pipeline", mime_type="image/png", label="Pipeline", character="Old Name", costume="", phase="Adult", pipeline="Test")]

    preview = service.preview_merge("entity", source["entity_id"], target["entity_id"])
    resolutions = {item["key"]: "target" for item in preview["conflicts"]}
    service.merge_records("entity", source["entity_id"], target["entity_id"], preview["token"], resolutions)
    service.list_assets()

    assert service.repository.fetchone("SELECT variant_id FROM asset_entities WHERE asset_id=? AND role='primary_subject'", (source_asset["asset_id"],))["variant_id"] == target_variant["variant_id"]
    assert service.repository.fetchone("SELECT count(*) AS n FROM asset_entities WHERE asset_id=? AND entity_id=?", (target_asset["asset_id"], target["entity_id"]))["n"] == 1
    assert service.get_asset(source_asset["asset_id"])["image_path"]
    assert service.repository.fetchone("SELECT text FROM descriptors WHERE owner_type='entity' AND owner_id=? AND descriptor_type='prompt_identity'", (target["entity_id"],))["text"] == "Target identity"
    pipeline_asset = next(item for item in service.list_assets() if item["origin"] == "pipeline")
    assert pipeline_asset["entities"][0]["entity_id"] == target["entity_id"]
    assert pipeline_asset["entities"][0]["variant_id"] == target_variant["variant_id"]


def test_merge_preview_rejects_stale_data_and_set_merge_redirects_references(library):
    _, service = library
    source = service.create_set({"name": "Old set", "set_type": "identity", "description": "Source purpose"})
    target = service.create_set({"name": "New set", "set_type": "identity", "description": "Target purpose"})
    member = service.import_asset("Member", "image/png", PNG)
    source = service.add_set_asset(source["set_id"], member["asset_id"], role="alternate", sort_order=0)
    target = service.add_set_asset(target["set_id"], member["asset_id"], role="primary", sort_order=0)
    service.save_logical_reference({"reference_key": "set.preferred", "asset_id": member["asset_id"], "set_id": source["set_id"]})
    preview = service.preview_merge("set", source["set_id"], target["set_id"])
    service.update_set(target["set_id"], {"name": "Renamed target", "description": "Changed after review"})
    with pytest.raises(EntityLibraryServiceError, match="changed after preview"):
        service.merge_records("set", source["set_id"], target["set_id"], preview["token"], {item["key"]: "target" for item in preview["conflicts"]})
    preview = service.preview_merge("set", source["set_id"], target["set_id"])
    resolutions = {item["key"]: "source" if item["key"] == f"member:{member['asset_id']}:role" else "target" for item in preview["conflicts"]}
    service.merge_records("set", source["set_id"], target["set_id"], preview["token"], resolutions)

    assert service.get_set(target["set_id"])["assets"][0]["role"] == "alternate"
    assert service.repository.fetchone("SELECT set_id FROM logical_references WHERE reference_key='set.preferred'")["set_id"] == target["set_id"]
    assert service.repository.fetchone("SELECT count(*) AS n FROM reference_sets WHERE set_id=?", (source["set_id"],))["n"] == 0


def test_variant_merge_unifies_image_assignments_and_resolves_descriptor_conflicts(library):
    _, service = library
    entity = service.create_entity({"name": "Morrow", "entity_type": "creature"})
    source = service.create_variant(entity["entity_id"], {"name": "Raven", "variant_type": "form"})
    target = service.create_variant(entity["entity_id"], {"name": "Bird form", "variant_type": "form"})
    asset = service.import_asset("Raven reference", "image/png", PNG)
    service.update_asset(asset["asset_id"], {"entity_links": [{"entity_id": entity["entity_id"], "variant_id": source["variant_id"], "role": "primary_subject"}]})
    service.save_descriptor({"owner_type": "variant", "owner_id": source["variant_id"], "descriptor_type": "prompt_identity", "text": "Source form"})
    service.save_descriptor({"owner_type": "variant", "owner_id": target["variant_id"], "descriptor_type": "prompt_identity", "text": "Target form"})
    preview = service.preview_merge("variant", source["variant_id"], target["variant_id"])
    resolution = {item["key"]: "source" for item in preview["conflicts"]}
    service.merge_records("variant", source["variant_id"], target["variant_id"], preview["token"], resolution)

    assert service.repository.fetchone("SELECT variant_id FROM asset_entities WHERE asset_id=?", (asset["asset_id"],))["variant_id"] == target["variant_id"]
    assert service.repository.fetchone("SELECT text FROM descriptors WHERE owner_type='variant' AND owner_id=? AND descriptor_type='prompt_identity'", (target["variant_id"],))["text"] == "Source form"
    assert service.repository.fetchone("SELECT count(*) AS n FROM variants WHERE variant_id=?", (source["variant_id"],))["n"] == 0


def test_facet_merge_deduplicates_image_links_and_used_facets_block_delete(library):
    _, service = library
    first = service.create_facet({"namespace": "view", "value": "front"})
    second = service.create_facet({"namespace": "view", "value": "forward"})
    asset = service.import_asset("Portrait", "image/png", PNG)
    service.update_asset(asset["asset_id"], {"facets": [{"namespace": "view", "value": "front"}, {"namespace": "view", "value": "forward"}]})
    assert len([item for item in service.list_facets() if item["namespace"] == "view"]) == 2
    with pytest.raises(EntityLibraryServiceError, match="assigned to 1 image"):
        service.delete_facet(first["facet_id"])
    preview = service.preview_merge("facet", second["facet_id"], first["facet_id"])
    service.merge_records("facet", second["facet_id"], first["facet_id"], preview["token"])

    assert service.repository.fetchone("SELECT count(*) AS n FROM asset_facets WHERE asset_id=?", (asset["asset_id"],))["n"] == 1
    assert service.repository.fetchone("SELECT count(*) AS n FROM facets WHERE facet_id=?", (second["facet_id"],))["n"] == 0


def test_entity_library_api_import_filter_and_detail(tmp_path):
    root = tmp_path / "Zet_Library_v5"
    root.mkdir()
    config_path = write_project_fixture(tmp_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "[BaseFolders]\n", f'[BaseFolders]\nBaseLibraryPath = "{root.as_posix()}"\n'
        ), encoding="utf-8",
    )
    with TestClient(create_app(config_path)) as client:
        entity = client.post("/api/entity-library/entities", json={"name": "Morrow", "entity_type": "creature"})
        assert entity.status_code == 200, entity.text
        entity_id = entity.json()["entity"]["entity_id"]
        imported = client.post(
            "/api/entity-library/assets", params={"label": "Raven form"}, content=PNG,
            headers={"content-type": "image/png"},
        )
        assert imported.status_code == 200, imported.text
        asset_id = imported.json()["asset"]["asset_id"]
        updated = client.patch(
            f"/api/entity-library/assets/{asset_id}",
            json={"entity_links": [{"entity_id": entity_id, "role": "primary_subject"}], "facets": [{"namespace": "form", "value": "raven"}]},
        )
        assert updated.status_code == 200, updated.text
        picker = client.get("/api/entity-library/picker", params={"entity_id": entity_id, "facet_namespace": "form", "facet_value": "raven"})
        assert picker.status_code == 200, picker.text
        assert [item["asset_id"] for item in picker.json()["assets"]] == [asset_id]
        detail = client.get(f"/api/entity-library/assets/{asset_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["asset"]["entities"][0]["name"] == "Morrow"
