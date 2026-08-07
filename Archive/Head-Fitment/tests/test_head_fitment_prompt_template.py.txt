import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "Config" / "Prompt_Templates" / "head_fitment_v1.md"
VIEW_CONFIG_PATH = PROJECT_ROOT / "Config" / "Prompt_View_Text.json"
BODY_VIEW_INSTRUCTION = (
    "Use the Reference Body only to match the fitted neck’s width, axis, and cut position in the requested view. "
    "The Character Head source controls the head pose, face, hair, expression, and identity. "
    "Do not reproduce any body geometry from the Reference Body."
)


class HeadFitmentPromptTemplateTests(unittest.TestCase):
    def test_neck_fitment_uses_a_single_concrete_cut_plane(self) -> None:
        prompt = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("neck-column anchor", prompt.lower())
        self.assertNotIn("base-neck docking", prompt.lower())
        self.assertNotIn("petite frame", prompt.lower())
        self.assertNotIn("docking", prompt.lower())
        self.assertIn("NECK FITMENT", prompt)
        self.assertIn("Use the Reference Body only to determine the fitted neck’s natural width, axis, and cut position.", prompt)
        self.assertNotIn("attachment position", prompt)
        self.assertIn("Cut the image across the upper neck, well above where the neck begins to widen", prompt)
        self.assertIn("Only the upper neck beneath the jaw is visible.", prompt)
        self.assertNotIn("middle of the Reference Body’s natural neck segment", prompt)
        self.assertIn(
            "The output fails if any shoulder slope, trapezius, collarbone, chest, torso, or body geometry is visible, "
            "or if the neck widens into the shoulders.",
            prompt,
        )
        self.assertEqual(1, prompt.count("shoulder slope"))
        self.assertNotIn("bust wrap", prompt)
        self.assertIn("Do not lengthen the neck to create space beneath the hairstyle", prompt)
        self.assertIn("extend below the neck cut into transparent space", prompt)
        self.assertIn("The cut edge may remain visible where the hairstyle naturally leaves it uncovered.", prompt)
        self.assertNotIn("mid-neck cut plane", prompt)
        self.assertNotIn("The output is incorrect if the neck is lengthened so that its lower cut edge appears beneath the hair.", prompt)
        self.assertNotIn("Character Head controls identity only", prompt)

    def test_source_rendering_is_locked_without_character_description_injections(self) -> None:
        prompt = TEMPLATE_PATH.read_text(encoding="utf-8")
        bundle = json.loads((PROJECT_ROOT / "Config" / "Prompt_Task_Bundles.json").read_text(encoding="utf-8"))["bundles"]["head-fitment"]

        self.assertIn("SOURCE RENDERING LOCK", prompt)
        self.assertIn("Do not beautify, idealize, smooth, rejuvenate", prompt)
        self.assertIn("Do not reinterpret the head from the textual character description.", prompt)
        self.assertIn("do not reapply a generalized art style", prompt)
        self.assertIn("through the complete jaw and chin", prompt)
        self.assertIn("protected head pixels must be copied from the source after rendering", prompt)
        self.assertNotIn("above the jawline", prompt)
        self.assertNotIn("art-style conversion if required", prompt)
        self.assertNotIn("{{SECTION:GENERAL_DESCRIPTION_FACTS}}", prompt)
        self.assertNotIn("{{SECTION:HEAD_DESCRIPTION_FACTS}}", prompt)
        self.assertNotIn("{{SECTION:HAIR_DESCRIPTION_FACTS}}", prompt)
        self.assertNotIn("{{SECTION:IDENTITY_PRESERVATION_FACE}}", prompt)
        self.assertNotIn("{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}", prompt)
        self.assertNotIn("generic replacement face", prompt)
        self.assertNotIn("long hair, curly hair, helmet hair", prompt)
        self.assertEqual(["HEAD_FITMENT_RENDERING_RULES"], bundle["required_sections"])
        self.assertEqual([], bundle["optional_sections"])

    def test_all_views_use_generic_body_authority_and_distinct_head_instructions(self) -> None:
        config = json.loads(VIEW_CONFIG_PATH.read_text(encoding="utf-8"))
        views = config["views"]

        self.assertEqual(8, len(views))
        self.assertEqual(8, len({view["head_instructions"]["head-fitment"] for view in views.values()}))
        for view in views.values():
            self.assertEqual(BODY_VIEW_INSTRUCTION, view["body_instructions"]["head-fitment"])
            self.assertNotIn(
                "camera angle, torso direction, shoulder direction",
                view["body_instructions"]["head-fitment"],
            )

    def test_three_quarter_orientation_lock_is_only_in_three_quarter_view_instructions(self) -> None:
        prompt = TEMPLATE_PATH.read_text(encoding="utf-8")
        views = json.loads(VIEW_CONFIG_PATH.read_text(encoding="utf-8"))["views"]

        self.assertNotIn("THREE-QUARTER ORIENTATION LOCK", prompt)
        for token, view in views.items():
            instruction = view["head_instructions"]["head-fitment"]
            expected_count = 1 if token.endswith("_3_4") else 0
            self.assertEqual(expected_count, instruction.count("THREE-QUARTER ORIENTATION LOCK"), token)


if __name__ == "__main__":
    unittest.main()
