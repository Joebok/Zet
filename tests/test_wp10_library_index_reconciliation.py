from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests.support.reliability_fixture import write_reliability_fixture
from zet.app import ZetApp
from zet.services.config_service import ConfigService
from zet.services.library_index_service import LibraryIndexReconciler, LibraryIndexService


class WP10LibraryIndexReconciliationTests(unittest.TestCase):
    def make_service(self, temporary: str, *, now=None):
        base = Path(temporary)
        fixture = write_reliability_fixture(base / "authored-library", scale=1)
        config = ConfigService.load(fixture.config_path)
        service = LibraryIndexService(
            config,
            index_root=base / "machine-state",
            project_root=base,
            now=now,
        )
        return fixture, service

    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_external_create_edit_delete_and_rename_converge_incrementally(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, service = self.make_service(temporary)
            service.reconcile()
            stories = fixture.root / "Stories" / "FirstDay"
            original = stories / "scene-001.scene.json"
            created = stories / "external.scene.json"
            value = json.loads(original.read_text(encoding="utf-8"))
            value["scene"]["slug"] = "external"
            value["scene"]["name"] = "External Create"
            self.write_json(created, value)

            created_report = service.reconcile()
            self.assertIn("library/Stories/FirstDay/external.scene.json", created_report["changed_sources"])
            self.assertEqual(1, created_report["parsed_sources"])
            self.assertGreater(created_report["reused_sources"], 0)
            self.assertEqual(
                "External Create",
                service.repository.query_scenes(story_slug="FirstDay", name="External Create").items[0]["name"],
            )

            value["scene"]["name"] = "External Edit"
            self.write_json(created, value)
            service.reconcile()
            self.assertEqual(
                1, len(service.repository.query_scenes(story_slug="FirstDay", name="External Edit").items)
            )

            renamed = stories / "renamed.scene.json"
            created.rename(renamed)
            rename_report = service.reconcile()
            self.assertEqual(
                {
                    "library/Stories/FirstDay/external.scene.json",
                    "library/Stories/FirstDay/renamed.scene.json",
                },
                set(rename_report["changed_sources"]),
            )
            renamed.unlink()
            service.reconcile()
            self.assertEqual(
                [], service.repository.query_scenes(story_slug="FirstDay", name="External Edit").items
            )

    def test_unrelated_change_preserves_cache_and_dependency_change_invalidates_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, service = self.make_service(temporary)
            service.reconcile()
            stories = fixture.root / "Stories" / "FirstDay"
            dependency = stories / "scene-001.scene.json"
            unrelated = stories / "scene-002.scene.json"
            service.record_compilation(
                "FirstDay",
                "scene-001",
                "main",
                dependency_paths=[dependency],
                compiler_version="scene_render_v4",
                result_fingerprint="compiled-one",
            )
            scope = "scene:FirstDay:scene-001:main"
            self.assertTrue(service.compilation_is_current("FirstDay", "scene-001", "main"))

            unrelated_value = json.loads(unrelated.read_text(encoding="utf-8"))
            unrelated_value["scene"]["name"] = "Unrelated"
            self.write_json(unrelated, unrelated_value)
            report = service.reconcile()
            self.assertEqual([], report["invalidated_scopes"])
            self.assertIsNotNone(service.repository.compilation(scope))

            dependency_value = json.loads(dependency.read_text(encoding="utf-8"))
            dependency_value["scene"]["name"] = "Changed dependency"
            self.write_json(dependency, dependency_value)
            self.assertFalse(service.compilation_is_current("FirstDay", "scene-001", "main"))
            report = service.reconcile()
            self.assertEqual([scope], report["invalidated_scopes"])
            self.assertIsNone(service.repository.compilation(scope))

    def test_templates_settings_and_referenced_records_are_dependency_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, service = self.make_service(temporary)
            service.reconcile()
            story_root = fixture.root / "Stories" / "FirstDay"
            scene = story_root / "scene-001.scene.json"
            settings = next(story_root.glob("*.story.json"))
            catalog = next((fixture.root / "ImageCatalog" / "Records").glob("*.json"))
            template = Path(temporary) / "prompt-template.md"
            template.write_text("template one\n", encoding="utf-8")
            service.record_compilation(
                "FirstDay",
                "scene-001",
                "main",
                dependency_paths=[scene, settings, catalog, template],
                compiler_version="scene_render_v4",
                result_fingerprint="compiled",
                result={"prompt": "cached prompt"},
            )
            scope = "scene:FirstDay:scene-001:main"
            edges = service.repository.dependencies(scope)
            self.assertEqual(4, len(edges))
            self.assertTrue(any(path.endswith(".story.json") for path in edges))
            self.assertTrue(any("ImageCatalog/Records/" in path for path in edges))
            self.assertEqual("cached prompt", service.repository.compilation(scope)["result"]["prompt"])

            template.write_text("template two\n", encoding="utf-8")
            report = service.reconcile()
            self.assertEqual([scope], report["invalidated_scopes"])
            self.assertIsNone(service.repository.compilation(scope))

    def test_restart_repairs_crash_between_source_write_and_index_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, service = self.make_service(temporary)
            service.reconcile()
            scene = fixture.root / "Stories" / "FirstDay" / "scene-003.scene.json"
            value = json.loads(scene.read_text(encoding="utf-8"))
            value["scene"]["name"] = "Written Before Crash"
            self.write_json(scene, value)
            self.assertEqual([], service.repository.query_scenes(name="Written Before Crash").items)

            restarted = LibraryIndexService(
                service.config,
                index_root=Path(temporary) / "machine-state",
                project_root=Path(__file__).resolve().parents[1],
            )
            restarted.reconcile()
            self.assertEqual(1, len(restarted.repository.query_scenes(name="Written Before Crash").items))

    def test_status_cursor_clock_and_post_completion_schedule_are_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            instant = datetime(2026, 9, 10, 12, 30, tzinfo=timezone.utc)
            _, service = self.make_service(temporary, now=lambda: instant)
            waits: list[float] = []

            def wait(delay: float) -> bool:
                waits.append(delay)
                return True

            LibraryIndexReconciler(service, interval_seconds=60, wait=wait)._run()
            status = service.repository.status()
            self.assertEqual([60], waits)
            self.assertEqual(instant.isoformat(), status["last_reconciliation_completed_at"])
            self.assertEqual(status["active_generation"], status["reconciliation_generation"])
            self.assertTrue(status["reconciliation_cursor"])
            self.assertEqual([], status["reconciliation_errors"])

    def test_backup_media_temporary_and_authored_archive_contents_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, service = self.make_service(temporary)
            service.reconcile()
            excluded = (
                fixture.root / "ImageCatalog" / "_backup" / "record.json",
                fixture.root / "ImageCatalog" / "Images" / "sidecar.json",
                fixture.root / "ImageCatalog" / "Records" / "record.tmp",
                fixture.root / "Stories" / "_Archive" / "archived.scene.json",
            )
            for path in excluded:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")

            report = service.reconcile()
            self.assertEqual([], report["changed_sources"])
            self.assertEqual(0, report["parsed_sources"])

    def test_successful_app_write_refreshes_before_return(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture, service = self.make_service(temporary)
            app = ZetApp.from_config(fixture.config_path)
            app.library_index_service = service
            app.library_index_reconciler = LibraryIndexReconciler(service)
            app.story_service.library_index_service = service
            app.image_catalog_service.repository.after_write = app.refresh_library_index
            service.reconcile()
            data = app.load_scene_builder("FirstDay", "scene-001").data
            data["scene"]["name"] = "Synchronous Index Refresh"

            app.save_scene_builder("FirstDay", "scene-001", data)

            indexed = service.repository.query_scenes(
                story_slug="FirstDay", name="Synchronous Index Refresh"
            ).items
            self.assertEqual(1, len(indexed))


if __name__ == "__main__":
    unittest.main()
