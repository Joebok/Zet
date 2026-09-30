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
    with pytest.raises(EntityLibraryServiceError, match="active logical reference"):
        service.delete_asset(asset["asset_id"])
    replacement = service.replace_asset(asset["asset_id"], "image/png", PNG + b"replacement")
    assert replacement["asset_id"] != asset["asset_id"]
    assert service.get_asset(asset["asset_id"])["status"] == "approved"
    assert service.resolve_reference("reference.current")["asset_id"] == replacement["asset_id"]


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
    resolver = StoryReferenceService(None, None, None, None, Exception)
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
