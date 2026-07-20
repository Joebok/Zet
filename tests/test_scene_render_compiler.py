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
                "environment": {"location": "In front of the archway..", "general_foreground_notes": "", "general_background_notes": ""},
            },
            "scene_elements": [{"id": "Valindia_38f52dd6", "display_name": "Valindia", "element_type": "Character"}],
            "placements": [{"scene_element_id": "Valindia_38f52dd6", "position_within_cell": "left", "depth": "foreground", "pose": {"summary": "stands"}}],
            "reference_assignments": [{"tag": "{{REF:VAL}}", "applies_to_element_id": "Valindia_38f52dd6", "roles": [], "ignore": []}],
        })

        self.assertIn("**Valindia:** Stands in the left foreground.", prompt)
        self.assertIn("In front of the archway.", prompt)
        self.assertIn("The scene takes place In front of the archway.", prompt)
        self.assertNotIn("The scene takes place at In front", prompt)
        self.assertIn("Create one finished scene. Do not show the planning grid or split the image into comic panels.", prompt)
        self.assertIn("# Canvas\n\n- Landscape 16:9.\n", prompt)
        self.assertNotIn("Create one finished landscape", prompt)
        self.assertNotIn("Render one continuous scene", prompt)
        self.assertNotIn("Valindia_38f52dd6", prompt)
        self.assertNotIn(": .", prompt)
        self.assertNotIn("preserve ; ignore .", prompt)

    def test_fallback_visual_description_used_without_reference_tag(self):
        prompt = self._prompt({
            "setup": {"canvas": {"orientation": "landscape", "aspect_ratio": "16:9"}, "environment": {}},
            "scene_elements": [{
                "id": "door",
                "display_name": "Door",
                "element_type": "Backdrop",
                "fallback_visual_description": "weathered green academy door with brass hinges",
            }],
            "placements": [{"scene_element_id": "door", "position_within_cell": "center", "depth": "background"}],
        })

        self.assertIn("**Visual description:** weathered green academy door with brass hinges", prompt)

    def test_semantic_placement_and_inferred_order(self):
        prompt = self._prompt({
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "environment": {},
            },
            "scene_elements": [
                {"id": "a", "display_name": "Left", "element_type": "Character"},
                {"id": "b", "display_name": "Right", "element_type": "Character"},
                {"id": "c", "display_name": "Center", "element_type": "Backdrop", "resource_type": "Place"},
            ],
            "placements": [
                {"scene_element_id": "b", "position_within_cell": "right", "depth": "foreground"},
                {"scene_element_id": "a", "position_within_cell": "left", "depth": "foreground"},
                {"scene_element_id": "c", "position_within_cell": "center", "depth": "background"},
            ],
        })

        self.assertIn("**Left:** Stands in the left foreground.", prompt)
        self.assertIn("Center defines the overall background and surrounding setting.", prompt)
        self.assertNotIn("Center occupies the center background.", prompt)
        self.assertNotIn("cell ", prompt)
        self.assertNotIn("row ", prompt)
        self.assertNotIn("column ", prompt)

    def test_interaction_dialogue_and_compact_preservation(self):
        prompt = self._prompt({
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "environment": {},
            },
            "scene_elements": [
                {
                    "id": "Tsaeytte_12345678",
                    "display_name": "Tsaeytte",
                    "element_type": "Character",
                    "resource_type": "Character",
                    "element_visual_override": "scene-only blue cloak",
                    "costume": "Canonical Adventure Gear",
                    "resolved_source_sections": {
                        "identity_preservation_core": "Compact scene identity.",
                        "identity_preservation_costume": "Compact costume prompt.",
                    },
                },
                {"id": "Valindia_38f52dd6", "display_name": "Valindia", "element_type": "Character"},
            ],
            "placements": [
                {"scene_element_id": "Tsaeytte_12345678", "position_within_cell": "left", "pose": {"gaze_target_element_id": "Valindia_38f52dd6"}},
                {"scene_element_id": "Valindia_38f52dd6", "position_within_cell": "right", "pose": {"gaze_target_element_id": "Tsaeytte_12345678"}},
            ],
            "interactions": [
                {"subject_element_id": "Tsaeytte_12345678", "relationship": "looking at", "target_element_id": "Valindia_38f52dd6"},
                {"subject_element_id": "Valindia_38f52dd6", "relationship": "looking at", "target_element_id": "Tsaeytte_12345678"},
            ],
            "custom_interactions": "Tsaeytte reaches toward Valindia.\n- Valindia steadies the books.",
            "dialogue": [{
                "speaker_element_id": "Valindia_38f52dd6",
                "text": "wait...",
                "pointer_target": "Valindia's mouth",
                "max_lines": 2,
            }],
        })

        self.assertIn("Tsaeytte and Valindia hold direct eye contact.", prompt)
        self.assertEqual(1, prompt.count("hold direct eye contact"))
        self.assertIn("- Tsaeytte reaches toward Valindia.", prompt)
        self.assertEqual(1, prompt.count("- Valindia steadies the books."))
        self.assertIn('Valindia says exactly: "wait..."', prompt)
        self.assertIn("**Identity:** Compact scene identity.", prompt)
        self.assertIn("**Costume - Canonical Adventure Gear:** Compact costume prompt.", prompt)
        self.assertIn("**Element Override:** scene-only blue cloak", prompt)
        self.assertIn("Aim the dialogue-panel pointer at Valindia's mouth.", prompt)
        self.assertIn("Wrap the dialogue in no more than 2 lines.", prompt)
        self.assertIn("Wrap the dialogue in no more than 1 line.", self._prompt({
            "setup": {"canvas": {"orientation": "landscape", "aspect_ratio": "16:9"}, "environment": {}},
            "scene_elements": [],
            "dialogue": [{"text": "Hello.", "max_lines": 1}],
        }))
        self.assertNotIn("{'subject_element_id'", prompt)
        self.assertNotIn("Valindia_38f52dd6", prompt)
        self.assertNotIn("Tsaeytte_12345678", prompt)

    def test_multiple_dialogue_panels_are_separated_with_special_instructions(self):
        prompt = self._prompt({
            "setup": {"canvas": {"orientation": "landscape", "aspect_ratio": "16:9"}, "environment": {}},
            "scene_elements": [
                {"id": "val", "display_name": "Valindia", "element_type": "Character"},
                {"id": "tsa", "display_name": "Tsaeytte", "element_type": "Character"},
            ],
            "dialogue": [
                {"speaker_element_id": "val", "target_element_id": "tsa", "text": "...camouflaged.", "pointer_target": "speaker mouth", "max_lines": 1},
                {"speaker_element_id": "tsa", "target_element_id": "val", "text": "hey!", "pointer_target": "speaker mouth", "max_lines": 1, "notes": "make this dialog panel smaller to indicate muttering"},
            ],
        })
        self.assertIn("# Dialogue Panels", prompt)
        self.assertIn("## Dialogue Panel 1", prompt)
        self.assertIn("## Dialogue Panel 2", prompt)
        self.assertIn("- **Special instructions:** make this dialog panel smaller to indicate muttering", prompt)

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
                "environment": {"weather_or_atmosphere": "evening dusk, partly cloudy"},
            },
            "scene_elements": [
                {
                    "id": "Tsaeytte_12345678",
                    "display_name": "Tsaeytte",
                    "element_type": "Character",
                    "resource_type": "Character",
                    "element_visual_override": "petite adult elf woman, black chin-length bob, teal off-shoulder adventuring outfit",
                },
                {
                    "id": "Spire_12345678",
                    "display_name": "Spire entrance arch",
                    "element_type": "Backdrop",
                    "resource_type": "Place",
                    "element_visual_override": "monumental gothic stone entrance arch",
                },
                {
                    "id": "Valindia_12345678",
                    "display_name": "Valindia",
                    "element_type": "Character",
                    "resource_type": "Character",
                    "element_visual_override": "tall adult half-elf woman, crimson-red and black jaw-length hair, black-and-gold academy outfit",
                },
            ],
            "placements": [
                {
                    "scene_element_id": "Valindia_12345678",
                    "position_within_cell": "right",
                    "depth": "foreground",
                    "pose": {
                        "summary": "standing",
                        "gaze_target_element_id": "Tsaeytte_12345678",
                    },
                },
                {
                    "scene_element_id": "Spire_12345678",
                    "position_within_cell": "center",
                    "depth": "background",
                    "placement_notes": "top of arch visible",
                },
                {
                    "scene_element_id": "Tsaeytte_12345678",
                    "position_within_cell": "left",
                    "depth": "foreground",
                    "pose": {
                        "summary": "arms crossed",
                        "expression": "angry",
                        "gaze_target_element_id": "Valindia_12345678",
                    },
                },
            ],
            "dialogue": [{"speaker_element_id": "Valindia_12345678", "target_element_id": "Tsaeytte_12345678", "text": "wait..."}],
        }
        brief = local_render_brief(compile_scene_render_ir(scene, story))
        prompt_text = local_render_prompt_text(brief)
        prompt = brief["plain_txt2img"]["prompt"]
        negative = brief["plain_txt2img"]["negative_prompt"]
        forge = local_render_forge_couple_prompt_text(brief)

        self.assertEqual(2, brief["subject_count"])
        self.assertIn("exactly two adult elf women", prompt)
        self.assertIn("landscape 16:9", prompt)
        self.assertEqual(["center background", "left foreground", "right foreground"], [region["region"] for region in brief["regions"]])
        self.assertIn("monumental gothic stone entrance arch", brief["regions"][0]["prompt"])
        self.assertIn("visible subject positioned", brief["regions"][1]["prompt"])
        self.assertIn("visible subject positioned", brief["regions"][2]["prompt"])
        self.assertIn("Expression: angry", brief["regions"][1]["prompt"])
        self.assertIn("scenery", prompt)
        self.assertNotIn("Backdrop secondary", prompt)
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
