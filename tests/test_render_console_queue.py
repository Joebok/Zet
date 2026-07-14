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
            app = ZetApp.from_config(config_path)
            first = app.stage_scene_render("First-Day", "At-the-Arch")
            first_ask = Path(first.ask_path)
            answer_path = root / "Queue" / "Ollama_Proxy" / "Answer" / first_ask.name
            claimed_path = root / "Queue" / "Ollama_Proxy" / "Claimed" / "worker" / first_ask.name
            claim_path = root / "Queue" / "Ollama_Proxy" / "Claims" / f"{first_ask.name}.claim.json"
            shutil.copytree(first_ask, answer_path)
            shutil.copytree(first_ask, claimed_path)
            claim_path.parent.mkdir(parents=True)
            claim_path.write_text("{}", encoding="utf-8")

            second = app.stage_scene_render("First-Day", "At-the-Arch")

            self.assertFalse(first_ask.exists())
            self.assertFalse(answer_path.exists())
            self.assertFalse(claimed_path.exists())
            self.assertFalse(claim_path.exists())
            self.assertTrue(Path(second.ask_path).exists())

    def test_write_answer_image_copies_story_target_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ask_path = root / "Queue" / "Ollama_Proxy" / "Ask" / "Ask_Story_Test"
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

            queue.write_answer_image(task, b"image bytes", "image/png")

            self.assertEqual(b"image bytes", target_path.read_bytes())
            self.assertEqual(b"image bytes", (root / "Queue" / "Ollama_Proxy" / "Answer" / "Ask_Story_Test" / "At-the-Arch.png").read_bytes())

    def test_harvester_applies_story_target_output_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            answer_path = root / "Queue" / "Ollama_Proxy" / "Answer" / "Ask_Story_Test"
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
            )

            manifest = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("local_image_render", manifest["worker_type"])
            self.assertEqual("local_test_render", manifest["task_type"])
            self.assertEqual("Ask_Story_Test", manifest["source_ask_id"])
            self.assertEqual("16:9", manifest["aspect_ratio"])
            self.assertEqual(str((workspace / "Local_Test_Renders").resolve()), manifest["target_output_dir"])
            self.assertEqual("condensed prompt\n", (ask_path / "Condensed_Image_Prompt.md").read_text(encoding="utf-8"))
            answer_path = root / "Queue" / "Ollama_Proxy" / "Answer" / ask_path.name
            answer_path.mkdir(parents=True)
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

            results = app.harvest_ai_answers()

            self.assertEqual("LOCAL_TEST_RENDER_APPLIED", results[0].status)
            self.assertEqual(b"local image", (workspace / "Local_Test_Renders" / manifest["expected_output"]).read_bytes())
            self.assertEqual(
                '{"prompt": "local"}',
                (workspace / "Local_Test_Renders" / "Stable_Matrix_API_Call.json").read_text(encoding="utf-8").strip(),
            )

    def test_local_image_worker_omits_unsupported_render_kwargs(self) -> None:
        def render_image(*, project_root, final_prompt_path, job_output_dir, prompt_review_path=None, preset_name=""):
            return None

        with patch.object(local_image_proxy_worker, "render_image", render_image):
            kwargs = local_image_proxy_worker.render_image_kwargs(
                {"reference_files": [{"path": "ref.png"}], "governing_template_path": "template.md"},
                Path("prompt.md"),
                Path("job"),
                "preset",
            )

        self.assertNotIn("reference_files", kwargs)
        self.assertNotIn("governing_template_path", kwargs)

    def test_harvester_archives_already_harvested_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            answer_path = root / "Queue" / "Ollama_Proxy" / "Answer" / "Ask_Story_Test"
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
            archive_matches = list((root / "Queue" / "Ollama_Proxy" / "Archive" / "Harvested").glob("*/*Ask_Story_Test"))
            self.assertEqual(1, len(archive_matches))


if __name__ == "__main__":
    unittest.main()
