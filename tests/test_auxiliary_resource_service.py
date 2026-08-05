import tempfile
import unittest
from pathlib import Path

from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.services.auxiliary_resource_service import AuxiliaryResourceService
from zet.services.config_service import Config
from zet.services.path_service import PathService


class AuxiliaryResourceServiceTests(unittest.TestCase):
    def test_delete_resource_removes_record_folder_and_all_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = Config(
                base_library_path=str(root),
                base_character_path=str(root / "Characters"),
                base_asset_path=str(root / "Assets"),
                base_pipeline_path=str(root / "Pipelines"),
                base_ai_queue_path=str(root / "Queue"),
            )
            paths = PathService(config, root)
            repository = AuxiliaryResourceRepository(paths)
            service = AuxiliaryResourceService(repository, paths)
            template = paths.auxiliary_resource_template_source_path()
            template.parent.mkdir(parents=True)
            template.write_text("Resource_Name: ``\nResource_Category: ``\n", encoding="utf-8")
            resource = service.create_resource("thing", "Magic Wand")
            folder = paths.auxiliary_resource_folder_path(resource.resource_id)
            (folder / "nested").mkdir()
            (folder / "nested" / "image.png").write_bytes(b"image")

            deleted = service.delete_resource(resource.resource_id)

            self.assertEqual(resource.resource_id, deleted.resource_id)
            self.assertFalse(folder.exists())
            self.assertEqual([], repository.list_resources())


if __name__ == "__main__":
    unittest.main()
