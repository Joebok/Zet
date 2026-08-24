import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from zet.web.app import create_app


class ZineWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("Characters", "Assets", "Pipelines", "Queue"):
            (self.root / name).mkdir()
        story_folder = self.root / "Stories" / "FirstDay"
        story_folder.mkdir(parents=True)
        (story_folder / "FirstDay.md").write_text("Title: `[FirstDay]`\n", encoding="utf-8")
        for number, title in enumerate(
            ("Standing in Wonder", "At the Arch", "Collision", "A Lending Hand", "Five", "Six", "Nice Hair"),
            start=1,
        ):
            slug = f"Chapter-{number:02d}-{title.replace(' ', '-')}"
            (story_folder / f"{slug}.md").write_text(f"Scene: `[{title}]`\n", encoding="utf-8")
            size = (400, 200) if number == 2 else (200, 400)
            Image.new("RGB", size, (number * 20, 40, 80)).save(story_folder / f"{slug}.png")
        config_path = self.root / "config.toml"
        config_path.write_text(
            f"""
[BaseFolders]
BaseLibraryPath = "{self.root.as_posix()}"
BaseCharacterPath = "{(self.root / 'Characters').as_posix()}"
BaseAssetPath = "{(self.root / 'Assets').as_posix()}"
BasePipelinePath = "{(self.root / 'Pipelines').as_posix()}"
BaseAIQueuePath = "{(self.root / 'Queue').as_posix()}"
""".lstrip(),
            encoding="utf-8",
        )
        self.client = TestClient(create_app(config_path))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_zine_api_round_trip_and_story_sources(self) -> None:
        sources_response = self.client.get("/api/zines/story-scenes/FirstDay")
        self.assertEqual(200, sources_response.status_code)
        sources = sources_response.json()["scenes"]
        self.assertEqual(7, len(sources))
        self.assertLess(sources[0]["width"], sources[0]["height"])
        self.assertGreater(sources[1]["width"], sources[1]["height"])
        builder = self.client.get(
            f"/api/stories/FirstDay/scenes/{sources[0]['scene_slug']}/builder"
        )
        self.assertEqual(200, builder.status_code, builder.text)
        self.assertIn("4:3", builder.json()["options"]["aspect_ratio"])

        tags = [source["tag"] for source in sources]
        payload = {
            "zine_name": "FirstDay",
            "slots": {
                "front": tags[0],
                "page_1": tags[1],
                "page_2": "",
                "page_3": tags[2],
                "page_4": tags[3],
                "page_5": tags[4],
                "page_6": tags[5],
                "back": tags[6],
            },
        }
        created = self.client.post("/api/zines", json=payload)
        self.assertEqual(200, created.status_code, created.text)
        document = created.json()["document"]
        self.assertTrue(document["zine"]["image_exists"])
        self.assertEqual("", document["metadata"]["slots"]["page_2"])

        self.assertEqual(200, self.client.get("/api/zines/FirstDay").status_code)
        self.assertEqual(200, self.client.post("/api/zines/FirstDay/regenerate").status_code)
        payload["zine_name"] = "First Day Zine"
        renamed = self.client.put("/api/zines/FirstDay", json=payload)
        self.assertEqual("First-Day-Zine", renamed.json()["document"]["zine"]["slug"])
        self.assertEqual(200, self.client.delete("/api/zines/First-Day-Zine").status_code)
        self.assertEqual([], self.client.get("/api/zines").json()["zines"])
