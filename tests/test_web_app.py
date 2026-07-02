import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from zet.web.app import create_app


class WebAppTests(unittest.TestCase):
    def _write_fixture(self, root: Path, *, stage: str = "LOCKED", actor: str = "HUMAN_AGENT") -> Path:
        character_dir = root / "Characters" / "Test" / "Adult"
        prompt_dir = character_dir / "Body_Reference" / "Front"
        pipeline_dir = root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1"
        character_dir.mkdir(parents=True)
        prompt_dir.mkdir(parents=True, exist_ok=True)
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        (root / "Assets" / "Test" / "Adult").mkdir(parents=True)
        (root / "Queue").mkdir()
        (prompt_dir / "Final_Image_Prompt.md").write_text("full final prompt\n", encoding="utf-8")
        (pipeline_dir / "front.png").write_bytes(b"test image")
        (character_dir / "Assets.json").write_text(
            json.dumps(
                {
                    "assets": [
                        {
                            "asset_id": 1,
                            "character": "Test",
                            "phase": "Adult",
                            "pipeline": "Body-Reference",
                            "body_view": "Front",
                            "head_view": None,
                            "costume": None,
                            "expression": None,
                            "asset_state": "IN_PROGRESS",
                            "pipeline_stage": stage,
                            "actor": actor,
                            "ai_state": None,
                            "final_image_output": "front.png",
                            "last_ai_update": None,
                            "error_code": None,
                            "error_message": None,
                            "updated_at": None,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (character_dir / "Pipelines.json").write_text(
            json.dumps(
                {
                    "pipelines": {
                        "Body-Reference": {
                            "stages": ["MANIFEST", "RENDER", "RENDER_REVIEW"],
                            "actor_by_stage": {
                                "MANIFEST": "PYTHON",
                                "RENDER": "AI_AGENT",
                                "RENDER_REVIEW": "HUMAN_AGENT",
                            },
                            "worker_by_stage": {"MANIFEST": "zet.workers.noop_worker"},
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        config_path = root / "config.toml"
        config_path.write_text(
            f"""
[BaseFolders]
BaseCharacterPath = "{(root / 'Characters').as_posix()}"
BaseAssetPath = "{(root / 'Assets').as_posix()}"
BasePipelinePath = "{(root / 'Pipelines').as_posix()}"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
""".lstrip(),
            encoding="utf-8",
        )
        return config_path

    def _write_manual_render_ask(self, root: Path) -> Path:
        ask_path = root / "Queue" / "Ollama_Proxy" / "Ask" / "Ask_Asset_1_RENDER_TEST"
        ask_path.mkdir(parents=True, exist_ok=True)
        (ask_path / "ask_manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "ask_id": "Ask_Asset_1_RENDER_TEST",
                    "asset_id": 1,
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline": "Body-Reference",
                    "pipeline_stage": "RENDER",
                    "ollama_attempt_id": "render-test",
                    "worker_type": "manual_chatgpt_render",
                    "ollama_model": "",
                    "prompt_file": "Final_Image_Prompt.md",
                    "expected_output": "front.png",
                    "candidate_output_file": "front.png",
                    "task_type": "render",
                    "render_preset": "chatgpt-manual",
                    "manual": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (ask_path / "Final_Image_Prompt.md").write_text("manual render prompt\n", encoding="utf-8")
        return ask_path

    def test_assets_api_serves_context_list_and_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_fixture(Path(temp_dir))
            client = TestClient(create_app(config_path))
            context = client.get("/api/context")
            self.assertEqual(context.status_code, 200)
            self.assertEqual(context.json()["default_character"], "Test")

            assets = client.get("/api/assets", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(assets.status_code, 200)
            self.assertEqual(assets.json()["assets"][0]["asset_id"], 1)

            detail = client.get("/api/assets/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["asset"]["pipeline_stage"], "LOCKED")

    def test_asset_action_api_runs_housekeeping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            response = client.post("/api/assets/1/run-housekeeping", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("Housekeeping complete", payload["message"])
            self.assertTrue(payload["detail"]["exists"]["stage"])

    def test_asset_action_api_runs_current_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="MANIFEST", actor="PYTHON")
            client = TestClient(create_app(config_path))

            response = client.post("/api/assets/1/run-current-worker", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("Worker finished", payload["message"])
            self.assertEqual(payload["detail"]["asset"]["pipeline_stage"], "RENDER")

    def test_prompt_review_api_serves_tasks_detail_and_fail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="PROMPT_REVIEW", actor="HUMAN_AGENT")
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/prompt-review/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["asset_id"], 1)

            detail = client.get("/api/prompt-review/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertTrue(detail.json()["is_reviewable"])
            self.assertEqual(detail.json()["prompt_text"], "full final prompt\n")

            failed = client.post("/api/prompt-review/1/fail", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(failed.status_code, 200)
            self.assertIn("Prompt failed", failed.json()["message"])
            self.assertEqual(failed.json()["asset"]["pipeline_stage"], "ERROR")

    def test_render_review_api_serves_tasks_detail_and_promotes_to_locked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER_REVIEW", actor="HUMAN_AGENT")
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/render-review/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["asset_id"], 1)
            self.assertTrue(tasks.json()["tasks"][0]["candidate_image_exists"])

            detail = client.get("/api/render-review/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertTrue(detail.json()["is_reviewable"])
            self.assertTrue(detail.json()["exists"]["candidate_image"])

            promoted = client.post(
                "/api/render-review/1/promote-to-locked",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(promoted.status_code, 200)
            self.assertEqual(promoted.json()["asset"]["asset_state"], "LOCKED")
            self.assertEqual(promoted.json()["asset"]["pipeline_stage"], "LOCKED")
            self.assertTrue((root / "Assets" / "Test" / "Adult" / "front.png").exists())

    def test_render_review_api_can_fail_back_to_render(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER_REVIEW", actor="HUMAN_AGENT")
            client = TestClient(create_app(config_path))

            failed = client.post(
                "/api/render-review/1/fail-to-render",
                params={"character": "Test", "phase": "Adult"},
            )

            self.assertEqual(failed.status_code, 200)
            payload = failed.json()
            self.assertEqual(payload["asset"]["pipeline_stage"], "RENDER")
            self.assertEqual(payload["asset"]["actor"], "AI_AGENT")
            self.assertEqual(payload["asset"]["ai_state"], "ASKED")
            self.assertFalse((root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1" / "front.png").exists())
            self.assertTrue(any((root / "Queue" / "Ollama_Proxy" / "Ask").iterdir()))

    def test_ai_controls_api_serves_snapshot_and_monitor_test(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            snapshot = client.get("/api/ai-controls")
            self.assertEqual(snapshot.status_code, 200)
            self.assertIn("queue_counts", snapshot.json())
            self.assertIn("processes", snapshot.json())

            monitor = client.post(
                "/api/ai-controls/monitor-test",
                params={"instruction": "ping"},
            )
            self.assertEqual(monitor.status_code, 200)
            self.assertIn("Monitor test sent", monitor.json()["message"])
            self.assertEqual(monitor.json()["monitor_requests"][0]["instruction"], "ping")

    def test_pipeline_controls_api_serves_snapshot_and_saves_automation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            snapshot = client.get("/api/pipeline-controls", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(snapshot.status_code, 200)
            self.assertEqual(snapshot.json()["pipeline_names"], ["Body-Reference"])

            saved = client.post(
                "/api/pipeline-controls/automation",
                params={"character": "Test", "phase": "Adult"},
                json={
                    "prompt_condense_enabled": True,
                    "prompt_condense_model": "vision-test",
                    "prompt_condense_file": "Config/Prompt_Condense_Tasks/body_reference_condense.md",
                    "local_render_auto_queue_after_condense": True,
                    "local_render_preset": "body-reference-preview",
                    "ai_harvest_auto_enabled": True,
                    "ai_harvest_interval_seconds": 600,
                    "render_backend": "manual_chatgpt",
                },
            )
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json()["automation"]["prompt_condense_enabled"])
            self.assertEqual(saved.json()["automation"]["render_backend"], "manual_chatgpt")
            self.assertIn("[PromptCondense]", config_path.read_text(encoding="utf-8"))

    def test_pipeline_controls_api_can_batch_reset_to_render(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="LOCKED", actor="HUMAN_AGENT")
            client = TestClient(create_app(config_path))

            reset = client.post(
                "/api/pipeline-controls/batch-render-reset",
                params={
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline_name": "Body-Reference",
                    "include_locked": "true",
                },
            )

            self.assertEqual(reset.status_code, 200)
            self.assertIn("1 reset", reset.json()["message"])
            self.assertEqual(reset.json()["batch_results"][0]["status"], "RESET")
            self.assertTrue(any((root / "Queue" / "Ollama_Proxy" / "Ask").iterdir()))

    def test_render_console_api_lists_task_detail_and_saves_image_answer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            ask_path = self._write_manual_render_ask(root)
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/render-console/tasks")
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["ask_id"], "Ask_Asset_1_RENDER_TEST")

            detail = client.get("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["prompt"], "manual render prompt\n")

            saved = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/answer-image",
                content=b"image bytes",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["status"], "SUCCESS")
            self.assertFalse(ask_path.exists())
            answer_path = root / "Queue" / "Ollama_Proxy" / "Answer" / "Ask_Asset_1_RENDER_TEST"
            self.assertTrue((answer_path / "front.png").exists())
            manifest = json.loads((answer_path / "answer_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
