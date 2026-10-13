from __future__ import annotations
import re
from typing import Any

def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" ,.;")


def _dedupe_join(parts: list[str]) -> str:
    result = []
    seen = set()
    for part in parts:
        cleaned = _clean(part)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return ", ".join(result)


def append_prompt_globals(prompt: str, additions: str) -> str:
    parts = [_clean(prompt)]
    parts.extend(item for item in re.split(r"[,\n]+", additions) if _clean(item))
    return _dedupe_join(parts)
