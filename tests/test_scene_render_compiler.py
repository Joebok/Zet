import unittest

from zet.services.scene_render_compiler import compile_scene_render_ir, final_image_prompt_text, local_render_brief, local_render_forge_couple_prompt_text, local_render_prompt_text


class SceneRenderCompilerTests(unittest.TestCase):
    def _prompt(self, scene):
        story = {
            "style_defaults": {
                "canonical_art_style": {"full_prompt_text": "ink wash"},
                "visual_continuity": {"rules": []},
                "default_avoid": [],
            },
            "dialogue_styles": [],
            "compiler_profiles": {"final_image_prompt": {}},
        }
        return final_image_prompt_text(compile_scene_render_ir(scene, story))

    def test_display_names_hide_internal_ids_and_empty_fields(self):
        prompt = self._prompt({
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "composition": {"grid": {"columns": 3, "rows": 1}, "primary_focal_point": "Valindia_38f52dd6", "left_to_right_order": []},
                "camera": {},
                "environment": {"location": "In front of the archway..", "general_foreground_notes": "", "general_background_notes": ""},
            },
            "scene_elements": [{"id": "Valindia_38f52dd6", "display_name": "Valindia", "element_type": "Character", "importance": "primary"}],
            "placements": [{"scene_element_id": "Valindia_38f52dd6", "screen_cell": {"column": 1}, "depth": "foreground", "pose": {"summary": "stands"}}],
            "reference_assignments": [{"tag": "{{REF:VAL}}", "applies_to_element_id": "Valindia_38f52dd6", "roles": [], "ignore": []}],
        })

        self.assertIn("Primary focal point: Valindia.", prompt)
        self.assertIn("Valindia stands in the left foreground.", prompt)
        self.assertIn("In front of the archway.", prompt)
        self.assertNotIn("Valindia_38f52dd6", prompt)
        self.assertNotIn(": .", prompt)
        self.assertNotIn("preserve ; ignore .", prompt)

    def test_semantic_placement_and_inferred_order(self):
        prompt = self._prompt({
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "composition": {"grid": {"columns": 3, "rows": 1}, "left_to_right_order": []},
                "camera": {},
                "environment": {},
            },
            "scene_elements": [
                {"id": "a", "display_name": "Left", "element_type": "Character"},
                {"id": "b", "display_name": "Right", "element_type": "Character"},
                {"id": "c", "display_name": "Center", "element_type": "Anchor", "resource_type": "Place"},
            ],
            "placements": [
                {"scene_element_id": "b", "screen_cell": {"row": 1, "column": 3}, "depth": "foreground"},
                {"scene_element_id": "a", "screen_cell": {"row": 1, "column": 1}, "depth": "foreground"},
                {"scene_element_id": "c", "screen_cell": {"row": 1, "column": 2}, "depth": "background"},
            ],
        })

        self.assertIn("Left-to-right order: Left -> Center -> Right.", prompt)
        self.assertIn("Left stands in the left foreground.", prompt)
        self.assertIn("Center occupies the center background.", prompt)
        self.assertNotIn("cell ", prompt)
        self.assertNotIn("row ", prompt)
        self.assertNotIn("column ", prompt)

    def test_interaction_dialogue_and_compact_preservation(self):
        prompt = self._prompt({
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "composition": {"grid": {"columns": 3, "rows": 1}},
                "camera": {},
                "environment": {},
            },
            "scene_elements": [
                {
                    "id": "Tsaeytte_12345678",
                    "display_name": "Tsaeytte",
                    "element_type": "Character",
                    "resource_type": "Character",
                    "costume": "Canonical Adventure Gear",
                    "resolved_source_sections": {
                        "identity_preservation_core": "Compact scene identity.",
                        "identity_preservation_costume": "Compact costume prompt.",
                    },
                },
                {"id": "Valindia_38f52dd6", "display_name": "Valindia", "element_type": "Character"},
            ],
            "placements": [
                {"scene_element_id": "Tsaeytte_12345678", "screen_cell": {"column": 1}, "pose": {"gaze_target_element_id": "Valindia_38f52dd6"}},
                {"scene_element_id": "Valindia_38f52dd6", "screen_cell": {"column": 3}, "pose": {"gaze_target_element_id": "Tsaeytte_12345678"}},
            ],
            "interactions": [
                {"subject_element_id": "Tsaeytte_12345678", "relationship": "looking at", "target_element_id": "Valindia_38f52dd6"},
                {"subject_element_id": "Valindia_38f52dd6", "relationship": "looking at", "target_element_id": "Tsaeytte_12345678"},
            ],
            "dialogue": [{"speaker_element_id": "Valindia_38f52dd6", "text": "wait...", "tone": "worried", "include_in_final_image_prompt": True}],
        })

        self.assertIn("Tsaeytte and Valindia hold direct eye contact.", prompt)
        self.assertEqual(1, prompt.count("hold direct eye contact"))
        self.assertIn('Valindia says exactly: "wait..."', prompt)
        self.assertIn("Valindia appears worried.", prompt)
        self.assertIn("**Identity:** Compact scene identity.", prompt)
        self.assertIn("**Costume - Canonical Adventure Gear:** Compact costume prompt.", prompt)
        self.assertNotIn("{'subject_element_id'", prompt)
        self.assertNotIn("Valindia_38f52dd6", prompt)
        self.assertNotIn("Tsaeytte_12345678", prompt)

    def test_local_render_prompt_is_composition_first(self):
        story = {
            "style_defaults": {
                "canonical_art_style": {"full_prompt_text": "Painterly semi-realistic fantasy illustration"},
                "visual_continuity": {"rules": []},
                "default_avoid": ["inconsistent character identity", "wrong costume"],
            },
            "dialogue_styles": [],
            "compiler_profiles": {"final_image_prompt": {}},
        }
        scene = {
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "composition": {"grid": {"columns": 3, "rows": 1}, "left_to_right_order": []},
                "camera": {"shot_type": "wide shot"},
                "environment": {"weather_or_atmosphere": "evening dusk, partly cloudy"},
            },
            "scene_elements": [
                {
                    "id": "Tsaeytte_12345678",
                    "display_name": "Tsaeytte",
                    "element_type": "Character",
                    "resource_type": "Character",
                    "scene_visual_override": "petite adult elf woman, black chin-length bob, teal off-shoulder adventuring outfit",
                },
                {
                    "id": "Spire_12345678",
                    "display_name": "Spire entrance arch",
                    "element_type": "Anchor",
                    "resource_type": "Place",
                    "scene_visual_override": "monumental gothic stone entrance arch",
                },
                {
                    "id": "Valindia_12345678",
                    "display_name": "Valindia",
                    "element_type": "Character",
                    "resource_type": "Character",
                    "scene_visual_override": "tall adult half-elf woman, crimson-red and black jaw-length hair, black-and-gold academy outfit",
                },
            ],
            "placements": [
                {
                    "scene_element_id": "Valindia_12345678",
                    "must_be_visible": True,
                    "screen_cell": {"row": 1, "column": 3},
                    "depth": "foreground",
                    "pose": {
                        "summary": "standing",
                        "left_hand_detail": "left hand raised in warning",
                        "gaze_target_element_id": "Tsaeytte_12345678",
                    },
                },
                {
                    "scene_element_id": "Spire_12345678",
                    "must_be_visible": True,
                    "screen_cell": {"row": 1, "column": 2},
                    "depth": "background",
                    "placement_notes": "top of arch visible",
                },
                {
                    "scene_element_id": "Tsaeytte_12345678",
                    "must_be_visible": True,
                    "screen_cell": {"row": 1, "column": 1},
                    "depth": "foreground",
                    "pose": {
                        "summary": "arms crossed",
                        "expression": "angry",
                        "gaze_target_element_id": "Valindia_12345678",
                    },
                },
            ],
            "dialogue": [{"speaker_element_id": "Valindia_12345678", "target_element_id": "Tsaeytte_12345678", "text": "wait...", "tone": "worried", "include_in_final_image_prompt": True}],
        }
        brief = local_render_brief(compile_scene_render_ir(scene, story))
        prompt_text = local_render_prompt_text(brief)
        prompt = brief["plain_txt2img"]["prompt"]
        negative = brief["plain_txt2img"]["negative_prompt"]
        forge = local_render_forge_couple_prompt_text(brief)

        self.assertEqual(2, brief["subject_count"])
        self.assertIn("exactly two adult elf women", prompt)
        self.assertIn("wide shot, landscape 16:9", prompt)
        self.assertIn("open empty space in the center foreground", prompt)
        self.assertEqual(["left", "center", "right"], [region["region"] for region in brief["regions"]])
        self.assertIn("left woman positioned", brief["regions"][0]["prompt"])
        self.assertIn("monumental gothic stone entrance arch", brief["regions"][1]["prompt"])
        self.assertIn("right woman positioned", brief["regions"][2]["prompt"])
        self.assertIn("facing screen-right", prompt)
        self.assertIn("facing screen-left", prompt)
        self.assertIn("worried", prompt)
        self.assertIn("scenery", prompt)
        self.assertNotIn("Anchor secondary", prompt)
        self.assertNotRegex(prompt_text, r"Painterly semi-realistic|cell|row 1 column|Character primary|scene_element_id|wait")
        self.assertNotRegex(prompt, r"Tsaeytte|Valindia|Spire_12345678|Valindia_12345678|Tsaeytte_12345678")
        self.assertIn("extra people", negative)
        self.assertIn("both characters on the same side", negative)
        self.assertNotIn("inconsistent character identity", negative)
        self.assertNotIn("wrong costume", negative)
        forge_lines = forge.splitlines()
        prompt_index = forge_lines.index("prompt:")
        negative_index = forge_lines.index("negative:")
        regional_lines = forge_lines[prompt_index + 1:negative_index - 1]
        self.assertEqual(4, len(regional_lines))
        self.assertFalse(forge.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
