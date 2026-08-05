from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job


class BodyReferenceRaceRulesTests(unittest.TestCase):
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
            (character_dir / "Character_Image_Template.md").write_text(
                """# Character Image Template

Character Name: `[Testa]`
Character Phase: `[Adult]`
Species / Ancestry: `[High elf]`
Canonical Art Style: `[ink and watercolor reference art]`
Gender Presentation: `[Feminine adult woman]`

<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
* Adult high-elf woman.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
* Lithe body proportions.
<!-- ZET:END BODY_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
* Preserve body proportions only.
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->

<!-- ZET:BEGIN BODY_REFERENCE_RENDERING_RULES -->
* Render as a technical fitment image.
<!-- ZET:END BODY_REFERENCE_RENDERING_RULES -->

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER -->
* Plain tank top and shorts.
<!-- ZET:END TECHNICAL_MODESTY_LAYER -->

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
* No costume.
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->
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
            self.assertIn("Shared neutral stance.", prompt)
            self.assertIn("For FRONT view.", prompt)
            self.assertNotIn("{VIEW}", prompt)
            self.assertIn("Shared front stance.", prompt)
            self.assertIn("Character race/species for mannequin silhouette: elf.", prompt)
            self.assertIn("Use a simplified elf mannequin head.", prompt)
            self.assertIn("Long pointed elf ears should be visible", prompt)
            self.assertIn("Do not use human rounded ears.", prompt)
            self.assertNotIn("{{", prompt)

    def test_shared_feminine_modesty_layer_is_used_when_character_section_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(PROJECT_ROOT / "Config", root / "Config")
            self._write_config(root)

            self._write_shared_stance_sections(
                root,
                """

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER -->
* default shared fitment clothing.
<!-- ZET:END TECHNICAL_MODESTY_LAYER -->

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER_FEMININE -->
* shared feminine tube top.
* shared feminine compression shorts.
<!-- ZET:END TECHNICAL_MODESTY_LAYER_FEMININE -->

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER_MASCULINE -->
* shared masculine compression shorts.
<!-- ZET:END TECHNICAL_MODESTY_LAYER_MASCULINE -->
""",
            )

            character_dir = root / "_Lib" / "Characters" / "Testa" / "Adult"
            character_dir.mkdir(parents=True)
            (character_dir / "Character_Image_Template.md").write_text(
                """# Character Image Template

Character Name: `[Testa]`
Character Phase: `[Adult]`
Species / Ancestry: `[High elf]`
Gender Presentation: `[Feminine adult woman]`

<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
* Adult high-elf woman.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
* Lithe body proportions.
<!-- ZET:END BODY_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
* Preserve body proportions only.
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->

<!-- ZET:BEGIN BODY_REFERENCE_RENDERING_RULES -->
* Render as a technical fitment image.
<!-- ZET:END BODY_REFERENCE_RENDERING_RULES -->

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
* No costume.
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->
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
            self.assertIn("shared feminine tube top.", prompt)
            self.assertIn("shared feminine compression shorts.", prompt)
            self.assertNotIn("default shared fitment clothing", prompt)

    def test_unknown_species_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(PROJECT_ROOT / "Config", root / "Config")
            self._write_config(root)
            self._write_shared_stance_sections(root)

            character_dir = root / "_Lib" / "Characters" / "Mystery" / "Adult"
            character_dir.mkdir(parents=True)
            (character_dir / "Character_Image_Template.md").write_text(
                """# Character Image Template

Character Name: `[Mystery]`
Character Phase: `[Adult]`
Species / Ancestry: `[Starlight being]`

<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
* Adult.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
* Ordinary proportions.
<!-- ZET:END BODY_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
* Preserve proportions.
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->

<!-- ZET:BEGIN BODY_REFERENCE_RENDERING_RULES -->
* Render as a technical fitment image.
<!-- ZET:END BODY_REFERENCE_RENDERING_RULES -->

<!-- ZET:BEGIN TECHNICAL_MODESTY_LAYER -->
* Plain tank top and shorts.
<!-- ZET:END TECHNICAL_MODESTY_LAYER -->

<!-- ZET:BEGIN NEGATIVE_GUIDANCE_GENERAL -->
* No costume.
<!-- ZET:END NEGATIVE_GUIDANCE_GENERAL -->
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TemplateCompileError, "Unknown character race/species"):
                compile_body_reference_job(
                    {
                        "Job": "test-body-front",
                        "Task": "body-reference",
                        "Character": "Mystery",
                        "Phase": "Adult",
                        "Body View": "front",
                    },
                    root,
                )


if __name__ == "__main__":
    unittest.main()
