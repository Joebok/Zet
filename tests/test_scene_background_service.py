import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image

from zet.services.config_service import Config
from zet.services.path_service import PathService
from zet.services.qwen_scene_prompt import compile_qwen_scene_prompt
from zet.services.scene_background_service import SceneBackgroundService
from zet.services.scene_background_service import BACKDROP_EXTENSION_COLOR
from zet.services.scene_layout_service import SceneLayoutError
from zet.services.scene_prompt_sections import load_final_image_prompt_sections
from zet.services.story_service import StoryService, StoryServiceError


class SceneBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = Config(base_library_path=str(self.root), base_character_path=str(self.root / "Characters"),
                             base_asset_path=str(self.root / "Assets"), base_pipeline_path=str(self.root / "Pipelines"),
                             base_ai_queue_path=str(self.root / "Queue"))
        self.story = StoryService(PathService(self.config, self.root), None, None)
        self.sections = load_final_image_prompt_sections(Path(__file__).resolve().parents[1] / "Config/Prompt_Templates/final_image_prompt_tail_v1.md")
        self.image = self.root / "arch.png"
        image = Image.new("RGB", (400, 200))
        for x in range(400):
            for y in range(200):
                image.putpixel((x, y), (x % 256, y, 50))
        image.save(self.image)
        self.tag = "{{IMAGE:img_arch}}"
        self.refs = [{"tag": self.tag, "path": str(self.image), "label": "Archway"}]
        self.scene = {"scene": {"slug": "Arch", "_story_slug": "Story"},
                      "setup": {"canvas": {"aspect_ratio": "1:1"}},
                      "scene_elements": [{"id": "arch", "element_type": "Backdrop", "display_name": "Archway",
                                          "reference_images": [{"tag": self.tag, "ignore": ["source framing", "source aspect ratio"],
                                                                "primary_prompt_source": True}]}],
                      "placements": [{"scene_element_id": "arch", "depth": "background"}], "subscenes": [],
                      "layout_3d": {"version": 3, "ground": {"enabled": False},
                                   "pawns": [{"element_id": "arch", "position": [0, 0, -6]}]}}
        self.backgrounds = SceneBackgroundService(SimpleNamespace(resolve_scene_references=lambda tag: self.refs),
                                                 self.story.scene_render_target_service)

    def tearDown(self):
        self.temp.cleanup()

    def layout(self):
        return self.story.scene_layout_service.normalize(self.scene["layout_3d"], self.scene["scene_elements"])

    def test_migration_preserves_actor_camera_and_manual_gaze(self):
        self.scene["scene_elements"].append({"id": "actor", "element_type": "Character"})
        actor = {"element_id": "actor", "position": [2, 0, -3], "body_yaw": 73, "head_yaw": 18,
                 "head_pitch": 22, "look_at": "arch", "measurement_overrides": {"height": "5 ft"}}
        self.scene["layout_3d"]["pawns"].append(actor)
        self.scene["layout_3d"]["migration_review_required"] = True
        camera = {"id": "main", "position": [3, 2, 10], "target": [0, 1, 0], "vertical_fov": 60}
        self.scene["layout_3d"]["cameras"] = [camera]
        layout = self.layout()
        self.assertEqual(3, layout["version"])
        self.assertEqual(["actor"], [pawn["element_id"] for pawn in layout["pawns"]])
        for key in ("position", "body_yaw", "head_yaw", "head_pitch"):
            self.assertEqual(actor[key], layout["pawns"][0][key])
        self.assertEqual("", layout["pawns"][0]["look_at"])
        self.assertTrue(layout["migration_notices"])
        self.assertTrue(layout["migration_review_required"])
        for key, value in camera.items():
            self.assertEqual(value, layout["cameras"][0][key])
        self.assertEqual({"kind": "element", "element_id": "arch"}, layout["background"])
        self.assertEqual(layout, self.story.scene_layout_service.normalize(layout, self.scene["scene_elements"]))

    def test_free_placement_preserves_aspect_and_allows_extension_across_aspects(self):
        for width, height in [(400, 200), (200, 400), (200, 200)]:
            for aspect in [1, 16 / 9, 9 / 16, 8 / 5]:
                for center, zoom in [([.5, .5], 1), ([-2, 3], .5), ([0, 1], 2), ([1, 0], 99)]:
                    crop = self.backgrounds.crop(width, height, aspect, {"center": center, "zoom": zoom})
                    self.assertEqual(center, crop["center"])
                    self.assertGreater(crop["width"], 0)
                    self.assertGreater(crop["height"], 0)
                    self.assertAlmostEqual(aspect, crop["width"] * width / (crop["height"] * height))

    def test_explicit_missing_source_and_frozen_input_block(self):
        layout = self.layout()
        self.image.unlink()
        with self.assertRaisesRegex(SceneLayoutError, "missing or unreadable"):
            self.backgrounds.resolve(self.scene, layout, width=128, height=128)
        with self.assertRaisesRegex(SceneLayoutError, "frozen"):
            self.backgrounds.resolve(self.scene, layout, width=128, height=128, resolved_references=[])
        layout["background"] = {"kind": "subscene", "target_id": "disabled"}
        with self.assertRaisesRegex(SceneLayoutError, "unavailable"):
            self.backgrounds.resolve(self.scene, layout, width=128, height=128)

    def test_invalid_framing_and_per_camera_framing(self):
        for framing in [{"center": [0]}, {"center": [float("nan"), 0]}, {"zoom": float("inf")}]:
            with self.assertRaises(SceneLayoutError):
                self.backgrounds.crop(400, 200, 1, framing)
        layout = self.layout()
        layout["cameras"].append({**layout["cameras"][0], "id": "other", "background_framing": {"center": [.25, .5], "zoom": 2}})
        first = self.backgrounds.resolve(self.scene, layout, width=128, height=128)
        layout["active_camera_id"] = "other"
        second = self.backgrounds.resolve(self.scene, layout, width=128, height=128)
        self.assertNotEqual(first["projection"]["crop"], second["projection"]["crop"])

    def test_backdrop_only_compile_replaces_source_and_hashes_framing(self):
        renderer = self.story.story_render_service
        refs, ir, digest = renderer._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.assertEqual([], ir["layout_projection"]["subjects"])
        self.assertEqual([], ir["layout_3d"]["pawns"])
        self.assertEqual(1, sum(item["role"] == "layout_reference" for item in ir["image_inputs"]))
        guide = next(ref for ref in refs if ref["prompt_role"] == "layout_reference")
        with Image.open(guide["path"]) as image:
            self.assertAlmostEqual(100, image.getpixel((0, 512))[0], delta=2)
        cropped = next(ref for ref in refs if ref["tag"] == self.tag)
        self.assertNotEqual(str(self.image), cropped["path"])
        with Image.open(cropped["path"]) as image:
            self.assertEqual((1024, 1024), image.size)
            self.assertAlmostEqual(100, image.getpixel((0, 512))[0], delta=2)
        inputs = next(item for item in ir["image_inputs"] if item["tag"] == self.tag)
        self.assertTrue(any("crop" in value for value in inputs["preserve"]))
        self.assertFalse(any("framing" in value for value in inputs["ignore"]))
        self.assertIn("already selected background crop", compile_qwen_scene_prompt(ir))
        before = Path(cropped["path"]).read_bytes()
        self.scene["layout_3d"] = self.layout()
        self.scene["layout_3d"]["cameras"][0]["background_framing"] = {"center": [.7, .5], "zoom": 2}
        new_refs, new_ir, new_digest = renderer._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.assertNotEqual(digest, new_digest)
        self.assertNotEqual(ir["layout_projection"]["background"]["crop"], new_ir["layout_projection"]["background"]["crop"])
        self.assertEqual(before, Path(cropped["path"]).read_bytes())
        self.assertNotEqual(cropped["path"], next(ref["path"] for ref in new_refs if ref["tag"] == self.tag))

    def test_accepted_background_survives_baked_element_filter_and_uses_frozen_bytes(self):
        self.scene["subscenes"] = [{"id": "environment", "kind": "background", "enabled": True,
                                     "layout_3d": {**self.layout(), "background": None,
                                                   "ground": {"enabled": False}}}]
        self.scene["scene_elements"][0]["subscene_id"] = "environment"
        self.scene["layout_3d"] = self.layout()
        self.scene["layout_3d"]["background"] = {"kind": "subscene", "target_id": "environment"}
        targets = self.story.scene_render_target_service
        tag = targets.image_tag("Story", "Arch", "environment")
        projected = targets.project_main(self.scene, {"environment": {"locked_image_path": str(self.image)}})
        self.assertEqual([], projected["scene_elements"])
        refs, ir, digest = self.story.story_render_service._compile_projected(projected, {}, self.sections,
            resolved_references=[{"tag": tag, "path": str(self.image)}], element_sources={})
        self.assertEqual("subscene", ir["layout_projection"]["background"]["source"]["kind"])
        self.assertEqual(1, sum(ref["tag"] == tag for ref in refs))
        frozen = self.root / "frozen.png"
        frozen.write_bytes(self.image.read_bytes())
        Image.new("RGB", (400, 200), "blue").save(self.image)
        frozen_refs, frozen_ir, frozen_digest = self.story.story_render_service._compile_projected(projected, {}, self.sections,
            resolved_references=[{"tag": tag, "path": str(frozen)}], element_sources={})
        self.assertEqual(Path(refs[0]["path"]).read_bytes(), Path(frozen_refs[0]["path"]).read_bytes())
        self.assertEqual(ir["layout_projection"]["background"], frozen_ir["layout_projection"]["background"])
        # Generation of this background must never use its own accepted output.
        generation = targets.project_subscene(self.scene, "environment")
        _, generation_ir, _ = self.story.story_render_service._compile_projected(generation, {}, self.sections,
            resolved_references=self.refs, element_sources={})
        self.assertNotIn("background", generation_ir["layout_projection"])
        self.assertNotIn(tag, [item["tag"] for item in generation_ir["image_inputs"]])

    def test_layout_reference_slot_limit_counts_only_submitted_inputs(self):
        # Frozen snapshots can contain unused sources; they must not consume slots.
        extra = [{"tag": f"{{{{IMAGE:img_unused_{index}}}}}", "path": str(self.image)} for index in range(12)]
        refs, _, _ = self.story.story_render_service._compile_projected(self.scene, {}, self.sections,
            resolved_references=[*self.refs, *extra], element_sources={})
        self.assertEqual(2, len(refs))
        for index in range(9):
            self.scene["scene_elements"][0]["reference_images"].append({"tag": extra[index]["tag"]})
        with self.assertRaisesRegex(StoryServiceError, "reference slot"):
            self.story.story_render_service._compile_projected(self.scene, {}, self.sections,
                resolved_references=[*self.refs, *extra], element_sources={})

    def test_dolly_and_lens_change_subject_projection_without_changing_background(self):
        self.scene["scene_elements"].append({"id": "actor", "element_type": "Character"})
        self.scene["layout_3d"]["pawns"].append({"element_id": "actor", "position": [0, 0, 0], "body_yaw": 180,
                                               "measurement_overrides": {"height": "5 ft 8 in"}})
        renderer = self.story.story_render_service
        _, before, old_hash = renderer._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.scene["layout_3d"] = self.layout()
        camera = self.scene["layout_3d"]["cameras"][0]
        camera["position"][2] -= 1
        camera["target"][2] -= 1
        camera["vertical_fov"] = 35
        _, after, new_hash = renderer._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.assertEqual(before["layout_projection"]["background"], after["layout_projection"]["background"])
        self.assertGreater(after["layout_projection"]["subjects"][0]["screen"]["height"], before["layout_projection"]["subjects"][0]["screen"]["height"])
        self.assertNotEqual(old_hash, new_hash)

    def test_batch_compilation_uses_selected_background_and_keeps_prior_guidance_immutable(self):
        self.scene["subscenes"] = [{"id": "environment", "name": "Environment", "kind": "background", "enabled": True,
                                     "layout_3d": {**self.layout(), "background": None,
                                                   "ground": {"enabled": False}}}]
        self.scene["scene_elements"][0]["subscene_id"] = "environment"
        self.scene["layout_3d"] = self.layout()
        self.scene["layout_3d"]["background"] = {"kind": "subscene", "target_id": "environment"}
        selected = {"environment": {"path": str(self.image)}}
        renderer = self.story.story_render_service
        before = renderer.compile_batch_target(self.scene, {}, self.sections, [], "main", selected)
        guide = next(ref for ref in before["references"] if ref["prompt_role"] == "layout_reference")
        original = Path(guide["path"]).read_bytes()
        Image.new("RGB", (400, 200), "blue").save(self.image)
        after = renderer.compile_batch_target(self.scene, {}, self.sections, [], "main", selected)
        self.assertNotEqual(before["render_input_hash"], after["render_input_hash"])
        self.assertEqual(original, Path(guide["path"]).read_bytes())
        self.assertEqual(2, len(before["references"]))
        self.assertNotIn(self.tag, [ref["tag"] for ref in before["references"]])

    def test_ground_surface_join_and_contacts_reach_compiler_and_invalidate_frozen_guidance(self):
        self.scene["layout_3d"]["ground"] = {"enabled": True, "surface": "a stone path"}
        self.scene["scene_elements"].append({"id": "actor", "element_type": "Character"})
        self.scene["placements"].append({"scene_element_id": "actor"})
        self.scene["layout_3d"]["pawns"].append({"element_id": "actor", "position": [0, 0, 0],
            "measurement_overrides": {"height": "5 ft 8 in"}})
        renderer = self.story.story_render_service
        refs, before, old_hash = renderer._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        ground = before["layout_projection"]["ground"]
        self.assertEqual("a stone path", ground["surface"])
        self.assertAlmostEqual(ground["visible_fraction"], before["layout_projection"]["background"]["ground_join_y"])
        prompt = compile_qwen_scene_prompt(before)
        self.assertIn("feet contacting the ground surface", prompt)
        self.assertIn("a stone path across the foreground", prompt)
        self.assertIn("contact shadows", prompt)
        guide = next(ref for ref in refs if ref["prompt_role"] == "layout_reference")
        old_bytes = Path(guide["path"]).read_bytes()
        self.scene["layout_3d"] = self.layout()
        self.scene["layout_3d"]["ground"]["surface"] = "a wooden floor"
        self.scene["layout_3d"]["cameras"][0]["ground_distance_m"] = 40
        _, after, new_hash = renderer._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.assertNotEqual(old_hash, new_hash)
        self.assertNotEqual(ground["join_y"], after["layout_projection"]["ground"]["join_y"])
        self.assertEqual(old_bytes, Path(guide["path"]).read_bytes())

    def test_background_generation_ignores_parent_foreground_framing(self):
        self.scene["subscenes"] = [{"id": "environment", "name": "Environment", "kind": "background", "enabled": True,
                                     "layout_3d": {**self.layout(), "background": None,
                                                   "ground": {"enabled": False}}}]
        self.scene["scene_elements"][0]["subscene_id"] = "environment"
        self.scene["layout_3d"] = self.layout()
        self.scene["layout_3d"]["ground"] = {"enabled": True, "surface": "a stone path"}
        renderer = self.story.story_render_service
        target = self.story.scene_render_target_service.project_subscene(self.scene, "environment")
        _, before, old_hash = renderer._compile_projected(target, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.scene["layout_3d"]["ground"]["surface"] = "a wooden floor"
        self.scene["layout_3d"]["cameras"][0]["ground_distance_m"] = 50
        target = self.story.scene_render_target_service.project_subscene(self.scene, "environment")
        _, after, new_hash = renderer._compile_projected(target, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.assertEqual(old_hash, new_hash)
        self.assertFalse(before["layout_projection"]["ground"]["enabled"])
        self.assertFalse(after["layout_projection"]["ground"]["enabled"])

    def test_shrunk_background_has_extension_regions_and_prompts_for_outpainting(self):
        self.scene["layout_3d"] = self.layout()
        framing = {"center": [.5, .5], "zoom": .25}
        self.scene["layout_3d"]["cameras"][0]["background_framing"] = framing
        background = self.backgrounds.resolve(self.scene, self.scene["layout_3d"], width=256, height=256)
        placement = background["projection"]["image_placement"]
        self.assertEqual({"left": .25, "top": .375, "width": .5, "height": .25}, placement)
        self.assertAlmostEqual(.875, sum(region["width"] * region["height"] for region in background["projection"]["extension_regions"]))
        with Image.open(io.BytesIO(background["png_bytes"])) as image:
            self.assertEqual(BACKDROP_EXTENSION_COLOR, image.getpixel((10, 10)))
            self.assertNotEqual(BACKDROP_EXTENSION_COLOR, image.getpixel((128, 128)))
        refs, ir, _ = self.story.story_render_service._compile_projected(self.scene, {}, self.sections, resolved_references=self.refs, element_sources={})
        self.assertIn("Extend its walls, sky", compile_qwen_scene_prompt(ir))
        assignment = next(item for item in ir["image_inputs"] if item["tag"] == self.tag)
        self.assertTrue(any("extension" in item for item in assignment["ignore"]))
        self.scene["layout_3d"]["cameras"][0]["background_framing"]["center"] = [-.25, 1.25]
        normalized = self.layout()
        self.assertEqual([-.25, 1.25], normalized["cameras"][0]["background_framing"]["center"])


if __name__ == "__main__":
    unittest.main()
