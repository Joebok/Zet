import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Scripts import Library_Paths
from zet.services.config_service import Config
from zet.services.path_service import PathService
from zet.services.view_service import UnknownViewError, ViewService


class ViewServiceTests(unittest.TestCase):
    def _service(self, root: Path) -> ViewService:
        config = root / "Config"
        config.mkdir()
        (config / "Prompt_View_Aliases.json").write_text(
            json.dumps({"aliases": {"front left 3/4": "FRONT_LEFT_3_4", "front_left_3_4": "FRONT_LEFT_3_4"}}),
            encoding="utf-8",
        )
        (config / "Prompt_View_Text.json").write_text(
            json.dumps({"views": {"FRONT_LEFT_3_4": {"folder_name": "Front_Left_3_4", "output_name_fragment": "Front-Left-3-4"}}}),
            encoding="utf-8",
        )
        return ViewService(root)

    def test_strict_normalization_and_folder_lookup_preserve_distinct_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self._service(Path(temp_dir))
            self.assertEqual(service.normalize_token("  front left 3/4  "), "FRONT_LEFT_3_4")
            self.assertEqual(service.normalize_token("FRONT_LEFT_3_4"), "FRONT_LEFT_3_4")
            self.assertEqual(service.folder_name("Front-Left-3-4"), "Front_Left_3_4")
            self.assertEqual(service.folder_name("Front_Left_3_4"), "Front_Left_3_4")
            self.assertEqual(service.folder_name("custom-view"), "custom_view")
            with self.assertRaises(UnknownViewError):
                service.normalize_token("custom-view")

    def test_tolerant_folder_lookup_falls_back_when_config_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self._service(Path(temp_dir))
            (Path(temp_dir) / "Config" / "Prompt_View_Text.json").write_text("not json", encoding="utf-8")
            self.assertEqual(service.folder_name_tolerant("Front-Left"), "Front_Left")
            with self.assertRaises(json.JSONDecodeError):
                service.folder_name("Front-Left")


class PathServiceTests(unittest.TestCase):
    def test_resolve_path_uses_explicit_project_and_library_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "Project"
            library_root = root / "Library"
            config = Config(
                base_library_path=str(library_root),
                base_character_path=str(library_root / "Characters"),
                base_asset_path=str(library_root / "Assets"),
                base_pipeline_path=str(library_root / "Pipelines"),
                base_ai_queue_path=str(library_root / "Queue"),
            )
            service = PathService(config, project_root)
            absolute = root / "outside.json"
            self.assertEqual(service.resolve_path(absolute), absolute)
            self.assertEqual(service.resolve_path("Config/file.json"), project_root / "Config/file.json")
            self.assertEqual(service.resolve_path("_Lib/Stories/story.md"), library_root / "Stories/story.md")
            self.assertEqual(service.resolve_path("Characters/Zara"), library_root / "Characters/Zara")
            with patch.object(Library_Paths, "load_project_config", return_value=config):
                self.assertEqual(
                    Library_Paths.resolve_library_path(project_root, "Config/file.json"),
                    project_root / "Config/file.json",
                )


if __name__ == "__main__":
    unittest.main()
