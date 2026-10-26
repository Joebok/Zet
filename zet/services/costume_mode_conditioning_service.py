"""Composable mode annotations and source-line edits without unchecked-context drift."""
from __future__ import annotations

import re

MODES = ("doll-dressing-ref", "doll-dressing-no-ref", "rotate")
_ANNOTATION = re.compile(r"\s*<!--\s*ZET:RENDER_MODES\s+([a-z, -]+?)\s*-->")


def condition_mode_line(line, mode):
    matches = list(_ANNOTATION.finditer(line))
    if "ZET:RENDER_MODES" not in line:
        return line, True, []
    if len(matches) != 1 or line.count("ZET:RENDER_MODES") != 1:
        raise ValueError("Each mode-specific source line needs one valid ZET:RENDER_MODES annotation.")
    match = matches[0]
    modes = [value.strip() for value in match[1].split(",")]
    if not modes or len(set(modes)) != len(modes) or set(modes) - set(MODES):
        raise ValueError("Unknown or duplicate rendering mode in ZET:RENDER_MODES.")
    cleaned = line[:match.start()] + line[match.end():]
    return cleaned, mode is None or mode in modes, modes


def condition_mode_sections(sections, sources, mode):
    """Filter before costume normalization derives equipment/visibility facts."""
    filtered, mapped = {}, dict(sources)
    for name, text in sections.items():
        source = sources.get(name, {})
        decisions = list(source.get("render_mode_conditioning") or [])
        lines = []
        for offset, line in enumerate(text.splitlines()):
            clean, allowed, scope = condition_mode_line(line, mode)
            if scope:
                decisions.append({"source_path": source.get("source_path", ""),
                    "source_line": int(source.get("start_line", 1)) + offset,
                    "render_modes": scope, "omission_reason": "" if allowed else "render mode"})
            lines.append(clean if allowed else "")
        filtered[name] = "\n".join(lines)
        mapped[name] = {**source, "render_mode_conditioning": decisions}
    return filtered, mapped


def scoped_replacement(text, before, after, views, modes):
    """Partition the original line's effective view/mode cells into disjoint prose."""
    from zet.services.view_conditioning_service import VIEW_ORDER, VIEW_SHORT, _TAG, _expand, _inferred_domain, _DIRECTIVE
    if not isinstance(before, str) or not before.strip() or "\n" in before or "\r" in before or text.splitlines().count(before) != 1:
        raise ValueError("A correction must identify exactly one complete source line.")
    if not isinstance(after, str) or not after.strip() or "\n" in after or "\r" in after or "<!-- ZET:BEGIN" in after or "<!-- ZET:END" in after:
        raise ValueError("Supply one replacement prose line, preserving compiler structure.")
    if not views or set(views) - set(VIEW_ORDER) or not modes or set(modes) - set(MODES):
        raise ValueError("Choose affected views and rendering modes.")
    # Determine the containing section and its active inherited view default.
    section, default, canon = "", set(VIEW_ORDER), False
    for line in text.splitlines():
        if line == before:
            break
        marker = re.match(r"\s*<!--\s*ZET:(BEGIN|END)\s+(\w+)\s*-->", line)
        if marker:
            section = marker[2] if marker[1] == "BEGIN" else ""
            default, canon = set(VIEW_ORDER), False
        directive = _DIRECTIVE.match(line)
        if directive and directive[1] == "VIEW_DEFAULT":
            _, default = _expand(directive[2] or "", path="costume", section=section, line=1)
        elif directive and directive[1] == "CANON_ONLY":
            canon = True
    if not section or canon or before.lstrip().startswith(("#", "<!--")) or _inferred_domain(section) != "body":
        raise ValueError("Only renderable costume/equipment prose inside a marked body section can be scoped.")
    clean, _, original_modes = condition_mode_line(before, None)
    tag = _TAG.match(clean)
    original_views = default
    if tag:
        _, original_views = _expand(tag[2], path="costume", section=section, line=1)
        old_body = tag[3]
    else:
        old_body = re.sub(r"^\s*[-*+]\s+", "", clean)
    new_clean, _, _ = condition_mode_line(after, None)
    new_tag = _TAG.match(new_clean)
    new_body = new_tag[3] if new_tag else re.sub(r"^\s*[-*+]\s+", "", new_clean)
    if "ZET:" in new_body and "ZET:SPATIAL" not in new_body:
        raise ValueError("Replacement prose may not add compiler directives.")
    selected_views, selected_modes = set(views), set(modes)
    available_modes = set(original_modes or MODES)
    # Auxiliary reference tags and placeholder tokens must not be duplicated by partitioning.
    if "{{" in before or "{{" in after:
        raise ValueError("Edit prose separately from compiler placeholders and resource declarations.")
    reverse = {view: token for token, view in VIEW_SHORT.items()}
    def emit(body, vs, ms):
        if not vs or not ms:
            return []
        expression = ",".join(reverse[v] for v in VIEW_ORDER if v in vs)
        annotation = "" if set(ms) == set(MODES) else " <!-- ZET:RENDER_MODES " + ",".join(m for m in MODES if m in ms) + " -->"
        return [f"- [{expression}] {body}{annotation}"]
    lines = emit(old_body, original_views - selected_views, available_modes)
    lines += emit(old_body, selected_views & original_views, available_modes - selected_modes)
    lines += emit(new_body, selected_views, selected_modes)
    source_lines = text.splitlines(keepends=True)
    index = next(i for i, line in enumerate(source_lines) if line.rstrip("\r\n") == before)
    start = sum(len(line) for line in source_lines[:index])
    return text[:start] + "\n".join(lines) + text[start + len(before):]
