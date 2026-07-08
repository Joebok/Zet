#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from Compile_Character_Template import MARKER_RE, TemplateCompileError, load_template_sections, resolve_section_name


@dataclass
class EditorSection:
    name: str
    source_name: str
    required: bool
    label: str
    description: str
    text: str


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_bundles(project_root: Path = PROJECT_ROOT) -> dict:
    data = _load_json(project_root / "Config" / "Prompt_Task_Bundles.json")
    return data.get("bundles", data)


def load_section_metadata(project_root: Path = PROJECT_ROOT) -> dict:
    data = _load_json(project_root / "Config" / "Prompt_Section_Metadata.json")
    return data.get("sections", data)


def list_pipeline_names(project_root: Path = PROJECT_ROOT) -> list[str]:
    bundles = load_bundles(project_root)
    return sorted(bundles.keys())


def list_pipeline_section_names(pipeline: str, view_token: str, project_root: Path = PROJECT_ROOT) -> tuple[list[str], set[str]]:
    bundles = load_bundles(project_root)
    bundle = bundles.get(pipeline)
    if not isinstance(bundle, dict):
        raise TemplateCompileError("MISSING_CONFIG", f"Unknown pipeline: {pipeline}")
    names: list[str] = []
    required: set[str] = set()
    for raw in bundle.get("required_sections", []):
        name = resolve_section_name(raw, view_token)
        names.append(name)
        required.add(name)
    for raw in bundle.get("optional_sections", []):
        names.append(resolve_section_name(raw, view_token))
    return names, required


def _metadata_for(section_name: str, source_name: str, metadata: dict) -> tuple[str, str]:
    item = metadata.get(source_name) or metadata.get(section_name) or {}
    if not isinstance(item, dict):
        return section_name, ""
    return str(item.get("label", section_name)), str(item.get("description", ""))


def load_editor_sections(template_path: Path, pipeline: str, view_token: str, project_root: Path = PROJECT_ROOT) -> list[EditorSection]:
    sections = load_template_sections(template_path) if template_path.exists() else {}
    bundles = load_bundles(project_root)
    bundle = bundles.get(pipeline)
    if not isinstance(bundle, dict):
        raise TemplateCompileError("MISSING_CONFIG", f"Unknown pipeline: {pipeline}")
    metadata = load_section_metadata(project_root)
    result: list[EditorSection] = []
    for source_name in list(bundle.get("required_sections", [])) + list(bundle.get("optional_sections", [])):
        name = resolve_section_name(source_name, view_token)
        label, description = _metadata_for(name, source_name, metadata)
        result.append(
            EditorSection(
                name=name,
                source_name=source_name,
                required=source_name in bundle.get("required_sections", []),
                label=label,
                description=description,
                text=sections.get(name, ""),
            )
        )
    return result


def validate_section_text(text: str) -> None:
    if "<!-- ZET:BEGIN" in text or "<!-- ZET:END" in text:
        raise TemplateCompileError("TEMPLATE_SAVE_REJECTED_MARKER_TEXT", "Section text cannot contain ZET markers.")


def _replace_existing_sections(original: str, updates: dict[str, str]) -> tuple[str, set[str]]:
    pieces: list[str] = []
    cursor = 0
    open_name: str | None = None
    begin_start = 0
    content_start = 0
    replaced: set[str] = set()

    for marker in MARKER_RE.finditer(original):
        kind, name = marker.group(1), marker.group(2)
        if kind == "BEGIN":
            if open_name is not None:
                raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"Nested marker before closing {open_name}.")
            open_name = name
            begin_start = marker.start()
            content_start = marker.end()
            continue
        if open_name is None:
            raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"End marker without begin: {name}")
        if name != open_name:
            raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"Marker mismatch: began {open_name}, ended {name}")
        if name in updates:
            pieces.append(original[cursor:begin_start])
            pieces.append(f"<!-- ZET:BEGIN {name} -->\n\n{updates[name].strip()}\n\n<!-- ZET:END {name} -->")
            cursor = marker.end()
            replaced.add(name)
        open_name = None

    if open_name is not None:
        raise TemplateCompileError("MALFORMED_TEMPLATE_MARKERS", f"Section missing end marker: {open_name}")
    pieces.append(original[cursor:])
    return "".join(pieces), replaced


def save_template_sections(template_path: Path, updated_sections: dict[str, str], section_order: list[str]) -> None:
    for text in updated_sections.values():
        validate_section_text(text)
    original = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    rebuilt, replaced = _replace_existing_sections(original, updated_sections)
    missing = [name for name in section_order if name in updated_sections and name not in replaced]
    if missing:
        if rebuilt and not rebuilt.endswith("\n"):
            rebuilt += "\n"
        for name in missing:
            rebuilt += f"\n<!-- ZET:BEGIN {name} -->\n\n{updated_sections[name].strip()}\n\n<!-- ZET:END {name} -->\n"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(rebuilt.lstrip() if not original else rebuilt, encoding="utf-8")

