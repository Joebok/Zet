import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from zet.services.local_run_all_remaining_service import LocalRunAllRemainingService, PIPELINES
from zet.services.local_image_pipeline_policy import mutate_local_run_state


class LocalRunAllRemainingServiceTests(unittest.TestCase):
    def test_short_state_updates_do_not_overwrite_concurrent_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def update(index):
                mutate_local_run_state(root, lambda state: state.setdefault("updates", {}).update({str(index): index}))
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(update, range(40)))
            saved = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual({str(index): index for index in range(40)}, saved["updates"])

    def test_discovery_covers_all_local_pipelines_including_costumes(self):
        class Adapter:
            def __init__(self, pipeline):
                self.pipeline = pipeline

            def list_runs(self):
                return [{"run_id": f"{self.pipeline}-run", "character": "Test", "phase": "Adult",
                         "costume": "Coat" if self.pipeline == "costume-dressing" else "",
                         "status": "COMPLETE"}]

            def detail(self, run_id, **_kwargs):
                return {"run_id": run_id, "character": "Test", "phase": "Adult",
                        "costume": "Coat" if self.pipeline == "costume-dressing" else "",
                        "status": "COMPLETE", "candidates": [
                             {"image_path": str(image)} for image in (complete, missing)
                        ]}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            complete, missing = root / "complete.png", root / "missing.png"
            complete.write_bytes(b"image")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root)))
            service = LocalRunAllRemainingService(app, root)
            with patch("zet.services.local_run_all_remaining_service.LocalImagePipelineWorkflowService",
                       side_effect=lambda _app, _root, pipeline: SimpleNamespace(adapter=Adapter(pipeline))):
                batches = service._discover()
            self.assertEqual(set(PIPELINES), {item["pipeline"] for item in batches})
            self.assertEqual(1, len([item for item in batches if item["pipeline"] == "costume-dressing"
                                    and item["costume"] == "Coat"]))
            self.assertTrue(all(item["images_complete"] == 1 and item["images_remaining"] == 1
                                for item in batches))

    def test_start_attaches_to_active_campaign_and_persists_image_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root)))
            service = LocalRunAllRemainingService(app, root)
            active = set()
            def launch(campaign_id):
                active.add(campaign_id)
            with patch.object(service, "_discover", return_value=[{
                "pipeline": "body-reference", "run_id": "run-1", "candidate_count": 2,
                "images_complete": 1, "images_remaining": 1, "result": "QUEUED", "error": "",
            }]), patch("zet.services.local_run_all_remaining_service._ACTIVE", active), \
                    patch.object(service, "_launch", side_effect=launch) as launch_mock:
                first = service.start()
                second = service.start()
            self.assertEqual(first["campaign_id"], second["campaign_id"])
            launch_mock.assert_called_once_with(first["campaign_id"])
            status = service.status(first["campaign_id"])
            self.assertEqual(1, status["images_complete"])
            self.assertEqual(1, status["images_remaining"])
            saved = json.loads(service._campaign_path(first["campaign_id"]).read_text(encoding="utf-8"))
            self.assertEqual("QUEUED", saved["status"])

    def test_recovery_reopens_a_batch_interrupted_by_server_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root)))
            service = LocalRunAllRemainingService(app, root)
            service.root.mkdir(parents=True)
            campaign_id = "a" * 32
            path = service._campaign_path(campaign_id)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"campaign_id": campaign_id, "status": "RUNNING", "batches": [
                {"pipeline": "body-reference", "run_id": "run-1", "result": "RUNNING"}
            ]}), encoding="utf-8")
            service.active_path.write_text(json.dumps({"campaign_id": campaign_id}), encoding="utf-8")
            adapter = SimpleNamespace(_run_update=lambda *_args, **_kwargs: None)
            with patch.object(service, "_adapter", return_value=adapter), patch.object(service, "_launch") as launch:
                service.recover()
            launch.assert_called_once_with(campaign_id)
            recovered = service.status(campaign_id)
            self.assertEqual("RECOVERING", recovered["status"])
            self.assertEqual("QUEUED", recovered["batches"][0]["result"])

    def test_proxy_failure_does_not_retry_or_block_other_candidates_in_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root)))
            service = LocalRunAllRemainingService(app, root)
            campaign_id = "b" * 32
            service.root.mkdir(parents=True)
            path = service._campaign_path(campaign_id)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"campaign_id": campaign_id, "status": "RUNNING", "batches": [{
                "pipeline": "body-reference", "run_id": "run-1", "result": "QUEUED",
            }]}), encoding="utf-8")
            failed_image, ready_image = root / "failed.png", root / "ready.png"
            run = {"run_id": "run-1", "root": str(root), "character": "Test", "phase": "Adult",
                   "status": "QUEUED", "views": ["FRONT"], "front_anchor": "", "candidates": [
                       {"candidate_id": "F-001", "view": "FRONT", "status": "FAILED", "ask_id": "proxy-error",
                        "image_path": str(failed_image)},
                       {"candidate_id": "F-002", "view": "FRONT", "status": "PENDING", "ask_id": "",
                        "image_path": str(ready_image)},
                   ]}
            class Adapter:
                def detail(self, *_args, **_kwargs):
                    return run

                def _run_update(self, *_args, **_kwargs):
                    pass

                def _proxy_answer(self, _ask_id):
                    return "ANSWERED", {"status": "ERROR", "error_message": "proxy failed"}

                def _candidate_update(self, _run_id, candidate_id, changes):
                    next(item for item in run["candidates"] if item["candidate_id"] == candidate_id).update(changes)

                def retry_candidate(self, *_args, **_kwargs):
                    raise AssertionError("A failed proxy ask must not be retried in this campaign.")

                def execute_run(self, _run_id, *, candidate_ids, **_kwargs):
                    self.submitted = candidate_ids
                    ready_image.write_bytes(b"rendered")
                    next(item for item in run["candidates"] if item["candidate_id"] == "F-002").update(
                        status="COMPLETE", image_path=str(ready_image))

            adapter = Adapter()
            with patch.object(service, "_adapter", return_value=adapter):
                service._run_batch(campaign_id, 0, {"pipeline": "body-reference", "run_id": "run-1"})
            self.assertEqual({"F-002"}, adapter.submitted)
            self.assertTrue(ready_image.is_file())
            saved = service.status(campaign_id)["batches"][0]
            self.assertEqual("FAILED", saved["result"])
            self.assertIn("proxy failed", saved["error"])
