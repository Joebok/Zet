import unittest

from zet.services.qwen_scene_prompt import analyze_qwen_scene_prompt, compile_qwen_scene_prompt


class QwenScenePromptTests(unittest.TestCase):
    def test_zero_and_one_reference_scene_prompts(self):
        ir = {"canvas": {"orientation": "portrait"}, "scene": {"story_beat": "An elf opens a gate"},
              "style": {"art_style": "painterly fantasy illustration"},
              "elements": [{"id": "elf", "display_name": "Tsaeytte", "resolved_source_sections": {
                  "identity_anchors": "petite high elf with violet eyes",
                  "costume_anchors": "dark teal blouse and brown boots"}}],
              "placements": [{"scene_element_id": "elf", "position_within_cell": "left",
                              "depth": "foreground", "pose": {"summary": "holding a lantern"}}],
              "image_inputs": [], "dialogue": [{"speaker_element_id": "elf", "text": "Open the gate"}]}
        prompt = compile_qwen_scene_prompt(ir)
        self.assertIn("painterly fantasy illustration", prompt)
        self.assertIn("petite high elf with violet eyes", prompt)
        self.assertIn('"Open the gate"', prompt)
        self.assertNotIn("<image1>", prompt)
        ir["image_inputs"] = [{"index": 1, "role": "subject_reference", "label": "Tsaeytte",
                                "applies_to": "Tsaeytte", "preserve": ["facial identity"]}]
        prompt = compile_qwen_scene_prompt(ir)
        self.assertIn("<image1> supplies subject reference for Tsaeytte; retain facial identity", prompt)

    def test_dialogue_layout_fields_reach_the_render_prompt(self):
        prompt = compile_qwen_scene_prompt({
            "elements": [{"id": "elf", "display_name": "Tsaeytte"}],
            "dialogue": [{"speaker_element_id": "elf", "text": "Potential is nothing without discipline",
                          "max_lines": 2, "pointer_target": "speaker mouth",
                          "notes": "Ivory rectangular box beside Tsaeytte, clear of the arch inscription"}],
        })
        self.assertIn('A clearly visible speech balloon shaped as a rounded-corner rectangle sits just above Tsaeytte', prompt)
        self.assertIn('its border fits closely around the text with minimal padding; it contains only "Potential is nothing without discipline"', prompt)
        self.assertIn("no more than 2 lines", prompt)
        self.assertIn("short tail ends at Tsaeytte's visible mouth", prompt)
        self.assertIn("Ivory rectangular box beside Tsaeytte, clear of the arch inscription", prompt)

    def test_dialogue_placement_and_external_listener_context_reach_qwen_prompt(self):
        for placement, direction in (("left", "to the left"), ("right", "to the right"),
                                     ("above", "above"), ("below", "below")):
            prompt = compile_qwen_scene_prompt({
                "elements": [{"id": "kaeldor", "display_name": "Kaeldor"}],
                "dialogue": [{"speaker_element_id": "kaeldor", "speaker_name": "Kaeldor",
                              "target_name": "Tsaeytte", "target_context": "Tsaeytte and Valindia",
                              "speaker_context": "Kaeldor and the Schoolboys", "text": "Sorry.",
                              "panel_placement": placement}],
            })
            self.assertIn(f"sits {direction} of Kaeldor", prompt)
            self.assertIn("Tsaeytte is in the separate Tsaeytte and Valindia image", prompt)
            self.assertIn("do not add a second copy of the speaker", prompt)
            self.assertEqual(1, prompt.count('contains only "Sorry."'))
        automatic = compile_qwen_scene_prompt({"elements": [{"id": "kaeldor", "display_name": "Kaeldor"}],
                                              "dialogue": [{"speaker_element_id": "kaeldor", "text": "Sorry."}]})
        self.assertIn("sits just above Kaeldor", automatic)

    def test_dialogue_follows_placed_speaker_and_avoids_other_character(self):
        prompt = compile_qwen_scene_prompt({
            "elements": [
                {"id": "valindia", "display_name": "Valindia", "element_type": "Character",
                 "resolved_source_sections": {"costume_anchors": "Black-and-gold jacket panels"}},
                {"id": "tsaeytte", "display_name": "Tsaeytte", "element_type": "Character"},
            ],
            "placements": [
                {"scene_element_id": "valindia", "position_within_cell": "left", "depth": "foreground"},
                {"scene_element_id": "tsaeytte", "position_within_cell": "right", "depth": "foreground"},
            ],
            "dialogue": [{"speaker_element_id": "valindia", "text": "country girl",
                          "max_lines": 1, "pointer_target": "speaker mouth"}],
        })
        balloon = 'A clearly visible speech balloon shaped as a rounded-corner rectangle sits just above Valindia at left foreground; its border fits closely around the text with minimal padding; it contains only "country girl" on one line'
        self.assertIn(balloon, prompt)
        self.assertLess(prompt.index("Valindia, Black-and-gold jacket panels"), prompt.index(balloon))
        self.assertLess(prompt.index(balloon), prompt.index("Tsaeytte, at right foreground"))
        self.assertIn("short tail ends at Valindia's visible mouth", prompt)
        self.assertIn("balloon stays clear of faces and readable background text", prompt)

    def test_reference_change_ignore_notes_and_structured_interactions_reach_prompt(self):
        prompt = compile_qwen_scene_prompt({
            "elements": [{"id": "red", "display_name": "Red-haired boy"},
                         {"id": "dark", "display_name": "Dark-haired boy"}],
            "image_inputs": [{"role": "subject_reference", "applies_to": "red",
                              "change": ["turn toward the other boy"],
                              "ignore": ["source background"], "notes": "Keep freckles visible",
                              "assignments": [{"applies_to": "red", "prompt_role": "subject_reference"},
                                              {"applies_to": "dark", "prompt_role": "costume_reference",
                                               "preserve": ["burgundy waistcoat"]}]}],
            "interactions": [{"subject_element_id": "red", "relationship": "gently pushes",
                              "target_element_id": "dark", "note": "at the shoulder"}],
            "custom_interactions": "Both boys remain fully visible.",
        })
        self.assertIn("change only turn toward the other boy", prompt)
        self.assertIn("disregard source background", prompt)
        self.assertIn("reference note: Keep freckles visible", prompt)
        self.assertIn("costume reference for Dark-haired boy", prompt)
        self.assertIn("burgundy waistcoat", prompt)
        self.assertIn("Red-haired boy gently pushes Dark-haired boy, at the shoulder", prompt)
        self.assertIn("Both boys remain fully visible", prompt)

    def test_named_identity_and_assignment_ignore_are_not_repeated(self):
        prompt = compile_qwen_scene_prompt({
            "elements": [{"id": "red", "display_name": "Schoolboy 1", "element_type": "Character",
                          "resolved_source_sections": {"identity_anchors": "Schoolboy 1: red hair and freckles"}},
                         {"id": "dark", "display_name": "Schoolboy 2", "element_type": "Character",
                          "resolved_source_sections": {"identity_anchors": "Schoolboy 2 is a young elf with dark hair"}}],
            "placements": [{"scene_element_id": "red"}, {"scene_element_id": "dark"}],
            "image_inputs": [{"role": "costume_reference", "applies_to": "dark",
                              "ignore": ["source pose", "source framing"],
                              "assignments": [{"applies_to": "dark", "prompt_role": "costume_reference",
                                               "ignore": ["source pose"]}]}],
        })
        self.assertIn("Schoolboy 1: red hair and freckles", prompt)
        self.assertIn("Schoolboy 2 is a young elf with dark hair", prompt)
        self.assertNotIn("Schoolboy 1, Schoolboy 1", prompt)
        self.assertNotIn("Schoolboy 2, Schoolboy 2", prompt)
        self.assertEqual(1, prompt.count("source pose"))
        self.assertEqual(1, prompt.count("source framing"))

    def test_element_subscene_lists_each_visible_character_once_and_omits_parent_placement(self):
        ir = {
            "render_target": {"kind": "element_subscene", "label": "Schoolboys and Kaeldor"},
            "canvas": {"orientation": "landscape"},
            "style": {"art_style": "painterly fantasy"},
            "environment": {
                "location": "A stone pathway",
                "general_background_notes": "This three-person group will be placed small in the background of the full scene. All characters should be shown full body.",
            },
            "composition": {
                "focal_point": "The playful interaction",
                "left_to_right": ["red", "dark", "kaeldor"],
                "composition_notes": (
                    "Exactly three separate young elven males, all full body. "
                    "Red-haired Schoolboy 1 at left gently shoves dark-haired Schoolboy 2 at center; "
                    "Kaeldor at right grins and points at Schoolboy 2. "
                    "All characters' hands and bodies remain distinct. No speech panels."
                ),
            },
            "elements": [
                {"id": "red", "display_name": "Schoolboy 1", "element_type": "Character",
                 "fallback_visual_description": "Red-haired young elf",
                 "element_visual_override": "Gently pushing Schoolboy 2 at the shoulder while smiling"},
                {"id": "dark", "display_name": "Schoolboy 2", "element_type": "Character",
                 "fallback_visual_description": "Dark-haired young elf"},
                {"id": "kaeldor", "display_name": "Kaeldor", "element_type": "Character",
                 "fallback_visual_description": "Tan elf with short light-brown hair",
                 "element_visual_override": "Ivory shirt and burgundy waistcoat; grinning and pointing toward the schoolboys"},
            ],
            "placements": [
                {"scene_element_id": "red", "position_within_cell": "left", "depth": "midground",
                 "pose": {"summary": "Extending one hand to Schoolboy 2's shoulder", "gaze_target_element_id": "dark"}},
                {"scene_element_id": "dark", "position_within_cell": "center", "depth": "midground",
                 "pose": {"summary": "Leaning away with both hands raised", "gaze_target_element_id": "red"}},
                {"scene_element_id": "kaeldor", "position_within_cell": "right", "depth": "midground",
                 "pose": {"summary": "Standing at the right, one hand pointing toward the schoolboys", "gaze_target_element_id": "dark"},
                 "motion": {"state": "moving", "cue": "Entering the scene from the background, moving along the pathway."},
                 "placement_notes": "Kaeldor is approaching from the far side of the archway."},
            ],
            "interactions": [
                {"subject_element_id": "red", "relationship": "gently shoves", "target_element_id": "dark",
                 "note": "One hand on the shoulder; Schoolboy 2 leans away laughing."},
                {"subject_element_id": "kaeldor", "relationship": "points at", "target_element_id": "dark",
                 "note": "Kaeldor grins at the boys' antics from their right."},
            ],
            "image_inputs": [],
        }
        prompt = compile_qwen_scene_prompt(ir)

        self.assertIn("Exactly 3 visible characters appear once each", prompt)
        self.assertEqual(1, prompt.count("Kaeldor"))
        self.assertIn("Schoolboy 1", prompt)
        self.assertIn("Schoolboy 2", prompt)
        self.assertIn("Red-haired young elf", prompt)
        self.assertIn("Dark-haired young elf", prompt)
        self.assertIn("Tan elf with short light-brown hair", prompt)
        self.assertIn("Ivory shirt and burgundy waistcoat", prompt)
        self.assertNotIn("Gently pushing Schoolboy 2 at the shoulder while smiling", prompt)
        self.assertIn("gently shoves Schoolboy 2", prompt)
        self.assertLess(prompt.index("Schoolboy 1,"), prompt.index("Schoolboy 2,"))
        self.assertLess(prompt.index("Schoolboy 2,"), prompt.index("Kaeldor,"))
        self.assertIn("both hands raised", prompt)
        self.assertIn("No speech panels", prompt)
        self.assertNotIn("will be placed small", prompt)
        self.assertNotIn("approaching from the far side", prompt)
        self.assertNotIn("Entering the scene", prompt)
        self.assertNotIn("Kaeldor grins at the boys' antics", prompt)

        warnings = analyze_qwen_scene_prompt(ir)
        self.assertTrue(any(item["field"] == "placements[Kaeldor].placement_notes" for item in warnings))
        self.assertTrue(any(item["field"] == "composition.composition_notes" for item in warnings))
        self.assertTrue(any(item["field"] == "setup.environment.general_background_notes" for item in warnings))

    def test_stationary_scene_keeps_single_subject_and_visible_pose(self):
        prompt = compile_qwen_scene_prompt({
            "render_target": {"kind": "element_subscene"},
            "elements": [{"id": "elf", "display_name": "Tsaeytte", "element_type": "Character",
                          "fallback_visual_description": "Petite elf with violet eyes"}],
            "placements": [{"scene_element_id": "elf", "position_within_cell": "center",
                            "depth": "foreground", "pose": {"summary": "Holding a lantern"}}],
        })
        self.assertIn("Exactly one visible character appears once", prompt)
        self.assertIn("Holding a lantern", prompt)

    def test_assembled_scene_uses_group_reference_without_claiming_its_internal_count(self):
        prompt = compile_qwen_scene_prompt({
            "render_target": {"kind": "main"},
            "elements": [{"id": "group", "display_name": "Schoolboys group", "element_type": "Character"},
                         {"id": "tsaeytte", "display_name": "Tsaeytte", "element_type": "Character"}],
            "placements": [{"scene_element_id": "group", "position_within_cell": "left", "depth": "background"},
                           {"scene_element_id": "tsaeytte", "position_within_cell": "right", "depth": "foreground"}],
            "image_inputs": [{"role": "group_reference", "applies_to": "group",
                              "preserve": ["the accepted group's subjects and internal arrangement"]}],
        })
        self.assertIn("group reference for Schoolboys group", prompt)
        self.assertIn("Tsaeytte", prompt)
        self.assertNotIn("Exactly 2 visible characters", prompt)

    def test_conflicting_world_position_warns_and_structured_position_wins(self):
        ir = {
            "elements": [{"id": "elf", "display_name": "Tsaeytte", "element_type": "Character"}],
            "placements": [{"scene_element_id": "elf", "position_within_cell": "left", "depth": "midground",
                            "world_position": "Standing at the far right of the archway"}],
        }
        prompt = compile_qwen_scene_prompt(ir)
        warnings = analyze_qwen_scene_prompt(ir)
        self.assertIn("at left midground", prompt)
        self.assertNotIn("far right", prompt)
        self.assertTrue(any("different screen position" in item["message"] for item in warnings))

    def test_unclear_image_reference_role_is_reported(self):
        warnings = analyze_qwen_scene_prompt({
            "elements": [{"id": "elf", "display_name": "Tsaeytte"}],
            "image_inputs": [{"role": "visual_reference", "applies_to": "elf"}],
        })
        self.assertTrue(any(item["field"] == "image_inputs[1]" for item in warnings))


if __name__ == "__main__":
    unittest.main()
