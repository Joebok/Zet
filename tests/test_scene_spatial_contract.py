import unittest

from zet.services.scene_spatial_contract import frame_extension_contract, projected_subject_text, suppress_spatial_clauses


class SceneSpatialContractTests(unittest.TestCase):
    def test_spatial_clauses_are_removed_but_anatomical_sides_survive(self):
        self.assertEqual(
            "Raises his left hand. Reaches for the pouch.",
            suppress_spatial_clauses(
                "Standing on the left side in the foreground. Raises his left hand. "
                "Facing away from the camera. Reaches for the pouch."
            ),
        )

    def test_group_projection_uses_each_members_composed_bounds_and_views(self):
        text = projected_subject_text({
            "kind": "group",
            "members": [{
                "element_id": "boy1", "display_name": "Schoolboy 1",
                "screen": {"x": .3, "y": .6, "width": .12, "height": .4, "feet": {"x": .3, "y": .8}},
                "camera_facing": "left three-quarter", "head_facing": "front", "physical_height": "5 ft 7 in",
            }],
        }, display_name="Schoolboys")
        self.assertIn("Schoolboys contains exactly 1 members", text)
        self.assertIn("Schoolboy 1: feet anchored 30.0%", text)
        self.assertIn("body in a left three-quarter view", text)
        self.assertIn("head in a front view", text)
        self.assertIn("5 ft 7 in", text)

    def test_frame_contract_preserves_crop_extensions_and_foreground_join(self):
        lines = frame_extension_contract({"layout_projection": {
            "background": {"image_placement": {"left": -.165, "top": 0, "width": 1.33, "height": .777},
                           "extension_regions": [{"left": 0, "top": 0, "width": .165, "height": .777},
                                                 {"left": .835, "top": 0, "width": .165, "height": .777}]},
            "ground": {"enabled": True, "join_y": .777},
        }})
        self.assertIn("occupying 133.0% of frame width", lines[0])
        self.assertIn("left, right extension areas", lines[1])
        self.assertIn("77.7% of frame height", lines[2])


if __name__ == "__main__":
    unittest.main()
