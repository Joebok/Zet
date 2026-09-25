from pathlib import Path
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from AI_Manager import local_image_proxy_worker
from zet.render_console.queue import RenderConsoleQueue
from zet.app import ZetApp
from zet.services.config_service import Config
from zet.services.manual_render_submission_service import ManualRenderSubmissionService
from tests.support.image_fixture import png_bytes


class RenderConsoleQueueTests(unittest.TestCase):

    def test_answer_publication_retries_transient_directory_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Test"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text(json.dumps({
                "ask_id": "Ask_Test",
                "worker_type": "manual_chatgpt_render",
                "prompt_file": "Final_Image_Prompt.md",
                "expected_output": "image.png",
            }), encoding="utf-8")
            (ask_path / "Final_Image_Prompt.md").write_text("prompt\n", encoding="utf-8")
            queue = RenderConsoleQueue(Config(
                base_library_path=str(root),
                base_character_path=str(root / "Characters"),
                base_asset_path=str(root / "Assets"),
                base_pipeline_path=str(root / "Pipelines"),
                base_ai_queue_path=str(root / "Queue"),
            ))

            real_replace = os.replace
            directory_attempts = 0

            def transient_directory_lock(source, destination):
                nonlocal directory_attempts
                if Path(source).is_dir():
                    directory_attempts += 1
                    if directory_attempts == 1:
                        raise PermissionError(13, "file is being used by another process")
                return real_replace(source, destination)

            with patch("zet.services.atomic_file_service.os.replace", side_effect=transient_directory_lock):
                answer_path = queue.write_answer_image(queue.get_task("Ask_Test"), png_bytes(), "image/png")

            self.assertEqual(2, directory_attempts)
            self.assertTrue((answer_path / "image.png").is_file())

    def test_manual_submission_validates_and_persists_refinement_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Test"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text(json.dumps({
                "ask_id": "Ask_Test",
                "worker_type": "manual_chatgpt_render",
                "prompt_file": "Final_Image_Prompt.md",
                "expected_output": "image.png",
            }), encoding="utf-8")
            (ask_path / "Final_Image_Prompt.md").write_text("prompt\n", encoding="utf-8")
            queue = RenderConsoleQueue(Config(
                base_library_path=str(root),
                base_character_path=str(root / "Characters"),
                base_asset_path=str(root / "Assets"),
                base_pipeline_path=str(root / "Pipelines"),
                base_ai_queue_path=str(root / "Queue"),
            ))
            service = ManualRenderSubmissionService(queue)
            task = service.get_task("Ask_Test")

            with self.assertRaisesRegex(ValueError, "at least 1"):
                service.submit_image(task, png_bytes(), refinement_required=True)
            with self.assertRaisesRegex(ValueError, "require the refinement checkbox"):
                service.submit_image(task, png_bytes(), refinement_note="changed pose")

            answer_path = service.submit_image(
                task,
                png_bytes(),
                "image/png",
                refinement_required=True,
                additional_image_generations=2,
                refinement_note="Changed pose.",
            )
            manifest = json.loads((answer_path / "answer_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({
                "schema_version": 1,
                "required": True,
                "additional_image_generations": 2,
                "note": "Changed pose.",
            }, manifest["chatgpt_refinement"])

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

            queue.write_answer_image(task, png_bytes(), "image/png")

            self.assertFalse(target_path.exists())
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Story_Test"
            self.assertEqual(png_bytes(), (answer_path / "At-the-Arch.png").read_bytes())
            self.assertEqual([], queue.list_tasks())
            self.assertIsNotNone(queue.get_task(task.ask_id))
            self.assertEqual(answer_path, queue.write_answer_image(task, png_bytes(), "image/png"))
            with self.assertRaises(FileExistsError):
                queue.write_answer_image(task, png_bytes("blue"), "image/png")
            with self.assertRaises(ValueError):
                queue.write_answer_image(task, b"image bytes", "image/png")

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

            source_ask_id = "Ask_Story_FirstDay_Chapter-07-Nice-Hair_RENDER_20260921_132624_987737_" + "a" * 32
            ask_path = app.stage_render_task_local_render_ask(
                {"ask_id": source_ask_id, "worker_type": "manual_chatgpt_render", "reference_files": [{"path": "ref.png"}], "aspect_ratio": "16:9"},
                prompt_path,
                workspace,
                checkpoint="override-model.safetensors",
            )

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            job = json.loads((ask_path / "job.json").read_text(encoding="utf-8"))
            self.assertEqual("local_image_render", manifest["worker_type"])
            self.assertEqual("image:stable_matrix:override-model.safetensors", job["resource_key"])
            self.assertEqual("local_test_render", manifest["task_type"])
            self.assertEqual(source_ask_id, manifest["source_ask_id"])
            self.assertLessEqual(len(job["job_id"]), 128)
            self.assertEqual(ask_path.name, job["job_id"])
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

    def test_qwen_scene_ask_snapshots_edited_prompt_without_local_prompt_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Config").mkdir()
            (root / "Config" / "Local_Render_Presets.json").write_text(json.dumps({
                "comfyui-ipadapter-preview": {"backend": "comfyui", "workflow_kind": "ipadapter_scene_preview"},
                "comfyui-qwen-image-2-1-scene": {
                    "backend": "comfyui", "workflow_kind": "qwen_image_21_scene_preview",
                    "diffusion_model": "qwen.safetensors",
                    "text_encoder": "encoder.safetensors", "vae": "vae.safetensors",
                },
            }), encoding="utf-8")
            config_path = root / "config.toml"
            config_path.write_text(f'''
[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"

[LocalRender]
Backend = "comfyui"

[ComfyUI]
Profile = "comfyui-ipadapter-preview"
Checkpoint = "sdxl.safetensors"
'''.lstrip(), encoding="utf-8")
            workspace = root / "Stories" / "FirstDay"
            workspace.mkdir(parents=True)
            (workspace / "Final_Image_Prompt.md").write_text("manual prompt\n", encoding="utf-8")
            (workspace / "Scene_Render_IR.json").write_text(json.dumps({
                "canvas": {"aspect_ratio": "4:5"}, "scene": {"story_beat": "Tsaeytte enters the arch"},
                "image_inputs": [],
            }), encoding="utf-8")
            app = ZetApp.from_config(config_path)
            with patch("zet.services.ai_proxy_service.LocalRenderBackendService.comfyui_options",
                       side_effect=AssertionError("Queue staging contacted ComfyUI")), patch(
                           "zet.services.ai_proxy_service.validate_scene_render_ir"):
                ask_path = app.stage_scene_local_render_ask(
                    {"ask_id": "Ask_Qwen_Scene"}, workspace, qwen_prompt_override="Edited natural-language scene.",
                    render_profile="comfyui-qwen-image-2-1-scene")
                revised_path = app.stage_scene_local_render_ask(
                    {"ask_id": "Ask_Qwen_Scene"}, workspace, qwen_prompt_override="A different scene edit.",
                    render_profile="comfyui-qwen-image-2-1-scene")

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("Qwen_Image_2_1_Prompt.md", manifest["prompt_file"])
            self.assertEqual("comfyui-qwen-image-2-1-scene", manifest["render_preset"])
            self.assertEqual("qwen.safetensors", manifest["checkpoint"])
            self.assertEqual("qwen_image_21_scene_preview", manifest["workflow_kind"])
            self.assertEqual("Edited natural-language scene.",
                             (ask_path / manifest["prompt_file"]).read_text(encoding="utf-8"))
            self.assertNotEqual(ask_path, revised_path)
            self.assertEqual("A different scene edit.",
                             (revised_path / manifest["prompt_file"]).read_text(encoding="utf-8"))
            self.assertFalse((workspace / "Qwen_Image_2_1_Prompt.md").exists())
            self.assertEqual("manual prompt\n", (workspace / "Final_Image_Prompt.md").read_text(encoding="utf-8"))






if __name__ == "__main__":
    unittest.main()
