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
_SPATIAL = re.compile(r"<!--\s*ZET:SPATIAL\s+(asymmetry|fixed)(?:\s+state=(visible|partial|occluded|hidden))?\s*-->")
_ANATOMICAL_SIDE = re.compile(r"\banatomical[ -](left|right)(?:[ -](side))?\b", re.IGNORECASE)
_BARE_SIDE = re.compile(r"(?<![\w-])(left|right)(?![\w-])", re.IGNORECASE)
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


_SCREEN_SIDE = {
    "FRONT": {"left": "screen-right", "right": "screen-left"},
    "BACK": {"left": "screen-left", "right": "screen-right"},
}
_NEAR_SIDE = {
    "FRONT_LEFT_3_4": "left", "LEFT_PROFILE": "left", "BACK_LEFT_3_4": "left",
    "FRONT_RIGHT_3_4": "right", "RIGHT_PROFILE": "right", "BACK_RIGHT_3_4": "right",
}


def resolve_anatomical_side(side: str, view: str) -> str:
    """Resolve an anatomical side to screen or depth language for one view."""
    token = normalize_view(view)
    side_key = str(side).strip().lower()
    if side_key not in {"left", "right"}:
        raise ViewConditioningError("INVALID_ANATOMICAL_SIDE", f"Unknown anatomical side: {side!r}")
    if token in _SCREEN_SIDE:
        return _SCREEN_SIDE[token][side_key]
    near = _NEAR_SIDE[token]
    return "near-side" if side_key == near else "far-side"


def _translate_spatial_line(body: str, kind: str, state: str, domain: str | None,
                            requested: str | None, allowed: set[str], explicit_visibility: bool, *, path: str,
                            section: str, line: int) -> tuple[str, dict | None]:
    location = f"{path}:{line} [{section}]"
    if domain is None:
        raise ViewConditioningError("MISSING_SPATIAL_DOMAIN", f"{location}: spatial annotation requires a head or body view domain")
    if kind == "fixed" and not explicit_visibility:
        raise ViewConditioningError("FIXED_FEATURE_VISIBILITY_REQUIRED", f"{location}: fixed features require an explicit view tag or ZET:VIEW_DEFAULT")
    sides = list(_ANATOMICAL_SIDE.finditer(body))
    if not sides:
        if _BARE_SIDE.search(body):
            raise ViewConditioningError("UNQUALIFIED_SPATIAL_SIDE", f"{location}: qualify left/right as anatomical left/right")
        raise ViewConditioningError("MISSING_ANATOMICAL_SIDE", f"{location}: spatial annotation must identify anatomical left or right")
    masked = _ANATOMICAL_SIDE.sub("", body)
    if _BARE_SIDE.search(masked):
        raise ViewConditioningError("UNQUALIFIED_SPATIAL_SIDE", f"{location}: qualify left/right as anatomical left/right")
    if requested is None:
        return body, {"section": section, "source_path": path, "source_line": line,
                      "domain": domain, "kind": kind, "state": state,
                      "canonical_text": body, "emitted_text": body,
                      "omission_reason": "requested view unavailable"}
    if kind == "fixed" and requested not in allowed:
        return "", {"section": section, "source_path": path, "source_line": line,
                    "domain": domain, "view": requested, "kind": kind, "state": state,
                    "canonical_text": body, "emitted_text": "",
                    "omission_reason": "outside authored visibility views"}
    if state in {"hidden", "occluded"}:
        return "", {"section": section, "source_path": path, "source_line": line,
                    "domain": domain, "view": requested, "kind": kind, "state": state,
                    "canonical_text": body, "emitted_text": "",
                    "omission_reason": state}
    # Reject unqualified directions in annotated clauses; they are ambiguous at generation time.
    pieces: list[str] = []
    cursor = 0
    for match in sides:
        pieces.append(body[cursor:match.start()])
        side = match.group(1).lower()
        phrase = resolve_anatomical_side(side, requested)
        if phrase in {"near-side", "far-side"}:
            opposite = "far-side" if phrase == "near-side" else "near-side"
            if opposite in body.lower() and phrase not in body.lower():
                raise ViewConditioningError(
                    "CONTRADICTORY_SPATIAL_SIDE",
                    f"{location}: {opposite} conflicts with anatomical-{side} in {requested}",
                )
        if match.group(2):
            phrase = phrase.replace("-side", " side") if "-side" in phrase else f"{phrase} side"
        pieces.append(phrase)
        cursor = match.end()
    pieces.append(body[cursor:])
    emitted = "".join(pieces)
    if state == "partial":
        emitted = f"Partially visible: {emitted}"
    return emitted, {"section": section, "source_path": path, "source_line": line,
                     "domain": domain, "view": requested, "kind": kind, "state": state,
                     "resolved_sides": {match.group(1).lower(): resolve_anatomical_side(match.group(1), requested) for match in sides},
                     "canonical_text": body, "emitted_text": emitted, "omission_reason": ""}


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
    spatial_translations: list[dict] = list(source.get("spatial_translations") or [])
    spatial_out = False
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
        spatial_match = _SPATIAL.search(body)
        spatial_kind = state = None
        if "ZET:SPATIAL" in body and not spatial_match:
            raise ViewConditioningError("MALFORMED_SPATIAL_ANNOTATION", f"{path}:{line_no} [{section}]: malformed ZET:SPATIAL annotation")
        if spatial_match:
            spatial_kind, state = spatial_match.groups()
            state = state or "visible"
            body = (body[:spatial_match.start()] + body[spatial_match.end():]).strip()
        if requested is not None and requested not in allowed and spatial_kind != "fixed":
            any_tagged_out = True
            continue
        if spatial_kind:
            body, record = _translate_spatial_line(
                body, spatial_kind, state, domain, requested, allowed,
                expression is not None or default is not None,
                path=path, section=section, line=line_no,
            )
            if record:
                spatial_translations.append(record)
            if not body:
                spatial_out = True
                continue
        cleaned = f"{bullet}{body}" if expression is not None or spatial_match else raw_line
        retained.append((cleaned, line_no))
    retained = _prune_empty_headings(retained)
    rendered = "\n".join(line for line, _ in retained).strip("\n")
    diagnostics = list(source.get("view_conditioning_diagnostics") or [])
    if any_tagged_out and context.unknown_view:
        diagnostics.append(f"{section}: view-specific lines omitted because the requested orientation is unavailable")
    if (context.head_view is not None or context.body_view is not None) and re.search(
        r"\banatomical[ -](?:left|right)\b", rendered, re.IGNORECASE
    ):
        diagnostics.append(f"{section}: unresolved anatomical side wording remains in legacy prose")
    updated_source = dict(source, retained_lines=[line for _, line in retained],
                          view_conditioning_diagnostics=diagnostics,
                          spatial_translations=spatial_translations)
    return rendered, updated_source, (any_tagged_out or spatial_out) and not bool(rendered.strip())


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
