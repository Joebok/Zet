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

        self.assertIn("Preserve the gaze shown by the Character Head source.", prompt)
        self.assertNotIn("or toward the viewer", prompt)

    def test_non_front_gaze_is_not_redirected_toward_viewer(self) -> None:
        result = compile_character_assembly_job(
            self._job("LEFT_PROFILE", output_name="profile"),
            PROJECT_ROOT,
        )
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("Do not redirect the eyes independently of the head or toward the viewer.", prompt)

    def test_style_modes_emit_only_their_allowed_rendering_changes(self) -> None:
        matched = compile_character_assembly_job(self._job(output_name="matched"), PROJECT_ROOT)
        harmonized = compile_character_assembly_job(
            self._job(style_mode="HARMONIZE_STYLE", output_name="harmonized"),
            PROJECT_ROOT,
        )
        matched_prompt = Path(matched["final_prompt"]).read_text(encoding="utf-8")
        harmonized_prompt = Path(harmonized["final_prompt"]).read_text(encoding="utf-8")

        self.assertEqual("MATCHED_STYLE", matched["assembly_style_mode"])
        self.assertIn("Allow localized blending, antialiasing, shading adjustment", matched_prompt)
        self.assertIn("limited reconstruction", matched_prompt)
        self.assertNotIn("Harmonize the Character Head's line quality", matched_prompt)
        self.assertEqual("HARMONIZE_STYLE", harmonized["assembly_style_mode"])
        self.assertIn("Harmonize the Character Head's line quality, shading, and surface finish", harmonized_prompt)
        self.assertNotIn("limited reconstruction", harmonized_prompt)

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
        self.assertEqual(1, prompt.count("fitment clothing"))

    def test_prompt_uses_generic_source_controlled_identity_rules(self) -> None:
        result = compile_character_assembly_job(self._job(), PROJECT_ROOT)
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("Produce one coherent full-body character in one direct front view.", prompt)
        self.assertIn("selected character-phase identity", prompt)
        self.assertIn("age characteristics, species", prompt)
        self.assertIn("Preserve the hairstyle's defining length, shape, part, asymmetry, volume, and identity", prompt)
        self.assertIn("Adjust only local strand placement and overlap", prompt)
        self.assertIn("Do not invent or expose an ear that is naturally occluded", prompt)
        self.assertNotIn("Local skin-transition and shading harmonization", prompt)

    def test_prompt_uses_adaptive_quality_first_assembly_region(self) -> None:
        result = compile_character_assembly_job(self._job(), PROJECT_ROOT)
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")

        self.assertIn("adaptive assembly region is the neck and immediate neck/hair/shoulder junction", prompt)
        self.assertIn("Neither source is pixel-locked within this local region", prompt)
        self.assertIn("Final anatomical continuity takes priority", prompt)
        self.assertIn("overall shoulder placement, width, and silhouette", prompt)
        self.assertIn("Adjust the visible neck length only as needed", prompt)
        self.assertIn("Do not beautify, smooth, rejuvenate", prompt)
        for omitted in (
            "Use the smallest practical area of change",
            "Preserve all other pixels",
            "Everything below the replacement boundary",
            "owns everything below the head-replacement boundary",
            "fitted upper neck match",
            "Preserve the fitted hair silhouette exactly",
        ):
            self.assertNotIn(omitted, prompt)

    def test_character_template_is_not_loaded_or_parsed(self) -> None:
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
                result = compile_character_assembly_job(job, PROJECT_ROOT)
                prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                self.assertIn("selected character-phase identity", prompt)
                self.assertNotIn("IDENTITY_PRESERVATION_CORE", prompt)

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
