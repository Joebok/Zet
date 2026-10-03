import unittest

from zet.services.qwen_scene_prompt import compile_qwen_scene_prompt


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
        self.assertIn("<image1> supplies the subject reference for Tsaeytte, preserving facial identity", prompt)

    def test_dialogue_layout_fields_reach_the_render_prompt(self):
        prompt = compile_qwen_scene_prompt({
            "elements": [{"id": "elf", "display_name": "Tsaeytte"}],
            "dialogue": [{"speaker_element_id": "elf", "text": "Potential is nothing without discipline",
                          "max_lines": 2, "pointer_target": "speaker mouth",
                          "notes": "Ivory rectangular box beside Tsaeytte, clear of the arch inscription"}],
        })
        self.assertIn('speech panel for Tsaeytte reading exactly "Potential is nothing without discipline"', prompt)
        self.assertIn("at most 2 lines", prompt)
        self.assertIn("pointer aims at speaker mouth", prompt)
        self.assertIn("Ivory rectangular box beside Tsaeytte, clear of the arch inscription", prompt)

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
        self.assertIn("change turn toward the other boy", prompt)
        self.assertIn("ignore source background", prompt)
        self.assertIn("Reference note for <image1>: Keep freckles visible", prompt)
        self.assertIn("use as costume reference for Dark-haired boy", prompt)
        self.assertIn("Preserve for this <image1> assignment: burgundy waistcoat", prompt)
        self.assertIn("Red-haired boy gently pushes Dark-haired boy, at the shoulder", prompt)
        self.assertIn("Both boys remain fully visible", prompt)


if __name__ == "__main__":
    unittest.main()
