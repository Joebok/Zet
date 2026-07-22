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
        (root / "Config").mkdir()
        (root / "Config" / "GPT_Helper_Prompts.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "defaults": {
                        "FRONT": "The character must face directly toward the viewer, just like the reference image."
                    },
                    "pipelines": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
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
                            "worker_by_stage": {
                                "MANIFEST": "zet.workers.noop_worker",
                                "PROMPT": "zet.workers.body_reference_prompt_worker",
                            },
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

    def _write_head_fitment_fixture(self, root: Path) -> Path:
        character_dir = root / "Characters" / "Test" / "Adult"
        asset_dir = root / "Assets" / "Test" / "Adult"
        headshot_dir = character_dir / "Reference_Images" / "Headshots"
        prompt_dir = root / "Pipelines" / "Test" / "Adult" / "Head-Fitment" / "Front" / "Front" / "Asset_2"
        character_dir.mkdir(parents=True)
        asset_dir.mkdir(parents=True)
        headshot_dir.mkdir(parents=True)
        prompt_dir.mkdir(parents=True, exist_ok=True)
        (root / "Queue").mkdir()
        (asset_dir / "body_front.png").write_bytes(b"body")
        (headshot_dir / "head_front.png").write_bytes(b"head")
        (prompt_dir / "Final_Image_Prompt.md").write_text("head fitment final prompt\n", encoding="utf-8")
        (character_dir / "Character_Image_Template.md").write_text(
            """
<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
Test character general facts.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN HEAD_DESCRIPTION_FACTS -->
Test head facts.
<!-- ZET:END HEAD_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN HEAD_DESCRIPTION_VIEW_FRONT -->
Test front head view.
<!-- ZET:END HEAD_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN HAIR_DESCRIPTION_FACTS -->
Test hair facts.
<!-- ZET:END HAIR_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN HAIR_DESCRIPTION_VIEW_FRONT -->
Test front hair view.
<!-- ZET:END HAIR_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_CORE -->
Preserve core identity.
<!-- ZET:END IDENTITY_PRESERVATION_CORE -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_FACE -->
Preserve face.
<!-- ZET:END IDENTITY_PRESERVATION_FACE -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_HAIR -->
Preserve hair.
<!-- ZET:END IDENTITY_PRESERVATION_HAIR -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_EARS -->
Preserve ears.
<!-- ZET:END IDENTITY_PRESERVATION_EARS -->
<!-- ZET:BEGIN HEAD_FITMENT_RENDERING_RULES -->
Use neutral fitment rendering.
<!-- ZET:END HEAD_FITMENT_RENDERING_RULES -->
<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
Avoid drift.
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->
<!-- ZET:BEGIN NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
Avoid head-fitment drift.
<!-- ZET:END NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
""".lstrip(),
            encoding="utf-8",
        )
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
                            "asset_state": "LOCKED",
                            "pipeline_stage": "LOCKED",
                            "actor": "HUMAN_AGENT",
                            "ai_state": None,
                            "final_image_output": "body_front.png",
                            "last_ai_update": None,
                            "error_code": None,
                            "error_message": None,
                            "updated_at": None,
                        },
                        {
                            "asset_id": 2,
                            "character": "Test",
                            "phase": "Adult",
                            "pipeline": "Head-Fitment",
                            "body_view": "Front",
                            "head_view": "Front",
                            "costume": None,
                            "expression": None,
                            "asset_state": "IN_PROGRESS",
                            "pipeline_stage": "MANIFEST",
                            "actor": "PYTHON",
                            "ai_state": None,
                            "final_image_output": "head_fitment.png",
                            "last_ai_update": None,
                            "error_code": None,
                            "error_message": None,
                            "updated_at": None,
                        },
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
                            "stages": ["LOCKED"],
                            "actor_by_stage": {"LOCKED": "HUMAN_AGENT"},
                            "worker_by_stage": {},
                        },
                        "Head-Fitment": {
                            "stages": ["ADD_REF", "MANIFEST", "PROMPT", "RENDER"],
                            "actor_by_stage": {
                                "ADD_REF": "PYTHON",
                                "MANIFEST": "PYTHON",
                                "PROMPT": "PYTHON",
                                "RENDER": "AI_AGENT",
                            },
                            "worker_by_stage": {
                                "ADD_REF": "zet.workers.head_fitment_manifest_worker",
                                "MANIFEST": "zet.workers.head_fitment_manifest_worker",
                                "PROMPT": "zet.workers.head_fitment_prompt_worker",
                            },
                        },
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

    def _write_character_assembly_fixture(self, root: Path) -> Path:
        character_dir = root / "Characters" / "Test" / "Adult"
        asset_dir = root / "Assets" / "Test" / "Adult"
        character_dir.mkdir(parents=True)
        asset_dir.mkdir(parents=True)
        (root / "Pipelines").mkdir()
        (root / "Queue").mkdir()
        (asset_dir / "body_front.png").write_bytes(b"body")
        (asset_dir / "head_fitment_front.png").write_bytes(b"head")
        (character_dir / "Character_Image_Template.md").write_text(
            """
<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
Test character general facts.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
Test body facts.
<!-- ZET:END BODY_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN BODY_DESCRIPTION_VIEW_FRONT -->
Test front body view.
<!-- ZET:END BODY_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN HEAD_DESCRIPTION_FACTS -->
Test head facts.
<!-- ZET:END HEAD_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN HEAD_DESCRIPTION_VIEW_FRONT -->
Test front head view.
<!-- ZET:END HEAD_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN HAIR_DESCRIPTION_FACTS -->
Test hair facts.
<!-- ZET:END HAIR_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN HAIR_DESCRIPTION_VIEW_FRONT -->
Test front hair view.
<!-- ZET:END HAIR_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->
Test costume facts.
<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN COSTUME_DESCRIPTION_VIEW_FRONT -->
Test front costume view.
<!-- ZET:END COSTUME_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN EQUIPMENT_DESCRIPTION_FACTS -->
Test equipment facts.
<!-- ZET:END EQUIPMENT_DESCRIPTION_FACTS -->
<!-- ZET:BEGIN EQUIPMENT_DESCRIPTION_VIEW_FRONT -->
Test front equipment view.
<!-- ZET:END EQUIPMENT_DESCRIPTION_VIEW_FRONT -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_CORE -->
Preserve core identity.
<!-- ZET:END IDENTITY_PRESERVATION_CORE -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_FACE -->
Preserve face.
<!-- ZET:END IDENTITY_PRESERVATION_FACE -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_HAIR -->
Preserve hair.
<!-- ZET:END IDENTITY_PRESERVATION_HAIR -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_EARS -->
Preserve ears.
<!-- ZET:END IDENTITY_PRESERVATION_EARS -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
Preserve body.
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->
<!-- ZET:BEGIN IDENTITY_PRESERVATION_COSTUME -->
Preserve costume.
<!-- ZET:END IDENTITY_PRESERVATION_COSTUME -->
<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER -->
Plain tan tank top and shorts.
<!-- ZET:END TECHNICAL_MODESTY_LAYER -->
<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
Avoid drift.
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->
<!-- ZET:BEGIN NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
Avoid assembly drift.
<!-- ZET:END NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
""".lstrip(),
            encoding="utf-8",
        )
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
                            "asset_state": "LOCKED",
                            "pipeline_stage": "LOCKED",
                            "actor": "HUMAN_AGENT",
                            "ai_state": None,
                            "final_image_output": "body_front.png",
                            "last_ai_update": None,
                            "error_code": None,
                            "error_message": None,
                            "updated_at": None,
                        },
                        {
                            "asset_id": 2,
                            "character": "Test",
                            "phase": "Adult",
                            "pipeline": "Head-Fitment",
                            "body_view": "Front",
                            "head_view": "Front",
                            "costume": None,
                            "expression": None,
                            "asset_state": "LOCKED",
                            "pipeline_stage": "LOCKED",
                            "actor": "HUMAN_AGENT",
                            "ai_state": None,
                            "final_image_output": "head_fitment_front.png",
                            "last_ai_update": None,
                            "error_code": None,
                            "error_message": None,
                            "updated_at": None,
                        },
                        {
                            "asset_id": 3,
                            "character": "Test",
                            "phase": "Adult",
                            "pipeline": "Character-Assembly",
                            "body_view": "Front",
                            "head_view": "Front",
                            "costume": "Default",
                            "expression": None,
                            "asset_state": "IN_PROGRESS",
                            "pipeline_stage": "MANIFEST",
                            "actor": "PYTHON",
                            "ai_state": None,
                            "final_image_output": "character_assembly_front.png",
                            "last_ai_update": None,
                            "error_code": None,
                            "error_message": None,
                            "updated_at": None,
                        },
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
                            "stages": ["LOCKED"],
                            "actor_by_stage": {"LOCKED": "HUMAN_AGENT"},
                            "worker_by_stage": {},
                        },
                        "Head-Fitment": {
                            "stages": ["LOCKED"],
                            "actor_by_stage": {"LOCKED": "HUMAN_AGENT"},
                            "worker_by_stage": {},
                        },
                        "Character-Assembly": {
                            "stages": ["MANIFEST", "PROMPT", "RENDER", "RENDER_REVIEW"],
                            "actor_by_stage": {
                                "MANIFEST": "PYTHON",
                                "PROMPT": "PYTHON",
                                "RENDER": "AI_AGENT",
                                "RENDER_REVIEW": "HUMAN_AGENT",
                            },
                            "worker_by_stage": {
                                "MANIFEST": "zet.workers.character_assembly_manifest_worker",
                                "PROMPT": "zet.workers.character_assembly_prompt_worker",
                            },
                        },
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

[Render]
Backend = "manual_chatgpt"
""".lstrip(),
            encoding="utf-8",
        )
        return config_path

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
            self.assertIn("Ran 1 worker(s)", payload["message"])
            self.assertIn("Finished at RENDER", payload["message"])
            self.assertEqual(payload["detail"]["asset"]["pipeline_stage"], "RENDER")

    def test_retired_prompt_review_api_is_not_registered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/prompt-review/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(tasks.status_code, 404)
            self.assertFalse(any(path.startswith("/api/prompt-review") for path in client.get("/openapi.json").json()["paths"]))

    def test_render_review_api_serves_tasks_detail_and_promotes_to_locked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER_REVIEW", actor="HUMAN_AGENT")
            (root / "Assets" / "Test" / "Adult" / "front.png").write_bytes(b"locked image")
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/render-review/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["asset_id"], 1)
            self.assertTrue(tasks.json()["tasks"][0]["candidate_image_exists"])

            detail = client.get("/api/render-review/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertTrue(detail.json()["is_reviewable"])
            self.assertTrue(detail.json()["exists"]["candidate_image"])
            self.assertTrue(detail.json()["exists"]["locked_image"])
            self.assertTrue(detail.json()["candidate_image_path"].endswith("front.png"))
            self.assertTrue(detail.json()["locked_image_path"].endswith("front.png"))

            comment = client.post(
                "/api/render-review/1/comment",
                params={"character": "Test", "phase": "Adult"},
                json={"comment": "Good face, boots need checking."},
            )
            self.assertEqual(comment.status_code, 200)
            self.assertEqual(comment.json()["render_review_comment"], "Good face, boots need checking.")
            self.assertTrue(comment.json()["asset"]["has_render_review_comment"])

            unconfirmed = client.post(
                "/api/render-review/1/promote-to-locked",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(unconfirmed.status_code, 409)

            promoted = client.post(
                "/api/render-review/1/promote-to-locked",
                params={"character": "Test", "phase": "Adult", "replace_existing": "true"},
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

    def test_asset_action_api_stages_retouch_as_manual_render(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="LOCKED", actor="HUMAN_AGENT")
            client = TestClient(create_app(config_path))

            response = client.post("/api/assets/1/retouch", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("Retouch render staged", payload["message"])
            self.assertEqual(payload["detail"]["asset"]["pipeline_stage"], "RENDER")
            self.assertEqual(payload["detail"]["asset"]["actor"], "AI_AGENT")
            self.assertEqual(payload["detail"]["asset"]["ai_state"], "ASKED")
            self.assertFalse((root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1" / "front.png").exists())
            ask_dirs = list((root / "Queue" / "Ollama_Proxy" / "Ask").iterdir())
            self.assertEqual(len(ask_dirs), 1)
            manifest = json.loads((ask_dirs[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["worker_type"], "manual_chatgpt_render")
            self.assertTrue(manifest["manual"])

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
                    "local_render_preset": "body-reference-preview",
                    "local_render_positive_prompt_globals": "masterpiece",
                    "local_render_negative_prompt_globals": "blurry",
                    "local_render_use_forge_couple": True,
                    "local_render_checkpoint": "test-checkpoint",
                    "ai_harvest_auto_enabled": True,
                    "ai_harvest_interval_seconds": 600,
                    "render_backend": "manual_chatgpt",
                },
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["automation"]["local_render_positive_prompt_globals"], "masterpiece")
            self.assertTrue(saved.json()["automation"]["local_render_use_forge_couple"])
            self.assertEqual(saved.json()["automation"]["local_render_checkpoint"], "test-checkpoint")
            self.assertEqual(saved.json()["automation"]["render_backend"], "manual_chatgpt")
            self.assertIn('Checkpoint = "test-checkpoint"', config_path.read_text(encoding="utf-8"))

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
            self.assertEqual(
                detail.json()["gpt_helper_prompt"]["text"],
                "The character must face directly toward the viewer, just like the reference image.",
            )
            saved_helper = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/gpt-helper-prompt",
                json={"text": "Keep this front view absolutely square to the viewer."},
            )
            self.assertEqual(saved_helper.status_code, 200)
            self.assertEqual(
                saved_helper.json()["gpt_helper_prompt"]["text"],
                "Keep this front view absolutely square to the viewer.",
            )
            self.assertEqual(saved_helper.json()["gpt_helper_prompt"]["source"], "pipeline:Body-Reference")
            helper_config = json.loads((root / "Characters" / "Test" / "Adult" / "GPT_Helper_Prompts.json").read_text(encoding="utf-8"))
            self.assertEqual(
                helper_config["pipelines"]["Body-Reference"]["FRONT"],
                "Keep this front view absolutely square to the viewer.",
            )
            saved = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/answer-image",
                params={"render_comment": "First render has strong silhouette."},
                content=b"image bytes",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["status"], "SUCCESS")
            self.assertFalse(ask_path.exists())
            answer_path = root / "Queue" / "Ollama_Proxy" / "Answer" / "Ask_Asset_1_RENDER_TEST"
            self.assertTrue((answer_path / "front.png").exists())
            self.assertEqual(
                (answer_path / "Render_Review_Comment.md").read_text(encoding="utf-8").strip(),
                "First render has strong silhouette.",
            )
            manifest = json.loads((answer_path / "answer_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "SUCCESS")
            self.assertEqual(manifest["render_comment"], "First render has strong silhouette.")

    def test_render_console_detail_supports_story_prompt_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            ask_path = root / "Queue" / "Ollama_Proxy" / "Ask" / "Ask_Story_demo_scene_RENDER_TEST"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text(
                json.dumps(
                    {
                        "ask_id": ask_path.name,
                        "asset_id": None,
                        "character": "",
                        "phase": "",
                        "pipeline": "Story",
                        "pipeline_stage": "RENDER",
                        "worker_type": "manual_chatgpt_render",
                        "prompt_file": "Final_Image_Prompt.md",
                        "expected_output": "scene.png",
                        "story_slug": "demo",
                        "scene_slug": "scene",
                    }
                ),
                encoding="utf-8",
            )
            (ask_path / "Final_Image_Prompt.md").write_text("scene line one\nscene line two\n", encoding="utf-8")

            detail = TestClient(create_app(config_path)).get(f"/api/render-console/tasks/{ask_path.name}")

            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["prompt"], "scene line one\nscene line two\n")
            self.assertEqual(detail.json()["manifest"]["scene_slug"], "scene")
            self.assertTrue(detail.json()["prompt_path"].endswith("Final_Image_Prompt.md"))

    def test_render_console_local_test_render_api_params(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            self._write_manual_render_ask(root)
            (root / "Characters" / "Test" / "Adult" / "Body_Reference" / "Front" / "Condensed_Image_Prompt.md").write_text(
                "condensed prompt\n",
                encoding="utf-8",
            )
            local_render_dir = root / "Characters" / "Test" / "Adult" / "Body_Reference" / "Front" / "Local_Test_Renders"
            local_render_dir.mkdir()
            (local_render_dir / "Stable_Matrix_API_Call.json").write_text('{"prompt": "rendered"}\n', encoding="utf-8")
            client = TestClient(create_app(config_path))

            response = client.get("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/local-test-render/api-params")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["text"], '{"prompt": "rendered"}\n')
            self.assertEqual(response.json()["path"], str(local_render_dir / "Stable_Matrix_API_Call.json"))

    def test_render_console_clear_and_fail_remove_all_local_test_renders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            ask_path = self._write_manual_render_ask(root)
            render_dir = ask_path / "Local_Test_Renders"
            render_dir.mkdir()
            (render_dir / "test_1.png").write_bytes(b"image")
            (render_dir / "test_1.json").write_text("{}", encoding="utf-8")
            (render_dir / "Stable_Matrix_API_Call.json").write_text("{}", encoding="utf-8")
            client = TestClient(create_app(config_path))

            cleared = client.delete("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/local-test-render")
            self.assertEqual(cleared.status_code, 200)
            self.assertFalse(render_dir.exists())

            render_dir.mkdir()
            (render_dir / "test_2.png").write_bytes(b"image")
            (render_dir / "test_2.json").write_text("{}", encoding="utf-8")
            failed = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/fail",
                json={"reason": "Test failure"},
            )
            self.assertEqual(failed.status_code, 200)
            self.assertFalse(render_dir.exists())

    def test_harvest_continues_after_malformed_answer_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER", actor="AI_AGENT")
            queue_root = root / "Queue" / "Ollama_Proxy" / "Answer"
            malformed = queue_root / "Ask_Asset_1_RENDER_A_MALFORMED"
            malformed.mkdir(parents=True)
            (malformed / "answer_manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ask_id": "Ask_Asset_1_RENDER_A_MALFORMED",
                        "asset_id": 1,
                        "ollama_attempt_id": "malformed",
                        "worker_id": "test",
                        "status": "SUCCESS",
                        "expected_output": "front.png",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            valid = queue_root / "Ask_Asset_1_RENDER_B_FAILED"
            valid.mkdir()
            (valid / "ask_manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ask_id": "Ask_Asset_1_RENDER_B_FAILED",
                        "asset_id": 1,
                        "character": "Test",
                        "phase": "Adult",
                        "pipeline": "Body-Reference",
                        "pipeline_stage": "RENDER",
                        "ollama_attempt_id": "failed",
                        "worker_type": "manual_chatgpt_render",
                        "prompt_file": "Final_Image_Prompt.md",
                        "expected_output": "front.png",
                        "task_type": "render",
                        "auxiliary": False,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (valid / "answer_manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ask_id": "Ask_Asset_1_RENDER_B_FAILED",
                        "asset_id": 1,
                        "ollama_attempt_id": "failed",
                        "worker_id": "manual-chatgpt-render-console",
                        "status": "ERROR",
                        "expected_output": "front.png",
                        "error_type": "MANUAL_RENDER_FAILED",
                        "error_message": "redo prompt",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            client = TestClient(create_app(config_path))
            harvested = client.post("/api/ai-controls/harvest")

            self.assertEqual(harvested.status_code, 200)
            statuses = [item["status"] for item in harvested.json()["harvest_results"]]
            self.assertIn("MALFORMED", statuses)
            self.assertIn("BLOCKED", statuses)
            self.assertTrue((malformed / "harvest_manifest.json").exists())

            detail = client.get("/api/assets/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.json()["asset"]["pipeline_stage"], "ERROR")
            self.assertEqual(detail.json()["asset"]["error_code"], "MANUAL_RENDER_FAILED")

    def test_harvest_applies_render_comment_to_image_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER", actor="AI_AGENT")
            self._write_manual_render_ask(root)
            client = TestClient(create_app(config_path))

            saved = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/answer-image",
                params={"render_comment": "Candidate is close; inspect hand shape."},
                content=b"image bytes",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(saved.status_code, 200)
            harvested = client.post("/api/ai-controls/harvest")
            self.assertEqual(harvested.status_code, 200)

            detail = client.get("/api/render-review/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["asset"]["pipeline_stage"], "RENDER_REVIEW")
            self.assertEqual(detail.json()["render_review_comment"], "Candidate is close; inspect hand shape.")
            self.assertTrue(detail.json()["asset"]["has_render_review_comment"])
            comment_path = root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1" / "Render_Review_Comment.md"
            self.assertEqual(comment_path.read_text(encoding="utf-8").strip(), "Candidate is close; inspect hand shape.")

    def test_ai_controls_archives_only_harvested_answer_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            answer_root = root / "Queue" / "Ollama_Proxy" / "Answer"
            harvested = answer_root / "Ask_Harvested"
            pending = answer_root / "Ask_Pending"
            harvested.mkdir(parents=True)
            pending.mkdir()
            (harvested / "answer_manifest.json").write_text("{}\n", encoding="utf-8")
            (harvested / "harvest_manifest.json").write_text("{}\n", encoding="utf-8")
            (pending / "answer_manifest.json").write_text("{}\n", encoding="utf-8")
            client = TestClient(create_app(config_path))

            response = client.post("/api/ai-controls/archive-harvested")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("Archived 1 harvested", payload["message"])
            self.assertFalse(harvested.exists())
            self.assertTrue(pending.exists())
            archive_matches = list((root / "Queue" / "Ollama_Proxy" / "Archive" / "Harvested").glob("*/*Ask_Harvested"))
            self.assertEqual(len(archive_matches), 1)

    def test_head_fitment_manifest_api_saves_reference_slots_and_uploads_headshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/head-fitment-manifest/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["asset_id"], 2)

            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            body_path = detail.json()["body_reference_options"][0]["path"]
            headshot_path = detail.json()["headshot_options"][0]["path"]

            uploaded = client.post(
                "/api/head-fitment-manifest/headshots",
                params={"character": "Test", "phase": "Adult", "filename": "new_head.png"},
                content=b"new head",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(uploaded.status_code, 200)
            self.assertTrue(Path(uploaded.json()["path"]).exists())

            saved = client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={"body_reference_path": body_path, "headshot_path": headshot_path},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(len(saved.json()["reference_files"]), 2)
            self.assertEqual(saved.json()["reference_files"][0]["role"], "body_reference")

    def test_head_fitment_render_ask_includes_reference_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            client = TestClient(create_app(config_path))

            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"})
            body_path = detail.json()["body_reference_options"][0]["path"]
            headshot_path = detail.json()["headshot_options"][0]["path"]
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={"body_reference_path": body_path, "headshot_path": headshot_path},
            )

            assets_path = root / "Characters" / "Test" / "Adult" / "Assets.json"
            payload = json.loads(assets_path.read_text(encoding="utf-8"))
            payload["assets"][1]["pipeline_stage"] = "RENDER"
            payload["assets"][1]["actor"] = "AI_AGENT"
            payload["assets"][1]["ai_state"] = "ASKED"
            assets_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            staged = client.post("/api/assets/2/stage-ai-ask", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(staged.status_code, 200)
            ask_dirs = list((root / "Queue" / "Ollama_Proxy" / "Ask").iterdir())
            manifest = json.loads((ask_dirs[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["worker_type"], "manual_chatgpt_render")
            self.assertEqual(manifest["prompt_file"], "Final_Image_Prompt.md")
            self.assertEqual([item["role"] for item in manifest["reference_files"]], ["body_reference", "headshot"])

    def test_head_fitment_prompt_worker_compiles_prompt_and_stages_render_ask(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            client = TestClient(create_app(config_path))

            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"})
            body_path = detail.json()["body_reference_options"][0]["path"]
            headshot_path = detail.json()["headshot_options"][0]["path"]
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={"body_reference_path": body_path, "headshot_path": headshot_path},
            )

            manifest_done = client.post("/api/assets/2/run-current-worker", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(manifest_done.status_code, 200)
            asset = manifest_done.json()["detail"]["asset"]
            self.assertEqual(asset["pipeline_stage"], "RENDER")
            self.assertEqual(asset["actor"], "AI_AGENT")
            self.assertEqual(asset["ai_state"], "ASKED")

            prompt_path = root / "Pipelines" / "Test" / "Adult" / "Head-Fitment" / "Front" / "Front" / "Asset_2" / "Final_Image_Prompt.md"
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("HEAD-FITMENT CHARACTER REFERENCE IMAGE", prompt_text)
            self.assertIn("The attached body-reference image is the Reference Body source.", prompt_text)
            self.assertIn("The attached headshot reference is the Character Head source.", prompt_text)
            self.assertIn("The output must be a standalone head-and-neck module.", prompt_text)
            self.assertIn("Use the Reference Body as a direct front-view neck-fitment source.", prompt_text)
            self.assertIn("Render the Character Head and fitted neck from a direct front view", prompt_text)
            ask_dirs = list((root / "Queue" / "Ollama_Proxy" / "Ask").iterdir())
            ask_manifest = json.loads((ask_dirs[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["role"] for item in ask_manifest["reference_files"]], ["body_reference", "headshot"])

    def test_head_fitment_manifest_worker_moves_to_add_ref_when_headshot_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            (root / "Characters" / "Test" / "Adult" / "Reference_Images" / "Headshots" / "head_front.png").unlink()
            client = TestClient(create_app(config_path))

            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"})
            body_path = detail.json()["body_reference_options"][0]["path"]
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={"body_reference_path": body_path, "headshot_path": ""},
            )

            manifest_done = client.post("/api/assets/2/run-current-worker", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(manifest_done.status_code, 200)
            asset = manifest_done.json()["detail"]["asset"]
            self.assertEqual(asset["pipeline_stage"], "ADD_REF")
            self.assertEqual(asset["actor"], "PYTHON")
            self.assertEqual(asset["asset_state"], "IN_PROGRESS")
            self.assertEqual(asset["error_code"], "MISSING_HEADSHOT_REFERENCE")

            manifest_tasks = client.get("/api/head-fitment-manifest/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(manifest_tasks.status_code, 200)
            task = manifest_tasks.json()["tasks"][0]
            self.assertEqual(task["pipeline_stage"], "ADD_REF")
            self.assertTrue(task["has_body_reference"])
            self.assertFalse(task["has_headshot"])

    def test_head_fitment_add_ref_can_resume_after_reference_is_added(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            headshot_dir = root / "Characters" / "Test" / "Adult" / "Reference_Images" / "Headshots"
            (headshot_dir / "head_front.png").unlink()
            client = TestClient(create_app(config_path))

            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"})
            body_path = detail.json()["body_reference_options"][0]["path"]
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={"body_reference_path": body_path, "headshot_path": ""},
            )
            client.post("/api/assets/2/run-current-worker", params={"character": "Test", "phase": "Adult"})

            added_headshot = headshot_dir / "Front.png"
            added_headshot.write_bytes(b"fake")
            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"})
            self.assertTrue(detail.json()["is_manifest_editable"])
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={"body_reference_path": body_path, "headshot_path": str(added_headshot)},
            )

            resumed = client.post("/api/assets/2/run-current-worker", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(resumed.status_code, 200)
            asset = resumed.json()["detail"]["asset"]
            self.assertEqual(asset["pipeline_stage"], "RENDER")
            self.assertEqual(asset["actor"], "AI_AGENT")
            self.assertEqual(asset["ai_state"], "ASKED")
            self.assertIsNone(asset["error_code"])

    def test_character_assembly_workers_resolve_refs_compile_prompt_and_stage_render(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_character_assembly_fixture(root)
            client = TestClient(create_app(config_path))

            manifest_done = client.post("/api/assets/3/run-current-worker", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(manifest_done.status_code, 200)
            manifest_asset = manifest_done.json()["detail"]["asset"]
            self.assertEqual(manifest_asset["pipeline_stage"], "RENDER")
            self.assertEqual(manifest_asset["actor"], "AI_AGENT")
            self.assertEqual(manifest_asset["ai_state"], "ASKED")
            self.assertEqual(
                [item["role"] for item in manifest_asset["reference_files"]],
                ["body_reference", "head_fitment"],
            )

            prompt_path = root / "Pipelines" / "Test" / "Adult" / "Character-Assembly" / "Front" / "Front" / "Asset_3" / "Final_Image_Prompt.md"
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("FULL-BODY HEAD-ASSEMBLY FITMENT IMAGE", prompt_text)
            self.assertIn("Preserve the Reference Body as a direct front-view full-body source", prompt_text)
            self.assertIn("The Character Head source is provided only as an identity reference.", prompt_text)
            self.assertIn("Re-render the Character Head in the exact orientation of the Reference Body mannequin head.", prompt_text)
            self.assertNotIn("{{", prompt_text)
            source_map = json.loads((prompt_path.parent / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
            source_kinds = {fragment["source_kind"] for fragment in source_map["fragments"]}
            self.assertIn("static_prompt_template", source_kinds)
            self.assertIn("shared_template_section", source_kinds)
            self.assertIn("config_view_instruction", source_kinds)

            ask_dirs = list((root / "Queue" / "Ollama_Proxy" / "Ask").iterdir())
            self.assertEqual(len(ask_dirs), 1)
            ask_manifest = json.loads((ask_dirs[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(ask_manifest["worker_type"], "manual_chatgpt_render")
            self.assertEqual(ask_manifest["prompt_file"], "Final_Image_Prompt.md")
            self.assertEqual([item["role"] for item in ask_manifest["reference_files"]], ["body_reference", "head_fitment"])


if __name__ == "__main__":
    unittest.main()
