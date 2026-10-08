import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image

from zet.services.scene_background_service import SceneBackgroundService
from zet.services.scene_layout_service import GROUND_COLOR, SceneLayoutError, SceneLayoutService


class GroundLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service = SceneLayoutService(SimpleNamespace(character_template_path=lambda *args: self.root / "missing.md"))
        self.elements = [{"id": "actor", "element_type": "Character"}, {"id": "arch", "element_type": "Backdrop",
                          "reference_images": [{"tag": "{{IMAGE:img_arch}}"}]}]
        self.raw = {"version": 2, "pawns": [{"element_id": "actor", "position": [0, 0, 0],
                                            "measurement_overrides": {"height": "5 ft 8 in"}}]}
        self.image = self.root / "backdrop.png"
        Image.new("RGB", (400, 200), "orange").save(self.image)
        self.backgrounds = SceneBackgroundService(SimpleNamespace(resolve_scene_references=lambda tag: [{"tag": tag, "path": str(self.image)}]), None)
        self.scene = {"scene_elements": self.elements, "setup": {"canvas": {"aspect_ratio": "16:9"}}}

    def tearDown(self):
        self.temp.cleanup()

    def layout(self):
        return self.service.normalize(self.raw, self.elements)

    def test_ground_defaults_preserve_actor_and_camera_and_are_idempotent(self):
        layout = self.layout()
        self.assertTrue(layout["ground"]["enabled"])
        self.assertEqual([0, 0, 0], layout["pawns"][0]["position"])
        self.assertEqual([0, 1.68, 8], layout["cameras"][0]["position"])
        self.assertGreater(layout["cameras"][0]["ground_distance_m"], 8)
        self.assertEqual(layout, self.service.normalize(layout, self.elements))

    def test_join_is_behind_every_grounded_actor_and_foreground_has_contact_shadows(self):
        self.elements.append({"id": "farther", "element_type": "Prop"})
        self.raw["pawns"].append({"element_id": "farther", "position": [2, 0, -6]})
        layout = self.layout()
        projection = self.service.project(layout, width=640, height=360)
        ground = projection["ground"]
        self.assertGreater(ground["visible_fraction"], 0)
        self.assertLess(ground["visible_fraction"], 1)
        for subject in projection["subjects"]:
            self.assertGreater(subject["ground_contact"]["y"], ground["join_y"])
        png = self.service.render_guidance(layout, projection, self.elements)
        with Image.open(io.BytesIO(png)) as image:
            self.assertEqual(GROUND_COLOR, image.getpixel((10, 350)))
            actor = next(item for item in projection["subjects"] if item["element_id"] == "actor")
            x = max(0, actor["pixel_bounds"]["left"])
            y = round(actor["ground_contact"]["y"] * 360)
            self.assertNotEqual(GROUND_COLOR, image.getpixel((x + 2, y)))

    def test_background_is_framed_above_join_without_stretching_and_ground_survives_compile_guidance(self):
        layout = self.layout()
        background = self.backgrounds.resolve(self.scene, layout, width=640, height=360)
        ground = self.service.ground_projection(layout)
        crop = background["projection"]["crop"]
        self.assertAlmostEqual((16 / 9) / ground["visible_fraction"], crop["width"] * 400 / (crop["height"] * 200))
        self.assertAlmostEqual(ground["visible_fraction"], background["projection"]["ground_join_y"])
        generated = self.service.guidance_reference(layout, self.elements, width=640, height=360, background=background)
        with Image.open(io.BytesIO(background["png_bytes"])) as image:
            self.assertEqual((255, 165, 0), image.getpixel((10, 10)))
            self.assertEqual(GROUND_COLOR, image.getpixel((10, 350)))
        with Image.open(io.BytesIO(generated["png_bytes"])) as image:
            self.assertEqual(GROUND_COLOR, image.getpixel((10, 350)))

    def test_backdrop_is_locked_and_actors_beyond_it_block_guidance(self):
        layout = self.layout()
        near = self.service.ground_projection(layout)
        layout["cameras"][0]["ground_distance_m"] = 100
        far = self.service.ground_projection(layout)
        self.assertLess(far["visible_fraction"], near["visible_fraction"])
        layout["cameras"][0]["ground_distance_m"] = 1
        safe = self.service.ground_projection(layout)
        self.assertEqual(1, safe["distance_m"])
        self.assertEqual(safe["origin"][1], 0)
        self.assertTrue(any("locked backdrop" in value for value in self.service.project(layout)["warnings"]))
        with self.assertRaisesRegex(SceneLayoutError, "locked backdrop"):
            self.service.guidance_reference(layout, self.elements)

    def test_disabled_ground_retains_full_frame_background(self):
        self.raw["ground"] = {"enabled": False, "surface": "Stone path"}
        layout = self.layout()
        background = self.backgrounds.resolve(self.scene, layout, width=640, height=360)
        self.assertEqual(1, background["projection"]["ground_join_y"])
        with Image.open(io.BytesIO(background["png_bytes"])) as image:
            self.assertEqual((255, 165, 0), image.getpixel((10, 350)))

    def test_invalid_ground_and_underground_staging_are_rejected(self):
        for ground in [[], {"enabled": "yes"}, {"surface": "x" * 1001}]:
            self.raw["ground"] = ground
            with self.assertRaises(SceneLayoutError):
                self.layout()
        self.raw["ground"] = {"enabled": True}
        self.raw["cameras"] = [{"id": "main", "ground_distance_m": float("nan")}]
        with self.assertRaises(SceneLayoutError):
            self.layout()
        self.raw.pop("cameras")
        self.raw["pawns"][0]["position"][1] = -1
        with self.assertRaisesRegex(SceneLayoutError, "on or above the ground"):
            self.service.guidance_reference(self.layout(), self.elements)

    def test_top_down_view_becomes_foreground_and_preserves_background_source(self):
        self.raw["cameras"] = [{"id": "main", "position": [0, 10, 0], "target": [0, 0, 0]}]
        layout = self.layout()
        self.assertEqual(0, self.service.ground_projection(layout)["visible_fraction"])
        background = self.backgrounds.resolve(self.scene, layout, width=640, height=360)
        self.assertEqual("arch", background["projection"]["source"]["element_id"])
        with Image.open(io.BytesIO(background["png_bytes"])) as image:
            self.assertEqual(GROUND_COLOR, image.getpixel((10, 10)))


if __name__ == "__main__":
    unittest.main()
