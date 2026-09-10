import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from zet.repositories.image_catalog_repository import ImageCatalogRepository, ImageCatalogRepositoryError
from zet.services.config_service import Config
from zet.services.image_catalog_migration_service import (
    ImageCatalogMigrationInterrupted,
    ImageCatalogMigrationService,
)
from zet.services.path_service import PathService


class WP08CatalogMigrationTests(unittest.TestCase):
    def make_legacy(self, root: Path) -> tuple[PathService, dict[str, str]]:
        config = Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )
        paths = PathService(config, root)
        image_root = root / "ImageCatalog" / "Images"
        image_root.mkdir(parents=True)
        (image_root / "one.png").write_bytes(b"first-image")
        (image_root / "two.png").write_bytes(b"second-image")
        records = {}
        items = {}
        for index, name in enumerate(("one", "two"), start=1):
            catalog_id = f"img_preserved_{index}"
            source_key = f"import:{catalog_id}"
            records[catalog_id] = {
                "catalog_id": catalog_id,
                "source_key": source_key,
                "label": name.title(),
                "image_path": str(image_root / f"{name}.png"),
                "mime_type": "image/png",
                "tag": f"{{{{IMAGE:{catalog_id}}}}}",
                "semantic_category": "Person",
                "reference_set_id": "people",
                "provenance": {"imported_by": "wp08", "ordinal": index},
            }
            items[source_key] = {
                "catalog_id": catalog_id,
                "collection_ids": ["heroes"],
                "keyword_ids": ["tested"],
                "sections": {
                    "identity": {
                        "mode": "override",
                        "approved_text": f"  exact identity {index}\nsecond line  ",
                        "provenance": "ai_reviewed",
                    },
                    "costume": {
                        "mode": "override",
                        "approved_text": f"exact costume {index}",
                        "provenance": "manual",
                    },
                },
            }
        legacy = {
            "schema_version": 2,
            "items": items,
            "managed_images": records,
            "reference_sets": {
                "people": {
                    "reference_set_id": "people",
                    "label": "People",
                    "identity_text": "shared identity",
                    "costume_text": "shared costume",
                    "provenance": {"source": "legacy"},
                }
            },
            "collections": [{"id": "heroes", "label": "Heroes"}],
            "keywords": [{"id": "tested", "label": "Tested"}],
        }
        manifest = root / "ImageCatalog" / "ImageCatalog.json"
        manifest.write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")
        hashes = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in image_root.glob("*.png")
        }
        return paths, hashes

    def test_dry_run_migration_preserves_records_references_overrides_and_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths, before_hashes = self.make_legacy(root)
            migration = ImageCatalogMigrationService(paths)
            legacy_bytes = paths.image_catalog_inventory_path().read_bytes()

            dry_run = migration.run(dry_run=True)

            self.assertEqual("dry-run", dry_run.status)
            self.assertEqual(2, dry_run.catalog_records)
            self.assertEqual(2, dry_run.image_hashes_verified)
            self.assertEqual(legacy_bytes, paths.image_catalog_inventory_path().read_bytes())
            self.assertFalse(migration.staging_path.exists())
            self.assertFalse(migration.backup_path.exists())

            migrated = migration.run()
            payload = ImageCatalogRepository(paths).load()

            self.assertEqual("migrated", migrated.status)
            self.assertEqual({"img_preserved_1", "img_preserved_2"}, set(payload["managed_images"]))
            self.assertEqual({"people"}, set(payload["reference_sets"]))
            self.assertEqual("  exact identity 1\nsecond line  ", payload["items"]["import:img_preserved_1"]["sections"]["identity"]["approved_text"])
            self.assertEqual("ai_reviewed", payload["items"]["import:img_preserved_1"]["sections"]["identity"]["provenance"])
            self.assertEqual({"source": "legacy"}, payload["reference_sets"]["people"]["provenance"])
            self.assertEqual("library", payload["managed_images"]["img_preserved_1"]["image_path_kind"])
            self.assertEqual("ImageCatalog/Images/one.png", payload["managed_images"]["img_preserved_1"]["image_path"])
            after_hashes = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (root / "ImageCatalog" / "Images").glob("*.png")
            }
            self.assertEqual(before_hashes, after_hashes)
            self.assertEqual(legacy_bytes, migration.backup_path.read_bytes())

            second = migration.run()
            self.assertEqual("no-op", second.status)
            self.assertEqual(legacy_bytes, migration.backup_path.read_bytes())

    def test_interrupted_migration_is_rejected_by_runtime_and_resumes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, _ = self.make_legacy(Path(temp_dir))
            migration = ImageCatalogMigrationService(paths)

            with self.assertRaises(ImageCatalogMigrationInterrupted):
                migration.run(interrupt_after=1)
            with self.assertRaisesRegex(ImageCatalogRepositoryError, "migrate_image_catalog"):
                ImageCatalogRepository(paths).load()

            result = migration.run()

            self.assertEqual("migrated", result.status)
            self.assertEqual(2, len(ImageCatalogRepository(paths).load()["managed_images"]))

    def test_incomplete_current_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths, _ = self.make_legacy(root)
            paths.image_catalog_inventory_path().write_text(
                json.dumps({**ImageCatalogRepository.MANIFEST, "status": "staging"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ImageCatalogRepositoryError, "migration is incomplete"):
                ImageCatalogRepository(paths).load()

    def test_external_image_path_remains_absolute_and_identifiable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "library"
            root.mkdir()
            paths, _ = self.make_legacy(root)
            external = Path(temp_dir) / "external.png"
            external.write_bytes(b"external-image")
            legacy = json.loads(paths.image_catalog_inventory_path().read_text(encoding="utf-8"))
            legacy["managed_images"]["img_preserved_1"]["image_path"] = str(external)
            paths.image_catalog_inventory_path().write_text(json.dumps(legacy), encoding="utf-8")

            ImageCatalogMigrationService(paths).run()
            record = ImageCatalogRepository(paths).load()["managed_images"]["img_preserved_1"]

            self.assertEqual("external", record["image_path_kind"])
            self.assertEqual(str(external.resolve()), record["image_path"])
            self.assertEqual(hashlib.sha256(b"external-image").hexdigest(), hashlib.sha256(external.read_bytes()).hexdigest())

    def test_one_item_edit_rewrites_and_backs_up_only_that_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths, _ = self.make_legacy(root)
            migration = ImageCatalogMigrationService(paths)
            migration.run()
            repository = ImageCatalogRepository(paths)
            payload = repository.load()
            records = root / "ImageCatalog" / "Records"
            before = {path.name: path.read_bytes() for path in records.glob("*.json")}
            manifest_before = paths.image_catalog_inventory_path().read_bytes()
            pre_v3_before = migration.backup_path.read_bytes()

            payload["items"]["import:img_preserved_1"]["sections"]["identity"]["approved_text"] = "edited once"
            repository.save(payload)

            after = {path.name: path.read_bytes() for path in records.glob("*.json")}
            self.assertNotEqual(before["img_preserved_1.json"], after["img_preserved_1.json"])
            self.assertEqual(before["img_preserved_2.json"], after["img_preserved_2.json"])
            self.assertEqual(manifest_before, paths.image_catalog_inventory_path().read_bytes())
            self.assertEqual(pre_v3_before, migration.backup_path.read_bytes())
            record_backups = list((root / "ImageCatalog" / "_backup" / "Records").glob("*.json"))
            self.assertEqual(1, len(record_backups))
            self.assertTrue(record_backups[0].name.startswith("img_preserved_1."))
            self.assertFalse((root / "ImageCatalog" / "_backup" / "Organization").exists())


if __name__ == "__main__":
    unittest.main()
