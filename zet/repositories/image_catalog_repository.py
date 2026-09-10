from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from zet.repositories.json_storage import write_json_atomic


class ImageCatalogRepositoryError(Exception):
    """Report invalid image-catalog storage."""


class ImageCatalogRepository:
    """Persist the versioned, record-oriented image catalog."""

    SCHEMA_VERSION = 3
    RECORD_VERSION = 1
    ORGANIZATION_VERSION = 1
    MANIFEST = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "records": {"directory": "Records", "record_version": RECORD_VERSION},
        "reference_sets": {"directory": "ReferenceSets", "record_version": RECORD_VERSION},
        "organization": {"path": "Organization.json", "schema_version": ORGANIZATION_VERSION},
    }

    def __init__(self, path_service):
        self.path_service = path_service
        self.after_write = None

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
    def catalog_id(source_key: str) -> str:
        return "img_" + hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def reference_filename(reference_set_id: str) -> str:
        digest = hashlib.sha256(reference_set_id.encode("utf-8")).hexdigest()
        return f"ref_{digest[:24]}.json"

    @property
    def root(self) -> Path:
        return self.path_service.image_catalog_root()

    @property
    def records_path(self) -> Path:
        return self.root / "Records"

    @property
    def reference_sets_path(self) -> Path:
        return self.root / "ReferenceSets"

    @property
    def organization_path(self) -> Path:
        return self.root / "Organization.json"

    def record_path(self, catalog_id: str) -> Path:
        return self.records_path / f"{catalog_id}.json"

    def reference_set_path(self, reference_set_id: str) -> Path:
        return self.reference_sets_path / self.reference_filename(reference_set_id)

    def _migration_error(self, detail: str) -> ImageCatalogRepositoryError:
        return ImageCatalogRepositoryError(
            f"{detail} Run `python3 -m zet.scripts.migrate_image_catalog --config <config.toml>` to migrate the catalog."
        )

    @staticmethod
    def _read_object(path: Path, description: str) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ImageCatalogRepositoryError(f"{description} is malformed at {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ImageCatalogRepositoryError(f"{description} must contain a JSON object: {path}")
        return value

    def _validate_manifest(self, manifest: dict) -> None:
        if manifest.get("schema_version") != self.SCHEMA_VERSION:
            raise self._migration_error(
                f"ImageCatalog.json uses unsupported schema version {manifest.get('schema_version')!r}."
            )
        if manifest.get("status") != "complete":
            raise self._migration_error("The image catalog migration is incomplete.")
        for key in ("records", "reference_sets", "organization"):
            if manifest.get(key) != self.MANIFEST[key]:
                raise self._migration_error(f"The image catalog manifest has an invalid {key} layout.")

    def load(self) -> dict:
        manifest_path = self.path_service.image_catalog_inventory_path()
        migration_path = self.root / ".migration-v3"
        if not manifest_path.exists():
            if migration_path.exists():
                raise self._migration_error("The image catalog migration is incomplete.")
            legacy_auxiliary = self.path_service.auxiliary_resource_inventory_path()
            if legacy_auxiliary.is_file():
                raise self._migration_error("Legacy auxiliary catalog data was detected.")
            return self.empty_payload()

        manifest = self._read_object(manifest_path, "ImageCatalog.json")
        self._validate_manifest(manifest)
        if not self.records_path.is_dir() or not self.reference_sets_path.is_dir() or not self.organization_path.is_file():
            raise self._migration_error("The image catalog record set is incomplete.")

        payload = self.empty_payload()
        source_keys: set[str] = set()
        catalog_ids: set[str] = set()
        for path in sorted(self.records_path.glob("*.json")):
            record = self._read_object(path, "Image catalog record")
            catalog_id = str(record.get("catalog_id") or "")
            source_key = str(record.get("source_key") or "")
            if record.get("record_version") != self.RECORD_VERSION or not catalog_id or not source_key:
                raise ImageCatalogRepositoryError(f"Invalid image catalog record: {path}")
            if path.name != f"{catalog_id}.json" or source_key in source_keys or catalog_id in catalog_ids:
                raise ImageCatalogRepositoryError(f"Duplicate or mismatched image catalog record: {path}")
            source_keys.add(source_key)
            catalog_ids.add(catalog_id)
            metadata = record.get("metadata")
            managed = record.get("managed_image")
            if metadata is not None:
                if not isinstance(metadata, dict):
                    raise ImageCatalogRepositoryError(f"Catalog metadata must be an object or null: {path}")
                payload["items"][source_key] = metadata
            if managed is not None:
                if not isinstance(managed, dict) or str(managed.get("catalog_id") or "") != catalog_id:
                    raise ImageCatalogRepositoryError(f"Invalid managed image record: {path}")
                payload["managed_images"][catalog_id] = managed

        for path in sorted(self.reference_sets_path.glob("*.json")):
            record = self._read_object(path, "Image catalog reference-set record")
            set_id = str(record.get("reference_set_id") or "")
            if record.get("record_version") != self.RECORD_VERSION or not set_id:
                raise ImageCatalogRepositoryError(f"Invalid reference-set record: {path}")
            if path.name != self.reference_filename(set_id) or set_id in payload["reference_sets"]:
                raise ImageCatalogRepositoryError(f"Duplicate or mismatched reference-set record: {path}")
            payload["reference_sets"][set_id] = {key: value for key, value in record.items() if key != "record_version"}

        organization = self._read_object(self.organization_path, "Image catalog organization")
        if organization.get("schema_version") != self.ORGANIZATION_VERSION:
            raise ImageCatalogRepositoryError("Unsupported image catalog organization schema version.")
        for name in ("collections", "keywords"):
            values = organization.get(name)
            if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
                raise ImageCatalogRepositoryError(f"Image catalog organization {name} must be a list of objects.")
            payload[name] = values

        missing = sorted(
            {str(item.get("reference_set_id") or "") for item in payload["managed_images"].values()}
            - {""}
            - set(payload["reference_sets"])
        )
        if missing:
            raise ImageCatalogRepositoryError(f"Managed image records reference missing sets: {', '.join(missing)}")
        return payload

    def record_payloads(self, payload: dict) -> dict[str, dict]:
        by_id: dict[str, dict] = {}
        managed_by_source = {
            str(record.get("source_key") or ""): record
            for record in payload.get("managed_images", {}).values()
            if isinstance(record, dict)
        }
        source_keys = set(payload.get("items", {})) | set(managed_by_source)
        for source_key in source_keys:
            metadata = payload.get("items", {}).get(source_key)
            managed = managed_by_source.get(source_key)
            catalog_id = str(
                (metadata or {}).get("catalog_id")
                or (managed or {}).get("catalog_id")
                or self.catalog_id(source_key)
            )
            if not source_key or not catalog_id or catalog_id in by_id:
                raise ImageCatalogRepositoryError(f"Duplicate or missing catalog id for source key {source_key!r}.")
            by_id[catalog_id] = {
                "record_version": self.RECORD_VERSION,
                "catalog_id": catalog_id,
                "source_key": source_key,
                "metadata": metadata,
                "managed_image": managed,
            }
        return by_id

    def _backup(self, path: Path, kind: str) -> None:
        if not path.is_file():
            return
        backup = self.root / "_backup" / kind
        backup.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(path, backup / f"{path.stem}.{stamp}.json")

    def _sync_directory(self, directory: Path, desired: dict[str, dict], kind: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        existing = {path.name: path for path in directory.glob("*.json")}
        for filename, value in desired.items():
            path = directory / filename
            current = self._read_object(path, kind) if path.is_file() else None
            if current == value:
                continue
            self._backup(path, kind)
            write_json_atomic(path, path.with_suffix(".tmp"), value)
        for filename, path in existing.items():
            if filename not in desired:
                self._backup(path, kind)
                path.unlink()

    def save(self, payload: dict) -> None:
        manifest_path = self.path_service.image_catalog_inventory_path()
        if manifest_path.exists():
            self._validate_manifest(self._read_object(manifest_path, "ImageCatalog.json"))
        elif (self.root / ".migration-v3").exists():
            raise self._migration_error("The image catalog migration is incomplete.")

        records = {
            f"{catalog_id}.json": value for catalog_id, value in self.record_payloads(payload).items()
        }
        references = {
            self.reference_filename(set_id): {**record, "record_version": self.RECORD_VERSION}
            for set_id, record in payload.get("reference_sets", {}).items()
        }
        organization = {
            "schema_version": self.ORGANIZATION_VERSION,
            "collections": payload.get("collections", []),
            "keywords": payload.get("keywords", []),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._sync_directory(self.records_path, records, "Records")
        self._sync_directory(self.reference_sets_path, references, "ReferenceSets")
        current_organization = (
            self._read_object(self.organization_path, "Image catalog organization")
            if self.organization_path.is_file()
            else None
        )
        if current_organization != organization:
            self._backup(self.organization_path, "Organization")
            write_json_atomic(self.organization_path, self.organization_path.with_suffix(".tmp"), organization)
        if not manifest_path.exists():
            write_json_atomic(manifest_path, manifest_path.with_suffix(".tmp"), self.MANIFEST)
        if self.after_write is not None:
            self.after_write()
