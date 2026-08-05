import json
import tempfile
import unittest
from pathlib import Path

from Scripts.Compile_Character_Template import load_template_sections
from zet.services.character_onboarding_service import CharacterOnboardingService
from zet.services.config_service import Config
from zet.services.path_service import PathService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIEWS = [
    "FRONT",
    "FRONT_LEFT_3_4",
    "FRONT_RIGHT_3_4",
    "LEFT_PROFILE",
    "RIGHT_PROFILE",
    "BACK_LEFT_3_4",
    "BACK_RIGHT_3_4",
    "BACK",
]


class CharacterMarkdownContractTests(unittest.TestCase):
    def _paths(self, root: Path) -> PathService:
        config = Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )
        return PathService(config, PROJECT_ROOT)

    def test_character_template_covers_active_character_sections(self) -> None:
        sections = load_template_sections(
            PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
        )
        bundles = json.loads((PROJECT_ROOT / "Config" / "Prompt_Task_Bundles.json").read_text(encoding="utf-8"))["bundles"]
        required = {"IDENTITY_PRESERVATION_SCENE", "IDENTITY_PRESERVATION_EYES"}
        for name in ["body-reference", "head-fitment", "character-assembly", "expression"]:
            for section in bundles[name].get("required_sections", []):
                if section == "IDENTITY_PRESERVATION_COSTUME":
                    continue
                if "{VIEW}" in section:
                    required.update(section.replace("{VIEW}", view) for view in VIEWS)
                else:
                    required.add(section)
        self.assertEqual(set(), required - set(sections))

    def test_canonical_character_path_is_character_md(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            self.assertEqual(
                Path(temp_dir) / "Characters" / "Tsaeytte" / "Adult" / "Character.md",
                paths.character_template_path("Tsaeytte", "Adult"),
            )

    def test_shared_placeholder_character_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = self._paths(root)
            phase = paths.character_path("Test", "Adult")
            phase.mkdir(parents=True)
            template = (PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md").read_text(encoding="utf-8")
            for old, new in {
                "[Character Name]": "[Test]",
                "[Adult / Youth / Variant / Costume Phase]": "[Adult]",
                "[Species]": "[Human]",
                "[Optional, non-sensitive rendering descriptor]": "[Masculine Adult]",
                "[Painterly semi-realistic, anime-influenced facial proportions, etc.]": "[Painterly]",
            }.items():
                template = template.replace(old, new, 1)
            paths.character_template_path("Test", "Adult").write_text(template, encoding="utf-8")
            service = CharacterOnboardingService(paths, PROJECT_ROOT)
            errors = service.validate_template(paths.character_template_path("Test", "Adult"))
            self.assertTrue(any("shared template placeholder text" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
