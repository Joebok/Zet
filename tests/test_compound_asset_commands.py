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
from zet.services.expression_service import ExpressionService, ExpressionServiceError
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

    def test_create_costume_does_not_create_traditional_assets(self) -> None:
        with patch.object(self.repository, "_write_payload", side_effect=OSError("traditional store must not be touched")):
            result = self.costumes.create_costume("Test", "Adult", "Travel Gear", "")

        self.assertTrue(Path(result.costume.path).is_file())
        self.assertEqual([], result.assets)
        self.assertEqual([], self._payload()["assets"])

    def test_update_costume_renames_local_provenance_and_preserves_published_image(self) -> None:
        created = self.costumes.create_costume("Test", "Adult", "Armored", "")
        experiment_root = self.paths.pipeline_candidates_path("Character-Pipeline", "Test", "Adult")
        old_workspace = experiment_root / "Costume-Dressing" / "Armored"
        old_workspace.mkdir(parents=True)
        (old_workspace / "spec.json").write_text(json.dumps({"costume": "Armored"}), encoding="utf-8")
        snapshot = old_workspace / "inputs" / "Costume_Armored.md"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text("Costume Name: `[Armored]`\n", encoding="utf-8")
        candidate = old_workspace / "candidate.png"
        candidate.write_bytes(b"candidate image")
        published_image = self.root / "images" / "published.png"
        published_image.parent.mkdir(parents=True)
        published_image.write_bytes(b"published image")
        local_store = experiment_root / "local_assets.json"
        local_store.write_text(json.dumps({"assets": {
            "costume-dressing:armored:FRONT": {
                "pipeline": "Costume-Dressing", "qualifier": "Armored",
                "image_path": str(candidate), "locked_image_path": str(published_image), "locked": True,
                "dependencies": [{"key": "body-reference:FRONT"}],
            }
        }}), encoding="utf-8")
        old_turnaround_id = "Local-Costume-Dressing_Armored"
        turnaround_dir = self.paths.pipeline_base_path("Test", "Adult") / "Turnaround" / old_turnaround_id
        turnaround_dir.mkdir(parents=True)
        turnaround_candidate = turnaround_dir / "Candidate" / f"{old_turnaround_id}.png"
        turnaround_candidate.parent.mkdir()
        turnaround_candidate.write_bytes(b"turnaround candidate")
        turnarounds_path = self.character_dir / "TurnaroundSheets.json"
        turnarounds_path.write_text(json.dumps({"turnarounds": [{
            "turnaround_id": old_turnaround_id, "character": "Test", "phase": "Adult",
            "source_pipeline": "Costume-Dressing", "costume": "Armored", "label": "Costume-Dressing / Armored",
            "candidate_image_path": str(turnaround_candidate), "source_local_keys": ["costume-dressing:armored:FRONT"],
        }]}), encoding="utf-8")

        self.costumes.update_costume("Test", "Adult", "Armored", "Paladin")

        new_workspace = experiment_root / "Costume-Dressing" / "Paladin"
        self.assertEqual("Paladin", json.loads((new_workspace / "spec.json").read_text(encoding="utf-8"))["costume"])
        self.assertTrue((new_workspace / "inputs" / "Costume_Paladin.md").is_file())
        stored = json.loads(local_store.read_text(encoding="utf-8"))["assets"]
        self.assertIn("costume-dressing:paladin:FRONT", stored)
        self.assertEqual("Paladin", stored["costume-dressing:paladin:FRONT"]["qualifier"])
        self.assertTrue(published_image.is_file())
        self.assertEqual(str(published_image), stored["costume-dressing:paladin:FRONT"]["locked_image_path"])
        self.assertEqual("body-reference:FRONT", stored["costume-dressing:paladin:FRONT"]["dependencies"][0]["key"])
        turnaround = json.loads(turnarounds_path.read_text(encoding="utf-8"))["turnarounds"][0]
        self.assertEqual("Local-Costume-Dressing_Paladin", turnaround["turnaround_id"])
        self.assertEqual("Paladin", turnaround["costume"])
        self.assertIn("Local-Costume-Dressing_Paladin", turnaround["candidate_image_path"])
        self.assertTrue((turnaround_dir.parent / "Local-Costume-Dressing_Paladin" / "Candidate" / "Local-Costume-Dressing_Paladin.png").is_file())
        self.assertEqual([], self._payload()["assets"])




    def test_expression_creation_is_retired(self) -> None:
        with self.assertRaisesRegex(ExpressionServiceError, "Expressions are retired"):
            self.expressions.create_expression("Test", "Adult", "Happy", "key-1", "")
        self.assertFalse((self.character_dir / "Expressions" / "Happy.md").exists())
        self.assertEqual([], self._payload()["assets"])

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
