from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "Config" / "Prompt_Templates" / "head_fitment_v1.md"


class HeadFitmentPromptTemplateTests(unittest.TestCase):
    def test_neck_fitment_uses_a_single_concrete_cut_plane(self) -> None:
        prompt = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("neck-column anchor", prompt.lower())
        self.assertNotIn("base-neck docking", prompt.lower())
        self.assertNotIn("petite frame", prompt.lower())
        self.assertNotIn("docking", prompt.lower())
        self.assertIn("NECK FITMENT", prompt)
        self.assertIn("short-to-average in length", prompt)
        self.assertIn("Hair may hang lower than the neck", prompt)
        self.assertIn("may hide the neck cut", prompt)


if __name__ == "__main__":
    unittest.main()
