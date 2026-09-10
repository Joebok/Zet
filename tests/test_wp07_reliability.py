from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.support.project_fixture import write_project_fixture
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.performance_instrumentation import PerformanceInstrumentation, collect
from zet.web.app import create_app


class WP07ReliabilityTests(unittest.TestCase):
    def test_empty_answer_harvest_does_not_access_archive_or_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            archive_root = root / "Queue" / "Zet_File_Proxy_State" / "Archive" / "Harvested"
            for index in range(100):
                archived = archive_root / f"2026-08-{(index % 28) + 1:02d}" / f"Archived_{index:03d}"
                archived.mkdir(parents=True)
                (archived / "harvest_manifest.json").write_text(
                    json.dumps({"ask_id": archived.name, "harvested_at": "2026-08-01T00:00:00"}),
                    encoding="utf-8",
                )

            client = TestClient(create_app(config_path))
            client.post("/api/ai-controls/harvest")
            metrics = PerformanceInstrumentation()
            with patch.object(
                AIProxyPathService,
                "harvested_archive_root",
                side_effect=AssertionError("hot harvest path accessed archived history"),
            ):
                started = time.perf_counter()
                with collect(metrics):
                    response = client.post("/api/ai-controls/harvest")
                elapsed = time.perf_counter() - started

            self.assertEqual(200, response.status_code, response.text)
            self.assertLess(elapsed, 0.5)
            self.assertEqual([], response.json()["harvest_results"])
            self.assertNotIn("recent_harvests", response.json())
            self.assertEqual(0, metrics.snapshot()["counts"].get("archive_traversals", 0))

    def test_failed_answer_remains_retryable_and_action_reports_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Failed"
            answer_path.mkdir(parents=True)
            (answer_path / "ask_manifest.json").write_text(
                json.dumps({"ask_id": "Ask_Failed", "consumer": "zet"}),
                encoding="utf-8",
            )
            (answer_path / "answer_manifest.json").write_text("{}", encoding="utf-8")

            with patch.object(
                AIProxyPathService,
                "harvested_archive_root",
                side_effect=AssertionError("hot harvest response accessed archived history"),
            ):
                response = TestClient(create_app(config_path)).post("/api/ai-controls/harvest")

            self.assertEqual(200, response.status_code, response.text)
            payload = response.json()
            self.assertEqual("HARVEST_FAILED", payload["harvest_results"][0]["status"])
            self.assertIn("failed and remain available for retry", payload["message"])
            self.assertEqual("Ask_Failed", payload["queue"]["answer"][0]["ask_id"])
            self.assertTrue((answer_path / "harvest_error.json").is_file())
            self.assertFalse((answer_path / "harvest_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
