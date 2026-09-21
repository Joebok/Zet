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


if __name__ == "__main__":
    unittest.main()
