from __future__ import annotations

from zet.services.local_render_types import LocalRenderError, LocalRenderResult, LocalRenderUnavailable


NEGATIVE_SECTION_MARKER = "Negative constraints:"


def split_positive_negative_prompt(prompt_text: str) -> tuple[str, str]:
    if NEGATIVE_SECTION_MARKER not in prompt_text:
        return prompt_text, ""
    positive, negative = prompt_text.split(NEGATIVE_SECTION_MARKER, 1)
    return positive.rstrip(), negative.strip()
