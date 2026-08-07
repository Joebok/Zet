import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

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
        ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Asset_1_RENDER_TEST"
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

    def _write_story_render_ask(self, root: Path, suffix: str) -> Path:
        story_dir = root / "Stories" / "demo"
        story_dir.mkdir(parents=True, exist_ok=True)
        (story_dir / "demo.md").write_text("Title: `[Demo]`\n", encoding="utf-8")
        (story_dir / "scene.md").write_text("Scene: `[Scene]`\n", encoding="utf-8")
        ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / f"Ask_Story_demo_scene_RENDER_{suffix}"
        ask_path.mkdir(parents=True)
        (ask_path / "ask_manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "ask_id": ask_path.name,
                    "asset_id": None,
                    "character": "",
                    "phase": "",
                    "pipeline": "Story",
                    "pipeline_stage": "RENDER",
                    "story_slug": "demo",
                    "scene_slug": "scene",
                    "ollama_attempt_id": suffix,
                    "worker_type": "manual_chatgpt_render",
                    "prompt_file": "Final_Image_Prompt.md",
                    "expected_output": "scene.png",
                    "candidate_output_file": "scene.png",
                    "task_type": "render",
                    "manual": True,
                    "target_output_file": str(story_dir / "scene.png"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (ask_path / "Final_Image_Prompt.md").write_text("scene render prompt\n", encoding="utf-8")
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
        (character_dir / "Character.md").write_text(
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
<!-- ZET:BEGIN HEAD_DESCRIPTION_VIEW_LEFT_PROFILE -->
Unrequested left-profile head view.
<!-- ZET:END HEAD_DESCRIPTION_VIEW_LEFT_PROFILE -->
<!-- ZET:BEGIN BODY_DESCRIPTION_VIEW_FRONT -->
Forbidden front body description.
<!-- ZET:END BODY_DESCRIPTION_VIEW_FRONT -->
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
                                "RENDER": "zet.workers.head_fitment_render_worker",
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
        (character_dir / "Character.md").write_text(
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

            summary = client.get(
                "/api/workspace-summary",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(summary.status_code, 200)
            self.assertEqual(summary.json()["character"]["character"], "Test")
            self.assertEqual(summary.json()["character"]["phase"], "Adult")

            assets = client.get("/api/assets", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(assets.status_code, 200)
            self.assertEqual(assets.json()["assets"][0]["asset_id"], 1)
            self.assertIn("costume_or_expression", assets.json()["assets"][0])

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

    def test_assets_page_shows_advance_all_and_removes_retired_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            response = client.get("/")

            self.assertEqual(response.status_code, 200)
            html = response.text
            self.assertIn("<th>Costume/Expression</th>", html)
            self.assertIn('data-action="advance-all" disabled>Advance All</button>', html)
            self.assertGreater(html.index('data-action="advance-all"'), html.index('id="asset-filter-hide-base"'))
            self.assertIn('id="asset-detail-image-mode" class="navigation-action" type="button">Show Locked Image</button>', html)
            self.assertIn('id="view-prompt-analysis" class="scene-builder-analysis-view"', html)
            self.assertIn('id="workspace-character" class="workspace-option"', html)
            self.assertIn('data-page="pipeline-inspection">Pipeline Inspection</button>', html)
            self.assertLess(
                html.index('data-page="phase-comparison">Phase Comparison</button>'),
                html.index('data-page="pipeline-inspection">Pipeline Inspection</button>'),
            )
            self.assertIn('data-page="phase-comparison">Phase Comparison</button>', html)
            self.assertIn('<option value="stable_matrix">Stable Matrix</option>', html)
            self.assertIn('<option value="comfyui">ComfyUI</option>', html)
            self.assertIn('<option value="prompt-review">Prompts</option>', html)
            self.assertIn('<option value="render-console">Render</option>', html)
            self.assertIn('<option value="local-image-review">Local Images</option>', html)
            self.assertLess(
                html.index('<option value="render-console">Render</option>'),
                html.index('<option value="local-image-review">Local Images</option>'),
            )
            self.assertLess(
                html.index('<option value="local-image-review">Local Images</option>'),
                html.index('<option value="render-review">Image Review</option>'),
            )
            self.assertLess(
                html.index('data-page="scenes">Scenes</button>'),
                html.index('data-page="auxiliary-resources">Aux Images</button>'),
            )
            self.assertLess(
                html.index('data-page="auxiliary-resources">Aux Images</button>'),
                html.index('data-page="zine">Zines</button>'),
            )
            self.assertIn('id="local-image-review-count"', html)
            self.assertIn('id="local-image-review-generate-all-models"', html)
            self.assertIn('id="local-image-review-gallery"', html)
            self.assertIn('id="stable-matrix-settings"', html)
            self.assertIn('id="comfyui-settings" hidden', html)
            self.assertIn('id="setting-comfyui-checkpoint"', html)
            self.assertIn('class="control-panel ai-automation-panel local-image-config-panel"', html)
            self.assertIn('document.querySelectorAll("button.tab")', (Path(__file__).parents[1] / "zet" / "web" / "static" / "zet.js").read_text(encoding="utf-8"))
            self.assertNotIn('data-action="retouch"', html)
            self.assertNotIn('data-action="stage-ai-ask"', html)
            self.assertNotIn('data-action="retry-ai"', html)

            paths = client.get("/openapi.json").json()["paths"]
            self.assertIn("/api/assets/advance-all", paths)
            self.assertIn("/api/pipeline-inspection", paths)
            self.assertIn("/api/pipeline-inspection/files", paths)
            self.assertIn("/api/pipeline-inspection/text", paths)
            self.assertIn("/api/pipeline-inspection/file", paths)
            self.assertIn("/api/pipeline-inspection/open-folder", paths)
            self.assertNotIn("/api/assets/advance-displayed", paths)
            self.assertNotIn("/api/assets/{asset_id}/retouch", paths)
            self.assertNotIn("/api/assets/{asset_id}/stage-ai-ask", paths)
            self.assertNotIn("/api/assets/{asset_id}/retry-ai", paths)

    def test_pipeline_inspection_api_lists_and_reads_pipeline_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            pipeline = root / "Pipelines" / "Stories" / "Demo" / "Opening"
            pipeline.mkdir(parents=True)
            (pipeline / "Scene.json").write_text('{"scene": "Opening"}\n', encoding="utf-8")
            client = TestClient(create_app(config_path))

            pipelines = client.get("/api/pipeline-inspection")
            self.assertEqual(pipelines.status_code, 200)
            self.assertEqual(
                [item["pipeline_id"] for item in pipelines.json()["pipelines"]],
                ["Test/Adult/Body-Reference/Front/_/Asset_1", "Stories/Demo/Opening"],
            )

            files = client.get(
                "/api/pipeline-inspection/files",
                params={"pipeline_id": "Stories/Demo/Opening"},
            )
            self.assertEqual(files.status_code, 200)
            self.assertEqual(files.json()["files"][0]["file_id"], "Scene.json")

            content = client.get(
                "/api/pipeline-inspection/text",
                params={"pipeline_id": "Stories/Demo/Opening", "file_id": "Scene.json"},
            )
            self.assertEqual(content.json()["content"], '{"scene": "Opening"}\n')

    def test_story_actions_are_consolidated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            html = client.get("/").text
            view_index = html.index('id="story-view"')
            save_index = html.index('id="story-save"')
            scenes_index = html.index('id="story-scenes"')
            delete_index = html.index('id="story-delete"')

            self.assertLess(view_index, save_index)
            self.assertLess(save_index, scenes_index)
            self.assertLess(scenes_index, delete_index)
            self.assertNotIn('id="story-settings-load"', html)
            self.assertNotIn('id="story-settings-save"', html)
            self.assertLess(html.index('id="story-table"'), html.index('id="story-new-title"'))
            self.assertLess(html.index('id="story-new-title"'), html.index('class="story-git-panel"'))

            javascript = (Path(__file__).parents[1] / "zet" / "web" / "static" / "zet.js").read_text(encoding="utf-8")
            autosave = javascript[javascript.index("async function saveStoryBeforeNavigation") : javascript.index("async function saveSceneBeforeNavigation")]
            save_story = javascript[javascript.index("async function saveStory()") : javascript.index("async function openStoryScenes()")]
            self.assertIn("return saveStory();", autosave)
            self.assertIn("await saveStorySettingsData(state.selectedStorySlug);", save_story)
            self.assertIn('await activatePage("scenes");', javascript)
            self.assertIn('"story.title",', javascript)
            self.assertIn("await loadStorySettingsData(state.selectedStorySlug);", javascript)

    def test_scene_controls_are_positioned_and_ordered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            html = TestClient(create_app(config_path)).get("/").text

            self.assertLess(html.index('id="scene-table"'), html.index('id="scene-new-name"'))
            image_index = html.index('id="scene-toggle-image"')
            builder_index = html.index('id="scene-builder-open"')
            render_index = html.index('id="scene-stage-render"')
            save_index = html.index('id="scene-save"')
            delete_index = html.index('id="scene-delete"')
            self.assertLess(image_index, builder_index)
            self.assertLess(builder_index, render_index)
            self.assertLess(render_index, save_index)
            self.assertLess(save_index, delete_index)
            self.assertIn('id="scene-image-candidate-link"', html)
            self.assertIn("Candidate Image Pending", html)
            javascript = (Path(__file__).parents[1] / "zet" / "web" / "static" / "zet.js").read_text(encoding="utf-8")
            self.assertIn('page: "render-review"', javascript)
            self.assertIn('review_kind: "scene"', javascript)
            self.assertIn("reference.candidate_pending", javascript)

    def test_asset_regenerate_advances_only_the_selected_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            assets_path = root / "Characters" / "Test" / "Adult" / "Assets.json"
            payload = json.loads(assets_path.read_text(encoding="utf-8"))
            second = dict(payload["assets"][0])
            second.update({"asset_id": 2, "pipeline_stage": "MANIFEST", "actor": "PYTHON", "final_image_output": "second.png"})
            payload["assets"].append(second)
            assets_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            pipelines_path = root / "Characters" / "Test" / "Adult" / "Pipelines.json"
            pipelines = json.loads(pipelines_path.read_text(encoding="utf-8"))
            body_pipeline = pipelines["pipelines"]["Body-Reference"]
            body_pipeline["stages"] = ["MANIFEST", "LOCKED"]
            body_pipeline["actor_by_stage"] = {"MANIFEST": "PYTHON", "LOCKED": "HUMAN_AGENT"}
            pipelines_path.write_text(json.dumps(pipelines, indent=2) + "\n", encoding="utf-8")
            client = TestClient(create_app(config_path))

            response = client.post("/api/assets/1/regenerate", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertIn("regenerated and advanced to LOCKED", result["message"])
            self.assertEqual(result["detail"]["asset"]["pipeline_stage"], "LOCKED")
            assets = {asset["asset_id"]: asset for asset in result["assets"]}
            self.assertEqual(assets[2]["pipeline_stage"], "MANIFEST")

    def test_asset_regenerate_and_clear_references_stops_at_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            assets_path = root / "Characters" / "Test" / "Adult" / "Assets.json"
            payload = json.loads(assets_path.read_text(encoding="utf-8"))
            payload["assets"][0]["reference_files"] = [{"role": "head_image_source", "path": "old.png"}]
            assets_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            client = TestClient(create_app(config_path))

            response = client.post(
                "/api/assets/1/regenerate-and-clear-references",
                params={"character": "Test", "phase": "Adult"},
            )

            self.assertEqual(response.status_code, 200)
            asset = response.json()["detail"]["asset"]
            self.assertEqual(asset["pipeline_stage"], "MANIFEST")
            self.assertEqual(asset["actor"], "PYTHON")
            self.assertEqual(asset["reference_files"], [])

    def test_asset_actions_include_regen_and_clear_references_before_promote(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_fixture(Path(temp_dir))
            html = TestClient(create_app(config_path)).get("/").text

            regen_index = html.index('data-action="regenerate"')
            clear_index = html.index('data-action="regenerate-and-clear-references"')
            promote_index = html.index('data-action="promote-to-locked"')
            self.assertLess(regen_index, clear_index)
            self.assertLess(clear_index, promote_index)
            self.assertIn('disabled>Regen</button>', html)
            self.assertIn('disabled>Regen &amp; clear refs</button>', html)
            self.assertIn('data-action="keep-locked" hidden disabled>Keep LOCKED</button>', html)

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
            self.assertTrue(any((root / "Queue" / "File_Proxy" / "Ask" / "zet").iterdir()))

    def test_render_review_api_can_discard_candidate_and_keep_locked_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER_REVIEW", actor="HUMAN_AGENT")
            locked_path = root / "Assets" / "Test" / "Adult" / "front.png"
            locked_path.write_bytes(b"locked image")
            candidate_path = root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1" / "front.png"
            client = TestClient(create_app(config_path))

            discarded = client.post(
                "/api/render-review/1/discard-candidate",
                params={"character": "Test", "phase": "Adult"},
            )

            self.assertEqual(discarded.status_code, 200)
            payload = discarded.json()
            self.assertEqual(payload["asset"]["asset_state"], "LOCKED")
            self.assertEqual(payload["asset"]["pipeline_stage"], "LOCKED")
            self.assertEqual(locked_path.read_bytes(), b"locked image")
            self.assertFalse(candidate_path.exists())

    def test_asset_api_can_keep_existing_locked_image_after_regen(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="MANIFEST", actor="PYTHON")
            locked_path = root / "Assets" / "Test" / "Adult" / "front.png"
            locked_path.write_bytes(b"locked image")
            candidate_path = root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1" / "front.png"
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Asset_1_RENDER_stale"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text('{"asset_id": 1}\n', encoding="utf-8")
            client = TestClient(create_app(config_path))

            kept = client.post(
                "/api/assets/1/keep-locked",
                params={"character": "Test", "phase": "Adult"},
            )

            self.assertEqual(kept.status_code, 200)
            payload = kept.json()["detail"]["asset"]
            self.assertEqual(payload["asset_state"], "LOCKED")
            self.assertEqual(payload["pipeline_stage"], "LOCKED")
            self.assertEqual(payload["actor"], "HUMAN_AGENT")
            self.assertEqual(locked_path.read_bytes(), b"locked image")
            self.assertFalse(candidate_path.exists())
            self.assertFalse(ask_path.exists())

    def test_ai_controls_api_serves_queue_and_managed_processes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            snapshot = client.get("/api/ai-controls")
            self.assertEqual(snapshot.status_code, 200)
            self.assertIn("queue_counts", snapshot.json())
            self.assertEqual(set(snapshot.json()["queue_counts"]), {"ask", "running", "answer"})
            processes = snapshot.json()["processes"]
            self.assertEqual([item["process_id"] for item in processes], ["zet_web", "auto_harvest"])
            self.assertTrue(all(item["manageable"] == "yes" for item in processes))

    def test_pipeline_controls_api_serves_snapshot_and_saves_automation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            web_app = create_app(config_path)
            original_zet_app = web_app.state.zet_app
            client = TestClient(web_app)

            snapshot = client.get("/api/pipeline-controls", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(snapshot.status_code, 200)
            self.assertEqual(snapshot.json()["pipeline_names"], ["Body-Reference"])

            saved = client.post(
                "/api/pipeline-controls/automation",
                params={"character": "Test", "phase": "Adult"},
                json={
                    "local_render_backend": "comfyui",
                    "local_render_preset": "body-reference-preview",
                    "local_render_positive_prompt_globals": "masterpiece",
                    "local_render_negative_prompt_globals": "blurry",
                    "local_render_use_forge_couple": True,
                    "local_render_checkpoint": "test-checkpoint",
                    "stable_matrix_profile": "body-reference-preview",
                    "stable_matrix_checkpoint": "test-checkpoint",
                    "comfyui_profile": "comfyui-core-preview",
                    "comfyui_server_url": "http://127.0.0.1:8188",
                    "comfyui_checkpoint": "comfy-checkpoint.safetensors",
                    "comfyui_positive_prompt_globals": "comfy positive",
                    "comfyui_negative_prompt_globals": "comfy negative",
                    "comfyui_poll_seconds": 0.5,
                    "comfyui_timeout_seconds": 120,
                    "ai_harvest_auto_enabled": True,
                    "ai_harvest_interval_seconds": 600,
                    "render_backend": "manual_chatgpt",
                },
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["automation"]["local_render_positive_prompt_globals"], "masterpiece")
            self.assertTrue(saved.json()["automation"]["local_render_use_forge_couple"])
            self.assertEqual(saved.json()["automation"]["local_render_checkpoint"], "test-checkpoint")
            self.assertEqual(saved.json()["automation"]["local_render_backend"], "comfyui")
            self.assertEqual(saved.json()["automation"]["comfyui_checkpoint"], "comfy-checkpoint.safetensors")
            self.assertEqual(saved.json()["automation"]["render_backend"], "manual_chatgpt")
            self.assertIn('Checkpoint = "test-checkpoint"', config_path.read_text(encoding="utf-8"))
            self.assertIn('[ComfyUI]', config_path.read_text(encoding="utf-8"))
            self.assertIsNot(web_app.state.zet_app, original_zet_app)

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
            self.assertTrue(any((root / "Queue" / "File_Proxy" / "Ask" / "zet").iterdir()))

    def test_pipeline_controls_batch_reset_preview_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="LOCKED", actor="HUMAN_AGENT")
            assets_path = root / "Characters" / "Test" / "Adult" / "Assets.json"
            assets_payload = json.loads(assets_path.read_text(encoding="utf-8"))
            assets_payload["assets"][0]["asset_state"] = "LOCKED"
            assets_path.write_text(json.dumps(assets_payload, indent=2) + "\n", encoding="utf-8")
            client = TestClient(create_app(config_path))

            preview = client.get(
                "/api/pipeline-controls/batch-render-reset/preview",
                params={
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline_name": "Body-Reference",
                    "include_locked": "false",
                },
            )

            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["counts"], {"affected": 0, "skipped": 1, "locked": 1})
            self.assertEqual(preview.json()["items"][0]["preview_status"], "SKIPPED")
            asset = client.get("/api/assets/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(asset.json()["asset"]["pipeline_stage"], "LOCKED")
            ask_dir = root / "Queue" / "File_Proxy" / "Ask" / "zet"
            self.assertFalse(ask_dir.exists() and any(ask_dir.iterdir()))

            included_preview = client.get(
                "/api/pipeline-controls/batch-render-reset/preview",
                params={
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline_name": "Body-Reference",
                    "include_locked": "true",
                },
            ).json()
            reset = client.post(
                "/api/pipeline-controls/batch-render-reset",
                params={
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline_name": "Body-Reference",
                    "include_locked": "true",
                },
            ).json()
            actual_reset_count = sum(item["status"] == "RESET" for item in reset["batch_results"])
            self.assertEqual(included_preview["counts"]["affected"], actual_reset_count)
            self.assertEqual(included_preview["items"][0]["previous_stage"], "LOCKED")

    def test_render_console_api_lists_task_detail_and_saves_image_answer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            ask_path = self._write_manual_render_ask(root)
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/render-console/tasks")
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["ask_id"], "Ask_Asset_1_RENDER_TEST")
            self.assertEqual(tasks.json()["tasks"][0]["display_label"], "Body-Reference / Front")

            detail = client.get("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["prompt"], "manual render prompt\n")
            self.assertNotIn("gpt_helper_prompt", detail.json())
            self.assertEqual(
                client.post("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/gpt-helper-prompt").status_code,
                404,
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
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Asset_1_RENDER_TEST"
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
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Story_demo_scene_RENDER_TEST"
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
            client = TestClient(create_app(config_path))
            scoped = client.get(
                "/api/render-console/tasks",
                params={"story_slug": "demo", "scene_slug": "scene"},
            ).json()["tasks"]
            self.assertEqual([task["ask_id"] for task in scoped], [ask_path.name])
            self.assertEqual(scoped[0]["story_slug"], "demo")
            self.assertEqual(scoped[0]["scene_slug"], "scene")
            self.assertEqual(client.get("/api/render-console/tasks", params={"story_slug": "other"}).json()["tasks"], [])

    def test_scene_render_answers_use_locked_candidate_review_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "[BaseFolders]\n",
                    f"[BaseFolders]\nBaseLibraryPath = \"{root.as_posix()}\"\n",
                ),
                encoding="utf-8",
            )
            local_image = root / "Pipelines" / "Stories" / "demo" / "scene" / "Local_Test_Renders" / "test_1.png"
            local_image.parent.mkdir(parents=True)
            local_image.write_bytes(b"local")
            first_ask = self._write_story_render_ask(root, "FIRST")
            client = TestClient(create_app(config_path))

            first = client.post(
                f"/api/render-console/tasks/{first_ask.name}/answer-image",
                content=b"first image",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(first.status_code, 200)
            self.assertFalse(first.json()["scene_image_review"]["candidate_exists"])
            locked = root / "Stories" / "demo" / "scene.png"
            candidate = root / "Pipelines" / "Stories" / "demo" / "scene" / "Candidate" / "scene.png"
            self.assertEqual(locked.read_bytes(), b"first image")
            self.assertFalse(candidate.exists())

            second_ask = self._write_story_render_ask(root, "SECOND")
            second = client.post(
                f"/api/render-console/tasks/{second_ask.name}/answer-image",
                params={"render_comment": "Compare the lighting."},
                content=b"second image",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(second.status_code, 200)
            self.assertTrue(second.json()["scene_image_review"]["candidate_exists"])
            self.assertEqual(locked.read_bytes(), b"first image")
            self.assertEqual(candidate.read_bytes(), b"second image")

            scene_document = client.get("/api/stories/demo/scenes/scene").json()["document"]
            self.assertEqual(scene_document["image_path"], str(locked))
            self.assertTrue(scene_document["candidate_pending"])
            references = client.get("/api/scene-image-picker").json()["rows"]
            scene_reference = next(row for row in references if row["kind"] == "scene")
            self.assertEqual(scene_reference["thumbnail_path"], str(locked))
            self.assertTrue(scene_reference["candidate_pending"])
            self.assertEqual(scene_reference["image_review_key"], "scene:demo:scene")

            tasks = client.get("/api/render-review/tasks")
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["review_key"], "scene:demo:scene")
            scoped_tasks = client.get(
                "/api/render-review/tasks",
                params={"story_slug": "demo", "scene_slug": "scene"},
            )
            self.assertEqual(scoped_tasks.json()["tasks"][0]["review_key"], "scene:demo:scene")
            self.assertEqual(
                client.get("/api/render-review/tasks", params={"story_slug": "other"}).json()["tasks"],
                [],
            )
            detail = client.get("/api/render-review/scenes/demo/scene")
            self.assertTrue(detail.json()["locked_exists"])
            self.assertTrue(detail.json()["candidate_exists"])
            self.assertEqual(detail.json()["render_review_comment"], "Compare the lighting.")

            promoted = client.post("/api/render-review/scenes/demo/scene/promote-to-locked")
            self.assertEqual(promoted.status_code, 200)
            self.assertEqual(locked.read_bytes(), b"second image")
            self.assertFalse(candidate.exists())
            backups = list((root / "Pipelines" / "Stories" / "demo" / "scene" / "Locked_Backups").glob("*.png"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"first image")

            third_ask = self._write_story_render_ask(root, "THIRD")
            client.post(
                f"/api/render-console/tasks/{third_ask.name}/answer-image",
                content=b"third image",
                headers={"content-type": "image/png"},
            )
            discarded = client.post("/api/render-review/scenes/demo/scene/discard-candidate")
            self.assertEqual(discarded.status_code, 200)
            self.assertEqual(locked.read_bytes(), b"second image")
            self.assertFalse(candidate.exists())

    def test_scene_render_answer_remains_accepted_when_immediate_harvest_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "[BaseFolders]\n",
                    f"[BaseFolders]\nBaseLibraryPath = \"{root.as_posix()}\"\n",
                ),
                encoding="utf-8",
            )
            ask_path = self._write_story_render_ask(root, "HARVEST_FAILURE")
            client = TestClient(create_app(config_path))

            with patch(
                "zet.services.ai_answer_harvester.AIAnswerHarvester.apply_answer_folder",
                side_effect=RuntimeError("temporary failure"),
            ):
                response = client.post(
                    f"/api/render-console/tasks/{ask_path.name}/answer-image",
                    content=b"saved image",
                    headers={"content-type": "image/png"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ACCEPTED")
            self.assertIn("pending harvest", response.json()["harvest_warning"])
            self.assertFalse(ask_path.exists())
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / ask_path.name
            self.assertTrue((answer_path / "scene.png").exists())

            harvested = client.post("/api/ai-controls/harvest")
            self.assertEqual(harvested.status_code, 200)
            self.assertEqual((root / "Stories" / "demo" / "scene.png").read_bytes(), b"saved image")

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

    def test_render_console_clear_removes_only_images_and_fail_preserves_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            self._write_manual_render_ask(root)
            render_dir = root / "Characters" / "Test" / "Adult" / "Body_Reference" / "Front" / "Local_Test_Renders"
            render_dir.mkdir()
            (render_dir / "test_1.png").write_bytes(b"image")
            (render_dir / "test_1.json").write_text("{}", encoding="utf-8")
            (render_dir / "Stable_Matrix_API_Call.json").write_text("{}", encoding="utf-8")
            client = TestClient(create_app(config_path))

            cleared = client.delete("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/local-test-render")
            self.assertEqual(cleared.status_code, 200)
            self.assertTrue(render_dir.exists())
            self.assertFalse((render_dir / "test_1.png").exists())
            self.assertTrue((render_dir / "test_1.json").exists())
            self.assertTrue((render_dir / "Stable_Matrix_API_Call.json").exists())

            (render_dir / "test_2.png").write_bytes(b"image")
            (render_dir / "test_2.json").write_text("{}", encoding="utf-8")
            failed = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/fail",
                json={"reason": "Test failure"},
            )
            self.assertEqual(failed.status_code, 200)
            self.assertTrue((render_dir / "test_2.png").exists())
            self.assertTrue((render_dir / "test_2.json").exists())

    def test_local_image_review_lists_clears_and_queues_distinct_seed_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            self._write_manual_render_ask(root)
            workspace = root / "Characters" / "Test" / "Adult" / "Body_Reference" / "Front"
            (workspace / "Condensed_Image_Prompt.md").write_text("prompt: test\nnegative: bad\n", encoding="utf-8")
            render_dir = workspace / "Local_Test_Renders"
            render_dir.mkdir()
            older = render_dir / "test_old.png"
            newer = render_dir / "test_new.png"
            older.write_bytes(b"old")
            newer.write_bytes(b"new")
            os.utime(older, (100, 100))
            os.utime(newer, (200, 200))
            (render_dir / "test_new.json").write_text(
                json.dumps(
                    {
                        "image_generation": "comfyui",
                        "render_profile": "portrait-preview",
                        "checkpoint": "portrait.safetensors",
                    }
                ),
                encoding="utf-8",
            )
            client = TestClient(create_app(config_path))

            detail = client.get("/api/local-image-review/tasks/Ask_Asset_1_RENDER_TEST")

            self.assertEqual(detail.status_code, 200)
            self.assertEqual(["test_new.png", "test_old.png"], [item["name"] for item in detail.json()["images"]])
            self.assertEqual(
                {
                    "image_generation": "comfyui",
                    "render_profile": "portrait-preview",
                    "checkpoint": "portrait.safetensors",
                },
                {
                    key: detail.json()["images"][0][key]
                    for key in ("image_generation", "render_profile", "checkpoint")
                },
            )

            generated = client.post(
                "/api/local-image-review/tasks/Ask_Asset_1_RENDER_TEST/images",
                params={"count": 3},
            )

            self.assertEqual(generated.status_code, 200)
            self.assertEqual(3, len(generated.json()["queued"]))
            seeds = [item["seed"] for item in generated.json()["queued"]]
            self.assertEqual(3, len(set(seeds)))
            queued_manifests = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (root / "Queue" / "File_Proxy" / "Ask" / "zet").glob("Ask_Render_Task_*/ask_manifest.json")
            ]
            self.assertEqual(3, len(queued_manifests))
            self.assertEqual(set(seeds), {item["seed"] for item in queued_manifests})

            cleared = client.delete("/api/local-image-review/tasks/Ask_Asset_1_RENDER_TEST/images")

            self.assertEqual(cleared.status_code, 200)
            self.assertEqual(2, cleared.json()["removed_count"])
            self.assertEqual([], cleared.json()["images"])
            self.assertTrue((render_dir / "test_new.json").exists())

    def test_harvest_continues_after_malformed_answer_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root, stage="RENDER", actor="AI_AGENT")
            queue_root = root / "Queue" / "Manual_Render_Queue" / "Answer"
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
            answer_root = root / "Queue" / "File_Proxy" / "Answer" / "zet"
            harvested = answer_root / "Ask_Harvested"
            pending = answer_root / "Ask_Pending"
            harvested.mkdir(parents=True)
            pending.mkdir()
            (harvested / "answer_manifest.json").write_text("{}\n", encoding="utf-8")
            (harvested / "harvest_manifest.json").write_text("{}\n", encoding="utf-8")
            (pending / "answer_manifest.json").write_text("{}\n", encoding="utf-8")
            client = TestClient(create_app(config_path))

            controls = client.get("/api/ai-controls")
            self.assertEqual(controls.status_code, 200)
            self.assertEqual(controls.json()["harvested_answer_count"], 1)

            response = client.post("/api/ai-controls/archive-harvested")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("Archived 1 harvested", payload["message"])
            self.assertFalse(harvested.exists())
            self.assertTrue(pending.exists())
            archive_matches = list((root / "Queue" / "Zet_File_Proxy_State" / "Archive" / "Harvested").glob("*/*Ask_Harvested"))
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

    def test_head_fitment_manifest_supports_masked_local_edit_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8")
                + "\n[HeadFitment]\nRenderMode = \"masked_local\"\nMaskedLocalPreset = \"head-fitment-inpaint\"\n",
                encoding="utf-8",
            )
            body = Image.new("RGB", (64, 96), "white")
            body.paste("gray", (20, 4, 44, 80))
            body.save(root / "Assets" / "Test" / "Adult" / "body_front.png")
            head = Image.new("RGB", (64, 80), "white")
            head.paste("silver", (8, 3, 56, 78))
            head.save(root / "Characters" / "Test" / "Adult" / "Reference_Images" / "Headshots" / "head_front.png")
            client = TestClient(create_app(config_path))
            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"}).json()
            saved = client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={
                    "body_reference_path": detail["body_reference_options"][0]["path"],
                    "head_image_path": detail["headshot_options"][0]["path"],
                },
            )
            self.assertEqual(saved.status_code, 200)
            initialized = client.post(
                "/api/head-fitment-manifest/2/masked-edit/initialize",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(initialized.status_code, 200)
            self.assertFalse(initialized.json()["mask_exists"])
            self.assertEqual("pending", initialized.json()["generation_status"])
            ask_paths = list((root / "Queue" / "File_Proxy" / "Ask" / "zet").glob("Ask_Asset_2_HEAD_FITMENT_MASK_*"))
            self.assertEqual(1, len(ask_paths))
            manifest = json.loads((ask_paths[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("local_image_render", manifest["worker_type"])
            self.assertEqual("head_fitment_mask_generate", manifest["task_type"])
            self.assertEqual("comfyui", manifest["image_generation"])

            asset_detail = client.get("/api/assets/2", params={"character": "Test", "phase": "Adult"}).json()
            self.assertTrue(asset_detail["asset"]["ai_proxy_status"]["pending"])
            self.assertIn("AI PROXY PENDING", asset_detail["asset"]["pipeline_stage_display"])
            self.assertEqual("PYTHON → AI PROXY", asset_detail["asset"]["actor_display"])

            pending_detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"}).json()
            self.assertTrue(pending_detail["ai_proxy_status"]["pending"])
            self.assertFalse(pending_detail["is_manifest_editable"])
            blocked = client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={
                    "body_reference_path": detail["body_reference_options"][0]["path"],
                    "head_image_path": detail["headshot_options"][0]["path"],
                },
            )
            self.assertEqual(400, blocked.status_code)
            self.assertIn("AI proxy jobs are pending", blocked.json()["detail"])

    def test_confirming_head_fitment_mask_advances_only_that_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8")
                + "\n[HeadFitment]\nRenderMode = \"masked_local\"\nMaskedLocalPreset = \"head-fitment-inpaint\"\n",
                encoding="utf-8",
            )
            body = Image.new("RGB", (64, 96), "white")
            body.paste("gray", (20, 4, 44, 80))
            body.save(root / "Assets" / "Test" / "Adult" / "body_front.png")
            head = Image.new("RGB", (64, 80), "white")
            head.paste("silver", (8, 3, 56, 78))
            head.save(root / "Characters" / "Test" / "Adult" / "Reference_Images" / "Headshots" / "head_front.png")
            web_app = create_app(config_path)
            client = TestClient(web_app)
            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"}).json()
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={
                    "body_reference_path": detail["body_reference_options"][0]["path"],
                    "head_image_path": detail["headshot_options"][0]["path"],
                },
            )
            edit = web_app.state.zet_app.head_fitment_edit_service.initialize("Test", "Adult", 2)

            response = client.put(
                "/api/head-fitment-manifest/2/masked-edit/mask",
                params={"character": "Test", "phase": "Adult"},
                content=Path(edit["mask_path"]).read_bytes(),
                headers={"content-type": "image/png"},
            )

            self.assertEqual(200, response.status_code, response.text)
            payload = response.json()
            self.assertTrue(payload["mask"]["confirmed"])
            self.assertEqual(2, payload["asset"]["asset_id"])
            self.assertEqual("RENDER", payload["asset"]["pipeline_stage"])
            self.assertEqual("AI_AGENT", payload["asset"]["actor"])
            untouched = client.get("/api/assets/1", params={"character": "Test", "phase": "Adult"}).json()["asset"]
            self.assertEqual("LOCKED", untouched["pipeline_stage"])

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
            self.assertIn("The output is a standalone head-and-neck module.", prompt_text)
            self.assertIn("Use the Reference Body only to determine the fitted neck’s natural width, axis, and cut position.", prompt_text)
            self.assertIn("Only the upper neck beneath the jaw is visible.", prompt_text)
            self.assertIn("The output fails if any shoulder slope, trapezius, collarbone, chest, torso, or body geometry is visible", prompt_text)
            self.assertIn("extend below the neck cut into transparent space", prompt_text)
            self.assertIn("Use the Reference Body only to match the fitted neck’s width, axis, and cut position", prompt_text)
            self.assertIn("The Character Head source controls the head pose, face, hair, expression, and identity.", prompt_text)
            self.assertIn("Render the Character Head and fitted neck from a direct front view", prompt_text)
            self.assertIn("SOURCE RENDERING LOCK", prompt_text)
            self.assertNotIn("Test character general facts.", prompt_text)
            self.assertNotIn("Avoid head-fitment drift.", prompt_text)
            self.assertNotIn("Unrequested left-profile head view.", prompt_text)
            self.assertNotIn("Forbidden front body description.", prompt_text)
            ask_dirs = list((root / "Queue" / "Manual_Render_Queue" / "Ask").iterdir())
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

    def test_masked_head_fitment_advance_initializes_mask_and_reports_waiting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_head_fitment_fixture(root)
            with config_path.open("a", encoding="utf-8") as handle:
                handle.write("\n[HeadFitment]\nRenderMode = \"masked_local\"\n")
            body = Image.new("RGB", (64, 96), (210, 210, 210))
            body_draw = ImageDraw.Draw(body)
            body_draw.ellipse((18, 3, 46, 35), fill=(110, 100, 90))
            body_draw.polygon([(27, 30), (37, 30), (43, 70), (21, 70)], fill=(110, 100, 90))
            body.save(root / "Assets" / "Test" / "Adult" / "body_front.png")
            head = Image.new("RGB", (64, 80), (220, 210, 190))
            head_draw = ImageDraw.Draw(head)
            head_draw.ellipse((8, 3, 56, 60), fill=(90, 70, 55))
            head_draw.rectangle((26, 52, 38, 78), fill=(130, 95, 75))
            head.save(root / "Characters" / "Test" / "Adult" / "Reference_Images" / "Headshots" / "head_front.png")
            client = TestClient(create_app(config_path))
            detail = client.get("/api/head-fitment-manifest/2", params={"character": "Test", "phase": "Adult"}).json()
            client.post(
                "/api/head-fitment-manifest/2/references",
                params={"character": "Test", "phase": "Adult"},
                json={
                    "body_reference_path": detail["body_reference_options"][0]["path"],
                    "headshot_path": detail["headshot_options"][0]["path"],
                },
            )

            response = client.post(
                "/api/assets/advance-all",
                params={"character": "Test", "phase": "Adult"},
                json={"asset_ids": [2]},
            )

            self.assertEqual(200, response.status_code)
            self.assertEqual("WAITING", response.json()["results"][0]["status"], response.json())
            self.assertIn("waiting for action 1", response.json()["message"])
            context = client.get(
                "/api/head-fitment-manifest/2",
                params={"character": "Test", "phase": "Adult"},
            ).json()
            self.assertEqual("MANIFEST", context["asset"]["pipeline_stage"])
            self.assertFalse(context["masked_edit"]["mask_exists"])
            self.assertFalse(context["masked_edit"]["confirmed"])
            self.assertEqual("pending", context["masked_edit"]["generation_status"])
            ask_paths = list((root / "Queue" / "File_Proxy" / "Ask" / "zet").glob("Ask_Asset_2_HEAD_FITMENT_MASK_*"))
            self.assertEqual(1, len(ask_paths))
            ask_manifest = json.loads((ask_paths[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("local_image_render", ask_manifest["worker_type"])
            self.assertEqual("head_fitment_mask_generate", ask_manifest["task_type"])
            self.assertEqual(["head_image", "body_reference"], [item["role"] for item in ask_manifest["reference_files"]])
            for reference in ask_manifest["reference_files"]:
                self.assertTrue((ask_paths[0] / reference["path"]).is_file())

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
            self.assertEqual(manifest_asset["pipeline_stage"], "RENDER", manifest_asset)
            self.assertEqual(manifest_asset["actor"], "AI_AGENT")
            self.assertEqual(manifest_asset["ai_state"], "ASKED")
            self.assertEqual(
                [item["role"] for item in manifest_asset["reference_files"]],
                ["body_reference", "head_fitment"],
            )
            self.assertEqual("MATCHED_STYLE", manifest_asset["assembly_style_mode"])
            for reference in manifest_asset["reference_files"]:
                self.assertEqual("Test", reference["character"])
                self.assertEqual("Adult", reference["phase"])

            prompt_path = root / "Pipelines" / "Test" / "Adult" / "Character-Assembly" / "Front" / "Front" / "Asset_3" / "Final_Image_Prompt.md"
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("# Render Task", prompt_text)
            self.assertIn("Replace the mannequin head and placeholder neck", prompt_text)
            self.assertIn("The Reference Body and Character Head already use the same direct front view.", prompt_text)
            self.assertIn("Assembly style mode: MATCHED_STYLE", prompt_text)
            self.assertIn("selected character-phase identity", prompt_text)
            self.assertIn("Adjust only local strand placement and overlap", prompt_text)
            self.assertIn("adaptive assembly region rather than a rigid source boundary", prompt_text)
            self.assertIn("Do not invent or expose an ear that is naturally occluded", prompt_text)
            self.assertNotIn("Re-render the Character Head", prompt_text)
            self.assertNotIn("{{", prompt_text)
            source_map = json.loads((prompt_path.parent / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
            source_kinds = {fragment["source_kind"] for fragment in source_map["fragments"]}
            self.assertIn("static_prompt_template", source_kinds)
            self.assertIn("config_view_instruction", source_kinds)
            self.assertIn("asset_metadata", source_kinds)

            dependency_manifest = json.loads((prompt_path.parent / "dependency_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("MATCHED_STYLE", dependency_manifest["assembly_style_mode"])
            image_review = (prompt_path.parent / "Image_Review.md").read_text(encoding="utf-8")
            self.assertIn("fitment clothing, exposed skin, background, and requested view", image_review)
            self.assertIn("identity, face, age phase, species", image_review)
            self.assertIn("no occluded ear was invented or exposed", image_review)
            self.assertIn("skin transition naturally without broad recoloring", image_review)
            self.assertNotIn("Costume and equipment match", image_review)
            self.assertNotIn("No mannequin, fitment shell, tank top, or compression shorts remain", image_review)

            ask_dirs = list((root / "Queue" / "Manual_Render_Queue" / "Ask").iterdir())
            self.assertEqual(len(ask_dirs), 1)
            ask_manifest = json.loads((ask_dirs[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(ask_manifest["worker_type"], "manual_chatgpt_render")
            self.assertEqual(ask_manifest["prompt_file"], "Final_Image_Prompt.md")
            self.assertEqual([item["role"] for item in ask_manifest["reference_files"]], ["body_reference", "head_fitment"])

    def test_story_management_api_renames_reorders_and_moves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    "[BaseFolders]\n",
                    f"[BaseFolders]\nBaseLibraryPath = \"{root.as_posix()}\"\n",
                ),
                encoding="utf-8",
            )
            for story_slug in ("Alpha", "Beta"):
                folder = root / "Stories" / story_slug
                folder.mkdir(parents=True)
                (folder / f"{story_slug}.md").write_text(f"Title: `[{story_slug}]`\n", encoding="utf-8")
                (folder / f"{story_slug}.story.json").write_text(
                    json.dumps({
                        "schema_version": 1,
                        "file_kind": "story_settings",
                        "story": {"slug": story_slug, "title": story_slug},
                        "scene_index": ["Opening"] if story_slug == "Alpha" else [],
                        "metadata": {},
                    }),
                    encoding="utf-8",
                )
            alpha = root / "Stories" / "Alpha"
            (alpha / "Opening.md").write_text("Scene: `[Opening]`\n", encoding="utf-8")
            (alpha / "Opening.scene.json").write_text(
                json.dumps({"schema_version": 3, "file_kind": "scene", "scene": {"slug": "Opening", "name": "Opening"}}),
                encoding="utf-8",
            )
            client = TestClient(create_app(config_path))

            response = client.put("/api/stories/order", json={"slugs": ["Beta", "Alpha"]})
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual(["Beta", "Alpha"], [item["slug"] for item in response.json()["stories"]])

            response = client.patch("/api/stories/Alpha", json={"title": "Renamed Alpha"})
            self.assertEqual(200, response.status_code)
            self.assertEqual("Renamed Alpha", response.json()["document"]["story"]["title"])

            response = client.put("/api/stories/Alpha/scenes/order", json={"slugs": ["Opening"]})
            self.assertEqual(200, response.status_code)
            self.assertEqual(["Opening"], [item["slug"] for item in response.json()["scenes"]])

            response = client.patch("/api/stories/Alpha/scenes/Opening", json={"title": "New Opening"})
            self.assertEqual(200, response.status_code)
            self.assertEqual("New Opening", response.json()["document"]["scene"]["title"])

            response = client.post(
                "/api/stories/Alpha/scenes/Opening/move",
                json={"target_story_slug": "Beta"},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual([], response.json()["source_scenes"])
            self.assertEqual(["Opening"], [item["slug"] for item in response.json()["target_scenes"]])


if __name__ == "__main__":
    unittest.main()
