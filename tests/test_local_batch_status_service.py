import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zet.services.local_batch_status_service import LocalBatchStatusService
from zet.web.local_character_asset_pipeline_router import create_local_character_asset_pipeline_router


class LocalBatchStatusServiceTests(unittest.TestCase):
    def test_aggregates_actionable_batches_in_priority_order_with_live_views_and_costumes(self):
        summaries = {
            "body-reference": [
                {"run_id": "render-new", "batch_name": "Front study", "character": "Mira", "phase": "Adult",
                 "created_at": "2026-09-25T10:00:00", "status": "RUNNING"},
                {"run_id": "render-old", "batch_name": "Older study", "character": "Mira", "phase": "Adult",
                 "created_at": "2026-09-24T10:00:00", "status": "RUNNING"},
                {"run_id": "failed", "character": "Mira", "phase": "Adult", "status": "ERROR"},
                {"run_id": "complete", "character": "Mira", "phase": "Adult", "status": "COMPLETE"},
            ],
            "head-image": [
                {"run_id": "anchor", "character": "Mira", "phase": "Adult", "status": "AWAITING_FRONT_ANCHOR"},
                {"run_id": "interrupted", "character": "Mira", "phase": "Adult", "status": "INTERRUPTED"},
            ],
            "character-assembly": [
                {"run_id": "review", "character": "Mira", "phase": "Adult", "status": "REVIEW_REQUIRED"},
                {"run_id": "stopped", "character": "Mira", "phase": "Adult", "status": "CANCELLED"},
            ],
            "costume-dressing": [
                {"run_id": "coat", "batch_name": "Winter coat", "character": "Mira", "phase": "Adult",
                 "costume": "Winter", "created_at": "2026-09-24T10:00:00", "status": "READY_FOR_VIEWS"},
            ],
        }
        details = {
            "render-new": {"target_views": ["FRONT"], "candidates": [
                {"candidate_id": "FL-001", "view": "FRONT_LEFT_3_4", "status": "RUNNING"},
            ]},
            "render-old": {"target_views": ["BACK"], "candidates": []},
        }

        class Adapter:
            def __init__(self, pipeline):
                self.pipeline = pipeline

            def list_run_summaries(self):
                return summaries[self.pipeline]

            def detail(self, run_id, **_kwargs):
                return details[run_id]

        service = LocalBatchStatusService(SimpleNamespace(), Path("."))
        with patch.object(service, "_adapter", side_effect=lambda pipeline: Adapter(pipeline)):
            result = service.list_actionable_batches()

        self.assertEqual(8, result["batch_count"])
        self.assertEqual(
            ["INTERRUPTED", "FAILED", "STOPPED", "AWAITING_FRONT_ANCHOR", "REVIEW_REQUIRED",
             "READY_FOR_VIEWS", "RUNNING"],
            [group["status"] for group in result["groups"]],
        )
        by_run = {batch["run_id"]: batch for group in result["groups"] for batch in group["batches"]}
        self.assertEqual("FRONT_LEFT_3_4", by_run["render-new"]["current_view"])
        self.assertEqual("Winter", by_run["coat"]["costume"])
        self.assertEqual("Winter coat", by_run["coat"]["batch_name"])
        self.assertNotIn("complete", by_run)
        self.assertEqual("Body-Reference", by_run["render-new"]["pipeline_label"])
        running_group = next(group for group in result["groups"] if group["status"] == "RUNNING")
        self.assertEqual(["render-new", "render-old"], [batch["run_id"] for batch in running_group["batches"]])
        self.assertEqual("BACK", by_run["render-old"]["current_view"])

    def test_api_exposes_aggregated_batch_status(self):
        app = FastAPI()
        config_app = SimpleNamespace()
        app.include_router(create_local_character_asset_pipeline_router(lambda: config_app, Path(".")))

        class Adapter:
            def __init__(self, pipeline):
                self.pipeline = pipeline

            def list_run_summaries(self):
                return [{"run_id": f"{self.pipeline}-run", "character": "Mira", "phase": "Adult",
                         "status": "AWAITING_HUMAN_SELECTION"}] if self.pipeline == "head-image" else []

        with patch.object(LocalBatchStatusService, "_adapter", autospec=True,
                          side_effect=lambda self, pipeline: Adapter(pipeline)):
            response = TestClient(app).get("/api/local/batch-status")

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["batch_count"])
        self.assertEqual("head-image-run", response.json()["groups"][0]["batches"][0]["run_id"])

    def test_scene_summary_without_batch_name_does_not_break_aggregation(self):
        scenes = SimpleNamespace(summaries=lambda: [{
            "run_id": "scene-run", "status": "RUNNING", "story_slug": "story",
            "scene_slug": "scene", "render_target_id": "main", "target_label": "Main",
            "created_at": "2026-10-05T10:00:00",
        }])
        service = LocalBatchStatusService(SimpleNamespace(local_scene_batch_service=scenes), Path("."))

        with patch.object(service, "_adapter", return_value=SimpleNamespace(list_run_summaries=lambda: [])):
            result = service.list_actionable_batches()

        self.assertEqual(1, result["batch_count"])
        batch = result["groups"][0]["batches"][0]
        self.assertEqual("scene-run", batch["run_id"])
        self.assertEqual("", batch["batch_name"])

    def test_discovers_queued_costume_batches_in_qualified_workspace(self):
        run_ids = ("6bdedfedce50446689df1688fb951719", "23cfbb159606407b967ffab25b58d1d4")
        with tempfile.TemporaryDirectory() as temp:
            library = Path(temp) / "Library"
            app = SimpleNamespace(config=SimpleNamespace(
                base_library_path=str(library), base_character_path=str(library / "Characters"),
            ))
            workspace = (library / "Experiments" / "Character-Pipeline" / "Tsaeytte" / "Adult"
                         / "Costume-Dressing" / "Canonical_Adventure_Gear")
            for run_id in run_ids:
                run_root = workspace / run_id
                run_root.mkdir(parents=True)
                (run_root / "spec.json").write_text(json.dumps({
                    "kind": "costume-dressing", "run_id": run_id, "batch_name": "",
                    "character": "Tsaeytte", "phase": "Adult", "costume": "Canonical Adventure Gear",
                    "created_at": "2026-09-26T14:40:31-07:00", "candidate_count": 36,
                }), encoding="utf-8")
                (run_root / "state.json").write_text(json.dumps({"status": "QUEUED"}), encoding="utf-8")

            result = LocalBatchStatusService(app, Path(temp)).list_actionable_batches()

        self.assertEqual(2, result["batch_count"])
        queued = next(group for group in result["groups"] if group["status"] == "QUEUED")
        self.assertEqual(set(run_ids), {batch["run_id"] for batch in queued["batches"]})
        self.assertTrue(all(batch["costume"] == "Canonical Adventure Gear" for batch in queued["batches"]))


if __name__ == "__main__":
    unittest.main()
