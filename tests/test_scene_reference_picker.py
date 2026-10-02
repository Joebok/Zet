from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from zet.app import ZetApp


@pytest.mark.parametrize("entities,category", [(None, ""), ([], ""), ([{"name": "Mira", "entity_type": "character"}], "character")])
def test_approved_unassociated_images_remain_in_scene_picker(entities, category):
    app = ZetApp.__new__(ZetApp)
    app.image_catalog_service = Mock(list_items=Mock(return_value=[]))
    asset = {"status": "approved", "label": "Image", "file_name": "image.png", "origin": "uploaded",
             "image_path": "image.png", "thumbnail_path": "image.png", "asset_id": "example",
             "descriptor_ready": False}
    if entities is not None:
        asset["entities"] = entities
    app.entity_library_service = SimpleNamespace(list_assets=lambda: [asset])
    rows = app.scene_image_reference_rows()
    assert len(rows) == 1
    assert rows[0].semantic_category == category
    assert rows[0].tag == "{{LIB:ASSET:example}}"
