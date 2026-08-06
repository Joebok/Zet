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
        self.assertIn("Use the Reference Body only to determine the fitted neck’s natural width, axis, and attachment position.", prompt)
        self.assertIn("Show a short-to-average, naturally proportioned upper-neck segment beneath the jaw.", prompt)
        self.assertIn("across the middle of the Reference Body’s natural neck segment", prompt)
        self.assertIn("Do not lengthen the neck to create space beneath the hairstyle", prompt)
        self.assertIn("extend below the neck cut into transparent space", prompt)
        self.assertIn("The cut edge may remain visible where the hairstyle naturally leaves it uncovered.", prompt)
        self.assertNotIn("mid-neck cut plane", prompt)
        self.assertNotIn("The output is incorrect if the neck is lengthened so that its lower cut edge appears beneath the hair.", prompt)
        self.assertNotIn("Character Head controls identity only", prompt)

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


if __name__ == "__main__":
    unittest.main()
