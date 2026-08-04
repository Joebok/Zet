"""Conservative deterministic cleanup for compiled scene prompt Markdown."""

from __future__ import annotations

import re


KNOWN_PHRASE_REPLACEMENTS = {
    "takes place On ": "takes place on ",
}

_REFERENCE_TAG_RE = re.compile(r"\{\{(?:ASSET|AUX):.*?\}\}")
_SIMPLE_LIST_SECTIONS = {
    "Environment",
    "Composition",
    "Interactions",
    "Lighting and Mood",
    "Scene Element Preservation",
    "Final Verification",
}


def _protect_reference_tags(markdown: str) -> tuple[str, list[str]]:
    tags: list[str] = []

    def replace(match: re.Match[str]) -> str:
        tags.append(match.group(0))
        return f"@@ZET_REFERENCE_{len(tags) - 1}@@"

    return _REFERENCE_TAG_RE.sub(replace, markdown), tags


def _restore_reference_tags(markdown: str, tags: list[str]) -> str:
    for index, tag in enumerate(tags):
        markdown = markdown.replace(f"@@ZET_REFERENCE_{index}@@", tag)
    return markdown


def _normalized_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().rstrip(".?!").casefold()


def _sentences(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", value.strip()) if part.strip()]


def _suppress_exact_override_duplicates(lines: list[str]) -> list[str]:
    emitted: set[str] = set()
    result: list[str] = []
    for line in lines:
        match = re.match(r"(\s*\*\*Element Override:\*\*\s*)(.*)$", line)
        if match:
            unique = [sentence for sentence in _sentences(match.group(2)) if _normalized_sentence(sentence) not in emitted]
            if unique:
                result.append(match.group(1) + " ".join(unique))
                emitted.update(_normalized_sentence(sentence) for sentence in unique)
            continue
        if line.strip() and not line.lstrip().startswith(("#", "-", "**")):
            emitted.update(_normalized_sentence(sentence) for sentence in _sentences(line))
        elif line.lstrip().startswith("- "):
            emitted.update(_normalized_sentence(sentence) for sentence in _sentences(line.lstrip()[2:]))
        result.append(line)
    return result


def _normalize_line(line: str) -> str:
    indentation = line[: len(line) - len(line.lstrip(" \t"))]
    content = line[len(indentation):]
    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\s+([,.;:])", r"\1", content)
    content = re.sub(r",(?=[.!?])", "", content)
    content = re.sub(r"(?<!\.)\.\s*\.(?!\.)", ".", content)
    content = re.sub(r"([!?])(?:\s*\1)+", r"\1", content)
    content = re.sub(r",(?=\S)", ", ", content)
    content = re.sub(r"([.!?])(?=[A-Z])", r"\1 ", content)
    return indentation + content.rstrip()


def _normalize_simple_section_bullets(lines: list[str]) -> list[str]:
    section = ""
    result: list[str] = []
    for line in lines:
        if line.startswith("# "):
            section = line[2:].strip()
        if section in _SIMPLE_LIST_SECTIONS and line.strip() and not line.startswith(("#", "-", "  ", "**", "```")):
            result.append(f"- {line}")
        else:
            result.append(line)
    return result


def _capitalize_bullet_first_letter(line: str) -> str:
    if not line.startswith("- "):
        return line
    match = re.search(r"[A-Za-z]", line[2:])
    if match is None:
        return line
    index = match.start() + 2
    return line[:index] + line[index].upper() + line[index + 1:]


def cleanup_compiled_scene_prompt(markdown: str, *, protected_ranges: list[tuple[int, int]] | None = None) -> str:
    """Apply narrow, predictable cleanup without rewriting user-authored prose."""
    del protected_ranges  # Reserved for callers that need explicit protected spans later.
    protected, tags = _protect_reference_tags(markdown)
    for old, new in KNOWN_PHRASE_REPLACEMENTS.items():
        protected = protected.replace(old, new)
    lines = [_normalize_line(line) for line in protected.splitlines()]
    lines = _suppress_exact_override_duplicates(lines)
    lines = _normalize_simple_section_bullets(lines)
    lines = [_capitalize_bullet_first_letter(line) for line in lines]
    result: list[str] = []
    previous_heading = False
    for line in lines:
        if line.startswith("#"):
            if result and result[-1] != "":
                result.append("")
            result.append(line)
            previous_heading = True
            continue
        if previous_heading and line != "":
            result.append("")
        if line or not result or result[-1] != "":
            result.append(line)
        previous_heading = False
    return _restore_reference_tags("\n".join(result).strip() + "\n", tags)
