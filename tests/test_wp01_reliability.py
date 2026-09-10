from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from Scripts.Benchmark_WP01 import run_wp01_benchmark
from tests.support.reliability_fixture import write_reliability_fixture
from zet.app import ZetApp
from zet.render_console.queue import RenderConsoleQueue
from zet.services.performance_instrumentation import PerformanceInstrumentation, collect
from zet.services.scene_render_compiler import compile_scene_render_ir
from zet.web.app import create_app


DEFAULT_PROMPT_SECTIONS = {
    "anatomical_requirements": "# Anatomical Requirements\nfixture",
    "avoid": "# Avoid\nfixture",
    "high_risk_elements": "# High-Risk Elements\nfixture",
    "final_verification": "# Final Verification\nfixture",
}


class WP01ReliabilityTests(unittest.TestCase):
    def test_generation_is_deterministic_and_contains_required_records(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = write_reliability_fixture(Path(first_dir), scale=1)
            second = write_reliability_fixture(Path(second_dir), scale=1)

            self.assertEqual(first.logical_snapshot(), second.logical_snapshot())
            self.assertEqual(list(first.scene_slugs), [f"scene-{index:03d}" for index in range(1, 9)])
            self.assertEqual(8, first.counts.scenes)
            self.assertEqual(8, first.counts.main_candidates)
            self.assertEqual(8, first.counts.subscene_candidates)

            app = ZetApp.from_config(first.config_path)
            self.assertEqual(list(first.scene_slugs), [item.slug for item in app.list_scenes(first.story_slug)])
            item = app.image_catalog_service.list_items(include_base=True)[0]
            self.assertEqual("inherited", item.identity_status)
            self.assertEqual("inherited", item.costume_status)
            self.assertEqual("A consistent fixture identity description.", item.identity_text)
            self.assertEqual("A consistent fixture costume description.", item.costume_text)

            queue = RenderConsoleQueue(app.config)
            self.assertEqual(1, len(queue.list_tasks()))
            self.assertIsNotNone(queue.get_task("WP01_COMPLETED_001"))

    def test_scaled_generation_uses_recorded_entity_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir), scale=10)
            self.assertEqual(
                {
                    "stories": 1,
                    "scenes": 80,
                    "main_candidates": 80,
                    "subscene_candidates": 80,
                    "catalog_images": 10,
                    "active_queue_records": 10,
                    "completed_queue_records": 10,
                },
                fixture.dataset_counts,
            )
            self.assertEqual(list(fixture.scene_slugs), [f"scene-{index:03d}" for index in range(1, 81)])

    def test_instrumentation_counts_core_operations_and_endpoint_duration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir))
            app = ZetApp.from_config(fixture.config_path)
            queue = RenderConsoleQueue(app.config)
            metrics = PerformanceInstrumentation()
            with collect(metrics):
                app.load_scene(fixture.story_slug, fixture.scene_slugs[0])
                app.image_catalog_service.list_items(include_base=True)
                queue.list_tasks()
                builder = app.story_service.load_scene_builder_data(fixture.story_slug, fixture.scene_slugs[0])
                settings_path = app.story_service.get_story_settings_path_from_story_md(
                    app.story_service.path_service.story_file_path(fixture.story_slug)
                )
                compile_scene_render_ir(
                    builder.data,
                    app.story_service.load_story_settings(settings_path),
                    default_prompt_sections=DEFAULT_PROMPT_SECTIONS,
                )
                app.ai_proxy_service.recent_harvests()

            counts = metrics.snapshot()["counts"]
            self.assertGreaterEqual(counts["catalog_discoveries"], 1)
            self.assertGreaterEqual(counts["scene_document_loads"], 1)
            self.assertGreaterEqual(counts["render_compiles"], 1)
            self.assertGreaterEqual(counts["file_reads"], 1)
            self.assertGreaterEqual(counts["archive_traversals"], 1)

            endpoint_metrics = PerformanceInstrumentation()
            response = TestClient(create_app(fixture.config_path, performance=endpoint_metrics)).get("/api/stories")
            self.assertEqual(200, response.status_code)
            self.assertEqual(1, endpoint_metrics.snapshot()["counts"]["endpoint_duration"])

    def test_benchmark_reports_isolated_cold_and_warm_runs(self) -> None:
        results = run_wp01_benchmark((1,))
        self.assertEqual(["cold", "warm"], [item["state"] for item in results])
        for item in results:
            self.assertTrue(item["concurrent_activity"] == "none")
            self.assertTrue(item["dataset_counts"]["scenes"] == 8)
            self.assertTrue(item["instrumentation"]["counts"]["endpoint_duration"] >= 1)


if __name__ == "__main__":
    unittest.main()
