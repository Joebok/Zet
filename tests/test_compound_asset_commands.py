import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zet.models.asset import Asset
from zet.models.identity_key import IdentityKey
from zet.repositories.asset_repository import AssetRepository
from zet.services.config_service import Config
from zet.services.costume_service import CostumeService
from zet.services.expression_service import ExpressionService
from zet.services.path_service import PathService


class FakeIdentityKeyRepository:
    def get_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        return IdentityKey(
            identity_key_id=identity_key_id,
            character=character,
            phase=phase,
            label="Test",
            crop_percent=50,
            source_asset_id=1,
            source_pipeline="Body-Reference",
            source_body_view="Front",
        )


class CompoundAssetCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.character_dir = self.root / "Characters" / "Test" / "Adult"
        self.character_dir.mkdir(parents=True)
        self.assets_path = self.character_dir / "Assets.json"
        self.assets_path.write_text(json.dumps({"next_asset_id": 1, "assets": []}) + "\n", encoding="utf-8")
        config = Config(
            base_library_path=str(self.root),
            base_character_path=str(self.root / "Characters"),
            base_asset_path=str(self.root / "Assets"),
            base_pipeline_path=str(self.root / "Pipelines"),
            base_ai_queue_path=str(self.root / "Queue"),
        )
        self.paths = PathService(config)
        self.repository = AssetRepository(self.paths)
        self.costumes = CostumeService(self.repository, self.paths)
        self.expressions = ExpressionService(self.repository, FakeIdentityKeyRepository(), self.paths)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _payload(self) -> dict:
        return json.loads(self.assets_path.read_text(encoding="utf-8"))

    def test_create_costume_rolls_back_template_when_asset_write_fails(self) -> None:
        with patch.object(self.repository, "_write_payload", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.costumes.create_costume("Test", "Adult", "Travel Gear", "Costume Name: `[Placeholder]`\n")

        self.assertFalse((self.character_dir / "Costume_Travel_Gear.md").exists())
        self.assertEqual([], self._payload()["assets"])

    def test_create_costume_does_not_write_assets_when_template_write_fails(self) -> None:
        with patch.object(self.costumes, "_write_text_atomic", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.costumes.create_costume("Test", "Adult", "Travel Gear", "Costume Name: `[Placeholder]`\n")

        self.assertEqual([], self._payload()["assets"])

    def test_update_costume_restores_template_when_asset_write_fails(self) -> None:
        created = self.costumes.create_costume("Test", "Adult", "Travel Gear", "Costume Name: `[Placeholder]`\n")
        old_path = Path(created.costume.path)
        original_assets = self.assets_path.read_bytes()

        with patch.object(self.repository, "_write_payload", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.costumes.update_costume("Test", "Adult", created.costume.slug, "Formal Gear")

        self.assertTrue(old_path.exists())
        self.assertFalse((self.character_dir / "Costume_Formal_Gear.md").exists())
        self.assertEqual(original_assets, self.assets_path.read_bytes())

    def test_create_expression_rolls_back_definition_when_asset_write_fails(self) -> None:
        with patch.object(self.repository, "_write_payload", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.expressions.create_expression("Test", "Adult", "Happy", "key-1", "Expression label: Placeholder.\n")

        self.assertFalse((self.character_dir / "Expressions" / "Happy.md").exists())
        self.assertEqual([], self._payload()["assets"])

    def test_update_expression_restores_definition_when_asset_write_fails(self) -> None:
        created = self.expressions.create_expression(
            "Test", "Adult", "Happy", "key-1", "Expression label: Placeholder.\n"
        )
        old_path = Path(created.expression.path)
        original_assets = self.assets_path.read_bytes()

        with patch.object(self.repository, "_write_payload", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.expressions.update_expression("Test", "Adult", created.asset.asset_id, "Joyful", "key-1")

        self.assertTrue(old_path.exists())
        self.assertFalse((self.character_dir / "Expressions" / "Joyful.md").exists())
        self.assertEqual(original_assets, self.assets_path.read_bytes())

    def test_batch_create_assigns_ids_and_writes_once(self) -> None:
        assets = [
            Asset(0, "Test", "Adult", "Expression", "Front"),
            Asset(0, "Test", "Adult", "Expression", "Back"),
        ]

        with patch.object(self.repository, "_write_payload", wraps=self.repository._write_payload) as write:
            created = self.repository.create_assets(assets)

        self.assertEqual([1, 2], [asset.asset_id for asset in created])
        self.assertEqual(1, write.call_count)
        self.assertEqual(2, len(self._payload()["assets"]))


if __name__ == "__main__":
    unittest.main()
