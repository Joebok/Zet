from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job


class CostumeDressingCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.library = self.root / "library"
        config_dir = self.root / "Config"
        template_dir = config_dir / "Prompt_Templates"
        template_dir.mkdir(parents=True)
        for name in (
            "Prompt_Task_Bundles.json",
            "Prompt_View_Text.json",
            "Prompt_View_Aliases.json",
            "Prompt_Background_Text.json",
        ):
            shutil.copyfile(PROJECT_ROOT / "Config" / name, config_dir / name)
        shutil.copyfile(
            PROJECT_ROOT / "Config" / "Prompt_Templates" / "costume_dressing_v1.md",
            template_dir / "costume_dressing_v1.md",
        )
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
        self.character_dir = self.library / "Characters" / "Tsaeytte" / "Youth"
        self.character_dir.mkdir(parents=True)
        self.character_dir.joinpath("Character.md").write_text(
            "Character Name: `Tsaeytte`\nCharacter Phase: `Youth`\nCanonical Art Style: `Painterly animation`\n",
            encoding="utf-8",
        )
        self.reference = self.library / "assembled.png"
        self.reference.write_bytes(b"image")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _compile(self, costume_sections: str, body_view: str = "FRONT", head_view: str | None = None) -> tuple[str, dict, dict]:
        costume_path = self.character_dir / "Costume_Test_Outfit.md"
        costume_path.write_text(
            "\n".join(
                [
                    "Costume Name: `Test Outfit`",
                    "Footwear: `boots`",
                    "Footwear Contact: `Both boots remain planted.`",
                    "",
                    costume_sections,
                ]
            ),
            encoding="utf-8",
        )
        output_dir = self.root / "output" / body_view / (head_view or body_view)
        result = compile_costume_dressing_job(
            {
                "Job": f"Test_{body_view}_{head_view or body_view}",
                "Task": "costume-dressing",
                "Character": "Tsaeytte",
                "Phase": "Youth",
                "Body View": body_view,
                "Head View": head_view or body_view,
                "Costume": "Test Outfit",
                "Costume Path": str(costume_path),
                "Output Directory": str(output_dir),
                "Expected Output": "result.png",
                "Reference Files": [{"role": "character_assembly", "path": str(self.reference)}],
            },
            self.root,
        )
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
        source_map = json.loads((output_dir / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
        return prompt, source_map, result

    @staticmethod
    def _sections(*parts: str) -> str:
        return "\n\n".join(parts)

    def test_front_prompt_is_ordered_and_suppresses_empty_equipment(self) -> None:
        prompt, _, result = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Costume name: `Test Outfit`.\n"
                "* Silhouette: `Fitted tunic and boots.`.\n"
                "* Jewelry: `Small blue pendant.`.\n"
                "* Equipment: `None.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_VIEW_FRONT -->\n"
                "* Front detail: `Visible center overlap.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_VIEW_FRONT -->",
                "<!-- ZET:BEGIN EQUIPMENT_DESCRIPTION_FACTS -->\n"
                "* Use anatomical left and right.\n"
                "* Right side: `None.`.\n"
                "* Left side: `None.`.\n"
                "* Jewelry: `Small blue pendant.`.\n"
                "* Primary weapon/tool: `N/A`.\n"
                "<!-- ZET:END EQUIPMENT_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN EQUIPMENT_DESCRIPTION_VIEW_FRONT -->\n"
                "* Front view should show `jewelry only; no equipment.`.\n"
                "<!-- ZET:END EQUIPMENT_DESCRIPTION_VIEW_FRONT -->",
            )
        )

        self.assertTrue(prompt.startswith("# Render Task\n"))
        opening = prompt[:500]
        for value in ("Tsaeytte", "Youth", "Test Outfit", "FRONT"):
            self.assertIn(value, opening)
        self.assertLess(prompt.index("# Locked Source"), prompt.index("# Costume Design"))
        self.assertLess(prompt.index("# Orientation Lock"), prompt.index("# Costume Design"))
        self.assertIn("Requested body view: FRONT.", prompt)
        self.assertIn("Preserve that view exactly.", prompt)
        self.assertIn("Small blue pendant", prompt)
        self.assertNotIn("None.", prompt)
        self.assertNotIn("Right side", prompt)
        self.assertNotIn("Left side", prompt)
        self.assertNotIn("GOOD OUTPUT", prompt.upper())
        self.assertNotIn("BAD OUTPUT", prompt.upper())
        self.assertIn("# Final Constraints", prompt)
        self.assertEqual(result["status"], "READY_FOR_RENDER")
        self.assertEqual(result["next_actor"], "AI_AGENT")
        for name in ("Final_Image_Prompt.md", "Compiled_Sections.md", "Prompt_Source_Map.json", "dependency_manifest.json", "Prompt_Review.md", "Image_Review.md"):
            self.assertTrue((Path(result["output_dir"]) / name).exists())

    def test_profile_and_back_three_quarter_locks_do_not_cross_contaminate(self) -> None:
        facts = (
            "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
            "* Silhouette: `Simple fitted outfit.`.\n"
            "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->"
        )
        left, _, _ = self._compile(facts, "LEFT_PROFILE")
        right, _, _ = self._compile(facts, "RIGHT_PROFILE")
        back, _, _ = self._compile(facts, "BACK_LEFT_3_4")

        self.assertIn("Requested body view: LEFT PROFILE.", left)
        self.assertNotIn("Requested body view: RIGHT PROFILE.", left)
        self.assertIn("Requested body view: RIGHT PROFILE.", right)
        self.assertNotIn("Requested body view: LEFT PROFILE.", right)
        self.assertIn("Requested body view: BACK-LEFT THREE-QUARTER.", back)
        self.assertIn("Do not rotate the head toward the viewer", back)
        self.assertIn("Preserve that view exactly.", back)

    def test_different_body_and_head_views_preserve_relative_turn(self) -> None:
        facts = (
            "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
            "* Silhouette: `Simple fitted outfit.`.\n"
            "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->"
        )
        prompt, source_map, _ = self._compile(facts, "FRONT_LEFT_3_4", "FRONT")

        self.assertIn("Requested body view: FRONT-LEFT THREE-QUARTER.", prompt)
        self.assertIn("Requested head view: FRONT.", prompt)
        self.assertIn("body orientation and head orientation", prompt)
        self.assertTrue(source_map["fragments"])

    def test_sided_equipment_keeps_side_rules_and_source_provenance(self) -> None:
        prompt, source_map, _ = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Silhouette: `Travel coat and boots.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN EQUIPMENT_DESCRIPTION_FACTS -->\n"
                "* Use anatomical left and right.\n"
                "* Right side / right hip: `Ordered lantern.`.\n"
                "* Left side / left hip: `Map satchel.`.\n"
                "* Front-view reminder: anatomical right appears on the viewer's left; anatomical left appears on the viewer's right.\n"
                "<!-- ZET:END EQUIPMENT_DESCRIPTION_FACTS -->",
            )
        )

        self.assertIn("# Equipment and Jewelry", prompt)
        self.assertIn("Ordered lantern", prompt)
        self.assertIn("Map satchel", prompt)
        self.assertIn("viewer's left", prompt)
        costume_sources = [fragment for fragment in source_map["fragments"] if fragment.get("source_kind") == "costume_template_section"]
        self.assertTrue(costume_sources)

    def test_no_jewelry_or_equipment_removes_optional_section_and_empty_view_stub(self) -> None:
        prompt, _, result = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Silhouette: `Travel coat and boots.`.\n"
                "* Jewelry: `None.`.\n"
                "* Equipment: `Not applicable`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_VIEW_FRONT -->\n"
                "* Front view: `None.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_VIEW_FRONT -->",
                "<!-- ZET:BEGIN EQUIPMENT_DESCRIPTION_FACTS -->\n"
                "* Primary weapon/tool: `None.`.\n"
                "<!-- ZET:END EQUIPMENT_DESCRIPTION_FACTS -->",
            )
        )

        self.assertNotIn("# Jewelry", prompt)
        self.assertNotIn("# Equipment and Jewelry", prompt)
        self.assertNotIn("# View-Specific Costume Details", prompt)
        compiled = (Path(result["output_dir"]) / "Compiled_Sections.md").read_text(encoding="utf-8")
        self.assertIn("normalized to empty", compiled)


if __name__ == "__main__":
    unittest.main()
