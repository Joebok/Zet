from __future__ import annotations

import shutil
import tempfile
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
from zet.services.pipeline_compiler_support import load_race_render_rules, load_view_data, technical_modesty_variant, view_instruction


class BodyReferenceRaceRulesTests(unittest.TestCase):
    def test_technical_modesty_variant_matrix(self) -> None:
        cases = {
            ("Adult", "female"): "TECHNICAL_MODESTY_LAYER_ADULT_FEMININE",
            ("adult", "Masculine man"): "TECHNICAL_MODESTY_LAYER_ADULT_MASCULINE",
            ("Adult", "neutral"): "TECHNICAL_MODESTY_LAYER_DEFAULT",
            ("Youth", "female"): "TECHNICAL_MODESTY_LAYER_YOUTH",
            ("pre-youth", "male"): "TECHNICAL_MODESTY_LAYER_YOUTH",
            ("Youth", "unknown"): "TECHNICAL_MODESTY_LAYER_YOUTH",
            ("Elder", "feminine woman"): "TECHNICAL_MODESTY_LAYER_DEFAULT",
            ("Ancient", "masculine man"): "TECHNICAL_MODESTY_LAYER_DEFAULT",
        }
        for values, expected in cases.items():
            with self.subTest(phase=values[0], gender=values[1]):
                self.assertEqual(expected, technical_modesty_variant(*values))
    def _write_config(self, root: Path) -> None:
        (root / "config.toml").write_text(
            f"""[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "_Lib/Characters"
BaseAssetPath = "_Lib/Assets"
BasePipelinePath = "_Lib/Pipelines"
BaseAIQueuePath = "_Lib/AI_Queue"
""",
            encoding="utf-8",
        )

    def _write_shared_stance_sections(self, root: Path, extra_sections: str = "") -> None:
        shared_dir = root / "Shared_Library" / "Characters" / "_Shared"
        shared_dir.mkdir(parents=True, exist_ok=True)
        (shared_dir / "Character_Template.md").write_text(
            f"""# Shared Character Template

<!-- ZET:BEGIN NEUTRAL_POSE_STANCE -->
* Shared neutral stance.
* For {{VIEW}} view.
<!-- ZET:END NEUTRAL_POSE_STANCE -->

<!-- ZET:BEGIN NEUTRAL_POSE_STANCE_VIEW_FRONT -->
* Shared front stance.
<!-- ZET:END NEUTRAL_POSE_STANCE_VIEW_FRONT -->

{extra_sections}
""",
            encoding="utf-8",
        )

    def test_high_elf_species_injects_elf_body_reference_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(PROJECT_ROOT / "Config", root / "Config")
            self._write_config(root)
            self._write_shared_stance_sections(root)

            character_dir = root / "_Lib" / "Characters" / "Testa" / "Adult"
            character_dir.mkdir(parents=True)
            (character_dir / "Character.md").write_text(
                """# Character Image Template

Character Name: `[Testa]`
Character Phase: `[Adult]`
Species / Ancestry: `[High elf]`
Canonical Art Style: `[ink and watercolor reference art]`
Gender Presentation: `[Feminine adult woman]`

<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
* Adult high-elf woman.
* Finished portrait markers: amber eyes, blue skin, braided hair, and elaborate age lines.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
* Lithe body proportions.
<!-- ZET:END BODY_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
* Preserve body proportions only.
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->

<!-- ZET:BEGIN BODY_REFERENCE_CHARACTER_REQUIREMENTS -->
* Painterly semi-realistic fantasy illustration.
<!-- ZET:END BODY_REFERENCE_CHARACTER_REQUIREMENTS -->

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER -->
* Use simple neutral fitment clothing: a plain tank top and shorts.
<!-- ZET:END TECHNICAL_MODESTY_LAYER -->

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
* Preserve the finished face and braided hair.
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
* Preserve amber eyes and elaborate age lines.
<!-- ZET:END NEGATIVE_GUIDANCE_JOB_SPECIFIC -->
""",
                encoding="utf-8",
            )

            result = compile_body_reference_job(
                {
                    "Job": "test-body-front",
                    "Task": "body-reference",
                    "Character": "Testa",
                    "Phase": "Adult",
                    "Body View": "front",
                },
                root,
            )

            prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
            self.assertIn("Adult elf female", prompt)
            self.assertNotIn("{{CHARACTER_GENDER}}", prompt)
            self.assertIn("Use a neutral anatomical reference stance.", prompt)
            self.assertNotIn("{VIEW}", prompt)
            self.assertIn("For FRONT view:", prompt)
            self.assertIn("The mannequin head must face the same direct FRONT view as the body.", prompt)
            self.assertIn("Use a simplified neutral light-gray elf mannequin head.", prompt)
            self.assertIn("Long pointed elf ears rendered as neutral mannequin geometry.", prompt)
            self.assertIn("Missing, hidden, rounded, or human ears.", prompt)
            self.assertEqual(prompt.count("MANNEQUIN HEAD — REQUIRED"), 1)
            self.assertIn("Painterly semi-realistic fantasy illustration.", prompt)
            self.assertIn("simple neutral fitment clothing", prompt)
            self.assertIn("olive green tube top", prompt)
            self.assertNotIn("tan tube top", prompt.lower())
            self.assertNotIn("tan compression shorts", prompt.lower())
            source_map = json.loads((Path(result["final_prompt"]).parent / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
            modesty = next(item for item in source_map["fragments"] if item.get("section_name") == "TECHNICAL_MODESTY_LAYER")
            self.assertEqual("TECHNICAL_MODESTY_LAYER_ADULT_FEMININE", modesty["selected_variant"])
            self.assertIn("Lithe body proportions.", prompt)
            self.assertNotIn("Preserve body proportions only.", prompt)
            self.assertNotIn("Generic replacement face.", prompt)
            self.assertNotIn("Finished portrait markers", prompt)
            self.assertNotIn("amber eyes", prompt)
            self.assertNotIn("blue skin", prompt)
            self.assertNotIn("braided hair", prompt)
            self.assertNotIn("elaborate age lines", prompt)
            self.assertNotIn("CRITICAL OVERRIDE", prompt)
            self.assertNotIn("HEAD REQUIREMENTS", prompt)
            self.assertNotIn("HEAD OVERRIDE", prompt)
            self.assertNotIn("THREE-QUARTER ORIENTATION LOCK", prompt)
            self.assertNotIn("{{", prompt)



    def test_body_reference_view_orientation_details_match_configured_view(self) -> None:
        view_tokens = (
            "FRONT", "FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4",
            "BACK", "BACK_RIGHT_3_4", "RIGHT_PROFILE", "FRONT_RIGHT_3_4",
        )
        for view_token in view_tokens:
            with self.subTest(view=view_token):
                view_data = load_view_data(PROJECT_ROOT, view_token)
                instruction = view_instruction(
                    view_data,
                    "body",
                    "body-reference",
                    include_intro=True,
                )
                self.assertIn(view_data["orientation_sentence"], instruction)
                self.assertIn("Do not rotate the head independently of the body.", instruction)
                camera_position = view_data.get("camera_position", "")
                if camera_position:
                    self.assertIn(camera_position, instruction)
                else:
                    self.assertNotIn("The camera is positioned", instruction)





if __name__ == "__main__":
    unittest.main()
