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

    def test_nonblank_tail_override_replaces_only_its_section_literally(self):
        override = "# Avoid\n\nkeep  lowercase,  spacing.."
        scene = {
            "final_image_prompt_overrides": {
                "anatomical_requirements": "  ",
                "avoid": f"\n{override}\n",
            },
            "setup": {"environment": {"important_exclusions": ["legacy environment term"]}},
            "avoid": {"scene_specific": ["legacy scene term"]},
        }
        ir = self._ir(scene)
        prompt = final_image_prompt_text(ir)

        self.assertEqual(override, ir["final_image_prompt_sections"]["avoid"])
        self.assertIn(override, prompt)
        self.assertNotIn(DEFAULT_PROMPT_SECTIONS["avoid"], prompt)
        self.assertNotIn("legacy environment term", prompt)
        self.assertNotIn("legacy scene term", prompt)
        self.assertIn(DEFAULT_PROMPT_SECTIONS["anatomical_requirements"], prompt)

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

    def test_world_position_is_separate_from_pose_and_camera_placement(self):
        prompt = self._prompt({
            "scene_elements": [{"id": "Tsaeytte", "display_name": "Tsaeytte", "element_type": "Character"}],
            "placements": [{
                "scene_element_id": "Tsaeytte",
                "position_within_cell": "left",
                "depth": "foreground",
                "world_position": "at the edge of the pit",
                "pose": {"summary": "Looking straight down"},
            }],
        })

        self.assertIn(
            "**Tsaeytte:** At the edge of the pit. Looking straight down. Place Tsaeytte in the left foreground region.",
            prompt,
        )
        self.assertNotIn("at the edge of the pit left foreground", prompt.lower())

    def test_world_position_without_pose_and_exact_pose_prefix_cleanup(self):
        scene = {
            "scene_elements": [{"id": "Tsaeytte", "display_name": "Tsaeytte", "element_type": "Character"}],
            "placements": [{
                "scene_element_id": "Tsaeytte",
                "position_within_cell": "center",
                "depth": "foreground",
                "world_position": "inside the doorway.",
            }],
        }
        self.assertIn(
            "**Tsaeytte:** Inside the doorway. Place Tsaeytte in the center foreground region.",
            self._prompt(scene),
        )
        scene["placements"][0].update({
            "world_position": "at the edge of the pit",
            "pose": {"summary": "At the edge of the pit, looking straight down."},
        })
        self.assertIn(
            "**Tsaeytte:** At the edge of the pit. Looking straight down. Place Tsaeytte in the center foreground region.",
            self._prompt(scene),
        )

    def test_none_position_suppresses_all_placement_output(self):
        scene = {
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "composition": {"left_to_right": ["satchel", "hero"]},
                "environment": {},
            },
            "scene_elements": [
                {"id": "satchel", "display_name": "Satchel", "element_type": "Prop", "element_visual_override": "worn red leather satchel"},
                {"id": "hero", "display_name": "Hero", "element_type": "Character"},
            ],
            "placements": [
                {
                    "scene_element_id": "satchel",
                    "position_within_cell": "None",
                    "depth": "foreground",
                    "motion": {"state": "moving", "direction_screen": "left", "cue": "swinging"},
                    "placement_notes": "beside the doorway",
                },
                {"scene_element_id": "hero", "position_within_cell": "center", "depth": "midground"},
            ],
        }
        story = {"style_defaults": {}, "compiler_profiles": {"final_image_prompt": {}}}

        ir = compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS)
        prompt = final_image_prompt_text(ir)

        self.assertEqual(["hero"], ir["composition"]["left_to_right"])
        self.assertEqual(["hero"], [item["scene_element_id"] for item in ir["placements"]])
        self.assertIn("**Element Override:** worn red leather satchel", prompt)
        self.assertNotIn("**Satchel:**", prompt)
        self.assertNotIn("beside the doorway", prompt)
        self.assertNotIn("Satchel is visibly moving", prompt)
        self.assertNotIn("Satchel, then Hero", prompt)

        scene["placements"][0]["position_within_cell"] = "left"
        placed_ir = compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS)
        placed_prompt = final_image_prompt_text(placed_ir)
        self.assertEqual(["satchel", "hero"], placed_ir["composition"]["left_to_right"])
        self.assertIn("**Satchel:** Stands in the left foreground.", placed_prompt)
        self.assertIn("beside the doorway", placed_prompt.lower())

    def test_composition_visual_read_is_grouped_by_depth(self):
        read_order = ["tsaeytte", "freydis", "galen", "rin", "peri", "blank", "none", "background", "backdrop"]
        scene = {
            "setup": {
                "composition": {
                    "focal_point": "Tsaeytte",
                    "left_to_right": read_order,
                    "composition_notes": "Keep the party separated by depth",
                },
            },
            "scene_elements": [
                {"id": element_id, "display_name": element_id.capitalize(), "element_type": "Character"}
                for element_id in [*read_order, "not-listed"]
            ],
            "placements": [
                {"scene_element_id": "tsaeytte", "position_within_cell": "left", "depth": "foreground"},
                {"scene_element_id": "freydis", "position_within_cell": "right", "depth": "distant background"},
                {"scene_element_id": "galen", "position_within_cell": "right", "depth": "distant background"},
                {"scene_element_id": "peri", "position_within_cell": "right", "depth": "distant background"},
                {"scene_element_id": "rin", "position_within_cell": "right", "depth": "distant background"},
                {"scene_element_id": "blank", "position_within_cell": " ", "depth": "midground"},
                {"scene_element_id": "none", "position_within_cell": "None", "depth": "midground"},
                {"scene_element_id": "background", "position_within_cell": "BACKGROUND", "depth": "background"},
                {"scene_element_id": "backdrop", "position_within_cell": "Backdrop", "depth": "background"},
                {"scene_element_id": "not-listed", "position_within_cell": "center", "depth": "midground"},
            ],
        }

        prompt = self._prompt(scene)
        composition = prompt.split("# Composition\n\n", 1)[1].split("\n\n# ", 1)[0]

        expected_foreground = "- Tsaeytte is in the left foreground."
        expected_distant = "- In the distant background from left to right the viewer sees Freydis, then Galen, then Rin, then Peri."
        self.assertIn(expected_foreground, composition)
        self.assertIn(expected_distant, composition)
        self.assertLess(composition.index(expected_foreground), composition.index(expected_distant))
        self.assertNotIn("- From left to right the viewer sees:", composition)
        self.assertNotIn("Blank", composition)
        self.assertNotIn("None", composition)
        self.assertNotIn("Background", composition)
        self.assertNotIn("Backdrop", composition)
        self.assertNotIn("Not-listed", composition)
        self.assertLess(composition.index("Primary focal point"), composition.index(expected_foreground))
        self.assertGreater(composition.index("Keep the party separated by depth"), composition.index(expected_distant))

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

    def test_enabled_story_dialogue_style_is_included_with_dialogue(self):
        scene = {"setup": {"environment": {}}, "dialogue": [{"text": "Hello."}]}
        story = {
            "style_defaults": {},
            "dialogue_styles": [{
                "display_name": "Compact parchment dialogue panel",
                "enabled_by_default": True,
                "panel_prompt": "Warm ivory parchment panel.",
                "pointer_prompt": "Short pointer toward the speaker.",
                "lettering_prompt": "Crisp sans-serif lettering.",
                "layout_rules": ["Do not obscure faces"],
                "avoid": ["oversized speech panel"],
            }],
            "compiler_profiles": {"final_image_prompt": {"include_dialogue_when_scene_has_dialogue": True}},
        }

        prompt = final_image_prompt_text(compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS))

        self.assertIn("## Compact parchment dialogue panel", prompt)
        self.assertIn("- **Panel:** Warm ivory parchment panel.", prompt)
        self.assertIn("- **Pointer:** Short pointer toward the speaker.", prompt)
        self.assertIn("- **Lettering:** Crisp sans-serif lettering.", prompt)
        self.assertIn("- **Layout:** Do not obscure faces.", prompt)
        self.assertIn("- **Avoid:** oversized speech panel.", prompt)

    def test_dialogue_style_is_omitted_when_profile_disables_dialogue(self):
        scene = {"setup": {"environment": {}}, "dialogue": [{"text": "Hello."}]}
        story = {
            "style_defaults": {},
            "dialogue_styles": [{"enabled_by_default": True, "panel_prompt": "Hidden style."}],
            "compiler_profiles": {"final_image_prompt": {"include_dialogue_when_scene_has_dialogue": False}},
        }

        prompt = final_image_prompt_text(compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS))

        self.assertNotIn("Hidden style", prompt)

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
