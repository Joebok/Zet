from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from Compile_Character_Template import TemplateCompileError
from Run_Body_Reference_Jobs import compile_body_reference_job


class BodyReferenceRaceRulesTests(unittest.TestCase):
    def test_high_elf_species_injects_elf_body_reference_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(PROJECT_ROOT / "Config", root / "Config")

            character_dir = root / "_Lib" / "Characters" / "Testa" / "Adult"
            character_dir.mkdir(parents=True)
            (character_dir / "Character_Image_Template.md").write_text(
                """# Character Image Template

Character Name: `[Testa]`
Character Phase: `[Adult]`
Species / Ancestry: `[High elf]`

<!-- ZET:BEGIN GENERAL_DESCRIPTION_FACTS -->
* Adult high-elf woman.
<!-- ZET:END GENERAL_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->
* Lithe body proportions.
<!-- ZET:END BODY_DESCRIPTION_FACTS -->

<!-- ZET:BEGIN IDENTITY_PRESERVATION_BODY -->
* Preserve body proportions only.
<!-- ZET:END IDENTITY_PRESERVATION_BODY -->

<!-- ZET:BEGIN FITMENT_RENDERING_RULES -->
* Render as a technical fitment image.
<!-- ZET:END FITMENT_RENDERING_RULES -->

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
            self.assertIn("Character race/species for mannequin silhouette: elf.", prompt)
            self.assertIn("Use a simplified elf mannequin head.", prompt)
            self.assertIn("Long pointed elf ears should be visible", prompt)
            self.assertIn("Do not use human rounded ears.", prompt)
            self.assertNotIn("{{", prompt)

    def test_unknown_species_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(PROJECT_ROOT / "Config", root / "Config")

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

<!-- ZET:BEGIN FITMENT_RENDERING_RULES -->
* Render as a technical fitment image.
<!-- ZET:END FITMENT_RENDERING_RULES -->

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
