import unittest

from zet.services.view_conditioning_service import (
    ViewConditioningError,
    ViewContext,
    condition_section,
    condition_sections,
)


class ViewConditioningTests(unittest.TestCase):
    def compile(self, source, *, body="FRONT", head="FRONT", name="COSTUME_DESCRIPTION_FACTS"):
        return condition_section(
            source,
            name,
            {"source_path": "Test.md", "start_line": 10},
            ViewContext(body_view=body, head_view=head),
        )[0]

    def test_groups_exclusions_and_all_reset(self):
        result = self.compile(
            "<!-- ZET:VIEW_DOMAIN body -->\n"
            "<!-- ZET:VIEW_DEFAULT rearish -->\n"
            "* default rear fact\n"
            "* [all] all-view fact\n"
            "* [rearish,!b] rear-three-quarter fact"
        , body="BACK_LEFT_3_4")
        self.assertEqual(
            "* default rear fact\n* all-view fact\n* rear-three-quarter fact",
            result,
        )
        self.assertNotIn("default rear fact", self.compile(
            "<!-- ZET:VIEW_DOMAIN body -->\n<!-- ZET:VIEW_DEFAULT rearish -->\n* default rear fact",
            body="FRONT",
        ))

    def test_independent_head_and_body_orientations(self):
        source = (
            "<!-- ZET:VIEW_DOMAIN body -->\n"
            "* [body:frontish] front garment\n"
            "* [body:rearish] rear garment\n"
            "* [head:profiles] profile earring"
        )
        result = self.compile(source, body="BACK", head="RIGHT_PROFILE")
        self.assertEqual("* rear garment\n* profile earring", result)

    def test_canon_only_directive_and_line_tag(self):
        result = self.compile(
            "* before\n<!-- ZET:CANON_ONLY -->\n* documentation\n* [canon_only] more documentation"
        )
        self.assertEqual("* before", result)

    def test_directives_reset_at_each_marked_section(self):
        sections, _, _ = condition_sections(
            {
                "HEAD_DESCRIPTION_FACTS": "<!-- ZET:VIEW_DEFAULT face_visible -->\n* [f] eyes",
                "COSTUME_DESCRIPTION_FACTS": "* untagged costume fact",
            },
            {},
            ViewContext(body_view="BACK", head_view="BACK"),
        )
        self.assertEqual("", sections["HEAD_DESCRIPTION_FACTS"])
        self.assertEqual("* untagged costume fact", sections["COSTUME_DESCRIPTION_FACTS"])

    def test_controls_are_removed_and_empty_headings_pruned(self):
        result = self.compile(
            "## Front\n\n* [frontish] front-only fact\n\n## Shared\n\n* all-view fact",
            body="BACK",
        )
        self.assertEqual("## Shared\n\n* all-view fact", result)
        self.assertNotIn("VIEW_DOMAIN", result)

    def test_invalid_tags_report_template_location(self):
        for source, code in (
            ("* [unknown_group] text", "UNKNOWN_VIEW_TAG"),
            ("* [b,!b] text", "EMPTY_VIEW_MATCH"),
            ("* [frontish text", "MALFORMED_VIEW_TAG"),
            ("<!-- ZET:VIEW_DOMAIN prop -->", "INVALID_VIEW_DOMAIN"),
        ):
            with self.subTest(source=source), self.assertRaises(ViewConditioningError) as raised:
                self.compile(source)
            self.assertEqual(code, raised.exception.code)
            self.assertIn("Test.md:10", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
