from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from Scripts.Build_Static_Final_Prompt import _replace_auxiliary_resource_tags
from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService
from zet.services.path_service import PathService
from zet.services.config_service import ConfigService
from zet.services.chatgpt_prompt_contract import build_image_inputs
from zet.services.view_conditioning_service import ViewContext, condition_section
from zet.services.auxiliary_resource_tags import (
    auxiliary_resource_image_for_tag,
    auxiliary_resource_tag,
    auxiliary_resource_tags_in_text,
    parse_auxiliary_resource_tag,
)


class AuxiliaryResourceTagTests(unittest.TestCase):
    def test_view_conditioned_library_references_resolve_to_numbered_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            library = project / "library"
            library.mkdir()
            (project / "config.toml").write_text(
                "\n".join([
                    "[BaseFolders]",
                    f'BaseLibraryPath = "{library.as_posix()}"',
                    'BaseCharacterPath = "Characters"',
                    'BaseAssetPath = "Assets"',
                    'BasePipelinePath = "Pipelines"',
                    'BaseAIQueuePath = "AI_Queue"',
                ]), encoding="utf-8"
            )
            paths = PathService(ConfigService.load(project / "config.toml"), project)
            repository = EntityLibraryRepository(paths.entity_library_database_path())
            repository.initialize()
            service = EntityLibraryService(paths, repository)
            front = service.import_asset("Front jewelry", "image/png", b"front")
            rear = service.import_asset("Rear jewelry", "image/png", b"rear")
            jewelry = service.create_entity({"name": "Jewelry", "entity_type": "prop"})
            for key, asset in (("jewelry.front", front), ("jewelry.rear", rear)):
                service.update_asset(asset["asset_id"], {"entity_links": [
                    {"entity_id": jewelry["entity_id"], "role": "primary_subject"},
                ]})
                service.save_logical_reference({"reference_key": key, "asset_id": asset["asset_id"]})
            source = (
                "* [body:frontish,profiles] {{LIB:REF:jewelry.front}}\n"
                "* [body:rearish] {{LIB:REF:jewelry.rear}}"
            )
            for view, expected in (("FRONT", front), ("LEFT_PROFILE", front), ("BACK_LEFT_3_4", rear), ("BACK", rear)):
                with self.subTest(view=view):
                    selected, _, _ = condition_section(
                        source, "EQUIPMENT_JEWELRY_PROPS_FACTS",
                        {"source_path": "Costume.md", "start_line": 1},
                        ViewContext(body_view=view, head_view=view),
                    )
                    references = auxiliary_references_for_texts(project, [selected], [])
                    self.assertEqual([expected["asset_id"]], [item["asset_id"] for item in references])
                    self.assertEqual("object_reference", references[0]["prompt_role"])
                    self.assertEqual("object_reference", build_image_inputs(references, render_mode="generate")[0]["role"])
                    self.assertEqual("* Image 1 (jewelry)", _replace_auxiliary_resource_tags(
                        selected, {references[0]["tag"]: {"index": 1, "label": "jewelry"}},
                    ))

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
