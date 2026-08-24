from pathlib import Path

import pytest

from Scripts.Migrate_Scene_Subscenes_V4 import migrate_document


def test_migration_adds_v4_fields_without_enabling_subscenes():
    source = {
        "schema_version": 3,
        "file_kind": "scene",
        "scene_elements": [{"id": "backdrop", "display_name": "Backdrop"}],
        "custom": {"preserved": True},
    }

    migrated, changed = migrate_document(source, Path("scene.scene.json"))

    assert changed is True
    assert migrated["schema_version"] == 4
    assert migrated["subscenes"] == []
    assert migrated["scene_elements"][0]["subscene_id"] == ""
    assert migrated["custom"] == {"preserved": True}


def test_migration_refuses_unknown_versions():
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        migrate_document({"schema_version": 2, "file_kind": "scene"}, Path("scene.scene.json"))
