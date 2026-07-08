from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from Build_Static_Final_Prompt import render_static_prompt
from Compile_Character_Template import CompiledSelection


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
                    "{{SECTION:ACTIVE_SECTION}}",
                    "~{{SECTION:COMMENTED_SECTION}}",
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
        self.assertNotIn("~{{SECTION", prompt)


if __name__ == "__main__":
    unittest.main()
