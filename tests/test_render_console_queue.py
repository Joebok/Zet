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
    def test_stage_scene_render_clears_stale_scene_queue_items(self) -> None:
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
            story_dir = root / "Stories" / "First-Day"
            story_dir.mkdir(parents=True)
            (story_dir / "First-Day.md").write_text(
                """
Title: First Day
Canonical Art Style: watercolor

<!-- ZET:BEGIN STORY_TITLE -->
First Day
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
watercolor
<!-- ZET:END CANONICAL_ART_STYLE -->
""".lstrip(),
                encoding="utf-8",
            )
            (story_dir / "At-the-Arch.md").write_text(
                """
<!-- ZET:BEGIN SCENE_NAME -->
At the Arch
<!-- ZET:END SCENE_NAME -->

<!-- ZET:BEGIN SCENE_DESCRIPTION -->
An arch.
<!-- ZET:END SCENE_DESCRIPTION -->
""".lstrip(),
                encoding="utf-8",
            )
            (story_dir / "At-the-Arch.scene.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "setup": {
                            "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                            "environment": {"location": "academy archway"},
                        },
                        "scene_elements": [],
                        "placements": [],
                    }
                ),
                encoding="utf-8",
            )
            app = ZetApp.from_config(config_path)
            app.story_service.save_story_settings(
                story_dir / "First-Day.story.json",
                app.story_service.create_default_story_settings(story_dir / "First-Day.md"),
            )
            first = app.stage_scene_render("First-Day", "At-the-Arch")
            first_ask = Path(first.ask_path)
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / first_ask.name
            shutil.copytree(first_ask, answer_path)

            second = app.stage_scene_render("First-Day", "At-the-Arch")

            self.assertFalse(first_ask.exists())
            self.assertFalse(answer_path.exists())
            self.assertTrue(Path(second.ask_path).exists())

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
            self.assertEqual("local_image_render", manifest["worker_type"])
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

    def test_local_image_worker_omits_unsupported_render_kwargs(self) -> None:
        def render_image(*, project_root, final_prompt_path, job_output_dir, prompt_review_path=None, preset_name=""):
            return None

        with patch.object(local_image_proxy_worker, "render_image", render_image):
            kwargs = local_image_proxy_worker.render_image_kwargs(
                {"reference_files": [{"path": "ref.png"}]},
                Path("prompt.md"),
                Path("job"),
                "preset",
            )

        self.assertNotIn("reference_files", kwargs)

    def test_parallel_local_render_asks_keep_distinct_seeds(self) -> None:
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
            prompt_path.write_text("prompt: scene\nnegative: bad\n", encoding="utf-8")
            app = ZetApp.from_config(config_path)
            manifest = {"ask_id": "Ask_Story_Test", "worker_type": "manual_chatgpt_render"}

            first = app.stage_render_task_local_render_ask(
                manifest,
                prompt_path,
                workspace,
                allow_parallel=True,
                seed=101,
            )
            second = app.stage_render_task_local_render_ask(
                manifest,
                prompt_path,
                workspace,
                allow_parallel=True,
                seed=202,
            )

            self.assertNotEqual(first, second)
            first_manifest = json.loads((first / "ask_manifest.json").read_text(encoding="utf-8"))
            second_manifest = json.loads((second / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(101, first_manifest["seed"])
            self.assertEqual(202, second_manifest["seed"])

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

    def test_stage_scene_local_render_ask_omits_forge_layout_for_single_subject(self) -> None:
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
            (workspace / "Local_Render_Prompt.md").write_text("prompt: one subject\nnegative: bad\n", encoding="utf-8")
            (workspace / "Local_Render_Brief.json").write_text(
                json.dumps({"subject_count": 1, "forge_couple_basic": {"prompt_lines": ["global", "subject"]}}),
                encoding="utf-8",
            )
            app = ZetApp.from_config(config_path)

            ask_path = app.stage_scene_local_render_ask({"ask_id": "Ask_Scene_One"}, workspace)

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("render_layout", manifest)

    def test_stage_scene_local_render_ask_omits_forge_layout_when_disabled(self) -> None:
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
LayoutBackend = "plain_txt2img"
""".lstrip(),
                encoding="utf-8",
            )
            workspace = root / "Stories" / "FirstDay"
            workspace.mkdir(parents=True)
            (workspace / "Local_Render_Prompt.md").write_text("prompt: two subjects\nnegative: bad\n", encoding="utf-8")
            (workspace / "Local_Render_Brief.json").write_text(
                json.dumps({"subject_count": 2, "forge_couple_basic": {"prompt_lines": ["global", "left", "right"]}}),
                encoding="utf-8",
            )
            app = ZetApp.from_config(config_path)

            ask_path = app.stage_scene_local_render_ask({"ask_id": "Ask_Scene_Plain"}, workspace)

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("render_layout", manifest)

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
            ir_text = json.dumps({"schema_version": 3, "scene": {"slug": "scene"}})
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

    def test_local_image_worker_forwards_render_layout_when_supported(self) -> None:
        def render_image(*, project_root, final_prompt_path, job_output_dir, prompt_review_path=None, preset_name="", render_layout=None):
            return None

        with patch.object(local_image_proxy_worker, "render_image", render_image):
            kwargs = local_image_proxy_worker.render_image_kwargs(
                {"render_layout": {"backend": "forge_couple_basic"}},
                Path("prompt.md"),
                Path("job"),
                "preset",
            )

        self.assertEqual({"backend": "forge_couple_basic"}, kwargs["render_layout"])

    def test_local_image_worker_forwards_scene_render_ir_when_supported(self) -> None:
        def render_image(
            *,
            project_root,
            final_prompt_path,
            job_output_dir,
            prompt_review_path=None,
            preset_name="",
            scene_render_ir_path=None,
        ):
            return None

        with patch.object(local_image_proxy_worker, "render_image", render_image):
            kwargs = local_image_proxy_worker.render_image_kwargs(
                {"scene_render_ir_file": "Scene_Render_IR.json"},
                Path("prompt.md"),
                Path("job"),
                "comfyui-core-preview",
            )

        self.assertEqual(Path("job") / "Scene_Render_IR.json", kwargs["scene_render_ir_path"])

    def test_local_image_worker_forwards_fixed_seed_when_supported(self) -> None:
        def render_image(
            *,
            project_root,
            final_prompt_path,
            job_output_dir,
            prompt_review_path=None,
            preset_name="",
            seed=None,
        ):
            return None

        with patch.object(local_image_proxy_worker, "render_image", render_image):
            kwargs = local_image_proxy_worker.render_image_kwargs(
                {"seed": 12345},
                Path("prompt.md"),
                Path("job"),
                "preset",
            )

        self.assertEqual(12345, kwargs["seed"])

    def test_harvester_archives_already_harvested_answer(self) -> None:
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
            app = ZetApp.from_config(config_path)

            self.assertEqual("RENDER_APPLIED", app.harvest_ai_answers()[0].status)
            results = app.harvest_ai_answers()

            self.assertEqual([], results)
            self.assertFalse(answer_path.exists())
            archive_matches = list((root / "Queue" / "Zet_File_Proxy_State" / "Archive" / "Harvested").glob("*/*Ask_Story_Test"))
            self.assertEqual(1, len(archive_matches))


if __name__ == "__main__":
    unittest.main()
