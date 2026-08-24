import json
import tempfile
import unittest
from pathlib import Path

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Character_Assembly_Jobs import PROJECT_ROOT, compile_character_assembly_job


class CharacterAssemblyPromptTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.template_path = self.root / "Character.md"
        self.template_path.write_text("Canonical Art Style: `[Test canonical style]`\n", encoding="utf-8")
        self.body_path = self.root / "body.png"
        self.head_path = self.root / "head.png"
        self.body_path.write_bytes(b"body")
        self.head_path.write_bytes(b"head")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _job(
        self,
        view: str = "FRONT",
        *,
        head_view: str | None = None,
        style_mode: str | None = None,
        body_reference: dict | None = None,
        head_image: dict | None = None,
        output_name: str = "output",
    ) -> dict:
        references = [
            body_reference
            or {
                "role": "body_reference",
                "path": str(self.body_path),
                "body_view": view,
                "character": "Test",
                "phase": "Adult",
            },
            head_image
            or {
                "role": "head_image",
                "path": str(self.head_path),
                "body_view": view,
                "head_view": view,
                "character": "Test",
                "phase": "Adult",
            },
        ]
        job = {
            "Job": f"assembly-{view}",
            "Task": "character-assembly",
            "Character": "Test",
            "Phase": "Adult",
            "Body View": view,
            "Head View": head_view or view,
            "Template Path": str(self.template_path),
            "Output Directory": str(self.root / output_name),
            "Reference Files": references,
        }
        if style_mode is not None:
            job["Assembly Style Mode"] = style_mode
        return job

    def test_all_views_emit_only_the_selected_view_instruction(self) -> None:
        view_config = json.loads((PROJECT_ROOT / "Config" / "Prompt_View_Text.json").read_text(encoding="utf-8"))["views"]
        assembly_instructions = {
            token: data["body_instructions"]["character-assembly"]
            for token, data in view_config.items()
        }

        for token, expected_instruction in assembly_instructions.items():
            with self.subTest(view=token):
                result = compile_character_assembly_job(
                    self._job(token, output_name=f"output-{token}"),
                    PROJECT_ROOT,
                )
                prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                self.assertIn(expected_instruction, prompt)
                for other_token, other_instruction in assembly_instructions.items():
                    if other_token != token:
                        self.assertNotIn(other_instruction, prompt)
                self.assertNotIn("{{", prompt)






    def test_prompt_uses_minimal_junction_scoped_assembly_contract(self) -> None:
        result = compile_character_assembly_job(self._job(), PROJECT_ROOT)
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("Keep the face, hair, ears, and apparent age of the head exactly as they are.", prompt)
        self.assertIn("Keep the body proportions, pose, stance, framing, and orientation exactly as they are.", prompt)
        self.assertIn("Make only the changes needed to join the head and neck naturally.", prompt)
        self.assertNotIn("{{", prompt)

    def test_missing_or_malformed_character_template_is_rejected(self) -> None:
        malformed_path = self.root / "Malformed.md"
        malformed_path.write_text("<!-- ZET:BEGIN IDENTITY_PRESERVATION_CORE -->\n", encoding="utf-8")
        missing_path = self.root / "Missing.md"

        for template_path, output_name in (
            (malformed_path, "malformed-template"),
            (missing_path, "missing-template"),
        ):
            with self.subTest(template_path=template_path):
                job = self._job(output_name=output_name)
                job["Template Path"] = str(template_path)
                with self.assertRaises(TemplateCompileError) as raised:
                    compile_character_assembly_job(job, PROJECT_ROOT)
                expected = "MALFORMED_TEMPLATE_MARKERS" if template_path.exists() else "MISSING_TEMPLATE"
                self.assertEqual(expected, raised.exception.code)
                self.assertFalse((self.root / output_name / "Final_Image_Prompt.md").exists())



    def test_mismatched_reference_view_fails_before_artifact_generation(self) -> None:
        head_image = {
            "role": "head_image",
            "path": str(self.head_path),
            "body_view": "FRONT",
            "head_view": "LEFT_PROFILE",
        }
        with self.assertRaises(TemplateCompileError) as raised:
            compile_character_assembly_job(
                self._job(head_image=head_image, output_name="reference-mismatch"),
                PROJECT_ROOT,
            )

        self.assertEqual("CHARACTER_ASSEMBLY_VIEW_MISMATCH", raised.exception.code)
        self.assertFalse((self.root / "reference-mismatch" / "Final_Image_Prompt.md").exists())




if __name__ == "__main__":
    unittest.main()
