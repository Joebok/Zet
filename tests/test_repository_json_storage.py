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

    def test_missing_file_policies_are_preserved(self) -> None:
        with self.assertRaisesRegex(AssetRepositoryError, "Assets.json not found"):
            self.asset_repository.list_assets("Test", "Adult")

        self.assertEqual([], self.turnaround_repository.list_sheets("Test", "Adult"))
        self.assertEqual([], self.identity_repository.list_identity_keys("Test", "Adult"))
        self.assertEqual([], self.auxiliary_repository.list_resources())

    def test_non_object_record_policies_are_preserved(self) -> None:
        self.character_dir.mkdir(parents=True)
        (self.character_dir / "Assets.json").write_text('{"assets": [1]}', encoding="utf-8")
        (self.character_dir / "TurnaroundSheets.json").write_text('{"turnarounds": [1]}', encoding="utf-8")
        (self.character_dir / "IdentityKeys.json").write_text('{"identity_keys": [1]}', encoding="utf-8")
        auxiliary_path = self.paths.auxiliary_resource_inventory_path()
        auxiliary_path.parent.mkdir(parents=True)
        auxiliary_path.write_text('{"resources": [1]}', encoding="utf-8")

        with self.assertRaisesRegex(AssetRepositoryError, "Each asset record"):
            self.asset_repository.list_assets("Test", "Adult")
        self.assertEqual([], self.turnaround_repository.list_sheets("Test", "Adult"))
        self.assertEqual([], self.identity_repository.list_identity_keys("Test", "Adult"))
        self.assertEqual([], self.auxiliary_repository.list_resources())

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

    def test_codec_preserves_domain_missing_field_error(self) -> None:
        self.character_dir.mkdir(parents=True)
        (self.character_dir / "Assets.json").write_text(
            '{"assets": [{"asset_id": 1}]}',
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            AssetRepositoryError,
            "Asset record is missing required fields: body_view, character, phase, pipeline",
        ):
            self.asset_repository.list_assets("Test", "Adult")

    def test_first_write_backup_directory_policies_are_preserved(self) -> None:
        self.turnaround_repository.save_sheet(
            TurnaroundSheet("body", "Test", "Adult", "Body-Reference")
        )
        self.assertFalse((self.character_dir / "_backup").exists())

        self.identity_repository.save_identity_key(
            IdentityKey("front", "Test", "Adult", "Front", 50, 1, "Body-Reference", "Front")
        )
        self.assertTrue((self.character_dir / "_backup").exists())

        self.auxiliary_repository.save_resource(
            AuxiliaryResource("arch", "place", "Arch", "arch", "arch.md", "now", "now")
        )
        auxiliary_path = self.paths.auxiliary_resource_inventory_path()
        self.assertFalse((auxiliary_path.parent / "_backup").exists())

    def test_identity_existing_payload_does_not_gain_schema_version(self) -> None:
        self.character_dir.mkdir(parents=True)
        path = self.character_dir / "IdentityKeys.json"
        path.write_text('{"identity_keys": []}', encoding="utf-8")

        self.identity_repository.save_identity_key(
            IdentityKey("front", "Test", "Adult", "Front", 50, 1, "Body-Reference", "Front")
        )

        self.assertNotIn("schema_version", json.loads(path.read_text(encoding="utf-8")))

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
