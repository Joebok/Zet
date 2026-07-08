import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from zet.web.app import create_app

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None


VIEWS = [
    "Front",
    "Front-Left-3-4",
    "Left-Profile",
    "Back-Left-3-4",
    "Back",
    "Back-Right-3-4",
    "Right-Profile",
    "Front-Right-3-4",
]


class TurnaroundServiceTests(unittest.TestCase):
    def _write_png(self, path: Path, height: int) -> None:
        """Write a gray-background test character image."""
        image = Image.new("RGBA", (120, 180), (128, 128, 128, 255))
        draw = ImageDraw.Draw(image)
        top = 160 - height
        middle = top + max(12, height // 2)
        draw.rectangle((48, top, 72, middle), fill=(20, 20, 20, 255))
        draw.rectangle((35, middle, 85, 160), fill=(20, 20, 20, 255))
        image.save(path)

    def _write_fixture(self, root: Path, *, include_images: bool = True) -> Path:
        """Create a temporary character fixture with eight locked body-reference assets."""
        character_dir = root / "Characters" / "Test" / "Adult"
        asset_dir = root / "Assets" / "Test" / "Adult"
        character_dir.mkdir(parents=True)
        asset_dir.mkdir(parents=True)
        (root / "Pipelines").mkdir()
        (root / "Queue").mkdir()
        records = []
        for index, view in enumerate(VIEWS, start=1):
            output = f"Body-Reference_{view}.png"
            if include_images:
                self._write_png(asset_dir / output, 80 + index)
            records.append(
                {
                    "asset_id": index,
                    "character": "Test",
                    "phase": "Adult",
                    "pipeline": "Body-Reference",
                    "body_view": view,
                    "head_view": None,
                    "costume": None,
                    "expression": None,
                    "asset_state": "LOCKED",
                    "pipeline_stage": "LOCKED",
                    "actor": "HUMAN_AGENT",
                    "ai_state": None,
                    "final_image_output": output,
                    "last_ai_update": None,
                    "error_code": None,
                    "error_message": None,
                    "updated_at": None,
                    "reference_files": [],
                }
            )
        (character_dir / "Assets.json").write_text(json.dumps({"assets": records}, indent=2) + "\n", encoding="utf-8")
        (character_dir / "Pipelines.json").write_text(
            json.dumps(
                {
                    "pipelines": {
                        "Body-Reference": {
                            "stages": ["LOCKED"],
                            "actor_by_stage": {"LOCKED": "HUMAN_AGENT"},
                            "worker_by_stage": {},
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        config_path = root / "config.toml"
        config_path.write_text(
            f"""
[BaseFolders]
BaseCharacterPath = "{(root / 'Characters').as_posix()}"
BaseAssetPath = "{(root / 'Assets').as_posix()}"
BasePipelinePath = "{(root / 'Pipelines').as_posix()}"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
""".lstrip(),
            encoding="utf-8",
        )
        return config_path

    def test_turnaround_api_lists_ready_groups(self):
        """Verify the dashboard API reports ready turnaround groups from locked assets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_fixture(Path(temp_dir), include_images=False)
            client = TestClient(create_app(config_path))

            response = client.get("/api/turnarounds", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(response.status_code, 200)
            rows = response.json()["rows"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["turnaround_id"], "Body-Reference")
            self.assertTrue(rows[0]["ready"])
            self.assertEqual(rows[0]["status"], "ready for turnaround")
            self.assertEqual(rows[0]["source_asset_ids"], list(range(1, 9)))

    @unittest.skipUnless(Image is not None, "Pillow is required for image assembly tests.")
    def test_turnaround_generate_and_promote(self):
        """Verify a generated candidate can be promoted into the locked turnaround folder."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            generated = client.post(
                "/api/turnarounds/Body-Reference/generate",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(generated.status_code, 200)
            row = generated.json()["row"]
            self.assertTrue(Path(row["candidate_image_path"]).exists())
            self.assertTrue(Path(row["analysis_path"]).exists())
            self.assertEqual(row["status"], "candidate ready for review")
            with Image.open(row["candidate_image_path"]) as image:
                self.assertLess(image.width, 900)
                cell_width = (image.width - 210) // 4
                gap_x = 60 + cell_width + 15
                self.assertEqual(image.getpixel((gap_x, 90))[:3], (128, 128, 128))

            promoted = client.post(
                "/api/turnarounds/Body-Reference/promote",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(promoted.status_code, 200)
            locked_path = Path(promoted.json()["row"]["locked_image_path"])
            self.assertTrue(locked_path.exists())
            self.assertEqual(locked_path.parent.name, "Turnarounds")

    @unittest.skipUnless(Image is not None, "Pillow is required for image assembly tests.")
    def test_partial_turnaround_can_update_percent_and_delete(self):
        """Verify auxiliary partial turnarounds can be re-rendered and deleted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self._write_fixture(root)
            client = TestClient(create_app(config_path))

            created = client.post(
                "/api/turnarounds/Body-Reference/partials",
                params={"character": "Test", "phase": "Adult"},
                json={"label": "Head and chest", "crop_percent": 45},
            )
            self.assertEqual(created.status_code, 200)
            aux = created.json()["row"]["auxiliary_sheets"][0]
            self.assertEqual(aux["label"], "Head and chest")
            self.assertEqual(aux["crop_percent"], 45.0)
            self.assertTrue(Path(aux["candidate_image_path"]).exists())
            self.assertFalse(Path(aux["locked_image_path"]).exists())
            with Image.open(aux["candidate_image_path"]) as image:
                first_height = image.height
                first_width = image.width
                cell_width = (image.width - 210) // 4
                gap_x = 60 + cell_width + 15
                self.assertEqual(image.getpixel((gap_x, 60))[:3], (128, 128, 128))
            full = client.post(
                "/api/turnarounds/Body-Reference/generate",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(full.status_code, 200)
            with Image.open(full.json()["row"]["candidate_image_path"]) as image:
                self.assertLess(first_width, image.width)

            updated = client.put(
                f"/api/turnarounds/partials/{aux['turnaround_id']}",
                params={"character": "Test", "phase": "Adult"},
                json={"label": "Head and upper chest", "crop_percent": 60},
            )
            self.assertEqual(updated.status_code, 200)
            updated_aux = updated.json()["row"]["auxiliary_sheets"][0]
            self.assertEqual(len(updated.json()["row"]["auxiliary_sheets"]), 1)
            self.assertEqual(updated_aux["turnaround_id"], aux["turnaround_id"])
            self.assertEqual(updated_aux["label"], "Head and upper chest")
            self.assertEqual(updated_aux["crop_percent"], 60.0)
            with Image.open(updated_aux["candidate_image_path"]) as image:
                self.assertGreater(image.height, first_height)

            promoted = client.post(
                f"/api/turnarounds/{updated_aux['turnaround_id']}/promote",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(promoted.status_code, 200)
            promoted_aux = promoted.json()["row"]["auxiliary_sheets"][0]
            self.assertTrue(Path(promoted_aux["locked_image_path"]).exists())

            regenerated = client.put(
                f"/api/turnarounds/partials/{promoted_aux['turnaround_id']}",
                params={"character": "Test", "phase": "Adult"},
                json={"label": "Head and upper chest", "crop_percent": 55},
            )
            self.assertEqual(regenerated.status_code, 200)
            replacement_required = client.post(
                f"/api/turnarounds/{promoted_aux['turnaround_id']}/promote",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(replacement_required.status_code, 409)
            replaced = client.post(
                f"/api/turnarounds/{promoted_aux['turnaround_id']}/promote",
                params={"character": "Test", "phase": "Adult", "replace_existing": "true"},
            )
            self.assertEqual(replaced.status_code, 200)

            deleted = client.delete(
                f"/api/turnarounds/partials/{updated_aux['turnaround_id']}",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(deleted.json()["row"]["auxiliary_sheets"], [])
            self.assertFalse(Path(promoted_aux["locked_image_path"]).exists())
