import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zet.models.asset import Asset
from zet.services.pipeline_inspection_service import PipelineInspectionService


class FakeAssetRepository:
    def __init__(self, assets):
        self.assets = assets

    def list_assets(self, character, phase):
        return [asset for asset in self.assets if asset.character == character and asset.phase == phase]


class FakePathService:
    def __init__(self, root):
        self.root = root

    def pipeline_path(self, asset):
        return self.root / asset.character / asset.phase / asset.pipeline / asset.body_view / (asset.head_view or "_") / f"Asset_{asset.asset_id}"


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

    def test_groups_multi_asset_costume_pipeline_by_costume_and_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assets = [
                Asset(25, "Tsaeytte", "Adult", "Costume-Dressing", "Front", "Front", costume="Adventure Gear"),
                Asset(26, "Tsaeytte", "Adult", "Costume-Dressing", "Back", "Back", costume="Adventure Gear"),
                Asset(33, "Tsaeytte", "Adult", "Costume-Dressing", "Front", "Front", costume="Formal Gown"),
            ]
            path_service = FakePathService(root)
            for asset in assets:
                workspace = path_service.pipeline_path(asset)
                workspace.mkdir(parents=True)
                (workspace / "_stage.txt").write_text("RENDER\n", encoding="utf-8")
                (workspace / "_history.log").write_text("created\n", encoding="utf-8")
            service = PipelineInspectionService(root, FakeAssetRepository(assets), path_service)

            pipeline = service.list_pipelines()[0]
            self.assertNotIn("pipeline_id", pipeline)
            self.assertEqual([group["label"] for group in pipeline["children"]], ["Adventure Gear", "Formal Gown"])
            self.assertEqual([view["label"] for view in pipeline["children"][0]["children"]], ["Back", "Front"])
            front_id = pipeline["children"][0]["children"][1]["pipeline_id"]
            self.assertEqual(service.read_text(front_id, "_stage.txt"), "RENDER\n")
            self.assertEqual([item["kind"] for item in service.list_files(front_id)], ["text", "text"])

    def test_rejects_paths_outside_a_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = root / "Zara" / "Adult" / "Body-Reference"
            pipeline.mkdir(parents=True)
            (root / "secret.md").write_text("secret", encoding="utf-8")
            service = PipelineInspectionService(root)

            with self.assertRaises(FileNotFoundError):
                service.file_path("Zara/Adult/Body-Reference", "../../../secret.md")



if __name__ == "__main__":
    unittest.main()
