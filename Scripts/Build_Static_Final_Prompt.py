#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

from Scripts.Compile_Character_Template import CompiledSelection, TemplateCompileError, resolve_section_name
from Scripts.Library_Paths import library_root
from zet.services.auxiliary_resource_tags import AUXILIARY_RESOURCE_TAG_RE, auxiliary_resource_image_for_tag


SECTION_PLACEHOLDER_RE = re.compile(r"\{\{SECTION:([A-Z0-9_{}]+)\}\}")
RAW_SECTION_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_{}]+)\}\}")
COMMENTED_SECTION_PLACEHOLDER_LINE_RE = re.compile(r"(?m)^[ \t]*~\{\{SECTION:[A-Z0-9_{}]+\}\}[ \t]*(?:\r?\n)?")
ANY_PLACEHOLDER_RE = re.compile(r"\{\{[^}]+(?:}[^}]*)?\}\}")
SINGLE_BRACE_TOKEN_RE = re.compile(r"(?<!\{)\{([A-Z0-9_]+)\}(?!\})")


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _source_fragment(
    text: str,
    source: dict,
    *,
    placeholder: str | None = None,
) -> dict:
    item = dict(source)
    item["text"] = text
    if placeholder:
        item["placeholder"] = placeholder
    return item


def _render_lines_with_sources(pieces: list[dict]) -> tuple[str, list[dict]]:
    line_items: list[dict] = []
    current_text = ""
    current_sources: list[dict] = []

    for piece in pieces:
        text = str(piece.get("text", ""))
        if not text:
            continue
        source = {key: value for key, value in piece.items() if key != "text"}
        parts = text.split("\n")
        for index, part in enumerate(parts):
            current_text += part
            if part.strip():
                current_sources.append(source)
            if index < len(parts) - 1:
                line_items.append({"text": current_text, "sources": list(current_sources)})
                current_text = ""
                current_sources = []
    line_items.append({"text": current_text, "sources": list(current_sources)})

    collapsed: list[dict] = []
    blank_count = 0
    for item in line_items:
        if item["text"].strip():
            blank_count = 0
            collapsed.append(item)
            continue
        blank_count += 1
        if blank_count <= 1:
            collapsed.append(item)

    while collapsed and not collapsed[0]["text"].strip():
        collapsed.pop(0)
    while collapsed and not collapsed[-1]["text"].strip():
        collapsed.pop()

    rendered = re.sub(r"\n{3,}", "\n\n", "\n".join(item["text"] for item in collapsed)).strip() + "\n"
    fragments: list[dict] = []
    active_key = None
    active_source = None
    start_line = 1
    previous_line = 0

    def best_source(sources: list[dict]) -> dict:
        if not sources:
            return {
                "source_kind": "unknown",
                "source_path": "",
                "source_label": "No source map entry",
                "editable": False,
            }
        for source in sources:
            if source.get("source_kind") != "static_prompt_template":
                return source
        return sources[0]

    for line_number, item in enumerate(collapsed, start=1):
        if not item["text"].strip():
            continue
        source = best_source(item.get("sources", []))
        key = tuple(sorted((k, str(v)) for k, v in source.items()))
        if key != active_key or line_number != previous_line + 1:
            if active_source is not None:
                fragments.append(
                    {
                        "fragment_id": f"f{len(fragments) + 1:04d}",
                        "prompt_start_line": start_line,
                        "prompt_end_line": previous_line,
                        **active_source,
                    }
                )
            active_key = key
            active_source = source
            start_line = line_number
        previous_line = line_number

    if active_source is not None:
        fragments.append(
            {
                "fragment_id": f"f{len(fragments) + 1:04d}",
                "prompt_start_line": start_line,
                "prompt_end_line": previous_line,
                **active_source,
            }
        )

    return rendered, fragments


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


def _single_brace_token_values(metadata: dict[str, str], view_token: str) -> dict[str, str]:
    """Build replacement values for single-brace prompt tokens."""
    values = {str(key): str(value) for key, value in metadata.items() if str(value).strip()}
    values["VIEW"] = view_token
    values.setdefault("FOOTWEAR", "feet")
    values.setdefault(
        "FOOTWEAR_CONTACT",
        "Both feet are flat on the floor.\nBoth heels are fully planted.\nBoth forefeet and toes touch the ground.",
    )
    values.setdefault("FOOTWEAR_GROUNDING", "Both feet remain flat on the ground.")
    return values


def _replace_single_brace_tokens(text: str, values: dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    return SINGLE_BRACE_TOKEN_RE.sub(replace, text)


def _raise_unresolved_single_brace_token(rendered: str) -> None:
    match = SINGLE_BRACE_TOKEN_RE.search(rendered)
    if match:
        raise TemplateCompileError(
            "UNRESOLVED_SINGLE_BRACE_TOKEN",
            f"Final prompt contains unresolved single-brace token: {{{match.group(1)}}}",
        )


def _project_root_for_template(template_path: Path) -> Path:
    """Find the project root for a prompt template path."""
    resolved = template_path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / "Config").exists() and (parent / "config.toml").exists():
            return parent
    return resolved.parents[2]


def _auxiliary_inventory_path(template_path: Path) -> Path:
    """Return the global auxiliary resource inventory path."""
    return library_root(_project_root_for_template(template_path)) / "AuxiliaryResources" / "AuxiliaryResources.json"


def _load_auxiliary_resources(template_path: Path) -> list[dict]:
    """Load global auxiliary resource records."""
    path = _auxiliary_inventory_path(template_path)
    if not path.exists():
        return []
    try:
        import json
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    records = payload.get("resources", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    resources = []
    for record in records:
        if not isinstance(record, dict):
            continue
        resources.append(record)
    return resources


def _auxiliary_resource_text(resource: dict, image: dict) -> str:
    """Render an auxiliary resource record into prompt-readable text."""
    category = str(resource.get("category") or "")
    resource_id = str(resource.get("resource_id") or "")
    label = str(resource.get("label") or resource_id)
    image_path = str(image.get("image_path") or "")
    return f"Auxiliary reference ({category}/{resource_id}): {label}. Image file: {image_path}."


def _replace_auxiliary_resource_tags(text: str, template_path: Path, resources: list[dict] | None = None) -> str:
    """Replace auxiliary resource tags with prompt-readable text."""
    resource_index = resources if resources is not None else _load_auxiliary_resources(template_path)

    def replace(match: re.Match) -> str:
        try:
            resource, image = auxiliary_resource_image_for_tag(resource_index, match.group(0))
        except LookupError:
            raise TemplateCompileError("MISSING_AUXILIARY_RESOURCE", f"No auxiliary resource found for tag: {match.group(0)}")
        return _auxiliary_resource_text(resource, image)

    return AUXILIARY_RESOURCE_TAG_RE.sub(replace, text)


def render_static_prompt(
    template_text: str,
    metadata: dict[str, str],
    selection: CompiledSelection,
    required_section_names: list[str],
    view_token: str,
) -> str:
    rendered = COMMENTED_SECTION_PLACEHOLDER_LINE_RE.sub("", template_text)
    single_brace_values = _single_brace_token_values(metadata, view_token)
    rendered = _replace_single_brace_tokens(rendered, single_brace_values)
    for key, value in metadata.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    required_set = {resolve_section_name(name, view_token) for name in required_section_names}

    def replace_section(match: re.Match) -> str:
        name = resolve_section_name(match.group(1), view_token)
        text = selection.sections.get(name, "")
        if name in required_set and not text.strip():
            raise TemplateCompileError("MISSING_REQUIRED_SECTION", f"Required section missing from final prompt: {name}")
        return _replace_single_brace_tokens(text, single_brace_values)

    rendered = SECTION_PLACEHOLDER_RE.sub(replace_section, rendered)

    def replace_raw_section(match: re.Match) -> str:
        inner = match.group(1)
        metadata_key = inner if inner in metadata else inner.upper()
        if metadata_key in metadata:
            return _replace_single_brace_tokens(metadata[metadata_key], single_brace_values)
        name = resolve_section_name(inner, view_token)
        text = selection.sections.get(name)
        if text is None:
            return match.group(0)
        if name in required_set and not text.strip():
            raise TemplateCompileError("MISSING_REQUIRED_SECTION", f"Required section missing from final prompt: {name}")
        return _replace_single_brace_tokens(text, single_brace_values)

    rendered = RAW_SECTION_PLACEHOLDER_RE.sub(replace_raw_section, rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip() + "\n"

    _raise_unresolved_single_brace_token(rendered)
    match = ANY_PLACEHOLDER_RE.search(rendered)
    if match:
        raise TemplateCompileError(
            "UNRESOLVED_PLACEHOLDER",
            f"Final prompt contains unresolved placeholder: {match.group(0)}",
        )
    if "<!-- ZET:" in rendered:
        raise TemplateCompileError("ZET_MARKER_IN_FINAL_PROMPT", "Final prompt contains ZET markers.")
    return rendered


def render_static_prompt_with_source_map(
    template_text: str,
    *,
    template_path: Path,
    metadata: dict[str, str],
    metadata_sources: dict[str, dict],
    selection: CompiledSelection,
    required_section_names: list[str],
    view_token: str,
    final_prompt_name: str,
) -> tuple[str, dict]:
    template_source = {
        "source_kind": "static_prompt_template",
        "source_path": str(template_path),
        "source_label": f"Prompt template: {template_path.name}",
        "editable": True,
    }
    single_brace_values = _single_brace_token_values(metadata, view_token)
    rendered_template = _replace_single_brace_tokens(
        COMMENTED_SECTION_PLACEHOLDER_LINE_RE.sub("", template_text),
        single_brace_values,
    )
    required_set = {resolve_section_name(name, view_token) for name in required_section_names}
    token_re = re.compile(rf"{AUXILIARY_RESOURCE_TAG_RE.pattern}|\{{\{{SECTION:[A-Z0-9_{{}}]+\}}\}}|\{{\{{[A-Za-z0-9_{{}}]+\}}\}}")
    pieces: list[dict] = []
    cursor = 0
    auxiliary_resources = _load_auxiliary_resources(template_path)

    def section_source(name: str) -> dict:
        return selection.section_sources.get(
            name,
            {
                "source_kind": "character_template_section",
                "source_path": "",
                "source_label": f"Template section: {name}",
                "section_name": name,
                "editable": True,
            },
        )

    for match in token_re.finditer(rendered_template):
        if match.start() > cursor:
            pieces.append(_source_fragment(rendered_template[cursor:match.start()], template_source))
        placeholder = match.group(0)
        inner = placeholder[2:-2]
        text = placeholder
        source = template_source
        if inner.startswith("SECTION:"):
            name = resolve_section_name(inner.split(":", 1)[1], view_token)
            text = selection.sections.get(name, "")
            if name in required_set and not text.strip():
                raise TemplateCompileError("MISSING_REQUIRED_SECTION", f"Required section missing from final prompt: {name}")
            text = _replace_single_brace_tokens(text, single_brace_values)
            text = _replace_auxiliary_resource_tags(text, template_path, auxiliary_resources)
            source = section_source(name)
        elif inner.startswith("AUX:"):
            try:
                resource, image = auxiliary_resource_image_for_tag(auxiliary_resources, placeholder)
            except LookupError:
                raise TemplateCompileError("MISSING_AUXILIARY_RESOURCE", f"No auxiliary resource found for tag: {placeholder}")
            text = _auxiliary_resource_text(resource, image)
            source = {
                "source_kind": "auxiliary_resource",
                "source_path": str(_auxiliary_inventory_path(template_path)),
                "source_label": f"Auxiliary resource: {resource.get('label') or resource.get('resource_id')}",
                "resource_id": resource.get("resource_id"),
                "category": resource.get("category"),
                "editable": True,
            }
        else:
            name = resolve_section_name(inner, view_token)
            metadata_key = inner if inner in metadata else inner.upper()
            if metadata_key in metadata:
                text = _replace_single_brace_tokens(metadata[metadata_key], single_brace_values)
                source = metadata_sources.get(
                    metadata_key,
                    {
                        "source_kind": "runtime_generated",
                        "source_path": "",
                        "source_label": metadata_key,
                        "editable": False,
                    },
                )
            elif name in selection.sections or name in selection.missing_optional:
                text = selection.sections.get(name, "")
                if name in required_set and not text.strip():
                    raise TemplateCompileError("MISSING_REQUIRED_SECTION", f"Required section missing from final prompt: {name}")
                text = _replace_single_brace_tokens(text, single_brace_values)
                text = _replace_auxiliary_resource_tags(text, template_path, auxiliary_resources)
                source = section_source(name)
        pieces.append(_source_fragment(text, source, placeholder=placeholder))
        cursor = match.end()

    if cursor < len(rendered_template):
        pieces.append(_source_fragment(rendered_template[cursor:], template_source))

    rendered, fragments = _render_lines_with_sources(pieces)
    _raise_unresolved_single_brace_token(rendered)
    match = ANY_PLACEHOLDER_RE.search(rendered)
    if match:
        raise TemplateCompileError(
            "UNRESOLVED_PLACEHOLDER",
            f"Final prompt contains unresolved placeholder: {match.group(0)}",
        )
    if "<!-- ZET:" in rendered:
        raise TemplateCompileError("ZET_MARKER_IN_FINAL_PROMPT", "Final prompt contains ZET markers.")

    return rendered, {
        "schema_version": 1,
        "final_prompt": final_prompt_name,
        "fragments": fragments,
    }


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
    suppressed = job_metadata.get("suppressed_sections", {})
    if isinstance(suppressed, dict) and suppressed:
        lines.extend(["", "## Suppressed Sections", ""])
        lines.extend(f"- {name}: {reason}" for name, reason in suppressed.items())
    lines.extend(["", "---", ""])

    for name in selection.included_required + selection.included_optional:
        lines.extend([f"# {name}", "", selection.sections[name], ""])

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

