#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
import re


class TemplateCompileError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class CompiledSelection:
    included_required: list[str]
    included_optional: list[str]
    missing_required: list[str]
    missing_optional: list[str]
    forbidden_matches: list[str]
    sections: dict[str, str]
    section_sources: dict[str, dict] = field(default_factory=dict)


MARKER_RE = re.compile(
    r"<!--\s*ZET:(BEGIN|END)\s+([A-Z0-9_]+)\s*-->",
    flags=re.MULTILINE,
)


def resolve_section_name(section_name: str, view_token: str) -> str:
    return str(section_name).replace("{VIEW}", view_token)


def _trim_section_text(text: str) -> str:
    return text.strip("\n")


def load_template_sections(template_path: str | Path) -> dict[str, str]:
    return load_template_sections_with_sources(template_path)[0]


def _line_number_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def load_template_sections_with_sources(
    template_path: str | Path,
    *,
    source_kind: str = "character_template_section",
    source_label: str = "",
) -> tuple[dict[str, str], dict[str, dict]]:
    path = Path(template_path)
    if not path.exists():
        raise TemplateCompileError("MISSING_TEMPLATE", f"Template file not found: {path}")
    text = path.read_text(encoding="utf-8")
    markers = list(MARKER_RE.finditer(text))
    sections: dict[str, str] = {}
    sources: dict[str, dict] = {}
    open_name: str | None = None
    content_start = 0

    for marker in markers:
        kind, name = marker.group(1), marker.group(2)
        if kind == "BEGIN":
            if open_name is not None:
                raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"Nested ZET marker before closing {open_name}.")
            if name in sections:
                raise TemplateCompileError("DUPLICATE_SECTION", f"Duplicate ZET section: {name}")
            open_name = name
            content_start = marker.end()
            continue
        if open_name is None:
            raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"ZET end marker without begin: {name}")
        if name != open_name:
            raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"ZET marker mismatch: began {open_name}, ended {name}")
        sections[name] = _trim_section_text(text[content_start:marker.start()])
        sources[name] = {
            "source_kind": source_kind,
            "source_path": str(path),
            "source_label": source_label or f"{source_kind}: {name}",
            "section_name": name,
            "start_line": _line_number_at(text, content_start),
            "end_line": _line_number_at(text, marker.start()),
            "editable": True,
        }
        open_name = None

    if open_name is not None:
        raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"ZET section missing end marker: {open_name}")
    return sections, sources


def select_sections(
    all_sections: dict[str, str],
    bundle: dict,
    view_token: str,
    section_sources: dict[str, dict] | None = None,
) -> CompiledSelection:
    required = [resolve_section_name(name, view_token) for name in bundle.get("required_sections", [])]
    optional = [resolve_section_name(name, view_token) for name in bundle.get("optional_sections", [])]
    forbidden_patterns = list(bundle.get("forbidden_sections", []))

    included_required: list[str] = []
    included_optional: list[str] = []
    missing_required: list[str] = []
    missing_optional: list[str] = []
    forbidden_matches: list[str] = []
    selected: dict[str, str] = {}
    selected_sources: dict[str, dict] = {}
    source_lookup = section_sources or {}

    for name in required:
        text = all_sections.get(name, "")
        if not text.strip():
            missing_required.append(name)
            continue
        included_required.append(name)
        selected[name] = text
        if name in source_lookup:
            selected_sources[name] = source_lookup[name]

    for name in optional:
        text = all_sections.get(name, "")
        if not text.strip():
            missing_optional.append(name)
            continue
        included_optional.append(name)
        selected[name] = text
        if name in source_lookup:
            selected_sources[name] = source_lookup[name]

    for name in selected:
        if any(fnmatchcase(name, pattern) for pattern in forbidden_patterns):
            forbidden_matches.append(name)

    return CompiledSelection(
        included_required=included_required,
        included_optional=included_optional,
        missing_required=missing_required,
        missing_optional=missing_optional,
        forbidden_matches=forbidden_matches,
        sections=selected,
        section_sources=selected_sources,
    )

