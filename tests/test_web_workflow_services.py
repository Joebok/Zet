import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from zet.services.character_phase_discovery_service import CharacterPhaseDiscoveryService
from zet.services.manual_render_submission_service import ManualRenderSubmissionService
from zet.services.source_editor_service import SourceEditorService


class WebWorkflowServiceTests(unittest.TestCase):

    def test_source_editor_updates_json_field_and_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.json"
            source.write_text('{"nested": {"value": "old"}}\n', encoding="utf-8")
            app = SimpleNamespace(
                config=SimpleNamespace(base_library_path=str(root)),
                path_service=SimpleNamespace(resolve_path=lambda path: Path(path)),
            )
            service = SourceEditorService(app, root)

            result = service.save({
                "path": str(source),
                "editor_type": "json_field",
                "json_pointer": "/nested/value",
                "text": "new",
            })

            self.assertEqual(result["status"], "SAVED")
            self.assertEqual(json.loads(source.read_text(encoding="utf-8"))["nested"]["value"], "new")
            with self.assertRaises(ValueError):
                service.resolve_path(str(root.parent / "outside.json"))

    def test_manual_render_submission_delegates_protocol_transitions(self) -> None:
        matching = SimpleNamespace(
            ask_id="one",
            character="Zara",
            phase="Adult",
            ask_path=Path("ask"),
            prompt_file="prompt.md",
            manifest={"story_slug": "story", "scene_slug": "scene"},
        )

        class Queue:
            def list_tasks(self):
                return [
                    matching,
                    SimpleNamespace(
                        ask_id="two",
                        character="Other",
                        phase="Adult",
                        manifest={"story_slug": "other", "scene_slug": "other-scene"},
                    ),
                ]

            def get_task(self, ask_id):
                return matching if ask_id == "one" else None

            def write_answer_image(self, *args):
                return Path("answer")

            def write_failed_answer(self, *args):
                return Path("failed")

        service = ManualRenderSubmissionService(Queue())

        self.assertEqual(service.list_tasks("Zara", "Adult"), [matching])
        self.assertEqual(service.list_tasks(story_slug="story", scene_slug="scene"), [matching])
        self.assertIs(service.get_task("one", "Zara", "Adult"), matching)
        self.assertIs(service.get_task("one", story_slug="story", scene_slug="scene"), matching)
        self.assertIsNone(service.get_task("one", story_slug="other"))
        self.assertEqual(service.submit_image(matching, b"image"), Path("answer"))
        self.assertEqual(service.submit_failure(matching, "reason"), Path("failed"))


if __name__ == "__main__":
    unittest.main()
