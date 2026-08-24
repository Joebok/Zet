import tempfile
import unittest
from pathlib import Path

from zet.services.scene_render_compiler import compile_scene_render_ir, final_image_prompt_text, local_render_brief, local_render_forge_couple_prompt_text, local_render_prompt_text
from zet.services.scene_prompt_sections import load_final_image_prompt_sections


DEFAULT_PROMPT_SECTIONS = load_final_image_prompt_sections(
    Path(__file__).resolve().parents[1] / "Config" / "Prompt_Templates" / "final_image_prompt_tail_v1.md"
)


class SceneRenderCompilerTests(unittest.TestCase):
    def _ir(self, scene):
        story = {
            "style_defaults": {
                "canonical_art_style": {"full_prompt_text": "ink wash"},
                "visual_continuity": {"rules": []},
                "default_avoid": [],
            },
            "dialogue_styles": [],
            "compiler_profiles": {"final_image_prompt": {}},
        }
        return compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS)

    def _prompt(self, scene):
        return final_image_prompt_text(self._ir(scene))

    def test_default_tail_sections_are_appended_literally_in_order(self):
        prompt = self._prompt({})

        expected_tail = "\n\n".join(DEFAULT_PROMPT_SECTIONS.values()) + "\n"
        self.assertTrue(prompt.endswith(expected_tail))


    def test_tail_template_validation_names_missing_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tail.md"
            path.write_text("# Avoid\n\n- Nothing.\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Anatomical Requirements"):
                load_final_image_prompt_sections(path)

            path.write_text(
                "\n\n".join(DEFAULT_PROMPT_SECTIONS.values()) + "\n\n# Avoid\n\n- Duplicate.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Avoid.*found 2"):
                load_final_image_prompt_sections(path)







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
        brief = local_render_brief(compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS))
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
        self.assertEqual(3, len(regional_lines))
        self.assertNotIn("background background scenery", "\n".join(regional_lines[1:]))
        self.assertIn("left foreground", regional_lines[1])
        self.assertIn("right foreground", regional_lines[2])
        self.assertFalse(forge.endswith("\n\n"))

    def test_chapter_five_forge_couple_plan_is_deterministic(self):
        story = {
            "style_defaults": {"canonical_art_style": {"full_prompt_text": "painterly fantasy"}},
            "compiler_profiles": {"final_image_prompt": {}},
        }
        scene = {
            "scene": {"story_beat": "The two walk through the arch."},
            "setup": {
                "canvas": {"orientation": "portrait", "aspect_ratio": "4:5"},
                "composition": {"focal_point": "Tsaeytte", "left_to_right": ["Valindia_8844d004", "Tsaeytte"]},
                "environment": {"location": "through the academy arch", "lighting": "morning sunlight", "general_background_notes": "Other students coming and going."},
            },
            "scene_elements": [
                {
                    "id": "Tsaeytte", "display_name": "Tsaeytte", "element_type": "Character", "phase": "Youth",
                    "resolved_source_sections": {"identity_preservation_core": "petite adolescent high elf with a short black bob", "identity_preservation_costume": "green blouse and forest-green skirt"},
                },
                {
                    "id": "Valindia_8844d004", "display_name": "Valindia", "element_type": "Character",
                    "element_visual_override": "Valindia is walking next to Tsaeytte with her arms wrapped around herself. Back-right 3/4 view.",
                    "resolved_source_sections": {"identity_preservation_core": "tall elegant half-elf with crimson-red hair", "identity_preservation_costume": "black academy clothing with gold embroidery"},
                },
                {"id": "Spire_Archway_efbf29cc", "display_name": "Spire Archway", "element_type": "Backdrop", "element_visual_override": "monumental stone academy archway"},
            ],
            "placements": [
                {"scene_element_id": "Tsaeytte", "position_within_cell": "center", "depth": "midground", "pose": {"summary": "Walking through the arch", "gaze_target_element_id": "Valindia_8844d004"}, "motion": {"state": "moving", "direction_screen": "away from camera"}, "placement_notes": "Tsaeytte is to the right of Valindia, holding a stack of books, back-left 3/4 view."},
                {"scene_element_id": "Valindia_8844d004", "position_within_cell": "left", "depth": "midground", "pose": {"summary": "Standing, holding one of the books", "gaze_target_element_id": "Tsaeytte"}, "motion": {"state": "moving", "direction_screen": "away from camera"}},
                {"scene_element_id": "Spire_Archway_efbf29cc", "depth": "background"},
            ],
            "dialogue": [{"text": "Maybe you should try not to be so ...", "pointer_target": "speaker mouth"}],
        }

        brief = local_render_brief(compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS))
        plan = brief["forge_couple_plan"]
        regions = plan["character_regions"]
        prompt_lines = [plan["global_region"]["prompt"], *[region["prompt"] for region in regions]]
        mappings = [plan["global_region"]["mapping"], *[region["mapping"] for region in regions]]

        self.assertEqual(("Advanced", 2), (plan["mode"], plan["subject_count"]))
        self.assertEqual(["Valindia_8844d004", "Tsaeytte"], [region["scene_element_id"] for region in regions])
        self.assertNotIn("Spire_Archway_efbf29cc", [region["scene_element_id"] for region in regions])
        self.assertIn("This region contains Valindia only", regions[0]["prompt"])
        self.assertIn("This region contains Tsaeytte only", regions[1]["prompt"])
        self.assertEqual(3, len(prompt_lines))
        self.assertEqual(len(prompt_lines), len(mappings))
        self.assertGreater(regions[1]["mapping"][4], regions[0]["mapping"][4])
        self.assertIn("walking", regions[0]["prompt"])
        self.assertNotIn("standing", regions[0]["prompt"].lower())
        self.assertNotIn("arms wrapped", regions[0]["prompt"].lower())
        self.assertNotRegex("\n".join(prompt_lines).lower(), r"maybe you should|speech panel|pointer|other students|crowd")
        self.assertNotRegex("\n".join(region["prompt"] for region in regions).lower(), r"direct eye contact|front-facing|looking directly at viewer")


if __name__ == "__main__":
    unittest.main()
