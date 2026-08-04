import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zet.services.pipeline_inspection_service import PipelineInspectionService


class PipelineInspectionServiceTests(unittest.TestCase):
    def test_lists_character_and_scene_pipelines_and_their_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character = root / "Zara" / "Adult" / "Body-Reference"
            scene = root / "Stories" / "Demo" / "Opening"
            character.mkdir(parents=True)
            scene.mkdir(parents=True)
            (character / "Prompt.md").write_text("character prompt", encoding="utf-8")
            (scene / "Manifest.json").write_text("{}", encoding="utf-8")
            (scene / "Candidate.png").write_bytes(b"image")
            service = PipelineInspectionService(root)

            self.assertEqual(
                service.list_pipelines(),
                [
                    {
                        "pipeline_id": "Zara/Adult/Body-Reference",
                        "label": "Zara / Adult / Body-Reference",
                        "path": str(character),
                        "kind": "character",
                    },
                    {
                        "pipeline_id": "Stories/Demo/Opening",
                        "label": "Stories / Demo / Opening",
                        "path": str(scene),
                        "kind": "scene",
                    },
                ],
            )
            self.assertEqual(service.read_text("Zara/Adult/Body-Reference", "Prompt.md"), "character prompt")
            files = service.list_files("Stories/Demo/Opening")
            self.assertEqual([item["kind"] for item in files], ["image", "text"])

    def test_rejects_paths_outside_a_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = root / "Zara" / "Adult" / "Body-Reference"
            pipeline.mkdir(parents=True)
            (root / "secret.md").write_text("secret", encoding="utf-8")
            service = PipelineInspectionService(root)

            with self.assertRaises(FileNotFoundError):
                service.file_path("Zara/Adult/Body-Reference", "../../../secret.md")

    @patch("zet.services.pipeline_inspection_service.platform.system", return_value="Windows")
    @patch("zet.services.pipeline_inspection_service.os.startfile", create=True)
    def test_open_folder_uses_system_browser(self, startfile, _system) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = root / "Zara" / "Adult" / "Body-Reference"
            pipeline.mkdir(parents=True)
            file_path = pipeline / "Prompt.md"
            file_path.write_text("prompt", encoding="utf-8")
            service = PipelineInspectionService(root)

            self.assertEqual(service.open_folder("Zara/Adult/Body-Reference", "Prompt.md"), pipeline)
            startfile.assert_called_once_with(str(pipeline))


if __name__ == "__main__":
    unittest.main()
