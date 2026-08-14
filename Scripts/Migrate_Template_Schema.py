#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

from Scripts.Compile_Character_Template import load_template_sections
from Scripts.Library_Paths import character_root


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIEWS = (
    "FRONT",
    "FRONT_LEFT_3_4",
    "FRONT_RIGHT_3_4",
    "LEFT_PROFILE",
    "RIGHT_PROFILE",
    "BACK_LEFT_3_4",
    "BACK_RIGHT_3_4",
    "BACK",
)


def metadata(text: str, labels: tuple[str, ...]) -> list[str]:
    values = []
    for label in labels:
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text)
        values.append(f"{label}: {match.group(1).strip() if match else '`[]`'}")
    return values


def marked(name: str, value: str) -> str:
    return f"<!-- ZET:BEGIN {name} -->\n\n{value.strip()}\n\n<!-- ZET:END {name} -->"


def section_block(title: str, name: str, value: str) -> str:
    return f"## {title}\n\n{marked(name, value)}"


def view_blocks(title: str, prefix: str, sections: dict[str, str]) -> str:
    blocks = [f"## {title}"]
    for view in VIEWS:
        name = f"{prefix}{view}"
        blocks.append(marked(name, sections.get(name, "")))
    return "\n\n".join(blocks)


def combined(sections: dict[str, str], names: tuple[str, ...], labels: tuple[str, ...]) -> str:
    blocks = []
    for name, label in zip(names, labels):
        value = sections.get(name, "").strip()
        if value:
            blocks.append(f"### {label}\n\n{value}")
    return "\n\n".join(blocks)


def assembly_character_requirements(sections: dict[str, str]) -> str:
    blocks = []
    rendering = sections.get("CHARACTER_ASSEMBLY_RENDERING_RULES", "").strip()
    if rendering:
        blocks.append(rendering)
    for name in (
        "CHARACTER_ASSEMBLY_NEGATIVE_GUIDANCE_JOB_SPECIFIC",
        "CHARACTER_ASSEMBLY_ACCEPTANCE_CRITERIA",
    ):
        selected = []
        for line in sections.get(name, "").splitlines():
            lowered = line.casefold()
            if any(term in lowered for term in ("age", "elder", "youth", "phase")):
                selected.append(line)
        if selected:
            blocks.append("\n".join(selected).strip())
    return "\n\n".join(blocks)


def archive(path: Path, title: str, sections: dict[str, str], names: list[str]) -> None:
    populated = [(name, sections.get(name, "").strip()) for name in names if sections.get(name, "").strip()]
    if not populated:
        return
    lines = [f"# {title}", "", "These sections were removed from the active template schema. Their original text is preserved verbatim for review and recovery.", ""]
    for name, value in populated:
        lines.extend([f"## {name}", "", value, ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def migrate_character(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    sections = load_template_sections(path)
    retained = {
        "BODY_DESCRIPTION_FACTS",
        "HEAD_DESCRIPTION_FACTS",
        "HAIR_DESCRIPTION_FACTS",
        "EXPRESSION_DESCRIPTION_FACTS",
        "IDENTITY_PRESERVATION_CORE",
        "IDENTITY_PRESERVATION_FACE",
        "IDENTITY_PRESERVATION_EYES",
        "IDENTITY_PRESERVATION_HAIR",
        "IDENTITY_PRESERVATION_EARS",
    }
    for prefix in ("BODY_DESCRIPTION_VIEW_", "HEAD_DESCRIPTION_VIEW_", "HAIR_DESCRIPTION_VIEW_"):
        retained.update(f"{prefix}{view}" for view in VIEWS)
    renamed = {
        "IDENTITY_PRESERVATION_SCENE",
        "BODY_REFERENCE_RENDERING_RULES",
        "HEAD_IMAGE_REFERENCE_INSTRUCTIONS",
        "HEAD_IMAGE_REFERENCE_RULES",
        "HEAD_IMAGE_RENDERING_RULES",
        "HEAD_IMAGE_NEGATIVE_GUIDANCE_JOB_SPECIFIC",
        "NEGATIVE_GUIDANCE_GENERAL",
        "NEGATIVE_GUIDANCE_JOB_SPECIFIC",
        "CHARACTER_ASSEMBLY_RENDERING_RULES",
        "CHARACTER_ASSEMBLY_NEGATIVE_GUIDANCE_JOB_SPECIFIC",
        "CHARACTER_ASSEMBLY_ACCEPTANCE_CRITERIA",
        "HEAD_IMAGE_TRANSFORM_INSTRUCTIONS",
    }
    retired = sorted(set(sections) - retained - renamed)
    retired.extend([
        "CHARACTER_ASSEMBLY_NEGATIVE_GUIDANCE_JOB_SPECIFIC",
        "CHARACTER_ASSEMBLY_ACCEPTANCE_CRITERIA",
    ])
    archive(path.with_name("Character_Retired_Sections.md"), "Retired Character Sections", sections, list(dict.fromkeys(retired)))

    negative_expression = combined(
        sections,
        ("NEGATIVE_GUIDANCE_GENERAL", "NEGATIVE_GUIDANCE_JOB_SPECIFIC"),
        ("General", "Phase-specific"),
    )
    groups = [
        "# Character Image Template\n\n" + "\n".join(metadata(original, (
            "Character Name", "Character Phase", "Species / Ancestry", "Gender Presentation", "Canonical Art Style"
        ))),
        "# Body Description\n\n" + section_block("Body Description — Just the Facts", "BODY_DESCRIPTION_FACTS", sections.get("BODY_DESCRIPTION_FACTS", "")) + "\n\n" + view_blocks("Body Description — View-Specific", "BODY_DESCRIPTION_VIEW_", sections),
        "# Head Description\n\n" + section_block("Head Description — Just the Facts", "HEAD_DESCRIPTION_FACTS", sections.get("HEAD_DESCRIPTION_FACTS", "")) + "\n\n" + view_blocks("Head Description — View-Specific", "HEAD_DESCRIPTION_VIEW_", sections),
        "# Hair Description\n\n" + section_block("Hair Description — Just the Facts", "HAIR_DESCRIPTION_FACTS", sections.get("HAIR_DESCRIPTION_FACTS", "")) + "\n\n" + view_blocks("Hair Description — View-Specific", "HAIR_DESCRIPTION_VIEW_", sections),
        "# Expression\n\n" + section_block("Expression Guidance", "EXPRESSION_DESCRIPTION_FACTS", sections.get("EXPRESSION_DESCRIPTION_FACTS", "")),
        "# Identity Preservation\n\n" + "\n\n".join((
            section_block("Core", "IDENTITY_PRESERVATION_CORE", sections.get("IDENTITY_PRESERVATION_CORE", "")),
            section_block("Face", "IDENTITY_PRESERVATION_FACE", sections.get("IDENTITY_PRESERVATION_FACE", "")),
            section_block("Eyes", "IDENTITY_PRESERVATION_EYES", sections.get("IDENTITY_PRESERVATION_EYES", "")),
            section_block("Hair", "IDENTITY_PRESERVATION_HAIR", sections.get("IDENTITY_PRESERVATION_HAIR", "")),
            section_block("Ears", "IDENTITY_PRESERVATION_EARS", sections.get("IDENTITY_PRESERVATION_EARS", "")),
        )),
        "# Scene Rendering\n\n" + section_block("Scene Character Identity", "SCENE_CHARACTER_IDENTITY", sections.get("IDENTITY_PRESERVATION_SCENE", "")),
        "# Body Reference\n\n" + section_block("Character Requirements", "BODY_REFERENCE_CHARACTER_REQUIREMENTS", sections.get("BODY_REFERENCE_RENDERING_RULES", "")),
        "# Head Image\n\n" + "\n\n".join((
            section_block("Transform Instructions", "HEAD_IMAGE_TRANSFORM_INSTRUCTIONS", sections.get("HEAD_IMAGE_TRANSFORM_INSTRUCTIONS", "")),
            section_block("Source Instructions", "HEAD_IMAGE_SOURCE_INSTRUCTIONS", sections.get("HEAD_IMAGE_REFERENCE_INSTRUCTIONS", "")),
            section_block("Source Rules", "HEAD_IMAGE_SOURCE_RULES", sections.get("HEAD_IMAGE_REFERENCE_RULES", "")),
            section_block("Character Requirements", "HEAD_IMAGE_CHARACTER_REQUIREMENTS", sections.get("HEAD_IMAGE_RENDERING_RULES", "")),
            section_block("Negative Guidance", "NEGATIVE_GUIDANCE_HEAD_IMAGE", sections.get("HEAD_IMAGE_NEGATIVE_GUIDANCE_JOB_SPECIFIC", "")),
        )),
        "# Character Assembly\n\n" + section_block("Character Requirements", "CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS", assembly_character_requirements(sections)),
        "# Expression Negative Guidance\n\n" + section_block("Negative Guidance", "NEGATIVE_GUIDANCE_EXPRESSION", negative_expression),
    ]
    path.write_text("\n\n---\n\n".join(groups).rstrip() + "\n", encoding="utf-8")


def migrate_costume(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    sections = load_template_sections(path)
    retired = [name for name in ("COMPILER_NOTES", "LOCAL_IMAGE_GEN_OVERRIDES") if name in sections]
    archive(path.with_name(f"{path.stem}_Retired_Sections.md"), "Retired Costume Sections", sections, retired)
    groups = [
        "# Costume Template\n\n" + "\n".join(metadata(original, (
            "Costume Name", "Character Name", "Character Phase", "Costume Role", "Footwear", "Footwear Contact"
        ))),
        "# Costume Description\n\n" + section_block("Costume Description — Just the Facts", "COSTUME_DESCRIPTION_FACTS", sections.get("COSTUME_DESCRIPTION_FACTS", "")) + "\n\n" + view_blocks("Costume Description — View-Specific", "COSTUME_DESCRIPTION_VIEW_", sections),
        "# Equipment, Jewelry, and Props\n\n" + section_block("Equipment, Jewelry, and Props — Just the Facts", "EQUIPMENT_JEWELRY_PROPS_FACTS", sections.get("EQUIPMENT_DESCRIPTION_FACTS", "")) + "\n\n" + view_blocks("Equipment, Jewelry, and Props — View-Specific", "EQUIPMENT_JEWELRY_PROPS_VIEW_", {
            f"EQUIPMENT_JEWELRY_PROPS_VIEW_{view}": sections.get(f"EQUIPMENT_DESCRIPTION_VIEW_{view}", "") for view in VIEWS
        }),
        "# Costume Identity\n\n" + section_block("Costume Identity Rules", "COSTUME_IDENTITY_RULES", sections.get("IDENTITY_PRESERVATION_COSTUME", "")) + "\n\n" + section_block("Scene Costume Identity", "SCENE_COSTUME_IDENTITY", sections.get("IDENTITY_PRESERVATION_COSTUME_SCENE", "")),
    ]
    path.write_text("\n\n---\n\n".join(groups).rstrip() + "\n", encoding="utf-8")


def migrate_expression_tokens(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "{{SECTION:EXPRESSION_DESCRIPTION_FACTS}}": "{{EXPRESSION_DESCRIPTION_FACTS}}",
        "{{SECTION:IDENTITY_PRESERVATION_CORE}}": "{{IDENTITY_PRESERVATION_CORE}}",
        "{{SECTION:IDENTITY_PRESERVATION_FACE}}": "{{IDENTITY_PRESERVATION_FACE}}",
        "{{SECTION:IDENTITY_PRESERVATION_HAIR}}": "{{IDENTITY_PRESERVATION_HAIR}}",
        "{{SECTION:IDENTITY_PRESERVATION_EARS}}": "{{IDENTITY_PRESERVATION_EARS}}",
        "{{SECTION:IDENTITY_PRESERVATION_COSTUME}}": "{{COSTUME_IDENTITY_RULES}}",
        "{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}": "{{NEGATIVE_GUIDANCE_EXPRESSION}}",
        "{{SECTION:NEGATIVE_GUIDANCE_JOB_SPECIFIC}}": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    shared = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared"
    migrate_character(shared / "Character_Template.md")
    migrate_costume(shared / "Costume_Template.md")
    migrate_expression_tokens(shared / "Expression_Template.md")

    root = character_root(PROJECT_ROOT) / "Tsaeytte"
    for path in sorted(root.glob("*/Character.md")):
        migrate_character(path)
    for path in sorted(root.glob("*/Costume_*.md")):
        migrate_costume(path)
    for path in sorted(root.glob("*/Expressions/*.md")):
        migrate_expression_tokens(path)


if __name__ == "__main__":
    main()
