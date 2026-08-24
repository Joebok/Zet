import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zet.models.asset import Asset
from zet.models.auxiliary_resource import AuxiliaryResource
from zet.models.identity_key import IdentityKey
from zet.models.turnaround import TurnaroundSheet
from zet.repositories.asset_repository import AssetRepository, AssetRepositoryError
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.repositories.turnaround_repository import TurnaroundRepository
from zet.services.config_service import Config
from zet.services.path_service import PathService


class RepositoryJsonStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        config = Config(
            base_library_path=str(self.root),
            base_character_path=str(self.root / "Characters"),
            base_asset_path=str(self.root / "Assets"),
            base_pipeline_path=str(self.root / "Pipelines"),
            base_ai_queue_path=str(self.root / "Queue"),
        )
        self.paths = PathService(config)
        self.asset_repository = AssetRepository(self.paths)
        self.turnaround_repository = TurnaroundRepository(self.paths)
        self.identity_repository = IdentityKeyRepository(self.paths)
        self.auxiliary_repository = AuxiliaryResourceRepository(self.paths)
        self.character_dir = self.paths.character_path("Test", "Adult")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()



    def test_asset_codec_applies_defaults_and_drops_unknown_replaced_fields(self) -> None:
        self.character_dir.mkdir(parents=True)
        path = self.character_dir / "Assets.json"
        path.write_text(
            json.dumps({
                "assets": [{
                    "asset_id": 1,
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline": "Body-Reference",
                    "body_view": "Front",
                    "future_field": "preserved only until replacement",
                }],
                "future_top_level": True,
            }),
            encoding="utf-8",
        )

        asset = self.asset_repository.list_assets("Test", "Adult")[0]
        self.assertEqual("NEW", asset.asset_state)
        self.assertEqual([], asset.reference_files)
        self.assertEqual("MATCHED_STYLE", asset.assembly_style_mode)
        self.asset_repository.save_asset(asset)

        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("future_field", payload["assets"][0])
        self.assertTrue(payload["future_top_level"])
        self.assertTrue(list((self.character_dir / "_backup").glob("Assets.backup.*.json")))
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))




    def test_failed_replace_preserves_repository_temp_cleanup_policies(self) -> None:
        self.character_dir.mkdir(parents=True)
        assets_path = self.character_dir / "Assets.json"
        assets_path.write_text('{"assets": []}', encoding="utf-8")
        with patch("pathlib.Path.replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.asset_repository.create_asset(
                    Asset(1, "Test", "Adult", "Body-Reference", "Front")
                )
        self.assertFalse((self.character_dir / "Assets.tmp.json").exists())

        with patch("pathlib.Path.replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.turnaround_repository.save_sheet(
                    TurnaroundSheet("body", "Test", "Adult", "Body-Reference")
                )
        self.assertTrue((self.character_dir / "TurnaroundSheets.tmp.json").exists())


if __name__ == "__main__":
    unittest.main()
