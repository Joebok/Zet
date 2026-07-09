from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_NEGATIVE_PROMPT = "EasyNegative, plastic texture, glossy"
NEGATIVE_SECTION_MARKER = "Negative constraints:"


class LocalRenderError(Exception):
    pass


class LocalRenderUnavailable(LocalRenderError):
    pass


@dataclass
class LocalRenderResult:
    image_path: Path
    metadata_path: Path
    prompt_review_path: Path | None
    prompt_id: str


def split_positive_negative_prompt(prompt_text: str) -> tuple[str, str]:
    if NEGATIVE_SECTION_MARKER not in prompt_text:
        return prompt_text, DEFAULT_NEGATIVE_PROMPT
    positive, negative = prompt_text.split(NEGATIVE_SECTION_MARKER, 1)
    negative_parts = [negative.strip(), DEFAULT_NEGATIVE_PROMPT]
    return positive.rstrip(), "\n\n".join(part for part in negative_parts if part)
