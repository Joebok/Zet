"""Parsing for template-owned prompt-packet declarations."""
from __future__ import annotations

import json
import re


_START = re.compile(r"<!--\s*ZET:PROMPT_PACKET\s*")
_COMMENT = re.compile(r"<!--\s*ZET:PROMPT_PACKET\b.*?-->", re.S)


def extract_prompt_packet_metadata(text: str, *, strip: bool = True) -> tuple[str, list[dict]]:
    """Return prose and decoded declarations; optionally preserve fragment whitespace."""
    declarations = []
    decoder = json.JSONDecoder()
    for match in _START.finditer(text):
        try:
            value, end = decoder.raw_decode(text, match.end())
        except json.JSONDecodeError as exc:
            raise ValueError("ZET:PROMPT_PACKET must contain valid JSON.") from exc
        if not isinstance(value, dict):
            raise ValueError("ZET:PROMPT_PACKET must contain a JSON object.")
        closing = re.match(r"\s*-->", text[end:])
        if closing is None:
            raise ValueError("ZET:PROMPT_PACKET JSON must end at the comment boundary.")
        declarations.append(value)
    prose = _COMMENT.sub("", text)
    return (prose.strip() if strip else prose), declarations
