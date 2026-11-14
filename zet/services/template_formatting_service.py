"""Formatting helpers for canonical Character and Costume Markdown templates."""
from __future__ import annotations

import re
import os

from Scripts.Compile_Character_Template import MARKER_RE


_BULLET_SEPARATOR = re.compile(r"(?<=\.)[ \t]+(?=\* +(?:\[[^]\n]+\][ \t]+)?[A-Z0-9])")
_INLINE_CODE = re.compile(r"`+[^`]*?`+")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")


def _split_body(body: str) -> str:
    lines = body.splitlines()
    trailing_newline = body.endswith("\n")
    in_fence = False
    result = []
    for line in lines:
        if re.match(r"^\s{0,3}`{3,}|^\s{0,3}~{3,}", line):
            in_fence = not in_fence
            result.append(line)
            continue
        if in_fence or not line.lstrip().startswith(("* ", "- ", "+ ")):
            result.append(line)
            continue
        # Mask inline code and comments so their asterisks cannot become bullets.
        protected = _INLINE_CODE.sub(lambda m: " " * len(m.group()), line)
        protected = _COMMENT.sub(lambda m: " " * len(m.group()), protected)
        separators = [m.start() for m in _BULLET_SEPARATOR.finditer(protected)]
        if not separators:
            result.append(line)
            continue
        start = 0
        for position in separators:
            result.append(line[start:position].rstrip())
            start = position + 1
        result.append(line[start:].lstrip())
    return "\n".join(result) + ("\n" if trailing_newline else "")


def format_template(text: str) -> str:
    """Normalize newlines and split clear packed bullets in ZET section bodies."""
    text = normalize_newlines(text)
    markers = list(MARKER_RE.finditer(text))
    for begin, end in reversed(list(zip(markers[::2], markers[1::2]))):
        if begin.group(1) != "BEGIN" or end.group(1) != "END" or begin.group(2) != end.group(2):
            continue
        body = text[begin.end():end.start()]
        formatted = _split_body(body)
        text = text[:begin.end()] + formatted + text[end.start():]
    return text


def format_bullet_list(text: str) -> str:
    """Split recognizable packed bullets in an editor field or wizard response."""
    return _split_body(normalize_newlines(text))


def template_bytes(text: str) -> bytes:
    newline = "\r\n" if os.name == "nt" else "\n"
    return format_template(text).replace("\n", newline).encode("utf-8")
