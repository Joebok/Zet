"""Compile tagged template prose for independent body and head orientations."""
from __future__ import annotations

import re
from dataclasses import dataclass

from Scripts.Compile_Character_Template import load_template_sections_with_sources


VIEW_ORDER = ("FRONT", "FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4", "BACK",
              "BACK_RIGHT_3_4", "RIGHT_PROFILE", "FRONT_RIGHT_3_4")
VIEW_SHORT = dict(zip(("f", "fl", "pl", "bl", "b", "br", "pr", "fr"), VIEW_ORDER))
_sets = {
    "all": VIEW_ORDER,
    "frontish": ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4"),
    "rearish": ("BACK", "BACK_LEFT_3_4", "BACK_RIGHT_3_4"),
    "profiles": ("LEFT_PROFILE", "RIGHT_PROFILE"),
    "front_3q": ("FRONT_LEFT_3_4", "FRONT_RIGHT_3_4"),
    "back_3q": ("BACK_LEFT_3_4", "BACK_RIGHT_3_4"),
    "three_quarter": ("FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "BACK_LEFT_3_4", "BACK_RIGHT_3_4"),
    "leftish": ("FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4"),
    "left_side": ("FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4"),
    "rightish": ("FRONT_RIGHT_3_4", "RIGHT_PROFILE", "BACK_RIGHT_3_4"),
    "right_side": ("FRONT_RIGHT_3_4", "RIGHT_PROFILE", "BACK_RIGHT_3_4"),
    "face_visible": ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE"),
    "both_eyes_visible": ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4"),
    "single_side_face": ("LEFT_PROFILE", "RIGHT_PROFILE"),
    "rear_head_visible": ("BACK", "BACK_LEFT_3_4", "BACK_RIGHT_3_4"),
    "near_ear_visible": ("FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4", "FRONT_RIGHT_3_4", "RIGHT_PROFILE", "BACK_RIGHT_3_4"),
    "front_torso_visible": ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE"),
    "rear_torso_visible": ("BACK", "BACK_LEFT_3_4", "BACK_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE"),
    "front_costume_visible": ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4"),
    "rear_costume_visible": ("BACK", "BACK_LEFT_3_4", "BACK_RIGHT_3_4"),
    "near_left": ("FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4"),
    "near_right": ("FRONT_RIGHT_3_4", "RIGHT_PROFILE", "BACK_RIGHT_3_4"),
    "far_left_3q": ("FRONT_RIGHT_3_4", "BACK_RIGHT_3_4"),
    "far_right_3q": ("FRONT_LEFT_3_4", "BACK_LEFT_3_4"),
}
_TAG = re.compile(r"^(\s*[-*+]\s+)\[([^]\n]*)\](?:[ \t]+|$)(.*)$")
_DIRECTIVE = re.compile(r"^\s*<!--\s*ZET:(VIEW_DOMAIN|VIEW_DEFAULT|CANON_ONLY)(?:\s+([^\s]*))?\s*-->\s*$")
_MARKDOWN_HEADING = re.compile(r"^(\s{0,3})(#{1,6})\s+.*$")


class ViewConditioningError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def normalize_view(value: str) -> str:
    value = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    value = re.sub(r"_+", "_", value)
    aliases = {
        "F": "FRONT", "FL": "FRONT_LEFT_3_4", "PL": "LEFT_PROFILE", "BL": "BACK_LEFT_3_4",
        "B": "BACK", "BR": "BACK_RIGHT_3_4", "PR": "RIGHT_PROFILE", "FR": "FRONT_RIGHT_3_4",
        "FRONT_3_4_LEFT": "FRONT_LEFT_3_4", "FRONT_3_4_RIGHT": "FRONT_RIGHT_3_4",
        "BACK_3_4_LEFT": "BACK_LEFT_3_4", "BACK_3_4_RIGHT": "BACK_RIGHT_3_4",
    }
    result = aliases.get(value, value)
    if result not in VIEW_ORDER:
        raise ViewConditioningError("UNKNOWN_VIEW", f"Unknown requested view: {value}")
    return result


@dataclass(frozen=True)
class ViewContext:
    body_view: str | None = None
    head_view: str | None = None
    unknown_view: bool = False

    def requested(self, domain: str) -> str | None:
        return self.head_view if domain == "head" else self.body_view


def _domain(value: str, *, path: str, section: str, line: int) -> str:
    domain = value.strip().lower()
    if domain == "costume":
        domain = "body"
    if domain not in {"head", "body"}:
        raise ViewConditioningError("INVALID_VIEW_DOMAIN", f"{path}:{line} [{section}]: invalid view domain {value!r}")
    return domain


def _expand(expression: str, *, path: str, section: str, line: int) -> tuple[str | None, set[str]]:
    tokens = [token.strip().lower() for token in expression.split(",")]
    if not tokens or any(not token for token in tokens):
        raise ViewConditioningError("MALFORMED_VIEW_TAG", f"{path}:{line} [{section}]: empty view tag")
    domain = None
    included: set[str] = set()
    excluded: set[str] = set()
    saw_include = False
    for token in tokens:
        negated = token.startswith("!")
        if negated:
            token = token[1:].strip()
        token_domain = None
        if ":" in token:
            token_domain, token = token.split(":", 1)
            token_domain = _domain(token_domain, path=path, section=section, line=line)
            if domain is not None and domain != token_domain:
                raise ViewConditioningError("CONTRADICTORY_VIEW_DOMAIN", f"{path}:{line} [{section}]: one expression cannot mix head and body domains")
            domain = token_domain
        token = token.strip()
        expanded = _sets.get(token)
        if expanded is None:
            view = VIEW_SHORT.get(token)
            expanded = (view,) if view else None
        if expanded is None:
            raise ViewConditioningError("UNKNOWN_VIEW_TAG", f"{path}:{line} [{section}]: unknown view or group {token!r}")
        (excluded if negated else included).update(expanded)
        saw_include |= not negated
    if not saw_include:
        raise ViewConditioningError("MALFORMED_VIEW_TAG", f"{path}:{line} [{section}]: an exclusion requires an inclusion")
    included.difference_update(excluded)
    if not included:
        raise ViewConditioningError("EMPTY_VIEW_MATCH", f"{path}:{line} [{section}]: view expression matches no views")
    return domain, included


def _inferred_domain(section: str) -> str | None:
    name = section.upper()
    if name.startswith(("HEAD_", "HAIR_", "EXPRESSION_")) or name in {
        "IDENTITY_PRESERVATION_FACE", "IDENTITY_PRESERVATION_EYES", "IDENTITY_PRESERVATION_HAIR", "IDENTITY_PRESERVATION_EARS",
    }:
        return "head"
    if name.startswith(("BODY_", "COSTUME_", "EQUIPMENT_JEWELRY_PROPS_")) or name == "BODY_REFERENCE_CHARACTER_REQUIREMENTS":
        return "body"
    return None


def _prune_empty_headings(lines: list[tuple[str, int]]) -> list[tuple[str, int]]:
    headings: list[tuple[int, int]] = []
    keep = [True] * len(lines)
    for index, (text, _) in enumerate(lines):
        heading = _MARKDOWN_HEADING.match(text)
        if heading:
            level = len(heading.group(2))
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, index))
        elif text.strip():
            for _, heading_index in headings:
                keep[heading_index] = True
    for index, (text, _) in enumerate(lines):
        if _MARKDOWN_HEADING.match(text):
            has_content = any(keep[index + 1:])
            next_heading = next((i for i in range(index + 1, len(lines)) if _MARKDOWN_HEADING.match(lines[i][0]) and len(_MARKDOWN_HEADING.match(lines[i][0]).group(2)) <= len(_MARKDOWN_HEADING.match(text).group(2))), len(lines))
            if not any(lines[i][0].strip() and not _MARKDOWN_HEADING.match(lines[i][0]) for i in range(index + 1, next_heading)):
                keep[index] = False
    return [(line, number) for index, (line, number) in enumerate(lines) if keep[index]]


def condition_section(text: str, section: str, source: dict, context: ViewContext) -> tuple[str, dict, bool]:
    path = str(source.get("source_path") or "<template>")
    start_line = int(source.get("start_line") or 1)
    section_domain = _inferred_domain(section)
    current_domain = section_domain
    default: set[str] | None = None
    canon_only = False
    retained: list[tuple[str, int]] = []
    any_tagged_out = False
    for offset, raw_line in enumerate(text.splitlines()):
        line_no = start_line + offset
        directive = _DIRECTIVE.match(raw_line)
        if directive:
            kind, value = directive.groups()
            if kind == "VIEW_DOMAIN":
                current_domain = _domain(value or "", path=path, section=section, line=line_no)
                continue
            if kind == "VIEW_DEFAULT":
                _, default = _expand(value or "", path=path, section=section, line=line_no)
                continue
            if value:
                raise ViewConditioningError("INVALID_DIRECTIVE", f"{path}:{line_no} [{section}]: CANON_ONLY takes no argument")
            canon_only = True
            continue
        tag = _TAG.match(raw_line)
        if tag and " " in tag.group(2).strip() and not any(mark in tag.group(2) for mark in ",!:"):
            tag = None
        if raw_line.lstrip().startswith(("* [", "- [", "+ [")) and not tag:
            candidate = re.match(r"^\s*[-*+]\s+\[([^]\n]*)\]", raw_line)
            if candidate is None or not (" " in candidate.group(1).strip() and not any(mark in candidate.group(1) for mark in ",!:")):
                raise ViewConditioningError("MALFORMED_VIEW_TAG", f"{path}:{line_no} [{section}]: malformed leading view tag")
        if canon_only:
            continue
        domain = current_domain
        expression = None
        body = raw_line
        bullet = ""
        if tag:
            bullet, expression, body = tag.groups()
        if expression is not None and expression.strip().lower() == "canon_only":
            continue
        if expression is not None:
            explicit_domain, allowed = _expand(expression, path=path, section=section, line=line_no)
            domain = explicit_domain or domain
        else:
            allowed = default if default is not None else set(VIEW_ORDER)
        requested = context.requested(domain) if domain else None
        if requested is None and context.unknown_view and domain is not None and allowed != set(VIEW_ORDER):
            any_tagged_out = True
            continue
        if requested is not None and requested not in allowed:
            any_tagged_out = True
            continue
        cleaned = f"{bullet}{body}" if expression is not None else raw_line
        retained.append((cleaned, line_no))
    retained = _prune_empty_headings(retained)
    rendered = "\n".join(line for line, _ in retained).strip("\n")
    diagnostics = list(source.get("view_conditioning_diagnostics") or [])
    if any_tagged_out and context.unknown_view:
        diagnostics.append(f"{section}: view-specific lines omitted because the requested orientation is unavailable")
    updated_source = dict(source, retained_lines=[line for _, line in retained], view_conditioning_diagnostics=diagnostics)
    return rendered, updated_source, any_tagged_out and not bool(rendered.strip())


def condition_sections(sections: dict[str, str], sources: dict[str, dict], context: ViewContext) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    filtered: dict[str, str] = {}
    filtered_sources: dict[str, dict] = {}
    conditioned_out: list[str] = []
    for name, value in sections.items():
        source = sources.get(name, {"source_path": "<template>", "start_line": 1})
        try:
            text, updated_source, removed_all = condition_section(str(value or ""), name, source, context)
        except ViewConditioningError:
            raise
        filtered[name] = text
        filtered_sources[name] = updated_source
        if removed_all:
            conditioned_out.append(name)
    return filtered, filtered_sources, conditioned_out


def validate_view_controls(template_path: str) -> None:
    sections, sources = load_template_sections_with_sources(template_path)
    condition_sections(sections, sources, ViewContext())
