from __future__ import annotations

import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.support.reliability_fixture import write_reliability_fixture
from zet.app import ZetApp
from zet.services.performance_instrumentation import PerformanceInstrumentation, collect
from zet.services.summary_cache import SummaryCache


class WP04ReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        SummaryCache.clear()

    def tearDown(self) -> None:
        SummaryCache.clear()

    def test_candidate_discovery_covers_main_and_subscenes_without_detail_compiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir))
            app = ZetApp.from_config(fixture.config_path)
            metrics = PerformanceInstrumentation()
            with collect(metrics):
                context = app.discovery_context()
                rows = app.list_pending_scene_image_reviews(discovery_context=context)

            self.assertEqual(16, len(rows))
            self.assertEqual({"main", "background"}, {row.render_target_id for row in rows})
            counts = metrics.snapshot()["counts"]
            self.assertEqual(16, counts["candidate_path_checks"])
            self.assertEqual(8, counts["scene_builder_loads"])
            self.assertEqual(0, counts.get("render_compiles", 0))

    def test_zero_candidates_skip_detailed_status_even_when_locked_images_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir))
            app = ZetApp.from_config(fixture.config_path)
            for scene_slug in fixture.scene_slugs:
                main_candidate = app.path_service.scene_candidate_image_path(fixture.story_slug, scene_slug)
                main_locked = app.path_service.scene_locked_image_path(fixture.story_slug, scene_slug)
                main_locked.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(main_candidate, main_locked)
                main_candidate.unlink()
                subscene_candidate = app.path_service.scene_subscene_candidate_path(
                    fixture.story_slug, scene_slug, "background"
                )
                subscene_locked = app.path_service.scene_subscene_locked_path(
                    fixture.story_slug, scene_slug, "background"
                )
                subscene_locked.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(subscene_candidate, subscene_locked)
                subscene_candidate.unlink()

            metrics = PerformanceInstrumentation()
            with collect(metrics):
                rows = app.list_pending_scene_image_reviews()

            self.assertEqual([], rows)
            self.assertEqual(0, metrics.snapshot()["counts"].get("render_compiles", 0))

    def test_catalog_discovery_is_reused_by_one_request_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir))
            app = ZetApp.from_config(fixture.config_path)
            context = app.discovery_context()
            metrics = PerformanceInstrumentation()
            with collect(metrics):
                app.image_catalog_items(discovery_context=context)
                app.image_catalog_items(discovery_context=context, source_type="scene")
                app.list_pending_scene_image_reviews(discovery_context=context)

            self.assertEqual(1, metrics.snapshot()["counts"]["catalog_discoveries"])
            self.assertEqual(8, metrics.snapshot()["counts"]["scene_builder_loads"])

    def test_summary_uses_one_snapshot_and_single_flight_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir))
            app = ZetApp.from_config(fixture.config_path)
            service = app.production_work_summary_service
            original_compute = service._compute
            compute_calls = 0
            compute_lock = threading.Lock()
            started = threading.Event()
            release = threading.Event()

            def wrapped_compute(*args):
                nonlocal compute_calls
                with compute_lock:
                    compute_calls += 1
                started.set()
                release.wait(timeout=5)
                return original_compute(*args)

            service._compute = wrapped_compute
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(service.summary, "story", story_slug=fixture.story_slug)
                self.assertTrue(started.wait(timeout=5))
                second = executor.submit(service.summary, "story", story_slug=fixture.story_slug)
                release.set()
                results = [first.result(), second.result()]

            self.assertEqual(1, compute_calls)
            self.assertEqual(results[0], results[1])
            self.assertEqual(16, results[0]["current"]["image_review_waiting"])
            self.assertEqual(results[0]["project"], results[0]["current"])

            metrics = PerformanceInstrumentation()
            SummaryCache.clear()
            with collect(metrics):
                app.production_work_summary("story", story_slug=fixture.story_slug)
            self.assertLessEqual(metrics.snapshot()["counts"].get("catalog_discoveries", 0), 1)

            context = app.discovery_context()
            review_rows = app.list_pending_scene_image_reviews(discovery_context=context)
            self.assertEqual(len(review_rows), results[0]["current"]["image_review_waiting"])

    def test_summary_cache_is_invalidated_by_candidate_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir))
            app = ZetApp.from_config(fixture.config_path)
            first = app.production_work_summary("story", story_slug=fixture.story_slug)
            app.discard_scene_image_candidate(fixture.story_slug, fixture.scene_slugs[0])
            second = app.production_work_summary("story", story_slug=fixture.story_slug)

            self.assertEqual(16, first["current"]["image_review_waiting"])
            self.assertEqual(15, second["current"]["image_review_waiting"])


if __name__ == "__main__":
    unittest.main()
