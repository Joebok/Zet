from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from Scripts.Run_Expression_Jobs import compile_expression_job


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _section(name: str, value: str) -> str:
    return f"<!-- ZET:BEGIN {name} -->\n{value}\n<!-- ZET:END {name} -->\n"


class ExpressionCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.library = self.root / "library"
        config_dir = self.root / "Config"
        prompt_dir = config_dir / "Prompt_Templates"
        prompt_dir.mkdir(parents=True)
        for name in (
            "Prompt_Task_Bundles.json",
            "Prompt_View_Text.json",
            "Prompt_View_Aliases.json",
            "Prompt_Background_Text.json",
        ):
            shutil.copyfile(PROJECT_ROOT / "Config" / name, config_dir / name)
        shutil.copyfile(PROJECT_ROOT / "Config" / "Prompt_Templates" / "expression_v1.md", prompt_dir / "expression_v1.md")
        self.root.joinpath("config.toml").write_text(
            "\n".join(
                [
                    "[BaseFolders]",
                    f'BaseLibraryPath = "{self.library.as_posix()}"',
                    'BaseCharacterPath = "Characters"',
                    'BaseAssetPath = "Assets"',
                    'BasePipelinePath = "Pipelines"',
                    'BaseAIQueuePath = "AI_Queue"',
                ]
            ),
            encoding="utf-8",
        )
        self.character_dir = self.library / "Characters" / "Test" / "Adult"
        self.character_dir.mkdir(parents=True)
        self.character_dir.joinpath("Character.md").write_text(
            "Character Name: `[Test]`\nCharacter Phase: `[Adult]`\nCanonical Art Style: `[Painterly]`\n\n"
            + _section("EXPRESSION_DESCRIPTION_FACTS", "Keep expressions readable.")
            + _section("IDENTITY_PRESERVATION_CORE", "Preserve core identity.")
            + _section("IDENTITY_PRESERVATION_FACE", "Preserve the face.")
            + _section("IDENTITY_PRESERVATION_HAIR", "Preserve the hair.")
            + _section("IDENTITY_PRESERVATION_EARS", "Preserve the ears.")
            + _section("NEGATIVE_GUIDANCE_GENERAL", "Avoid identity drift."),
            encoding="utf-8",
        )
        self.costume = self.character_dir / "Costume_Travel_Gear.md"
        self.costume.write_text(
            _section("IDENTITY_PRESERVATION_COSTUME", "Preserve the blue travel coat."),
            encoding="utf-8",
        )
        self.definition = self.character_dir / "Expressions" / "Happy.md"
        self.definition.parent.mkdir()
        self.definition.write_text("EXPRESSION TARGET\n\nA warm restrained smile.\n", encoding="utf-8")
        self.reference = self.library / "identity.png"
        self.reference.write_bytes(b"image")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_selected_costume_preservation_is_compiled_with_provenance(self) -> None:
        output = self.root / "output"
        result = compile_expression_job(
            {
                "Task": "expression",
                "Character": "Test",
                "Phase": "Adult",
                "Expression Label": "Happy",
                "Identity Key Label": "Test Key",
                "Template Path": str(self.character_dir / "Character.md"),
                "Expression Definition Path": str(self.definition),
                "Costume": "Travel Gear",
                "Costume Path": str(self.costume),
                "Output Directory": str(output),
                "Reference Files": [{"role": "identity_key", "path": str(self.reference)}],
            },
            self.root,
        )
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
        source_map = json.loads((output / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
        self.assertIn("Preserve the blue travel coat.", prompt)
        costume_fragments = [
            item for item in source_map["fragments"] if item.get("section_name") == "IDENTITY_PRESERVATION_COSTUME"
        ]
        self.assertTrue(costume_fragments)
        self.assertEqual(str(self.costume), costume_fragments[0]["source_path"])


if __name__ == "__main__":
    unittest.main()
