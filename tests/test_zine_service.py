import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from zet.models.story import SceneRecord
from zet.services.path_service import PathService
from zet.services.story_reference_service import StoryReferenceService
from zet.services.zine_service import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    ZineService,
    ZineServiceError,
    assemble_zine,
    cover_crop,
    make_page_image,
    make_spread_pages,
    scale_and_center_zine,
)


class FakeReferenceService:
    def __init__(self, paths: dict[str, Path]):
        self.paths = paths

    def resolve_image_tag(self, tag: str) -> dict:
        if tag not in self.paths:
            raise ValueError(f"Unresolved tag: {tag}")
        return {"tag": tag, "path": str(self.paths[tag])}


class FakeStoryService:
    def __init__(self, path_service: PathService, reference_paths: dict[str, Path]):
        self.path_service = path_service
        self.story_reference_service = FakeReferenceService(reference_paths)

    def safe_slug(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-")
        return safe or "Untitled"

    def list_scenes(self, story_slug: str) -> list[SceneRecord]:
        folder = self.path_service.story_folder_path(story_slug)
        return [
            SceneRecord(story_slug, path.stem, path.stem.replace("-", " "), str(path))
            for path in sorted(folder.glob("*.md"))
            if path.stem != story_slug
        ]

    def scene_image_path(self, story_slug: str, scene_slug: str) -> Path:
        return self.path_service.story_folder_path(story_slug) / f"{scene_slug}.png"


class EmptyAuxiliaryRepository:
    def list_resources(self) -> list:
        return []


class ZineImageTests(unittest.TestCase):
    def test_cover_crop_and_spread_dimensions(self) -> None:
        source = Image.new("RGB", (400, 200), "red")
        cropped = cover_crop(source, PANEL_WIDTH, PANEL_HEIGHT)
        left, right = make_spread_pages(source)
        self.assertEqual((PANEL_WIDTH, PANEL_HEIGHT), cropped.size)
        self.assertEqual((PANEL_WIDTH, PANEL_HEIGHT), left.size)
        self.assertEqual((PANEL_WIDTH, PANEL_HEIGHT), right.size)






class ZineServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        config = SimpleNamespace(
            base_library_path=str(self.root),
            base_asset_path=str(self.root / "Assets"),
            zine_print_scale=0.978,
            zine_page_margin=4,
        )
        self.path_service = PathService(config, self.root)
        self.source = self.root / "source.png"
        Image.new("RGB", (300, 180), "navy").save(self.source)
        self.tag = "{{TEST:image}}"
        self.story = FakeStoryService(self.path_service, {self.tag: self.source})
        self.service = ZineService(self.path_service, self.story)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def payload(self, name: str = "My Zine") -> dict:
        return {
            "zine_name": name,
            "slots": {
                "front": self.tag,
                "page_1": self.tag,
                "page_2": "",
                "page_3": self.tag,
                "page_4": "",
                "page_5": self.tag,
                "page_6": "",
                "back": self.tag,
            },
        }

    def test_create_regenerate_rename_and_delete(self) -> None:
        created = self.service.create_zine(self.payload())
        self.assertEqual("My-Zine", created.record.slug)
        with Image.open(created.record.image_path) as image:
            self.assertEqual((CANVAS_WIDTH, CANVAS_HEIGHT), image.size)
            self.assertEqual((255, 255, 255), image.getpixel((0, 0)))
        metadata = json.loads(Path(created.record.json_path).read_text(encoding="utf-8"))
        self.assertEqual(self.tag, metadata["slots"]["front"])
        self.assertTrue(metadata["guides"]["enabled"])

        regenerated = self.service.regenerate_zine("My-Zine")
        self.assertTrue(Path(regenerated.record.image_path).is_file())
        renamed = self.service.update_zine("My-Zine", self.payload("Renamed Zine"))
        self.assertEqual("Renamed-Zine", renamed.record.slug)
        self.assertFalse((self.root / "Assets" / "Zines" / "My-Zine").exists())
        self.assertTrue(Path(renamed.record.json_path).is_file())
        self.service.delete_zine("Renamed-Zine")
        self.assertEqual([], self.service.list_zines())


    def test_validation_rejects_missing_required_slot_and_duplicate(self) -> None:
        payload = self.payload()
        payload["slots"]["page_3"] = ""
        with self.assertRaisesRegex(ZineServiceError, "Page 3 is required"):
            self.service.create_zine(payload)
        self.service.create_zine(self.payload())
        with self.assertRaisesRegex(ZineServiceError, "already exists"):
            self.service.create_zine(self.payload())

    def test_story_scene_sources_include_dimensions_and_tags(self) -> None:
        folder = self.root / "Stories" / "FirstDay"
        folder.mkdir(parents=True)
        (folder / "Chapter-01.md").write_text("scene", encoding="utf-8")
        Image.new("RGB", (100, 200), "red").save(folder / "Chapter-01.png")
        sources = self.service.story_scene_sources("FirstDay")
        self.assertEqual("{{SCENE:FirstDay:Chapter-01}}", sources[0].tag)
        self.assertEqual((100, 200), (sources[0].width, sources[0].height))
