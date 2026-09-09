import json
import hashlib
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

from tests.support.image_fixture import png_bytes
from tests.support.project_fixture import write_project_fixture, write_manual_render_ask
from tests.test_scene_image_review_service import _StoryService
from zet.app import ZetApp
from zet.render_console.queue import RenderConsoleQueue
from zet.repositories.asset_repository import AssetRepositoryError
from zet.services.atomic_file_service import write_json_atomic
from zet.services.comfyui_render_service import run_comfyui_workflow
from zet.services.local_render_types import LocalRenderError
from zet.services.scene_image_review_service import SceneImageReviewError, SceneImageReviewService
from zet.services.workflow_storage import snapshot_manual_ask, task_state_path
from zet.models.worker import WorkerResult
from zet.models.story import StoryRenderTask
from zet.services.scene_prompt_analysis_service import ScenePromptAnalysisService


class WorkflowReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = ZetApp.from_config(write_project_fixture(self.root, stage="RENDER", actor="AI_AGENT"))
        self.queue = RenderConsoleQueue(self.app.config)

    def answer(self):
        ask = write_manual_render_ask(self.root)
        task = self.queue.get_task(ask.name)
        return self.queue.write_answer_image(task, png_bytes(), "image/png")

    def test_stale_asset_write_is_rejected_without_losing_newer_changes(self):
        first = self.app.asset_repository.get_asset("Test", "Adult", 1)
        stale = self.app.asset_repository.get_asset("Test", "Adult", 1)
        first.error_message = "newer edit"
        self.app.asset_repository.save_asset(first)
        stale.body_view = "Back"
        with self.assertRaises(AssetRepositoryError):
            self.app.asset_repository.save_asset(stale)
        current = self.app.asset_repository.get_asset("Test", "Adult", 1)
        self.assertEqual("newer edit", current.error_message)
        self.assertEqual("Front", current.body_view)

    def test_concurrent_writers_cannot_overwrite_the_same_revision(self):
        barrier = Barrier(2)
        def save(value):
            asset = self.app.asset_repository.get_asset("Test", "Adult", 1)
            asset.error_message = value
            barrier.wait(timeout=3)
            try:
                self.app.asset_repository.save_asset(asset)
                return True
            except AssetRepositoryError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual([False, True], sorted(executor.map(save, ["first", "second"])))

    def test_recompile_publishes_new_prompt_and_reference_bundle(self):
        self.enterContext(patch.object(self.app.ai_proxy_service, "_render_backend", return_value="manual_chatgpt"))
        old = write_manual_render_ask(self.root)
        reference = self.root / "reference.png"
        reference.write_bytes(png_bytes())
        result = WorkerResult(True, "compiled", reference_files=[{"path": str(reference), "role": "subject_reference"}])
        with patch.object(self.app.prompt_review_service.worker_service, "run_named_worker", return_value=result):
            self.app.recompile_prompt_review("Test", "Adult", 1)
        tasks = self.queue.list_tasks()
        self.assertEqual(1, len(tasks))
        self.assertNotEqual(old.name, tasks[0].ask_id)
        self.assertEqual(str(reference), tasks[0].manifest["reference_files"][0]["source_path"])
        self.assertTrue(old.is_dir())

    def test_failed_staging_restores_previous_active_attempt(self):
        self.enterContext(patch.object(self.app.ai_proxy_service, "_render_backend", return_value="manual_chatgpt"))
        before = self.app.asset_repository.get_asset("Test", "Adult", 1)
        with patch.object(self.app.ai_proxy_service, "_publish_ask_folder", side_effect=OSError("publish failure")):
            with self.assertRaises(OSError):
                self.app.ai_proxy_service.stage_current_ai_ask("Test", "Adult", 1)
        after = self.app.asset_repository.get_asset("Test", "Adult", 1)
        self.assertEqual(before.active_attempt_id, after.active_attempt_id)
        self.assertEqual(before.ai_state, after.ai_state)

    def test_receipt_failure_replays_without_advancing_twice(self):
        answer = self.answer()
        harvester = self.app.asset_service.ai_answer_harvester
        with patch.object(harvester, "_write_harvest_manifest", side_effect=OSError("receipt unavailable")):
            with self.assertRaises(OSError):
                harvester.apply_answer_folder(answer)
        first = self.app.asset_repository.get_asset("Test", "Adult", 1)
        self.assertEqual("RENDER_REVIEW", first.pipeline_stage)
        self.assertEqual("APPLIED", harvester.apply_answer_folder(answer).status)
        current = self.app.asset_repository.get_asset("Test", "Adult", 1)
        self.assertEqual(first.revision, current.revision)
        self.assertEqual("ALREADY_APPLIED", harvester.apply_answer_folder(answer).status)

    def test_failed_answer_does_not_stop_later_harvest(self):
        good = self.answer()
        bad = good.parent / "AAA_broken"
        bad.mkdir()
        write_json_atomic(bad / "ask_manifest.json", {"consumer": "zet"})
        write_json_atomic(bad / "answer_manifest.json", {})
        results = self.app.asset_service.ai_answer_harvester.harvest_once()
        self.assertIn("HARVEST_FAILED", [result.status for result in results])
        self.assertIn("APPLIED", [result.status for result in results])
        self.assertTrue((bad / "harvest_error.json").is_file())

    def test_failed_publication_keeps_original_task_and_allows_retry(self):
        ask = write_manual_render_ask(self.root)
        task = self.queue.get_task(ask.name)
        original = write_json_atomic
        def fail_manifest(path, payload, *args, **kwargs):
            if path.name == "answer_manifest.json":
                raise OSError("disk failure")
            return original(path, payload, *args, **kwargs)
        with patch("zet.render_console.queue.write_json_atomic", side_effect=fail_manifest):
            with self.assertRaises(OSError):
                self.queue.write_answer_image(task, png_bytes(), "image/png")
        self.assertEqual([ask.name], [item.ask_id for item in self.queue.list_tasks()])
        self.assertEqual([], list(self.app.ai_proxy_service.ai_proxy_path_service.task_paths("answer")))
        answer = self.queue.write_answer_image(task, png_bytes(), "image/png")
        self.assertTrue((answer / "answer_manifest.json").is_file())

    def test_cleanup_uses_character_phase_and_asset_id(self):
        ask = write_manual_render_ask(self.root)
        other = ask.parent / "Other_character_same_id"
        other.mkdir()
        manifest = json.loads((ask / "ask_manifest.json").read_text())
        manifest.update(ask_id=other.name, character="Other")
        write_json_atomic(other / "ask_manifest.json", manifest)
        asset = self.app.asset_repository.get_asset("Test", "Adult", 1)
        self.app.ai_proxy_service.clear_asset_queue_items(asset)
        self.assertTrue(other.is_dir())
        self.assertFalse(task_state_path(self.root / "Queue", "Superseded", other.name).exists())
        self.assertTrue(task_state_path(self.root / "Queue", "Superseded", ask.name).exists())

    def test_prompt_snapshot_survives_reference_replacement(self):
        source = self.root / "reference.png"
        source.write_bytes(png_bytes())
        staging, ready = self.root / ".staging", self.root / "ready"
        staging.mkdir()
        (staging / "prompt.md").write_text("Preserve identity; change the lighting.")
        manifest = snapshot_manual_ask(staging, ready, {"prompt_file": "prompt.md", "reference_files": [{"path": str(source)}],
                    "image_inputs": [{"path": str(source), "assignments": [{"applies_to": "hero"}, {"applies_to": "reflection"}]}]}, Path)
        staging.rename(ready)
        source.write_bytes(png_bytes("blue"))
        self.assertEqual(png_bytes(), Path(manifest["reference_files"][0]["path"]).read_bytes())
        self.assertEqual(2, len(manifest["image_inputs"][0]["assignments"]))

    def scene_answer(self, service, ask_id="old"):
        answer = self.root / ask_id
        answer.mkdir()
        response = answer / "scene.png"
        response.write_bytes(png_bytes())
        write_json_atomic(answer / "answer_manifest.json", {})
        manifest = {"ask_id": ask_id, "story_slug": "story", "scene_slug": "scene", "render_input_hash": "hash"}
        return answer, response, manifest

    def test_late_scene_answer_is_retained_without_replacing_candidate(self):
        service = SceneImageReviewService(_StoryService(self.root))
        pipeline = service.target_service.pipeline_path("story", "scene", "main")
        write_json_atomic(pipeline / "Active_Render.json", {"ask_id": "new"})
        answer, response, manifest = self.scene_answer(service)
        disposition, archive = service.apply_answer(answer, response, manifest)
        self.assertEqual("stale", disposition)
        self.assertEqual(png_bytes(), archive.read_bytes())
        self.assertFalse(service.status("story", "scene").candidate_exists)

    def test_scene_promotion_retries_after_metadata_write_failure(self):
        service = SceneImageReviewService(_StoryService(self.root))
        service.apply_answer(*self.scene_answer(service))
        paths = service.target_service.review_paths("story", "scene", "main")
        paths["locked"].parent.mkdir(parents=True, exist_ok=True)
        paths["locked"].write_bytes(png_bytes("blue"))
        original = service._write_json
        def fail_metadata(path, payload):
            if path == paths["metadata"]:
                raise OSError("metadata unavailable")
            return original(path, payload)
        with patch.object(service, "_write_json", side_effect=fail_metadata):
            with self.assertRaises(OSError):
                service.promote("story", "scene")
        self.assertTrue(paths["candidate"].is_file())
        service.promote("story", "scene")
        service.promote("story", "scene")
        self.assertEqual(png_bytes(), paths["locked"].read_bytes())
        backups = list(paths["backups"].glob("*.png"))
        self.assertEqual(1, len(backups))
        self.assertEqual(png_bytes("blue"), backups[0].read_bytes())

    def test_invalid_scene_provenance_preserves_both_images(self):
        service = SceneImageReviewService(_StoryService(self.root))
        service.apply_answer(*self.scene_answer(service))
        paths = service.target_service.review_paths("story", "scene", "main")
        paths["candidate"].with_suffix(".render.json").write_text("broken")
        with self.assertRaises(SceneImageReviewError):
            service.promote("story", "scene")
        self.assertTrue(paths["candidate"].is_file())
        self.assertFalse(paths["locked"].exists())

    def test_comfyui_timeout_resumes_prompt_without_resubmission(self):
        output = self.root / "render"
        workflow = {"1": {"class_type": "Test", "inputs": {}}}
        with patch("zet.services.comfyui_render_service._request_json", return_value={"prompt_id": "job-1"}) as submit:
            with self.assertRaisesRegex(LocalRenderError, "Retry to resume"):
                run_comfyui_workflow(workflow, server_url="http://test", output_dir=output, timeout_seconds=0)
            self.assertEqual(1, submit.call_count)
        history = {"job-1": {"status": {"status_str": "success"}, "outputs": {"1": {"images": [{"filename": "result.png"}]}}}}
        with patch("zet.services.comfyui_render_service._request_json", return_value=history) as resume, patch(
                "zet.services.comfyui_render_service._request_bytes", return_value=png_bytes()):
            result = run_comfyui_workflow(workflow, server_url="http://test", output_dir=output)
        resume.assert_called_once_with("http://test/history/job-1")
        self.assertEqual("job-1", result.prompt_id)

    def test_analysis_is_complete_only_for_the_current_prompt_and_request(self):
        pipeline = self.root / "scene"
        pipeline.mkdir()
        (pipeline / "Final_Image_Prompt.md").write_text("Current prompt\n", encoding="utf-8")
        (pipeline / "AI_Prompt_Analysis.md").write_text("Old analysis", encoding="utf-8")
        story = SimpleNamespace(scene_pipeline_path=lambda *args: pipeline)
        service = ScenePromptAnalysisService(self.app.config, story)
        self.assertFalse(service.status("story", "scene")["complete"])
        digest = hashlib.sha256(b"Current prompt\n").hexdigest()
        metadata = {"ask_id": "analysis-1", "prompt_sha256": digest, "status": "SUCCESS"}
        write_json_atomic(pipeline / "AI_Prompt_Analysis.request.json", metadata)
        write_json_atomic(pipeline / "AI_Prompt_Analysis.result.json", metadata)
        self.assertTrue(service.status("story", "scene")["complete"])
        story.story_render_service = SimpleNamespace(_compile=lambda *args, **kwargs: ("Edited scene prompt", "hash"))
        self.assertFalse(service.status("story", "scene")["complete"])

    def test_analysis_metadata_failure_keeps_answer_retryable(self):
        answer = self.root / "analysis"
        answer.mkdir()
        write_json_atomic(answer / "answer_manifest.json", {})
        (answer / "analysis.md").write_text("A finding", encoding="utf-8")
        target = self.root / "analysis-target"
        manifest = {"task_type": "scene_prompt_analysis", "target_output_dir": str(target), "source_prompt_sha256": "hash"}
        response = SimpleNamespace(status="SUCCESS", expected_output="analysis.md", ask_id="analysis-1", asset_id=None)
        harvester = self.app.asset_service.ai_answer_harvester
        with patch("zet.services.ai_answer_harvester.write_json_atomic", side_effect=OSError("metadata failure")):
            with self.assertRaises(OSError):
                harvester._apply_auxiliary_answer(answer, response, manifest)
        self.assertFalse((answer / "harvest_manifest.json").exists())
        harvester._apply_auxiliary_answer(answer, response, manifest)
        self.assertTrue((answer / "harvest_manifest.json").is_file())
        self.assertEqual("SUCCESS", json.loads((target / "AI_Prompt_Analysis.result.json").read_text())["status"])

    def test_optional_analysis_failure_returns_the_successfully_staged_render(self):
        ask = self.root / "scene-ask"
        ask.mkdir()
        task = StoryRenderTask("story", "scene", ask.name, str(ask), str(self.root), str(ask / "Final_Image_Prompt.md"), "scene.png", [])
        self.app.config = replace(self.app.config, ai_prompt_analysis_auto_queue_on_render=True)
        with patch.object(self.app.story_service, "stage_scene_render", return_value=task), patch.object(
                self.app.scene_prompt_analysis_service, "queue", side_effect=OSError("proxy unavailable")):
            result = self.app.stage_scene_render("story", "scene")
        self.assertEqual(task.ask_id, result.ask_id)
        self.assertIn("Render is staged", result.warning)
        self.assertTrue((ask / "analysis_queue_error.json").is_file())


if __name__ == "__main__":
    unittest.main()
