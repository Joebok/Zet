#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Library_Paths import library_root, resolve_library_path
from zet.services.auxiliary_resource_tags import auxiliary_resource_image_for_tag, auxiliary_resource_tags_in_text

IMAGE_TAG_RE = re.compile(r"\{\{IMAGE:(img_[A-Za-z0-9_-]+)\}\}")


def auxiliary_inventory_path(project_root: Path) -> Path:
    """Return the global auxiliary resource inventory path."""
    return library_root(project_root) / "AuxiliaryResources" / "AuxiliaryResources.json"


def auxiliary_tags_in_text(text: str) -> list[tuple[str, str, str, str]]:
    """Return unique auxiliary tags found in prompt/source text."""
    return auxiliary_resource_tags_in_text(text)


def load_auxiliary_resource_lookup(project_root: Path) -> list[dict]:
    """Load auxiliary resource records."""
    path = auxiliary_inventory_path(project_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateCompileError("MALFORMED_AUXILIARY_RESOURCES", f"Auxiliary resource inventory is malformed: {path}: {exc}") from exc
    resources = payload.get("resources") if isinstance(payload, dict) else []
    if not isinstance(resources, list):
        raise TemplateCompileError("MALFORMED_AUXILIARY_RESOURCES", f"Auxiliary resource inventory has no resources list: {path}")
    records: list[dict] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        records.append(resource)
    return records


def load_managed_image_lookup(project_root: Path) -> dict[str, dict]:
    """Load catalog-owned imported images keyed by their stable tag."""
    path = library_root(project_root) / "ImageCatalog" / "ImageCatalog.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateCompileError("MALFORMED_IMAGE_CATALOG", f"Image catalog is malformed: {path}: {exc}") from exc
    managed = payload.get("managed_images", {}) if isinstance(payload, dict) else {}
    if not isinstance(managed, dict):
        raise TemplateCompileError("MALFORMED_IMAGE_CATALOG", f"Image catalog has no managed_images object: {path}")
    return {
        str(record.get("tag") or ""): record
        for record in managed.values()
        if isinstance(record, dict) and str(record.get("tag") or "")
    }


def auxiliary_references_for_texts(project_root: Path, texts: list[str], existing_references: list[dict]) -> list[dict]:
    """Append auxiliary image references for all tags found in source/prompt text."""
    combined_text = "\n\n".join(text for text in texts if text)
    tags = auxiliary_tags_in_text(combined_text)
    image_tags = [match.group(0) for match in IMAGE_TAG_RE.finditer(combined_text)]
    if not tags and not image_tags:
        return existing_references

    lookup = load_auxiliary_resource_lookup(project_root)
    managed_lookup = load_managed_image_lookup(project_root)
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
    for tag, category, resource_id, image_id in tags:
        image = managed_lookup.get(tag)
        resource = None
        if image is None:
            try:
                resource, image = auxiliary_resource_image_for_tag(lookup, tag)
            except LookupError:
                raise TemplateCompileError("MISSING_REFERENCE", f"Auxiliary resource tag not found: {tag}")
        image_path = resolve_library_path(project_root, str(image.get("image_path") or ""))
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
                "label": str((resource or {}).get("label") or image.get("label") or resource_id),
                "tag": tag,
                "path": str(image_path),
            }
        )
        existing_keys.add(key)
    for tag in dict.fromkeys(image_tags):
        image = managed_lookup.get(tag)
        if image is None:
            raise TemplateCompileError("MISSING_REFERENCE", f"Imported image tag not found: {tag}")
        image_path = resolve_library_path(project_root, str(image.get("image_path") or ""))
        if not image_path.is_file():
            raise TemplateCompileError("MISSING_REFERENCE", f"Imported image file not found for {tag}: {image_path}")
        key = ("imported_image", "", "", str(image_path))
        if key in existing_keys:
            continue
        references.append({
            "role": "imported_image",
            "label": str(image.get("label") or image.get("catalog_id") or tag),
            "tag": tag,
            "path": str(image_path),
            "catalog_id": str(image.get("catalog_id") or ""),
        })
        existing_keys.add(key)
    return references
