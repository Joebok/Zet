#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

from Compile_Character_Template import CompiledSelection, TemplateCompileError, resolve_section_name


SECTION_PLACEHOLDER_RE = re.compile(r"\{\{SECTION:([A-Z0-9_{}]+)\}\}")
ANY_PLACEHOLDER_RE = re.compile(r"\{\{[^}]+(?:}[^}]*)?\}\}")


def prompt_template_path(project_root: Path, template_name: str) -> Path:
    raw = str(template_name or "").strip()
    if not raw:
        raise TemplateCompileError("MISSING_CONFIG", "Bundle does not define static_prompt_template.")
    if raw.endswith(".md") or "/" in raw:
        path = project_root / raw
    else:
        path = project_root / "Config" / "Prompt_Templates" / f"{raw}.md"
    if not path.exists():
        raise TemplateCompileError("MISSING_TEMPLATE", f"Static prompt template not found: {path}")
    return path


def render_static_prompt(
    template_text: str,
    metadata: dict[str, str],
    selection: CompiledSelection,
    required_section_names: list[str],
    view_token: str,
) -> str:
    rendered = template_text.replace("{VIEW}", view_token)
    for key, value in metadata.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    required_set = {resolve_section_name(name, view_token) for name in required_section_names}

    def replace_section(match: re.Match) -> str:
        name = resolve_section_name(match.group(1), view_token)
        text = selection.sections.get(name, "")
        if name in required_set and not text.strip():
            raise TemplateCompileError("MISSING_REQUIRED_SECTION", f"Required section missing from final prompt: {name}")
        return text

    rendered = SECTION_PLACEHOLDER_RE.sub(replace_section, rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip() + "\n"

    if ANY_PLACEHOLDER_RE.search(rendered):
        raise TemplateCompileError("UNRESOLVED_PLACEHOLDER", "Final prompt contains unresolved placeholders.")
    if "<!-- ZET:" in rendered:
        raise TemplateCompileError("ZET_MARKER_IN_FINAL_PROMPT", "Final prompt contains ZET markers.")
    return rendered


def write_compiled_sections(
    path: Path,
    *,
    job_metadata: dict[str, str],
    view_token: str,
    selection: CompiledSelection,
) -> None:
    lines = [
        "# Compiled Sections",
        "",
        f"Job ID: {job_metadata.get('job_id', '')}",
        f"Task: {job_metadata.get('task', '')}",
        f"Character: {job_metadata.get('character', '')}",
        f"Phase: {job_metadata.get('phase', '')}",
        f"View Token: {view_token}",
        "",
        "## Included Required Sections",
        "",
    ]
    lines.extend(f"- {name}" for name in selection.included_required)
    lines.extend(["", "## Included Optional Sections", ""])
    lines.extend(f"- {name}" for name in selection.included_optional)
    lines.extend(["", "## Missing Optional Sections", ""])
    lines.extend(f"- {name}" for name in selection.missing_optional)
    lines.extend(["", "---", ""])

    for name in selection.included_required + selection.included_optional:
        lines.extend([f"# {name}", "", selection.sections[name], ""])

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

