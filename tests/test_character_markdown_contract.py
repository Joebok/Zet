import json
import tempfile
import unittest
from pathlib import Path

from Scripts.Compile_Character_Template import load_template_sections
from zet.services.character_onboarding_service import CharacterOnboardingError, CharacterOnboardingService
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
        metadata = json.loads((PROJECT_ROOT / "Config" / "Prompt_Section_Metadata.json").read_text(encoding="utf-8"))["sections"]
        expected = set()
        for name in metadata:
            if name.startswith(("COSTUME_", "EQUIPMENT_")) or name == "SCENE_COSTUME_IDENTITY":
                continue
            expected.update(name.replace("{VIEW}", view) for view in VIEWS) if "{VIEW}" in name else expected.add(name)
        self.assertEqual(expected, set(sections))
        self.assertFalse(any(name.startswith("TECHNICAL_MODESTY_LAYER") for name in sections))
        self.assertFalse(any("PICARESQUE" in name for name in sections))
        global_sections = load_template_sections(PROJECT_ROOT / "Config" / "Prompt_Global_Sections.md")
        self.assertEqual(
            {
                "TECHNICAL_MODESTY_LAYER_DEFAULT",
                "TECHNICAL_MODESTY_LAYER_ADULT_FEMININE",
                "TECHNICAL_MODESTY_LAYER_ADULT_MASCULINE",
                "TECHNICAL_MODESTY_LAYER_YOUTH",
            },
            {name for name in global_sections if name.startswith("TECHNICAL_MODESTY_LAYER")},
        )

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

    def test_new_character_upload_does_not_replace_existing_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            template_path = paths.character_template_path("Test", "Adult")
            template_path.parent.mkdir(parents=True)
            template_path.write_text("existing", encoding="utf-8")
            service = CharacterOnboardingService(paths, PROJECT_ROOT)

            with self.assertRaisesRegex(CharacterOnboardingError, "already exists"):
                service.upload_template("Test", "Adult", "replacement", create_only=True)

            self.assertEqual("existing", template_path.read_text(encoding="utf-8"))

    def test_new_character_upload_without_source_phase_writes_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._paths(Path(temp_dir))
            paths.character_path("New Hero", "Adult").mkdir(parents=True)
            service = CharacterOnboardingService(paths, PROJECT_ROOT)
            service.validate_template = lambda template_path: ["incomplete"]

            status = service.upload_template("New Hero", "Adult", "uploaded", create_only=True)

            self.assertTrue(status.template_exists)
            self.assertEqual(
                "uploaded",
                paths.character_template_path("New Hero", "Adult").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
