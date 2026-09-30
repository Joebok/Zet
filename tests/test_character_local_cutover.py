import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from zet.repositories.asset_repository import AssetRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.config_service import Config
from zet.services.identity_key_service import IdentityKeyService, IdentityKeyServiceError
from zet.services.local_asset_source_service import LocalAssetSourceService
from zet.services.local_asset_store_service import LocalAssetStoreError, LocalAssetStoreService
from zet.services.path_service import PathService
from zet.services.phase_comparison_service import PhaseComparisonService


class CharacterLocalCutoverTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.paths = PathService(Config(
            base_library_path=str(self.root),
            base_character_path=str(self.root / "Characters"),
            base_asset_path=str(self.root / "Assets"),
            base_pipeline_path=str(self.root / "Pipelines"),
            base_ai_queue_path=str(self.root / "Queue"),
        ))
        self.store = LocalAssetStoreService(self.root)
        self.sources = LocalAssetSourceService(self.store)
        self.image_path = self.root / "locked.png"
        image = Image.new("RGB", (64, 80), "white")
        ImageDraw.Draw(image).rectangle((24, 10, 40, 68), fill="black")
        image.save(self.image_path)
        self.record = {
            "pipeline": "Body-Reference", "view": "FRONT", "qualifier": "",
            "batch_id": "batch-1", "candidate_id": "candidate-1", "locked": True, "stale": False,
            "image_sha256": hashlib.sha256(self.image_path.read_bytes()).hexdigest(),
            "locked_image_path": str(self.image_path),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_store(self):
        path = self.store.workspace_path("Test", "Adult")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"assets": {"body-reference:FRONT": self.record}}), encoding="utf-8")

    def test_source_provider_filters_unlocked_stale_and_changed_locks(self):
        self.record["locked"] = False
        self._write_store()
        self.assertEqual([], self.sources.list_sources("Test", "Adult"))
        with self.assertRaisesRegex(LocalAssetStoreError, "missing, unlocked, or stale"):
            self.sources.get_source("Test", "Adult", "body-reference:FRONT")

        self.record["locked"] = True
        self.record["image_sha256"] = "0" * 64
        self._write_store()
        self.assertEqual([], self.sources.list_sources("Test", "Adult"))

    def test_identity_keys_save_with_local_provenance_and_no_numeric_asset_id(self):
        self._write_store()
        identity = IdentityKeyService(
            AssetRepository(self.paths), IdentityKeyRepository(self.paths), self.paths, self.sources,
        )
        preview = identity.preview_identity_key("Test", "Adult", None, "Front", 100, source_local_key="body-reference:FRONT")
        self.assertTrue(Path(preview.preview_path).is_file())
        saved = identity.save_identity_key("Test", "Adult", None, "Front", 100, source_local_key="body-reference:FRONT")
        self.assertIsNone(saved.source_asset_id)
        self.assertEqual("body-reference:FRONT", saved.source_local_key)
        self.assertEqual(self.record["image_sha256"], saved.source_sha256)
        with self.assertRaisesRegex(IdentityKeyServiceError, "Traditional pipeline assets are retired"):
            identity.save_identity_key("Test", "Adult", 1, "Traditional", 100)

    def test_phase_comparison_matches_local_views_and_keeps_missing_slots_empty(self):
        def record(view):
            return {
                "pipeline": "Body-Reference", "view": view, "qualifier": "", "locked": True,
                "stale": False, "locked_image_path": str(self.image_path),
                "image_sha256": hashlib.sha256(self.image_path.read_bytes()).hexdigest(),
                "batch_id": f"{view}-batch", "candidate_id": f"{view}-candidate",
            }

        for phase, records in (("Adult", {"body-reference:FRONT": record("FRONT")} ),
                               ("YoungAdult", {"body-reference:BACK": record("BACK")})):
            path = self.store.workspace_path("Test", phase)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"assets": records}), encoding="utf-8")
        comparison = PhaseComparisonService(
            AssetRepository(self.paths), PipelineRepository(self.paths), self.paths,
            Path(__file__).resolve().parents[1], self.sources,
        )

        result = comparison.compare("Test", "Adult", "YoungAdult", "Body-Reference")

        self.assertEqual(["Body-Reference"], result.available_pipelines)
        self.assertEqual(2, len(result.rows))
        front = next(row for row in result.rows if row.slot_label == "Front")
        self.assertTrue(front.left.image_exists)
        self.assertFalse(front.right.image_exists)
        self.assertIsNone(front.right.asset_id)
        self.assertEqual("body-reference:FRONT", front.left.source_key)


if __name__ == "__main__":
    unittest.main()
