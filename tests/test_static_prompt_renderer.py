from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from Build_Static_Final_Prompt import render_static_prompt
from Scripts.Compile_Character_Template import CompiledSelection, TemplateCompileError


class StaticPromptRendererTests(unittest.TestCase):
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

    def test_arbitrary_direct_section_placeholder_needs_no_bundle_entry(self) -> None:
        selection = CompiledSelection([], ["NEW_SECTION"], [], [], [], {"NEW_SECTION": "new text"})
        self.assertEqual("new text\n", render_static_prompt("{{NEW_SECTION}}", {}, selection, [], "FRONT"))

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
