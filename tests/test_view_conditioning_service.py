import unittest

from zet.services.view_conditioning_service import (
    ViewConditioningError,
    ViewContext,
    condition_section,
    condition_sections,
    resolve_anatomical_side,
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

    def test_anatomical_side_projection_for_all_views(self):
        expected = {
            "FRONT": ("screen-right", "screen-left"),
            "FRONT_LEFT_3_4": ("near-side", "far-side"),
            "LEFT_PROFILE": ("near-side", "far-side"),
            "BACK_LEFT_3_4": ("near-side", "far-side"),
            "BACK": ("screen-left", "screen-right"),
            "BACK_RIGHT_3_4": ("far-side", "near-side"),
            "RIGHT_PROFILE": ("far-side", "near-side"),
            "FRONT_RIGHT_3_4": ("far-side", "near-side"),
        }
        for view, sides in expected.items():
            with self.subTest(view=view):
                self.assertEqual(sides[0], resolve_anatomical_side("left", view))
                self.assertEqual(sides[1], resolve_anatomical_side("right", view))

    def test_spatial_annotations_translate_and_retain_provenance(self):
        text, source, _ = condition_section(
            "<!-- ZET:VIEW_DOMAIN head -->\n"
            "* [frontish] <!-- ZET:SPATIAL asymmetry --> Hair part is on the anatomical-left side.\n"
            "* [frontish] <!-- ZET:SPATIAL asymmetry --> Hair mass is heavier on the anatomical-right side.",
            "HAIR_DESCRIPTION_FACTS",
            {"source_path": "Tsaeytte.md", "start_line": 20},
            ViewContext(body_view="BACK", head_view="FRONT"),
        )
        self.assertEqual(
            "* Hair part is on the screen-right side.\n* Hair mass is heavier on the screen-left side.", text
        )
        self.assertEqual(2, len(source["spatial_translations"]))
        self.assertEqual(21, source["spatial_translations"][0]["source_line"])

    def test_fixed_feature_visibility_and_partial_state(self):
        source = (
            "<!-- ZET:VIEW_DOMAIN head -->\n"
            "* [head:pr] <!-- ZET:SPATIAL fixed --> A scar is on the anatomical-right cheek.\n"
            "* [head:fl] <!-- ZET:SPATIAL fixed state=partial --> A scar is on the anatomical-right cheek."
        )
        self.assertIn("near-side cheek", self.compile(source, head="RIGHT_PROFILE"))
        self.assertNotIn("scar", self.compile(source, head="LEFT_PROFILE"))
        partial = self.compile(source, head="FRONT_LEFT_3_4")
        self.assertIn("Partially visible:", partial)
        self.assertIn("far-side cheek", partial)

    def test_fixed_annotation_requires_explicit_visibility_and_bare_sides_fail(self):
        with self.assertRaises(ViewConditioningError) as raised:
            self.compile("* <!-- ZET:SPATIAL fixed --> A scar is on the anatomical-right cheek.")
        self.assertEqual("FIXED_FEATURE_VISIBILITY_REQUIRED", raised.exception.code)
        with self.assertRaises(ViewConditioningError) as raised:
            self.compile("* [f] <!-- ZET:SPATIAL asymmetry --> Hair is heavier on the left.")
        self.assertEqual("UNQUALIFIED_SPATIAL_SIDE", raised.exception.code)
        with self.assertRaises(ViewConditioningError) as raised:
            condition_section(
                "* <!-- ZET:SPATIAL fixed --> A scar is on the anatomical-right cheek.",
                "HEAD_DESCRIPTION_FACTS", {"source_path": "Test.md", "start_line": 1}, ViewContext(),
            )
        self.assertEqual("FIXED_FEATURE_VISIBILITY_REQUIRED", raised.exception.code)

    def test_spatial_annotations_require_domain_and_reject_conflicts(self):
        with self.assertRaises(ViewConditioningError) as raised:
            condition_section(
                "* <!-- ZET:SPATIAL asymmetry --> Hair is heavier on the anatomical-left side.",
                "MISCELLANEOUS", {"source_path": "Test.md", "start_line": 4},
                ViewContext(body_view="FRONT", head_view="FRONT"),
            )
        self.assertEqual("MISSING_SPATIAL_DOMAIN", raised.exception.code)
        with self.assertRaises(ViewConditioningError) as raised:
            self.compile(
                "* [head:fl] <!-- ZET:SPATIAL asymmetry --> The far-side anatomical-left cheek is visible.",
                head="FRONT_LEFT_3_4",
            )
        self.assertEqual("CONTRADICTORY_SPATIAL_SIDE", raised.exception.code)

    def test_head_and_body_side_resolution_use_their_own_views(self):
        text = (
            "<!-- ZET:VIEW_DOMAIN head -->\n"
            "* [head:all] <!-- ZET:SPATIAL fixed --> Earring on anatomical-left ear.\n"
            "<!-- ZET:VIEW_DOMAIN body -->\n"
            "* [body:all] <!-- ZET:SPATIAL asymmetry --> Belt is heavier on anatomical-left side."
        )
        result = self.compile(text, body="BACK", head="RIGHT_PROFILE")
        self.assertIn("Earring on far-side ear.", result)
        self.assertIn("Belt is heavier on screen-left side.", result)

    def test_hidden_and_occluded_fixed_features_are_omitted(self):
        text = (
            "* [f] <!-- ZET:SPATIAL fixed state=hidden --> A scar on the anatomical-right cheek.\n"
            "* [f] <!-- ZET:SPATIAL fixed state=occluded --> An earring on the anatomical-left ear."
        )
        self.assertEqual("", self.compile(text, name="HEAD_DESCRIPTION_FACTS"))


if __name__ == "__main__":
    unittest.main()
