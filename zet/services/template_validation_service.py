"""Deterministic validation and raw-line view applicability for template editing."""
from __future__ import annotations

from pathlib import Path
import re

from Scripts.Compile_Character_Template import MARKER_RE, PLACEHOLDER_RE, parse_template_sections_with_sources
from Scripts.Auxiliary_Resource_Tags import IMAGE_TAG_RE, LIB_REFERENCE_TAG_RE
from Scripts.Build_Static_Final_Prompt import ANY_PLACEHOLDER_RE
from zet.services.auxiliary_resource_tags import AUXILIARY_RESOURCE_TAG_RE
from zet.services.costume_mode_conditioning_service import condition_mode_line, _ANNOTATION
from zet.services.template_source_service import template_sources
from zet.services.view_conditioning_service import (
    VIEW_ORDER, ViewContext, condition_section, _DIRECTIVE, _SPATIAL,
)


class TemplateValidationService:
    def __init__(self, app):
        self.app = app

    def analyze(self, path: Path, text: str, kind: str) -> dict:
        diagnostics = []
        lines = text.splitlines()
        # None means structurally neutral/unknown; arrays identify applicable views.
        applicability = [None] * len(lines)

        def error(message, code="INVALID_TEMPLATE", line=None, section=None):
            location = re.search(r":(\d+) \[([^]]+)\]:", str(message))
            item = {"code": code, "message": str(message),
                    "line": line or getattr(message, "line", None) or (int(location[1]) if location else None),
                    "section": section or getattr(message, "section", None) or (location[2] if location else None)}
            if not any(d["message"] == item["message"] and d["line"] == item["line"] for d in diagnostics):
                diagnostics.append(item)

        if not text.strip() or len(text) > 250000:
            error("Template must be nonempty and at most 250,000 characters.", "INVALID_SIZE")
            return {"diagnostics": diagnostics, "line_views": applicability, "views": VIEW_ORDER}

        invalid_lines = set()
        for number, line in enumerate(lines, 1):
            cleaned = line
            for pattern in (MARKER_RE, _DIRECTIVE, _SPATIAL, _ANNOTATION):
                cleaned = pattern.sub("", cleaned)
            if re.search(r"ZET\s*:|<!--\s*ZET\b", cleaned, re.I):
                error("Malformed or unknown ZET marker/directive.", "INVALID_DIRECTIVE", number)
                invalid_lines.add(number)
            if len(_SPATIAL.findall(line)) > 1:
                error("Each source line may have only one spatial annotation.", "MALFORMED_SPATIAL_ANNOTATION", number)
                invalid_lines.add(number)
            try:
                condition_mode_line(line, None)
            except ValueError as exc:
                error(exc, "INVALID_RENDER_MODES", number)
                invalid_lines.add(number)
            cleaned = line
            for pattern in (IMAGE_TAG_RE, LIB_REFERENCE_TAG_RE, AUXILIARY_RESOURCE_TAG_RE, PLACEHOLDER_RE):
                cleaned = pattern.sub("", cleaned)
            if "{{" in cleaned or "}}" in cleaned:
                error("Malformed placeholder or image reference tag.", "INVALID_PLACEHOLDER", number)
                invalid_lines.add(number)

        try:
            sections, sources = parse_template_sections_with_sources(text, path)
        except Exception as exc:
            error(exc, getattr(exc, "code", "INVALID_TEMPLATE"))
            return {"diagnostics": diagnostics, "line_views": applicability, "views": VIEW_ORDER}

        section_lines = {number for name, content in sections.items()
                         for number in range(sources[name]["start_line"], sources[name]["start_line"] + len(content.splitlines()))}
        for number, raw in enumerate(lines, 1):
            if number not in section_lines and (_DIRECTIVE.fullmatch(raw) or _SPATIAL.search(raw) or _ANNOTATION.search(raw)):
                error("View and mode controls must be inside a marked template section.", "CONTROL_OUTSIDE_SECTION", number)

        for name, content in sections.items():
            source = sources[name]
            start = source["start_line"]
            positions = range(start, start + len(content.splitlines()))
            if invalid_lines.intersection(positions):
                continue
            retained = {view: set() for view in VIEW_ORDER}
            failed = False
            # Empty context catches errors even on prose omitted in all concrete views.
            for view in (None, *VIEW_ORDER):
                try:
                    rendered, mapped, _ = condition_section(content, name, source, ViewContext(view, view))
                    if view:
                        retained[view].update(mapped["retained_lines"])
                        for pattern in (IMAGE_TAG_RE, LIB_REFERENCE_TAG_RE, AUXILIARY_RESOURCE_TAG_RE):
                            rendered = pattern.sub("", rendered)
                        unresolved = ANY_PLACEHOLDER_RE.search(rendered)
                        if unresolved:
                            number = next((n for n in mapped["retained_lines"] if unresolved[0] in lines[n - 1]), None)
                            error(f"Task-template placeholder {unresolved[0]} is not supported in authored template prose.",
                                  "UNRESOLVED_PLACEHOLDER", number, name)
                            failed = True
                except ValueError as exc:
                    error(exc, getattr(exc, "code", "INVALID_VIEW_CONTROLS"))
                    failed = True
            if failed:
                continue
            for number in positions:
                raw = lines[number - 1]
                if not raw.strip() or _DIRECTIVE.fullmatch(raw):
                    continue
                applicability[number - 1] = [v for v in VIEW_ORDER if number in retained[v]]

        # File headings outside marked sections inherit their following prose's views.
        for index, line in enumerate(lines):
            heading = re.match(r"^\s{0,3}(#{1,6})\s", line)
            if not heading or applicability[index] is not None:
                continue
            following = []
            has_prose = False
            for offset in range(index + 1, len(lines)):
                next_heading = re.match(r"^\s{0,3}(#{1,6})\s", lines[offset])
                if next_heading and len(next_heading[1]) <= len(heading[1]):
                    break
                if applicability[offset] is not None:
                    has_prose = True
                    following.extend(applicability[offset])
            if has_prose:
                applicability[index] = [v for v in VIEW_ORDER if v in following]

        # Canonical schema/content checks retain the existing upload acceptance rules.
        try:
            if kind == "character":
                with template_sources([{"source_path": str(path), "text": text}]):
                    for message in self.app.character_onboarding_service.validate_template(path):
                        error(message)
            else:
                self.app.costume_service.validate_template_text(text)
        except Exception as exc:
            error(exc, getattr(exc, "code", "INVALID_TEMPLATE"))
        return {"diagnostics": diagnostics, "line_views": applicability, "views": VIEW_ORDER}
