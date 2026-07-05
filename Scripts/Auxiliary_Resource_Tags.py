#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

from Compile_Character_Template import TemplateCompileError
from Library_Paths import library_root, resolve_library_path


AUX_TAG_RE = re.compile(r"\{\{AUX:(person|place|thing):([a-z0-9][a-z0-9-]*)\}\}")


def auxiliary_inventory_path(project_root: Path) -> Path:
    """Return the global auxiliary resource inventory path."""
    return library_root(project_root) / "AuxiliaryResources" / "AuxiliaryResources.json"


def auxiliary_tags_in_text(text: str) -> list[tuple[str, str, str]]:
    """Return unique auxiliary tags found in prompt/source text."""
    tags: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for match in AUX_TAG_RE.finditer(text or ""):
        tag = match.group(0)
        if tag in seen:
            continue
        seen.add(tag)
        tags.append((tag, match.group(1), match.group(2)))
    return tags


def load_auxiliary_resource_lookup(project_root: Path) -> dict[tuple[str, str], dict]:
    """Load auxiliary resources keyed by category and resource id."""
    path = auxiliary_inventory_path(project_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateCompileError("MALFORMED_AUXILIARY_RESOURCES", f"Auxiliary resource inventory is malformed: {path}: {exc}") from exc
    resources = payload.get("resources") if isinstance(payload, dict) else []
    if not isinstance(resources, list):
        raise TemplateCompileError("MALFORMED_AUXILIARY_RESOURCES", f"Auxiliary resource inventory has no resources list: {path}")
    lookup: dict[tuple[str, str], dict] = {}
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        category = str(resource.get("category") or "").strip().lower()
        resource_id = str(resource.get("resource_id") or "").strip()
        if category and resource_id:
            lookup[(category, resource_id)] = resource
    return lookup


def auxiliary_references_for_texts(project_root: Path, texts: list[str], existing_references: list[dict]) -> list[dict]:
    """Append auxiliary image references for all tags found in source/prompt text."""
    combined_text = "\n\n".join(text for text in texts if text)
    tags = auxiliary_tags_in_text(combined_text)
    if not tags:
        return existing_references

    lookup = load_auxiliary_resource_lookup(project_root)
    references = list(existing_references)
    existing_keys = {
        (
            str(reference.get("role") or ""),
            str(reference.get("category") or ""),
            str(reference.get("resource_id") or ""),
            str(reference.get("path") or ""),
        )
        for reference in references
        if isinstance(reference, dict)
    }
    for tag, category, resource_id in tags:
        resource = lookup.get((category, resource_id))
        if resource is None:
            raise TemplateCompileError("MISSING_REFERENCE", f"Auxiliary resource tag not found: {tag}")
        image_path = resolve_library_path(project_root, str(resource.get("image_path") or ""))
        if not image_path.exists() or not image_path.is_file():
            raise TemplateCompileError("MISSING_REFERENCE", f"Auxiliary resource image not found for {tag}: {image_path}")
        key = ("auxiliary_resource", category, resource_id, str(image_path))
        if key in existing_keys:
            continue
        references.append(
            {
                "role": "auxiliary_resource",
                "category": category,
                "resource_id": resource_id,
                "label": str(resource.get("label") or resource_id),
                "tag": tag,
                "path": str(image_path),
            }
        )
        existing_keys.add(key)
    return references
