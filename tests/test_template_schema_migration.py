from __future__ import annotations

from pathlib import Path
import unittest

from Scripts.Compile_Character_Template import load_template_sections


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = PROJECT_ROOT / "Docs" / "Template_Schema_Review"
LIBRARY_ROOT = PROJECT_ROOT.parent / "Zet_Library" / "Characters" / "Tsaeytte"


class TemplateSchemaMigrationTests(unittest.TestCase):
    def test_character_and_costume_section_text_is_preserved_active_or_retired(self) -> None:
        before_root = REVIEW_ROOT / "before" / "structure"
        after_root = REVIEW_ROOT / "after" / "structure"
        candidates = [
            path for path in before_root.rglob("*.md")
            if path.name == "Character.md" or path.name.startswith("Costume_") or path.name in {"Character_Template.md", "Costume_Template.md"}
        ]
        for before in candidates:
            relative = before.relative_to(before_root)
            after = after_root / relative
            if not after.exists():
                continue
            preservation_text = after.read_text(encoding="utf-8")
            retired = list(after.parent.glob(f"{after.stem}*_Retired_Sections.md"))
            if after.name in {"Character.md", "Character_Template.md"}:
                retired.extend(after.parent.glob("Character_Retired_Sections.md"))
            if after.name == "Costume_Template.md":
                retired.extend(after.parent.glob("Costume_Template_Retired_Sections.md"))
            preservation_text += "\n".join(path.read_text(encoding="utf-8") for path in set(retired))
            for name, text in load_template_sections(before).items():
                if text.strip():
                    self.assertIn(text.strip(), preservation_text, f"{relative}: {name}")

    def test_expression_authored_lines_survive_direct_token_migration(self) -> None:
        before_root = REVIEW_ROOT / "before" / "structure" / "library"
        after_root = REVIEW_ROOT / "after" / "structure" / "library"
        for before in before_root.rglob("Expressions/*.md"):
            after_text = (after_root / before.relative_to(before_root)).read_text(encoding="utf-8")
            for line in before.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("{{SECTION:"):
                    self.assertIn(line, after_text, str(before))

    def test_live_templates_use_only_canonical_markers(self) -> None:
        for path in LIBRARY_ROOT.rglob("*.md"):
            if "Retired_Sections" in path.name or any(part in {"Archive", "Pipelines", "_backup"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8")
            if path.name == "Character.md":
                self.assertNotIn("TECHNICAL_MODESTY_LAYER", text)
                self.assertNotIn("PICARESQUE", text)
            if path.parent.name == "Expressions":
                self.assertNotIn("{{SECTION:", text)

    def test_review_bundle_contains_complete_comparisons(self) -> None:
        for side in ("before", "after"):
            prompts = list((REVIEW_ROOT / side / "prompts").rglob("*.md"))
            self.assertEqual(16, len(prompts), side)
        self.assertEqual(16, len(list((REVIEW_ROOT / "diffs").rglob("*.diff"))))
        self.assertTrue((REVIEW_ROOT / "Trees_Before.md").is_file())
        self.assertTrue((REVIEW_ROOT / "Trees_After.md").is_file())


if __name__ == "__main__":
    unittest.main()
