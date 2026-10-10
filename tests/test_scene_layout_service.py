import tempfile
import unittest
from pathlib import Path

from zet.services.imperial_units import parse_feet_inches
from zet.services.scene_layout_service import SceneLayoutError, SceneLayoutService


class _Paths:
    def __init__(self, root):
        self.root = Path(root)

    def character_template_path(self, character, phase):
        return self.root / character / phase / "Character.md"


class SceneLayoutServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        template = root / "Traveler" / "Adult" / "Character.md"
        template.parent.mkdir(parents=True)
        template.write_text(
            "Standing Barefoot Height: `5 ft 8 in`\nEye Height: `5 ft 2 in`\n"
            "Shoulder Width: `1 ft 6 in`\nBody Depth: `10 in`\n",
            encoding="utf-8",
        )
        self.service = SceneLayoutService(_Paths(root))

    def tearDown(self):
        self.temporary.cleanup()

    def test_template_measurements_resolve_as_meters(self):
        measurements = self.service.measurements({"element_type": "Character", "character": "Traveler", "phase": "Adult"})
        self.assertAlmostEqual(parse_feet_inches("5 ft 8 in"), measurements["standing_barefoot_height"])
        self.assertAlmostEqual(parse_feet_inches("1 ft 6 in"), measurements["shoulder_width"])

    def test_projection_preserves_perspective_scale_and_front_facing(self):
        element = {"id": "traveler", "display_name": "Traveler", "element_type": "Character", "character": "Traveler", "phase": "Adult"}
        draft = self.service.normalize({"version": 1, "cameras": [{"id": "main", "position": [0, 1.7, 12], "target": [0, 1, 0]}],
                                        "pawns": [{"element_id": "traveler", "position": [0, 0, 0], "body_yaw": 180}]}, [element])
        projection = self.service.project(draft, width=1024, height=576)
        subject = projection["subjects"][0]
        self.assertEqual("front", subject["camera_facing"])
        self.assertEqual("front", subject["head_facing"])
        self.assertAlmostEqual(parse_feet_inches("5 ft 8 in"), subject["physical_height_m"])

        farther = {**draft, "pawns": [{**draft["pawns"][0], "position": [0, 0, -12]}]}
        far_projection = self.service.project(farther, width=1024, height=576)
        self.assertLess(far_projection["subjects"][0]["screen"]["height"], subject["screen"]["height"])

    def test_subscene_layout_migrates_to_anchor_local_coordinates_and_composes_without_rescaling(self):
        scene = {
            "scene_elements": [
                {"id": "traveler", "element_type": "Character", "character": "Traveler", "phase": "Adult"},
                {"id": "group", "element_type": "Prop"},
                {"id": "short", "element_type": "Character", "subscene_id": "group-scene"},
                {"id": "tall", "element_type": "Character", "subscene_id": "group-scene"},
            ],
            "subscenes": [{"id": "group-scene", "kind": "element", "enabled": True,
                           "anchor_element_id": "group", "name": "Group"}],
            "layout_3d": {"version": 2, "pawns": [
                {"element_id": "traveler", "position": [5, 0, 0], "measurement_overrides": {"height": "5 ft 8 in"}},
                {"element_id": "group", "position": [10, 0, -4], "body_yaw": 90},
                {"element_id": "short", "position": [11, 0, -4], "measurement_overrides": {"height": "4 ft"}},
                {"element_id": "tall", "position": [10, 0, -2], "measurement_overrides": {"height": "6 ft"}},
            ]},
        }
        normalized = self.service.normalize_targets(scene)
        local = {item["element_id"]: item for item in normalized["targets"]["group-scene"]["pawns"]}
        for actual, expected in zip(local["short"]["position"], [0, 0, 1]):
            self.assertAlmostEqual(expected, actual)
        for actual, expected in zip(local["tall"]["position"], [-2, 0, 0]):
            self.assertAlmostEqual(expected, actual)
        persisted = {**scene, "layout_3d": normalized["targets"]["main"],
                     "subscenes": [{**scene["subscenes"][0], "layout_3d": normalized["targets"]["group-scene"]}]}
        migrated_again = self.service.normalize_targets(persisted)
        self.assertEqual(normalized["targets"]["group-scene"]["pawns"], migrated_again["targets"]["group-scene"]["pawns"])
        composed = self.service.compose_targets(scene)
        world = {item["element_id"]: item for item in composed["pawns"]}
        self.assertEqual([11, 0, -4], world["short"]["position"])
        self.assertEqual([10, 0, -2], world["tall"]["position"])
        self.assertEqual(local["short"]["dimensions"], world["short"]["dimensions"])
        self.assertEqual(["group-scene"], [item["target_id"] for item in composed["groups"]])

        moved = {**persisted, "scene_elements": [
            {**item, "subscene_id": ""} if item["id"] == "short" else item for item in persisted["scene_elements"]
        ]}
        after_move = self.service.compose_targets(moved)
        moved_short = next(item for item in after_move["pawns"] if item["element_id"] == "short")
        for actual, expected in zip(moved_short["position"], [11, 0, -4]):
            self.assertAlmostEqual(expected, actual)

    def test_group_projection_aggregates_members_under_the_parent_anchor(self):
        projection = {"width": 100, "height": 100, "subjects": [
            {"element_id": "short", "pixel_bounds": {"left": 10, "top": 20, "right": 30, "bottom": 80},
             "screen": {"feet": {"x": .2}, "height": .6}, "depth_m": 5, "in_frame": True, "physical_height": "4 ft",
             "camera_facing": "front three-quarter", "head_facing": "left profile"},
            {"element_id": "tall", "pixel_bounds": {"left": 40, "top": 5, "right": 60, "bottom": 95},
             "screen": {"feet": {"x": .5}, "height": .9}, "depth_m": 6, "in_frame": True, "physical_height": "6 ft"},
        ]}
        composition = {"groups_workspace": "main", "parents": {"group-scene": "main"}, "groups": [
            {"target_id": "group-scene", "anchor_element_id": "group", "parent_id": "main"}], "pawns": [
            {"element_id": "short", "subscene_id": "group-scene", "body_yaw": 0},
            {"element_id": "tall", "subscene_id": "group-scene", "body_yaw": 15}]}
        self.service.aggregate_group_projection(projection, composition, [{"id": "group", "display_name": "Group"}])
        self.assertEqual(["group"], [item["element_id"] for item in projection["subjects"]])
        group = projection["subjects"][0]
        self.assertEqual("group", group["kind"])
        self.assertEqual({"left": 10, "top": 5, "right": 60, "bottom": 95}, group["pixel_bounds"])
        self.assertEqual({"short", "tall"}, {item["element_id"] for item in group["members"]})
        short = next(item for item in group["members"] if item["element_id"] == "short")
        self.assertEqual(0, short["body_yaw"])
        self.assertEqual("front three-quarter", short["camera_facing"])
        self.assertEqual("left profile", short["head_facing"])

    def test_empty_group_has_an_editor_only_render_warning(self):
        composition = {"parents": {"empty": "main"}, "groups": [{"target_id": "empty"}], "pawns": []}
        warnings = self.service.empty_group_warnings(composition, [{"id": "empty", "name": "Empty group"}])
        self.assertEqual(1, len(warnings))
        self.assertIn("available for editing", warnings[0])
        self.assertIn("will not appear in renders", warnings[0])

    def test_occupied_height_does_not_change_canonical_stature(self):
        element = {"id": "traveler", "element_type": "Character", "character": "Traveler", "phase": "Adult"}
        layout = self.service.normalize({"version": 1, "pawns": [{"element_id": "traveler",
            "measurement_overrides": {"occupied_height": "3 ft"}}]}, [element])
        subject = self.service.project(layout, width=1024, height=576)["subjects"][0]
        self.assertEqual("5 ft 8 in", subject["physical_height"])
        self.assertEqual("3 ft 0 in", subject["occupied_height"])

    def test_pawn_behind_camera_blocks_guidance(self):
        element = {"id": "traveler", "element_type": "Character", "character": "Traveler", "phase": "Adult"}
        layout = self.service.normalize({"version": 1, "cameras": [{"id": "main", "position": [0, 1.7, 8],
            "target": [0, 1, 0]}], "pawns": [{"element_id": "traveler", "position": [0, 0, 20]}]}, [element])
        with self.assertRaisesRegex(SceneLayoutError, "in front of the render camera"):
            self.service.guidance_reference(layout, [element], width=256, height=144)

    def test_missing_height_is_provisional_and_blocks_guided_render(self):
        layout = self.service.normalize({"version": 1}, [{"id": "unknown", "element_type": "Character"}])
        self.assertTrue(layout["pawns"][0]["provisional_height"])
        with self.assertRaisesRegex(SceneLayoutError, "confirm character height"):
            self.service.guidance_reference(layout, [{"id": "unknown", "element_type": "Character"}], width=256, height=144)

    def test_legacy_draft_requires_review_before_guidance(self):
        layout = self.service.draft_from_scene({"scene_elements": [{"id": "traveler", "element_type": "Character",
                                                                   "character": "Traveler", "phase": "Adult"}],
                                               "placements": [{"scene_element_id": "traveler", "position_within_cell": "right", "depth": "foreground"}]})
        self.assertTrue(layout["migration_review_required"])
        with self.assertRaisesRegex(SceneLayoutError, "Review and confirm"):
            self.service.guidance_reference(layout, [])

    def test_projection_reports_invalid_camera_and_grid_size_is_scene_aspect_aware(self):
        layout = self.service.normalize({"version": 1, "cameras": [{"id": "main", "position": [0, 0, 0], "target": [0, 0, 0]}]}, [])
        with self.assertRaisesRegex(SceneLayoutError, "must differ"):
            self.service.project(layout, width=256, height=144)
        self.assertEqual((1024, 1024), self.service.output_size("1:1", 1_048_576))
        self.assertEqual((1376, 768), self.service.output_size("16:9", 1_048_576))


if __name__ == "__main__":
    unittest.main()
