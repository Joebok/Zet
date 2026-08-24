from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from AI_Manager import local_image_proxy_worker
from zet.render_console.queue import RenderConsoleQueue
from zet.app import ZetApp
from zet.services.config_service import Config


class RenderConsoleQueueTests(unittest.TestCase):

    def test_write_answer_image_defers_story_target_output_to_harvester(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Story_Test"
            target_path = root / "Stories" / "FirstDay" / "At-the-Arch.png"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text(
                json.dumps(
                    {
                        "ask_id": "Ask_Story_Test",
                        "asset_id": None,
                        "worker_type": "manual_chatgpt_render",
                        "prompt_file": "Final_Image_Prompt.md",
                        "expected_output": "At-the-Arch.png",
                        "story_slug": "FirstDay",
                        "scene_slug": "At-the-Arch",
                        "target_output_file": str(target_path),
                    }
                ),
                encoding="utf-8",
            )
            (ask_path / "Final_Image_Prompt.md").write_text("prompt\n", encoding="utf-8")
            queue = RenderConsoleQueue(
                Config(
                    base_library_path=str(root),
                    base_character_path=str(root / "Characters"),
                    base_asset_path=str(root / "Assets"),
                    base_pipeline_path=str(root / "Pipelines"),
                    base_ai_queue_path=str(root / "Queue"),
                )
            )
            task = queue.get_task("Ask_Story_Test")
            self.assertEqual(task.to_dict()["display_label"], "FirstDay / At-the-Arch")

            queue.write_answer_image(task, b"image bytes", "image/png")

            self.assertFalse(target_path.exists())
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Story_Test"
            self.assertEqual(b"image bytes", (answer_path / "At-the-Arch.png").read_bytes())
            self.assertEqual(b"image bytes", (root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Story_Test" / "At-the-Arch.png").read_bytes())

    def test_harvester_applies_story_target_output_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Story_Test"
            target_path = root / "Stories" / "FirstDay" / "At-the-Arch.png"
            answer_path.mkdir(parents=True)
            (answer_path / "ask_manifest.json").write_text(
                json.dumps(
                    {
                        "ask_id": "Ask_Story_Test",
                        "asset_id": None,
                        "character": "",
                        "phase": "",
                        "task_type": "render",
                        "target_output_file": str(target_path),
                    }
                ),
                encoding="utf-8",
            )
            (answer_path / "answer_manifest.json").write_text(
                json.dumps(
                    {
                        "ask_id": "Ask_Story_Test",
                        "asset_id": None,
                        "ollama_attempt_id": "story-render",
                        "worker_id": "manual",
                        "status": "SUCCESS",
                        "expected_output": "At-the-Arch.png",
                    }
                ),
                encoding="utf-8",
            )
            (answer_path / "At-the-Arch.png").write_bytes(b"story image")
            (answer_path / "Final_Image_Prompt.md").write_text("story prompt\n", encoding="utf-8")
            (answer_path / "Stable_Matrix_API_Call.json").write_text('{"prompt": "story"}\n', encoding="utf-8")
            config_path = root / "config.toml"
            config_path.write_text(
                f"""
[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
""".lstrip(),
                encoding="utf-8",
            )

            results = ZetApp.from_config(config_path).harvest_ai_answers()

            self.assertEqual("RENDER_APPLIED", results[0].status)
            self.assertEqual(b"story image", target_path.read_bytes())
            self.assertEqual("story prompt\n", (target_path.parent / "Final_Image_Prompt.md").read_text(encoding="utf-8"))
            self.assertEqual(
                '{"prompt": "story"}',
                (target_path.parent / "Stable_Matrix_API_Call.json").read_text(encoding="utf-8").strip(),
            )

    def test_stage_render_task_local_render_ask_targets_local_test_renders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.toml"
            config_path.write_text(
                f"""
[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
""".lstrip(),
                encoding="utf-8",
            )
            workspace = root / "Stories" / "FirstDay"
            workspace.mkdir(parents=True)
            prompt_path = workspace / "Condensed_Image_Prompt.md"
            prompt_path.write_text("condensed prompt\n", encoding="utf-8")
            app = ZetApp.from_config(config_path)

            ask_path = app.stage_render_task_local_render_ask(
                {"ask_id": "Ask_Story_Test", "worker_type": "manual_chatgpt_render", "reference_files": [{"path": "ref.png"}], "aspect_ratio": "16:9"},
                prompt_path,
                workspace,
                checkpoint="override-model.safetensors",
            )

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            job = json.loads((ask_path / "job.json").read_text(encoding="utf-8"))
            self.assertEqual("local_image_render", manifest["worker_type"])
            self.assertEqual("image:stable_matrix:override-model.safetensors", job["resource_key"])
            self.assertEqual("local_test_render", manifest["task_type"])
            self.assertEqual("Ask_Story_Test", manifest["source_ask_id"])
            self.assertEqual("override-model.safetensors", manifest["checkpoint"])
            self.assertEqual("16:9", manifest["aspect_ratio"])
            route = app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.load_route(ask_path.name)
            self.assertEqual(str((workspace / "Local_Test_Renders").resolve()), route["target_output_dir"])
            self.assertEqual("condensed prompt\n", (ask_path / "Condensed_Image_Prompt.md").read_text(encoding="utf-8"))
            answer_path = root / "Queue" / "File_Proxy" / "Answer" / "zet" / ask_path.name
            answer_path.mkdir(parents=True)
            shutil.copy2(ask_path / "job.json", answer_path / "job.json")
            (answer_path / "ask_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (answer_path / "answer_manifest.json").write_text(
                json.dumps(
                    {
                        "ask_id": manifest["ask_id"],
                        "asset_id": None,
                        "ollama_attempt_id": manifest["ollama_attempt_id"],
                        "worker_id": "local",
                        "status": "SUCCESS",
                        "expected_output": manifest["expected_output"],
                    }
                ),
                encoding="utf-8",
            )
            (answer_path / manifest["expected_output"]).write_bytes(b"local image")
            (answer_path / "Stable_Matrix_API_Call.json").write_text('{"prompt": "local"}\n', encoding="utf-8")
            (answer_path / "LOCAL_RENDER_METADATA.json").write_text(
                json.dumps(
                    {
                        "image_generation": "stable_matrix",
                        "render_profile": "body-reference-preview",
                        "checkpoint": "model.safetensors",
                    }
                ),
                encoding="utf-8",
            )
            client = app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
            (answer_path / "proxy_result.json").write_text(
                json.dumps(
                    {
                        "status": "SUCCEEDED",
                        "output_files": client._file_inventory(answer_path),
                    }
                ),
                encoding="utf-8",
            )

            results = app.harvest_ai_answers()

            self.assertEqual("LOCAL_TEST_RENDER_APPLIED", results[0].status)
            self.assertEqual(b"local image", (workspace / "Local_Test_Renders" / manifest["expected_output"]).read_bytes())
            self.assertEqual(
                '{"prompt": "local"}',
                (workspace / "Local_Test_Renders" / "Stable_Matrix_API_Call.json").read_text(encoding="utf-8").strip(),
            )
            metadata = json.loads(
                (workspace / "Local_Test_Renders" / Path(manifest["expected_output"]).with_suffix(".json")).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("stable_matrix", metadata["image_generation"])
            self.assertEqual("body-reference-preview", metadata["render_profile"])
            self.assertEqual("model.safetensors", metadata["checkpoint"])



    def test_stage_scene_local_render_ask_adds_forge_layout_for_multiple_subjects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.toml"
            config_path.write_text(
                f"""
[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"

[LocalRender]
LayoutBackend = "forge_couple_basic"
""".lstrip(),
                encoding="utf-8",
            )
            workspace = root / "Stories" / "FirstDay"
            workspace.mkdir(parents=True)
            (workspace / "Local_Render_Prompt.md").write_text("prompt: flat\nnegative: bad\n", encoding="utf-8")
            (workspace / "Local_Render_Brief.json").write_text(
                json.dumps(
                    {
                        "subject_count": 2,
                        "canvas": {"aspect_ratio": "16:9"},
                        "forge_couple_basic": {
                            "direction": "Horizontal",
                            "background": "First Line",
                            "background_weight": 0.5,
                            "prompt_lines": ["global", "left", "right"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            app = ZetApp.from_config(config_path)

            ask_path = app.stage_scene_local_render_ask({"ask_id": "Ask_Scene_Test"}, workspace)

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("16:9", manifest["aspect_ratio"])
            self.assertEqual("Local_Render_Prompt.md", manifest["prompt_file"])
            self.assertEqual("forge_couple_basic", manifest["render_layout"]["backend"])
            self.assertEqual(["global", "left", "right"], manifest["render_layout"]["prompt_lines"])



    def test_stage_scene_comfyui_render_ask_copies_canonical_ir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.toml"
            config_path.write_text(
                f"""
[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"

[LocalRender]
Backend = "comfyui"

[ComfyUI]
Profile = "comfyui-core-preview"
Checkpoint = "model.safetensors"
""".lstrip(),
                encoding="utf-8",
            )
            workspace = root / "Stories" / "FirstDay"
            workspace.mkdir(parents=True)
            (workspace / "Local_Render_Prompt.md").write_text("prompt: scene\nnegative: bad\n", encoding="utf-8")
            (workspace / "Local_Render_Brief.json").write_text(
                json.dumps({"canvas": {"aspect_ratio": "16:9"}}),
                encoding="utf-8",
            )
            ir_text = json.dumps({"schema_version": 4, "scene": {"slug": "scene"}})
            (workspace / "Scene_Render_IR.json").write_text(ir_text, encoding="utf-8")
            app = ZetApp.from_config(config_path)

            ask_path = app.stage_scene_local_render_ask({"ask_id": "Ask_Scene_Comfy"}, workspace)

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("comfyui-core-preview", manifest["render_preset"])
            self.assertEqual("core_txt2img_scene_preview", manifest["workflow_kind"])
            self.assertEqual("Scene_Render_IR.json", manifest["scene_render_ir_file"])
            self.assertNotIn("render_layout", manifest)
            self.assertEqual(
                json.loads(ir_text),
                json.loads((ask_path / "Scene_Render_IR.json").read_text(encoding="utf-8")),
            )






if __name__ == "__main__":
    unittest.main()
