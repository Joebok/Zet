import unittest

from zet.services.scene_prompt_cleanup import cleanup_compiled_scene_prompt


class ScenePromptCleanupTests(unittest.TestCase):
    def test_normalizes_punctuation_and_known_boundary_phrase(self):
        prompt = cleanup_compiled_scene_prompt("The scene takes place On the pathway..\nShe looks at Valindia,.\n")

        self.assertEqual("The scene takes place on the pathway.\nShe looks at Valindia.\n", prompt)

    def test_preserves_reference_tags_exactly(self):
        tag = "{{ASSET:Tsaeytte:Youth:26:Costume | Front-Left-3-4 | Woodland outfit}}"

        self.assertIn(tag, cleanup_compiled_scene_prompt(f"- {tag}\n"))

    def test_formats_environment_as_bullets(self):
        prompt = cleanup_compiled_scene_prompt("# Environment\n\na few books are scattered on the pathway.\n")

        self.assertEqual("# Environment\n\n- A few books are scattered on the pathway.\n", prompt)

    def test_suppresses_only_exact_override_sentences(self):
        prompt = cleanup_compiled_scene_prompt(
            "# Interactions\n\n- Valindia is holding one of the books out to Tsaeytte.\n\n"
            "# Scene Element Preservation\n\n**Element Override:** Valindia is holding one of the books out to Tsaeytte. Valindia remains too far away for Tsaeytte to reach it.\n"
        )

        self.assertIn("**Element Override:** Valindia remains too far away for Tsaeytte to reach it.", prompt)
        self.assertEqual(1, prompt.count("Valindia is holding one of the books out to Tsaeytte."))

    def test_preserves_non_exact_override_text(self):
        prompt = cleanup_compiled_scene_prompt(
            "- Valindia reluctantly extends a book toward Tsaeytte.\n"
            "**Element Override:** Valindia is holding one of the books out to Tsaeytte.\n"
        )

        self.assertIn("**Element Override:** Valindia is holding one of the books out to Tsaeytte.", prompt)


if __name__ == "__main__":
    unittest.main()
