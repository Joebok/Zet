import tempfile
import unittest
from pathlib import Path

from zet.services.chatgpt_prompt_contract import (
    build_image_inputs,
    compile_prompt_diagnostics,
    enrich_reference_files,
    manifest_contract,
    prompt_contract_values,
    write_prompt_diagnostics,
)


class ChatGptPromptContractTests(unittest.TestCase):
    def test_builds_stable_numbered_inputs_from_pipeline_roles(self):
        references = [
            {"role": "body_reference", "label": "Body", "path": "body.png"},
            {"role": "head_image", "label": "Head", "path": "head.png"},
        ]

        inputs = build_image_inputs(references, render_mode="composite")

        self.assertEqual([1, 2], [item["index"] for item in inputs])
        self.assertEqual(["edit_base", "subject_reference"], [item["role"] for item in inputs])
        prompt = prompt_contract_values("composite", inputs)
        self.assertIn("Image 1", prompt["CHATGPT_IMAGE_INPUTS"])
        self.assertIn("Image 2", prompt["CHATGPT_IMAGE_INPUTS"])
        self.assertIn("composition base", prompt["CHATGPT_CHANGE_PRESERVE_CONTRACT"])

    def test_render_mode_authority_rules_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "exactly one edit_base"):
            build_image_inputs([], render_mode="edit")
        with self.assertRaisesRegex(ValueError, "cannot contain an edit_base"):
            build_image_inputs([{"role": "head_image_source"}], render_mode="generate")
        with self.assertRaisesRegex(ValueError, "at most one edit_base"):
            build_image_inputs([
                {"role": "body_reference"},
                {"role": "character_assembly"},
            ], render_mode="composite")

    def test_manifest_and_legacy_references_share_the_same_order(self):
        references = [{"role": "character_assembly", "path": "source.png"}]
        inputs = build_image_inputs(references, render_mode="edit")
        enriched = enrich_reference_files(references, inputs)
        manifest = manifest_contract("edit", inputs)

        self.assertEqual(1, enriched[0]["image_index"])
        self.assertEqual("edit_base", enriched[0]["prompt_role"])
        self.assertEqual(inputs, manifest["image_inputs"])

    def test_diagnostics_reject_unresolved_placeholders_and_missing_image_markers(self):
        inputs = build_image_inputs([{"role": "identity_key", "path": "identity.png"}], render_mode="edit")
        diagnostics = compile_prompt_diagnostics("Change {{UNKNOWN}} and {{ASSET:unresolved}}.", inputs, "edit")

        self.assertTrue(any("UNKNOWN" in error for error in diagnostics["errors"]))
        self.assertTrue(any("ASSET:unresolved" in error for error in diagnostics["errors"]))
        self.assertTrue(any("Image 1" in error for error in diagnostics["errors"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Prompt_Compile_Diagnostics.json"
            with self.assertRaisesRegex(ValueError, "Invalid ChatGPT image prompt"):
                write_prompt_diagnostics(path, "Change {{UNKNOWN}}.", inputs, "edit")
            self.assertTrue(path.is_file())

    def test_custom_reference_metadata_is_preserved_without_reordering(self):
        references = [{
            "prompt_role": "style_reference",
            "label": "Ink treatment",
            "path": "style.png",
            "applies_to": "whole image",
            "preserve": ["line character"],
            "change": ["apply to the authored composition"],
            "ignore": ["source subjects"],
            "notes": "Use color handling only.",
        }]

        inputs = build_image_inputs(references, render_mode="generate")

        self.assertEqual("style_reference", inputs[0]["role"])
        self.assertEqual(["line character"], inputs[0]["preserve"])
        self.assertEqual(["apply to the authored composition"], inputs[0]["change"])
        self.assertEqual(["source subjects"], inputs[0]["ignore"])
        self.assertEqual("Use color handling only.", inputs[0]["notes"])

    def test_diagnostics_reject_unresolved_image_paths_and_warn_on_suspicious_conflicts(self):
        inputs = build_image_inputs([{"role": "identity_key", "label": "Identity"}], render_mode="edit")
        diagnostics = compile_prompt_diagnostics(
            "# Image Inputs\n\nImage 1 controls identity. The subject is walking while standing still.",
            inputs,
            "edit",
        )

        self.assertTrue(any("Unresolved ChatGPT image input path" in error for error in diagnostics["errors"]))
        self.assertTrue(any("action and posture" in warning for warning in diagnostics["warnings"]))


if __name__ == "__main__":
    unittest.main()
