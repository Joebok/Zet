from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from Scripts.Benchmark_WP12 import run_migration_rehearsal, run_scale_acceptance


class WP12ScaleAcceptanceTests(unittest.TestCase):
    def test_migration_rehearsal_preserves_first_day_data_and_resumes(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = run_migration_rehearsal(Path(temporary))

        self.assertTrue(report["comparison_equal"])
        self.assertTrue(report["interrupted_checkpoint_resumed"])
        self.assertTrue(report["backup_exists"])
        self.assertEqual(8, len(report["comparison"]["after"]["associations"]))
        self.assertTrue(all(
            value["main_candidate"] and value["background_candidate"] and value["tasks"]
            for value in report["comparison"]["after"]["associations"].values()
        ))

    def test_hot_paths_are_bounded_and_single_flight(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = run_scale_acceptance(Path(temporary), 1, runs=30)

        self.assertTrue(report["pass"])
        self.assertEqual(30, report["runs"])
        self.assertLess(report["navigation_p95_seconds"], 2)
        self.assertLess(report["review_listing_p95_seconds"], 3)
        self.assertLessEqual(report["review_page_items"], 50)
        self.assertEqual(0, report["archive_traversals"])
        self.assertEqual(1, report["reconciliation_maximum_active"])
        self.assertEqual(1, report["summary_maximum_active"])
        self.assertTrue(report["rebuild_recovery"]["interrupted"])
        self.assertTrue(report["rebuild_recovery"]["navigation_retained_generation"])
        self.assertLess(report["rebuild_recovery"]["navigation_seconds"], 2)
        self.assertTrue(report["rebuild_recovery"]["resumed"])


if __name__ == "__main__":
    unittest.main()
