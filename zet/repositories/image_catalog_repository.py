import json
import shutil
import hashlib
import re
from datetime import datetime
from pathlib import Path

from zet.repositories.json_storage import write_json_atomic


class ImageCatalogRepositoryError(Exception):
    """Report invalid image-catalog storage."""


class ImageCatalogRepository:
    """Persist user-managed image metadata without owning image files."""

    SCHEMA_VERSION = 2

    def __init__(self, path_service):
        self.path_service = path_service

    def empty_payload(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "items": {},
            "managed_images": {},
            "reference_sets": {},
            "collections": [],
            "keywords": [],
        }

    @staticmethod
    def _catalog_id(source_key: str) -> str:
        return "img_" + hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _section(path: Path, name: str) -> str:
        if not path.is_file():
            return ""
        match = re.search(
            rf"<!-- ZET:BEGIN {re.escape(name)} -->\s*(.*?)\s*<!-- ZET:END {re.escape(name)} -->",
            path.read_text(encoding="utf-8"),
            re.DOTALL,
        )
        return str(match.group(1)).strip() if match else ""

    def _migrate_legacy_auxiliary(self, payload: dict) -> dict:
        """Adopt legacy auxiliary records without moving or rewriting their image files."""
        legacy_path = self.path_service.auxiliary_resource_inventory_path()
        if not legacy_path.is_file():
            legacy_path = self.path_service.auxiliary_resource_inventory_default_path()
        if not legacy_path.is_file():
            return payload
        try:
            legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ImageCatalogRepositoryError(f"AuxiliaryResources.json is malformed at {legacy_path}: {exc}") from exc
        resources = legacy.get("resources") if isinstance(legacy, dict) else None
        if not isinstance(resources, list):
            raise ImageCatalogRepositoryError("AuxiliaryResources.json must contain a resources list.")
        category_map = {"person": "Person", "place": "Place", "thing": "Object"}
        managed = payload.setdefault("managed_images", {})
        reference_sets = payload.setdefault("reference_sets", {})
        seen_source_keys: set[str] = set()
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            set_id = str(resource.get("resource_id") or "").strip()
            category = str(resource.get("category") or "thing").strip().lower()
            if not set_id:
                raise ImageCatalogRepositoryError("Auxiliary resource id is required.")
            if set_id in reference_sets:
                raise ImageCatalogRepositoryError(f"Duplicate auxiliary resource id: {set_id}")
            template = self.path_service.resolve_path(str(resource.get("template_path") or ""))
            reference_sets[set_id] = {
                "reference_set_id": set_id,
                "label": str(resource.get("label") or set_id),
                "identity_text": self._section(template, "IDENTITY_PRESERVATION_SCENE"),
                "costume_text": self._section(template, "IDENTITY_PRESERVATION_COSTUME_SCENE"),
                "legacy_category": category,
                "created_at": str(resource.get("created_at") or ""),
                "updated_at": str(resource.get("updated_at") or ""),
            }
            for image in resource.get("images") or []:
                if not isinstance(image, dict):
                    continue
                image_id = str(image.get("image_id") or "").strip()
                source_key = f"aux:{category}:{set_id}:{image_id}"
                if not image_id or source_key in seen_source_keys:
                    raise ImageCatalogRepositoryError(f"Duplicate or missing auxiliary image id in {set_id}.")
                seen_source_keys.add(source_key)
                image_path = self.path_service.resolve_path(str(image.get("image_path") or ""))
                if not image_path.is_file():
                    raise ImageCatalogRepositoryError(f"Auxiliary image is missing: {image_path}")
                catalog_id = self._catalog_id(source_key)
                managed[catalog_id] = {
                    "catalog_id": catalog_id,
                    "source_key": source_key,
                    "label": str(image.get("label") or image_id),
                    "image_path": str(image_path),
                    "mime_type": {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}.get(image_path.suffix.lower(), "image/png"),
                    "tag": str(image.get("tag") or f"{{{{AUX:{category}:{set_id}:{image_id}}}}}"),
                    "semantic_category": category_map.get(category, "Object"),
                    "reference_set_id": set_id,
                    "created_at": str(image.get("created_at") or resource.get("created_at") or ""),
                    "updated_at": str(image.get("updated_at") or resource.get("updated_at") or ""),
                }
        writable_legacy = self.path_service.auxiliary_resource_inventory_path()
        if legacy_path.resolve() == writable_legacy.resolve():
            backup_dir = legacy_path.parent / "_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(legacy_path, backup_dir / f"AuxiliaryResources.migration.{stamp}.json")
        return payload

    def _upgrade(self, payload: dict) -> dict:
        version = int(payload.get("schema_version") or 1)
        changed = False
        if version > self.SCHEMA_VERSION:
            raise ImageCatalogRepositoryError(f"Unsupported ImageCatalog.json schema version: {version}")
        payload.setdefault("items", {})
        payload.setdefault("collections", [])
        payload.setdefault("keywords", [])
        payload.setdefault("managed_images", {})
        payload.setdefault("reference_sets", {})
        if version < 2:
            payload = self._migrate_legacy_auxiliary(payload)
            payload["schema_version"] = 2
            changed = True
        for record in payload["managed_images"].values():
            if isinstance(record, dict) and "content_type" in record and "mime_type" not in record:
                record["mime_type"] = record.pop("content_type")
                changed = True
        if changed:
            self.save(payload)
        return payload

    def load(self) -> dict:
        path = self.path_service.image_catalog_inventory_path()
        if not path.exists():
            payload = self._migrate_legacy_auxiliary(self.empty_payload())
            if payload["managed_images"] or payload["reference_sets"]:
                self.save(payload)
            return payload
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ImageCatalogRepositoryError(f"ImageCatalog.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items", {}), dict):
            raise ImageCatalogRepositoryError("ImageCatalog.json must contain an items object.")
        return self._upgrade(payload)

    def save(self, payload: dict) -> None:
        path = self.path_service.image_catalog_inventory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = path.parent / "_backup"
            backup.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(path, backup / f"ImageCatalog.backup.{stamp}.json")
        write_json_atomic(path, path.with_suffix(".tmp"), payload)
