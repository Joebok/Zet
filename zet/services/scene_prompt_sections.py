from __future__ import annotations

import re
from pathlib import Path


FINAL_IMAGE_PROMPT_SECTION_TITLES = {
    "anatomical_requirements": "Anatomical Requirements",
    "avoid": "Avoid",
    "high_risk_elements": "High-Risk Elements",
    "final_verification": "Final Verification",
}


def load_final_image_prompt_sections(path: Path) -> dict[str, str]:
    markdown = Path(path).read_text(encoding="utf-8")
    matches = list(re.finditer(r"^# ([^\r\n]+)\s*$", markdown, flags=re.MULTILINE))
    headings = [match.group(1).strip() for match in matches]
    expected = list(FINAL_IMAGE_PROMPT_SECTION_TITLES.values())
    for title in expected:
        count = headings.count(title)
        if count != 1:
            raise ValueError(f"Expected exactly one '# {title}' section; found {count}.")
    if headings != expected:
        raise ValueError(f"Expected sections in this order: {', '.join(expected)}.")
    sections = {}
    for index, (key, title) in enumerate(FINAL_IMAGE_PROMPT_SECTION_TITLES.items()):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        section = markdown[matches[index].start():end].strip()
        if not any(line.strip() for line in section.splitlines()[1:]):
            raise ValueError(f"Expected '# {title}' section to contain text.")
        sections[key] = section
    return sections


def select_final_image_prompt_sections(
    defaults: dict[str, str], overrides: dict | None
) -> dict[str, str]:
    selected = {}
    overrides = overrides if isinstance(overrides, dict) else {}
    for key, title in FINAL_IMAGE_PROMPT_SECTION_TITLES.items():
        default = defaults.get(key)
        if not isinstance(default, str) or not default.strip():
            raise ValueError(f"Missing default '# {title}' section.")
        override = overrides.get(key)
        selected[key] = override.strip() if isinstance(override, str) and override.strip() else default.strip()
    return selected
