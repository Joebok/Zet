from pathlib import Path
import json
import tempfile
import unittest

from zet.render_console.queue import RenderConsoleQueue
from zet.app import ZetApp
from zet.services.config_service import Config


class RenderConsoleQueueTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
