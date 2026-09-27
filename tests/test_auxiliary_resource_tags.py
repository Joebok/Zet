from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from zet.services.auxiliary_resource_tags import (
    auxiliary_resource_image_for_tag,
    auxiliary_resource_tag,
    auxiliary_resource_tags_in_text,
    parse_auxiliary_resource_tag,
)


class AuxiliaryResourceTagTests(unittest.TestCase):
    def test_resolves_imported_image_from_record_oriented_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            library = project / "library"
            records = library / "ImageCatalog" / "Records"
            records.mkdir(parents=True)
            image_path = library / "ImageCatalog" / "Images" / "jewelry.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"image")
            tag = "{{IMAGE:img_jewelry}}"
            (project / "config.toml").write_text(
                "\n".join([
                    "[BaseFolders]",
                    f'BaseLibraryPath = "{library.as_posix()}"',
                    'BaseCharacterPath = "Characters"',
                    'BaseAssetPath = "Assets"',
                    'BasePipelinePath = "Pipelines"',
                    'BaseAIQueuePath = "AI_Queue"',
                ]),
                encoding="utf-8",
            )
            (library / "ImageCatalog" / "ImageCatalog.json").write_text(
                json.dumps({"schema_version": 3, "status": "complete"}),
                encoding="utf-8",
            )
            (records / "img_jewelry.json").write_text(
                json.dumps({
                    "record_version": 1,
                    "catalog_id": "img_jewelry",
                    "source_key": "import:img_jewelry",
                    "managed_image": {
                        "catalog_id": "img_jewelry",
                        "tag": tag,
                        "label": "Jewelry",
                        "image_path": str(image_path),
                    },
                }),
                encoding="utf-8",
            )

            references = auxiliary_references_for_texts(project, [tag], [])

            self.assertEqual(1, len(references))
            self.assertEqual("imported_image", references[0]["role"])
            self.assertEqual(tag, references[0]["tag"])
            self.assertEqual(str(image_path), references[0]["path"])

    def test_matches_the_specific_stored_image(self) -> None:
        tag = "{{AUX:thing:tsaeytte-props:jewelry}}"
        resource, image = auxiliary_resource_image_for_tag(
            [{
                "category": "thing",
                "resource_id": "tsaeytte-props",
                "images": [
                    {"image_id": "skirt", "image_path": "skirt.png"},
                    {"image_id": "jewelry", "image_path": "jewelry.png"},
                ],
            }],
            tag,
        )

        self.assertEqual("tsaeytte-props", resource["resource_id"])
        self.assertEqual("jewelry.png", image["image_path"])
        self.assertEqual(("thing", "tsaeytte-props", "jewelry"), parse_auxiliary_resource_tag(tag))
        self.assertEqual(tag, auxiliary_resource_tag("thing", "tsaeytte-props", "jewelry"))
        self.assertEqual([(tag, "thing", "tsaeytte-props", "jewelry")], auxiliary_resource_tags_in_text(f"{tag}\n{tag}"))



if __name__ == "__main__":
    unittest.main()
