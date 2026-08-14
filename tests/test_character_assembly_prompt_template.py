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

    def test_front_gaze_is_preserved_without_viewer_prohibition(self) -> None:
        result = compile_character_assembly_job(self._job(), PROJECT_ROOT)
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("Preserve the Character Head's exact facial-plane direction, feature visibility, and supplied gaze.", prompt)
        self.assertNotIn("or toward the viewer", prompt)

    def test_non_front_gaze_is_not_redirected_toward_viewer(self) -> None:
        result = compile_character_assembly_job(
            self._job("LEFT_PROFILE", output_name="profile"),
            PROJECT_ROOT,
        )
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("Do not turn the face toward the viewer or reveal more of the face", prompt)

    def test_style_mode_is_recorded_without_changing_the_established_prompt(self) -> None:
        matched = compile_character_assembly_job(self._job(output_name="matched"), PROJECT_ROOT)
        harmonized = compile_character_assembly_job(
            self._job(style_mode="HARMONIZE_STYLE", output_name="harmonized"),
            PROJECT_ROOT,
        )
        matched_prompt = Path(matched["final_prompt"]).read_text(encoding="utf-8")
        harmonized_prompt = Path(harmonized["final_prompt"]).read_text(encoding="utf-8")

        self.assertEqual("MATCHED_STYLE", matched["assembly_style_mode"])
        self.assertEqual("HARMONIZE_STYLE", harmonized["assembly_style_mode"])
        self.assertEqual(matched_prompt, harmonized_prompt)

    def test_prompt_omits_superseded_generation_rules(self) -> None:
        result = compile_character_assembly_job(self._job(), PROJECT_ROOT)
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        for omitted in (
            "STANCE AND FOOT PLACEMENT",
            "Re-render the Character Head",
            "CANONICAL ART STYLE DIRECTIVE",
            "THREE-QUARTER ORIENTATION LOCK",
            "Negative constraints:",
            "TECHNICAL_MODESTY_LAYER",
            "adult identity",
            "Tsaeytte",
            "Elder Tsaeytte",
            "Core identity anchors",
            "Body preservation rules",
            "when shoulders are not rendered",
        ):
            self.assertNotIn(omitted, prompt)
        self.assertNotIn("fitment clothing", prompt)

    def test_prompt_uses_character_template_assembly_sections(self) -> None:
        self.template_path.write_text(
            """Canonical Art Style: `[Test canonical style]`
<!-- ZET:BEGIN CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS -->
Use the character-specific assembly rules.
Do not alter the character-specific head.
The character-specific head and body remain recognizable.
<!-- ZET:END CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS -->
""",
            encoding="utf-8",
        )
        result = compile_character_assembly_job(self._job(), PROJECT_ROOT)
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("Use the character-specific assembly rules.", prompt)
        self.assertIn("Do not alter the character-specific head.", prompt)
        self.assertIn("The character-specific head and body remain recognizable.", prompt)
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

    def test_mismatched_job_views_fail_before_artifact_generation(self) -> None:
        with self.assertRaises(TemplateCompileError) as raised:
            compile_character_assembly_job(
                self._job(head_view="LEFT_PROFILE", output_name="job-mismatch"),
                PROJECT_ROOT,
            )

        self.assertEqual("CHARACTER_ASSEMBLY_VIEW_MISMATCH", raised.exception.code)
        self.assertFalse((self.root / "job-mismatch" / "Final_Image_Prompt.md").exists())

    def test_missing_reference_view_fails_before_artifact_generation(self) -> None:
        body_reference = {"role": "body_reference", "path": str(self.body_path)}
        with self.assertRaises(TemplateCompileError) as raised:
            compile_character_assembly_job(
                self._job(body_reference=body_reference, output_name="missing-view"),
                PROJECT_ROOT,
            )

        self.assertEqual("MISSING_REFERENCE_VIEW", raised.exception.code)
        self.assertFalse((self.root / "missing-view" / "Final_Image_Prompt.md").exists())

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

    def test_explicit_provenance_mismatch_is_rejected(self) -> None:
        body_reference = {
            "role": "body_reference",
            "path": str(self.body_path),
            "body_view": "FRONT",
            "character": "Other",
        }
        with self.assertRaises(TemplateCompileError) as raised:
            compile_character_assembly_job(
                self._job(body_reference=body_reference, output_name="provenance-mismatch"),
                PROJECT_ROOT,
            )

        self.assertEqual("CHARACTER_ASSEMBLY_REFERENCE_MISMATCH", raised.exception.code)

    def test_invalid_style_mode_is_rejected_before_artifact_generation(self) -> None:
        with self.assertRaises(TemplateCompileError) as raised:
            compile_character_assembly_job(
                self._job(style_mode="REPAINT_ALL", output_name="invalid-mode"),
                PROJECT_ROOT,
            )

        self.assertEqual("INVALID_ASSEMBLY_STYLE_MODE", raised.exception.code)
        self.assertFalse((self.root / "invalid-mode" / "Final_Image_Prompt.md").exists())


if __name__ == "__main__":
    unittest.main()
