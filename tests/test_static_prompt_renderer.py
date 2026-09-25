from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from Build_Static_Final_Prompt import render_static_prompt
from Scripts.Compile_Character_Template import CompiledSelection, TemplateCompileError
from zet.services.prompt_template_service import filter_pipeline_mode_blocks, filter_prompt_variant_blocks


class StaticPromptRendererTests(unittest.TestCase):
    def test_all_configured_pipeline_templates_support_both_variants(self) -> None:
        bundles = json.loads((PROJECT_ROOT / "Config" / "Prompt_Task_Bundles.json").read_text(encoding="utf-8"))["bundles"]
        for task, bundle in bundles.items():
            for pipeline_mode in ("traditional", "local"):
                with self.subTest(task=task, pipeline_mode=pipeline_mode):
                    template = (PROJECT_ROOT / "Config" / "Prompt_Templates" / f'{bundle["static_prompt_template"]}.md').read_text(encoding="utf-8")
                    selected = filter_pipeline_mode_blocks(template, pipeline_mode)
                    generation = filter_prompt_variant_blocks(selected, "generation")
                    analysis = filter_prompt_variant_blocks(selected, "analysis")
                    if task != "head-image" or pipeline_mode == "traditional":
                        self.assertIn("# Render Task", generation)
                    else:
                        self.assertIn("Create one clean head reference", generation)
                    self.assertIn("# Review Specification" if task != "body-reference" else "# Body-Reference specification", analysis)
                    self.assertNotIn("# Render Task", analysis)
                    self.assertNotIn("{{CHATGPT_CHANGE_CONTRACT}}", analysis)
                self.assertNotIn("<!-- ZET:", generation)
                self.assertNotIn("<!-- ZET:", analysis)

    def test_tilde_section_placeholder_line_is_ignored(self) -> None:
        selection = CompiledSelection(
            included_required=["ACTIVE_SECTION"],
            included_optional=[],
            missing_required=[],
            missing_optional=[],
            forbidden_matches=[],
            sections={
                "ACTIVE_SECTION": "active text",
                "COMMENTED_SECTION": "commented text",
            },
        )

        prompt = render_static_prompt(
            "\n".join(
                [
                    "Before",
                    "{{ACTIVE_SECTION}}",
                    "~{{COMMENTED_SECTION}}",
                    "After",
                ]
            ),
            {},
            selection,
            ["ACTIVE_SECTION"],
            "FRONT",
        )

        self.assertIn("active text", prompt)
        self.assertIn("After", prompt)
        self.assertNotIn("commented text", prompt)
        self.assertNotIn("~{{", prompt)


    def test_known_optional_section_renders_empty(self) -> None:
        selection = CompiledSelection([], [], [], ["OPTIONAL_SECTION"], [], {})
        self.assertEqual("Before\n\nAfter\n", render_static_prompt("Before\n{{OPTIONAL_SECTION}}\nAfter", {}, selection, [], "FRONT"))

    def test_unknown_placeholder_fails(self) -> None:
        selection = CompiledSelection([], [], [], [], [], {})
        with self.assertRaises(TemplateCompileError) as raised:
            render_static_prompt("{{UNKNOWN_TOKEN}}", {}, selection, [], "FRONT")
        self.assertEqual("UNRESOLVED_PLACEHOLDER", raised.exception.code)

    def test_metadata_section_collision_fails(self) -> None:
        selection = CompiledSelection([], ["TOKEN"], [], [], [], {"TOKEN": "section"})
        with self.assertRaisesRegex(TemplateCompileError, "metadata and a marked section"):
            render_static_prompt("{{TOKEN}}", {"TOKEN": "metadata"}, selection, [], "FRONT")


if __name__ == "__main__":
    unittest.main()
