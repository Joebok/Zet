#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Library_Paths import library_root, load_project_config, resolve_library_path
from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService, EntityLibraryServiceError
from zet.services.path_service import PathService
from zet.services.auxiliary_resource_tags import auxiliary_resource_image_for_tag, auxiliary_resource_tags_in_text

IMAGE_TAG_RE = re.compile(r"\{\{IMAGE:(img_[A-Za-z0-9_-]+)\}\}")
LIB_REFERENCE_TAG_RE = re.compile(r"\{\{LIB:REF:([a-z0-9][a-z0-9._-]*)\}\}")


def auxiliary_inventory_path(project_root: Path) -> Path:
    """Return the global auxiliary resource inventory path."""
    return library_root(project_root) / "_state" / "AuxiliaryResourceIndex.json"


def auxiliary_tags_in_text(text: str) -> list[tuple[str, str, str, str]]:
    """Return unique auxiliary tags found in prompt/source text."""
    return auxiliary_resource_tags_in_text(text)


def load_auxiliary_resource_lookup(project_root: Path) -> list[dict]:
    """Load auxiliary resource records."""
    path = auxiliary_inventory_path(project_root)
    if not path.is_file():
        legacy_root = library_root(project_root) / "AuxiliaryResources" / "AuxiliaryResources.json"
        if legacy_root.is_file():
            path = legacy_root
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
    universe_root = library_root(project_root)
    catalog_root = universe_root / "_state" / "ImageCatalog"
    if not catalog_root.is_dir():
        catalog_root = universe_root / "ImageCatalog"
    legacy_references: dict[str, dict] = {}
    try:
        service = PathService(load_project_config(project_root), project_root)
        catalog = EntityLibraryRepository(service.entity_library_database_path())
        rows = catalog.fetchall("SELECT r.reference_tag,a.asset_id,a.label,a.file_name,a.checksum,a.status FROM legacy_image_references r JOIN assets a ON a.asset_id=r.asset_id") if service.entity_library_database_path().is_file() else []
        for row in rows:
            legacy_references[row["reference_tag"]] = {
                "tag": row["reference_tag"], "label": row["label"],
                "image_path": str(service.entity_library_images_path() / f"{row['asset_id']}{Path(row['file_name']).suffix.lower()}"),
                "checksum": row["checksum"], "status": row["status"],
            }
    except Exception:
        # Older libraries do not have an entity catalog or alias table yet.
        pass
    path = catalog_root / "ImageCatalog.json"
    if not path.is_file():
        return legacy_references
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateCompileError("MALFORMED_IMAGE_CATALOG", f"Image catalog is malformed: {path}: {exc}") from exc
    managed = payload.get("managed_images") if isinstance(payload, dict) else None
    if isinstance(managed, dict):
        return {**legacy_references, **{
            str(record.get("tag") or ""): record
            for record in managed.values()
            if isinstance(record, dict) and str(record.get("tag") or "")
        }}

    # Schema v3 catalogs keep the manifest in ImageCatalog.json and each image
    # in a separate Records/<catalog_id>.json file.
    if isinstance(payload, dict) and payload.get("schema_version") == 3:
        records_dir = catalog_root / "Records"
        if not records_dir.is_dir():
            raise TemplateCompileError("MALFORMED_IMAGE_CATALOG", f"Image catalog records are missing: {records_dir}")
        records: dict[str, dict] = {}
        for record_path in sorted(records_dir.glob("*.json")):
            try:
                record_payload = json.loads(record_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise TemplateCompileError("MALFORMED_IMAGE_CATALOG", f"Image catalog record is malformed: {record_path}: {exc}") from exc
            image = record_payload.get("managed_image") if isinstance(record_payload, dict) else None
            if isinstance(image, dict) and str(image.get("tag") or ""):
                records[str(image["tag"])] = image
        return {**legacy_references, **records}

    raise TemplateCompileError("MALFORMED_IMAGE_CATALOG", f"Image catalog has no managed_images object: {path}")


def auxiliary_references_for_texts(project_root: Path, texts: list[str], existing_references: list[dict]) -> list[dict]:
    """Append auxiliary image references for all tags found in source/prompt text."""
    combined_text = "\n\n".join(text for text in texts if text)
    tags = auxiliary_tags_in_text(combined_text)
    image_tags = [match.group(0) for match in IMAGE_TAG_RE.finditer(combined_text)]
    library_tags = list(dict.fromkeys(match.group(0) for match in LIB_REFERENCE_TAG_RE.finditer(combined_text)))
    if not tags and not image_tags and not library_tags:
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
        image_label = str(image.get("label") or image_id).strip()
        resource_label = str(
            (resource or {}).get("label") or (resource_id if resource is not None else "")
        ).strip()
        label = (
            f"{resource_label} — {image_label}"
            if resource_label and image_label and resource_label.casefold() != image_label.casefold()
            else image_label or resource_label
        )
        references.append(
            {
                "role": "auxiliary_resource",
                "category": category,
                "resource_id": resource_id,
                "image_id": image_id,
                "label": label,
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
    if library_tags:
        config = load_project_config(project_root)
        paths = PathService(config, project_root)
        repository = EntityLibraryRepository(paths.entity_library_database_path())
        if not repository.database_path.is_file():
            raise TemplateCompileError("MISSING_REFERENCE", f"Entity image library not found: {repository.database_path}")
        service = EntityLibraryService(paths, repository)
        for tag in library_tags:
            key = LIB_REFERENCE_TAG_RE.fullmatch(tag).group(1)
            try:
                asset = service.resolve_reference(key)
            except EntityLibraryServiceError as exc:
                raise TemplateCompileError("MISSING_REFERENCE", str(exc)) from exc
            image_path = Path(asset["image_path"])
            if not image_path.is_file():
                raise TemplateCompileError("MISSING_REFERENCE", f"Entity image file not found for {tag}: {image_path}")
            reference_key = ("entity_library", "", "", str(image_path))
            if reference_key in existing_keys:
                continue
            primary = next((item for item in asset["entities"] if item["role"] == "primary_subject"), None)
            subject_type = primary["entity_type"] if primary else ""
            prompt_role = (
                "object_reference" if subject_type in {"prop", "symbol", "structure"}
                else "costume_reference" if subject_type == "costume"
                else "subject_reference"
            )
            references.append({
                "role": "entity_library",
                "prompt_role": prompt_role,
                "label": asset["label"],
                "tag": tag,
                "path": str(image_path),
                "asset_id": asset["asset_id"],
                "reference_key": key,
            })
            existing_keys.add(reference_key)
    return references
