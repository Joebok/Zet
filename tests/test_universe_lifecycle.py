import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.auxiliary_resource_service import AuxiliaryResourceService
from zet.services.config_service import Config
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.path_service import PathService
from zet.services.universe_migration_service import UniverseMigrationService
from zet.services.universe_service import UniverseService


def test_universe_contexts_bind_independent_roots_and_selection(tmp_path):
    container = tmp_path / "Library"
    project = tmp_path / "Project"
    project.mkdir()
    for name in ("Moonsea", "Eberron"):
        root = container / name
        root.mkdir(parents=True)
        (root / "universe.json").write_text(json.dumps({"universe_id": name, "name": name, "layout_version": 1}))
    service = UniverseService(container, project / "Config" / "universe-selection.json")
    base = Config(base_library_path=str(container), base_character_path="", base_asset_path="",
                  base_pipeline_path="", base_ai_queue_path="shared-queue")

    moonsea = service.bind_config(base, "Moonsea")
    eberron = service.bind_config(base, "Eberron")

    assert moonsea.base_library_path == str(container / "Moonsea")
    assert eberron.base_library_path == str(container / "Eberron")
    assert moonsea.base_ai_queue_path == eberron.base_ai_queue_path == "shared-queue"
    assert service.select("Eberron")["universe_id"] == "Eberron"
    assert service.selection() == "Eberron"
    assert Path(moonsea.base_pipeline_path) != Path(eberron.base_pipeline_path)


def test_migration_moves_library_imports_aux_images_and_can_roll_back(tmp_path):
    container, queue, project = tmp_path / "Library", tmp_path / "Queue", tmp_path / "Project"
    container.mkdir()
    queue.mkdir()
    project.mkdir()
    (container / "Characters" / "Morrow").mkdir(parents=True)
    (container / "Stories").mkdir()
    EntityLibraryRepository(container / "catalog.sqlite3").initialize()
    candidate = container / "Experiments" / "Character-Pipeline" / "Morrow" / "Adult" / "run"
    candidate.mkdir(parents=True)
    (candidate / "candidate.png").write_bytes(b"candidate")
    selected_image = candidate / "candidate.png"
    selected_hash = hashlib.sha256(selected_image.read_bytes()).hexdigest()
    legacy_store = container / "Experiments" / "Character-Pipeline" / "Morrow" / "Adult" / "local_assets.json"
    legacy_store.write_text(json.dumps({"schema_version": 1, "character": "Morrow", "phase": "Adult", "assets": {
        "body-reference:FRONT": {"pipeline": "Body-Reference", "view": "FRONT", "candidate_id": "F-001",
                                  "batch_id": "run", "image_path": str(selected_image), "image_sha256": selected_hash,
                                  "locked": True, "locked_image_path": str(selected_image), "dependencies": [], "stale": False}
    }}))
    (candidate.parent / "spec.json").write_text(json.dumps({
        "run_id": "run", "image_path": str(candidate / "candidate.png"),
        "prompt_path": str(candidate.parent / "prompt.md"),
    }))
    resource_images = container / "AuxiliaryResources" / "Images" / "morrow"
    resource_images.mkdir(parents=True)
    image = resource_images / "raven.png"
    image.write_bytes(b"raven reference")
    old_inventory = container / "AuxiliaryResources" / "AuxiliaryResources.json"
    old_inventory.write_text(json.dumps({"resources": [{
        "resource_id": "morrow", "category": "person", "label": "Morrow",
        "resource_path": str(resource_images), "template_path": "",
        "images": [{"image_id": "raven", "label": "Raven", "tag": "{{AUX:person:morrow:raven}}", "image_path": str(image)}],
        "created_at": "today", "updated_at": "today",
    }]}))
    route = queue / "Zet_File_Proxy_State" / "Routes" / "job.json"
    route.parent.mkdir(parents=True)
    route.write_text(json.dumps({"target_output_dir": str(container / "Experiments"), "_producer_id": "worker"}))
    ask = queue / "Answer" / "job" / "ask_manifest.json"
    ask.parent.mkdir(parents=True)
    ask.write_text(json.dumps({"target_output_dir": str(container / "Stories")}))
    selection = project / "Config" / "universe-selection.json"
    selection.parent.mkdir()
    selection.write_text(json.dumps({"universe_id": "old"}))
    journal = project / "Config" / "Moonsea-migration.json"
    service = UniverseMigrationService(container, journal, queue, project / "config.toml")

    assert service.dry_run()["status"] == "ready"
    assert service.apply()["status"] == "verified"
    moonsea = container / "Moonsea"
    assert (moonsea / "PipelineCandidates" / "Character-Pipeline" / "Morrow" / "Adult" / "run" / "candidate.png").is_file()
    migrated_spec = json.loads((moonsea / "PipelineCandidates" / "Character-Pipeline" / "Morrow" / "Adult" / "spec.json").read_text())
    assert migrated_spec["image_path"] == str(moonsea / "PipelineCandidates" / "Character-Pipeline" / "Morrow" / "Adult" / "run" / "candidate.png")
    store_path = moonsea / "_state" / "LocalAssets" / "Morrow" / "Adult" / "local_assets.json"
    locked = json.loads(store_path.read_text())["assets"]["body-reference:FRONT"]
    assert locked["entity_library_asset_id"]
    assert Path(locked["locked_image_path"]).is_file()
    assert LocalAssetStoreService(moonsea).locked_assets("Morrow", "Adult")[0]["entity_library_asset_id"] == locked["entity_library_asset_id"]
    assert not (moonsea / "Experiments").exists()
    assert not (moonsea / "AuxiliaryResources").exists()
    assert not (moonsea / "_state" / "AuxiliaryResources").exists()
    assert (journal.with_suffix("") / "AuxiliaryResources" / "AuxiliaryResources.json").is_file()
    assert json.loads(route.read_text())["universe_id"] == "Moonsea"
    assert json.loads(ask.read_text())["universe_id"] == "Moonsea"
    assert json.loads(selection.read_text())["universe_id"] == "Moonsea"

    config = SimpleNamespace(base_library_path=str(moonsea), base_character_path=str(moonsea / "Characters"),
                             base_asset_path=str(moonsea / "Assets"), base_pipeline_path=str(moonsea / "PipelineCandidates"),
                             base_ai_queue_path=str(queue), universe_id="Moonsea", universe_is_legacy=False)
    paths = PathService(config, project)
    resources = AuxiliaryResourceService(AuxiliaryResourceRepository(paths), paths)
    migrated = resources.repository.list_resources()[0].images[0]
    assert Path(migrated["image_path"]).is_file()
    assert resources.entity_library.resolve_legacy_reference("{{AUX:person:morrow:raven}}") ["image_path"] == migrated["image_path"]
    migration_journal = json.loads(journal.read_text())
    assert "PipelineCandidates/Character-Pipeline/Morrow/Adult/local_assets.json" in migration_journal["path_rewrites"]

    assert service.rollback()["status"] == "rolled_back"
    assert (container / "Experiments" / "Character-Pipeline" / "Morrow" / "Adult" / "run" / "candidate.png").is_file()
    assert json.loads(legacy_store.read_text())["assets"]["body-reference:FRONT"]["image_path"] == str(selected_image)
    assert old_inventory.is_file()
    assert not (container / "images").exists()
    assert json.loads(selection.read_text())["universe_id"] == "old"
