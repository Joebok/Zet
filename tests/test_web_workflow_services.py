import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from zet.services.character_phase_discovery_service import CharacterPhaseDiscoveryService
from zet.services.gpt_helper_prompt_service import GptHelperPromptService
from zet.services.manual_render_submission_service import ManualRenderSubmissionService
from zet.services.source_editor_service import SourceEditorService


class WebWorkflowServiceTests(unittest.TestCase):
    def test_character_phase_discovery_lists_directories_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Zara" / "Adult").mkdir(parents=True)
            (root / "Zara" / "notes.txt").write_text("ignored", encoding="utf-8")
            service = CharacterPhaseDiscoveryService(root)

            self.assertEqual(service.list_characters(), ["Zara"])
            self.assertEqual(service.list_phases("Zara"), ["Adult"])

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

    def test_gpt_helper_prompt_migrates_legacy_defaults_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "Config"
            config_dir.mkdir()
            (config_dir / "Prompt_View_Text.json").write_text('{"views": {"FRONT": {}}}', encoding="utf-8")
            (config_dir / "GPT_Helper_Prompts.json").write_text(
                '{"defaults": {"FRONT": "legacy prompt"}}', encoding="utf-8"
            )
            phase_path = root / "Characters" / "Zara" / "Adult" / "Config" / "GPT_Helper_Prompts.json"
            asset = SimpleNamespace(character="Zara", phase="Adult", pipeline="Body", body_view="Front")
            app = SimpleNamespace(
                config_path=root / "config.toml",
                asset=lambda *_: SimpleNamespace(get=lambda: asset),
                path_service=SimpleNamespace(gpt_helper_prompt_path=lambda *_: phase_path),
                pipeline_repository=SimpleNamespace(list_pipelines=lambda *_: [SimpleNamespace(name="Body")]),
            )
            task = SimpleNamespace(asset_id=1, character="Zara", phase="Adult")
            service = GptHelperPromptService(app, root)

            self.assertEqual(service.get(task)["text"], "legacy prompt")
            self.assertEqual(service.save(task, "updated prompt")["text"], "updated prompt")
            self.assertEqual(json.loads(phase_path.read_text(encoding="utf-8"))["pipelines"]["Body"]["FRONT"], "updated prompt")

    def test_manual_render_submission_delegates_protocol_transitions(self) -> None:
        matching = SimpleNamespace(ask_id="one", character="Zara", phase="Adult", ask_path=Path("ask"), prompt_file="prompt.md")

        class Queue:
            def list_tasks(self):
                return [matching, SimpleNamespace(ask_id="two", character="Other", phase="Adult")]

            def get_task(self, ask_id):
                return matching if ask_id == "one" else None

            def write_answer_image(self, *args):
                return Path("answer")

            def write_failed_answer(self, *args):
                return Path("failed")

        service = ManualRenderSubmissionService(Queue())

        self.assertEqual(service.list_tasks("Zara", "Adult"), [matching])
        self.assertIs(service.get_task("one", "Zara", "Adult"), matching)
        self.assertEqual(service.submit_image(matching, b"image"), Path("answer"))
        self.assertEqual(service.submit_failure(matching, "reason"), Path("failed"))


if __name__ == "__main__":
    unittest.main()
