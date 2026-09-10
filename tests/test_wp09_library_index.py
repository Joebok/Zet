from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.support.reliability_fixture import write_reliability_fixture
from zet.repositories.library_index_repository import LibraryIndexCorruptError
from zet.services.config_service import ConfigService
from zet.services.library_index_service import LibraryIndexService


def authored_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class WP09LibraryIndexTests(unittest.TestCase):
    def make_service(self, temporary: str, *, scale: int = 1) -> tuple[Path, LibraryIndexService]:
        base = Path(temporary)
        library = base / "authored-library"
        fixture = write_reliability_fixture(library, scale=scale)
        config = ConfigService.load(fixture.config_path)
        service = LibraryIndexService(config, index_root=base / "machine-state")
        return library, service

    def test_rebuild_is_external_and_preserves_authored_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            library, service = self.make_service(temporary)
            before = authored_hashes(library)

            self.assertEqual("building", service.repository.status()["state"])
            report = service.rebuild()
            database = service.repository.database_path

            self.assertEqual("ready", report["state"])
            self.assertEqual(1, report["counts"]["stories"])
            self.assertEqual(8, report["counts"]["scenes"])
            self.assertEqual(16, report["counts"]["render_targets"])
            self.assertEqual(1, report["counts"]["catalog_records"])
            self.assertEqual(1, report["counts"]["active_work"])
            self.assertEqual(1, report["counts"]["job_summaries"])
            self.assertTrue(database.is_file())
            self.assertNotEqual(library, database.parent)
            self.assertNotIn(library, database.parents)
            self.assertEqual(before, authored_hashes(library))

            database.unlink()
            rebuilt = service.rebuild()
            self.assertEqual("ready", rebuilt["state"])
            self.assertEqual(before, authored_hashes(library))

    def test_queries_are_stable_paginated_and_scope_status_name_filtered(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, service = self.make_service(temporary, scale=2)
            service.rebuild()
            repository = service.repository

            first = repository.query_scenes(story_slug="FirstDay", limit=5)
            second = repository.query_scenes(story_slug="FirstDay", cursor=first.next_cursor, limit=5)
            third = repository.query_scenes(story_slug="FirstDay", cursor=second.next_cursor, limit=20)
            scene_slugs = [item["scene_slug"] for page in (first, second, third) for item in page.items]
            self.assertEqual([f"scene-{index:03d}" for index in range(1, 17)], scene_slugs)
            self.assertIsNone(third.next_cursor)
            self.assertEqual([], repository.query_scenes(story_slug="Other").items)
            self.assertEqual("scene-001", repository.query_scenes(name="Arrival").items[0]["scene_slug"])

            targets = repository.query_render_targets(story_slug="FirstDay", scene_slug="scene-002").items
            self.assertEqual(["main", "background"], [item["target_id"] for item in targets])
            catalog = repository.query_catalog(reference_set_id="wp01-inherited", semantic_category="Person").items
            self.assertEqual(["img_wp01_001", "img_wp01_002"], [item["catalog_id"] for item in catalog])
            self.assertEqual(1, len(repository.query_catalog(name="Fixture Identity 001").items))
            self.assertEqual(2, len(repository.query_active_work(status="queued", story_slug="FirstDay").items))
            self.assertEqual(2, len(repository.query_active_work(name="render").items))
            self.assertEqual(2, len(repository.query_job_history(status="success", story_slug="FirstDay").items))

    def test_interrupted_publication_retains_last_complete_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, service = self.make_service(temporary)
            service.rebuild()
            repository = service.repository
            active_generation = repository.status()["active_generation"]
            expected = repository.query_scenes(story_slug="FirstDay").items
            generation = repository.begin_rebuild()

            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                repository.publish(
                    generation,
                    service.snapshot(),
                    before_activate=lambda: (_ for _ in ()).throw(RuntimeError("simulated interruption")),
                )

            status = repository.status()
            self.assertEqual(active_generation, status["active_generation"])
            self.assertEqual(generation, status["building_generation"])
            self.assertTrue(status["rebuild_in_progress"])
            self.assertEqual(expected, repository.query_scenes(story_slug="FirstDay").items)

    def test_malformed_sources_are_reported_while_valid_records_remain(self):
        with tempfile.TemporaryDirectory() as temporary:
            library, service = self.make_service(temporary)
            (library / "ImageCatalog" / "Records" / "broken.json").write_text("{not json", encoding="utf-8")
            (library / "Stories" / "FirstDay" / "scene-004.scene.json").write_text("[]", encoding="utf-8")

            report = service.rebuild()
            errors = service.repository.query_errors().items

            self.assertEqual(2, report["counts"]["errors"])
            self.assertEqual(7, len(service.repository.query_scenes(story_slug="FirstDay").items))
            self.assertEqual(1, len(service.repository.query_catalog().items))
            self.assertEqual(
                [
                    "library/ImageCatalog/Records/broken.json",
                    "library/Stories/FirstDay/scene-004.scene.json",
                ],
                [item["source_path"] for item in errors],
            )
            self.assertTrue(all(item["message"] for item in errors))

    def test_database_corruption_gives_rebuild_guidance_and_clean_rebuild_recovers(self):
        with tempfile.TemporaryDirectory() as temporary:
            library, service = self.make_service(temporary)
            before = authored_hashes(library)
            service.rebuild()
            database = service.repository.database_path
            database.write_bytes(b"not a sqlite database")

            with self.assertRaisesRegex(LibraryIndexCorruptError, "Delete this database.*rebuild_library_index"):
                service.repository.status()

            database.unlink()
            report = service.rebuild()
            self.assertEqual("ready", report["state"])
            self.assertEqual(before, authored_hashes(library))

    def test_unchanged_rebuild_publishes_equivalent_new_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            library, service = self.make_service(temporary)
            before = authored_hashes(library)
            first_report = service.rebuild()
            first_rows = service.repository.query_catalog().items
            second_report = service.rebuild()

            self.assertGreater(second_report["active_generation"], first_report["active_generation"])
            self.assertEqual(first_rows, service.repository.query_catalog().items)
            self.assertEqual(before, authored_hashes(library))


if __name__ == "__main__":
    unittest.main()
