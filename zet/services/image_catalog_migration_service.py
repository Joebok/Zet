from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from zet.repositories.image_catalog_repository import ImageCatalogRepository, ImageCatalogRepositoryError
from zet.repositories.json_storage import write_json_atomic


class ImageCatalogMigrationError(Exception):
    """Report a migration preflight, staging, or verification failure."""


class ImageCatalogMigrationInterrupted(RuntimeError):
    """Test-only interruption raised after a durable staging checkpoint."""


@dataclass(frozen=True)
class ImageCatalogMigrationReport:
    status: str
    dry_run: bool
    catalog_records: int
    reference_sets: int
    organization_entries: int
    image_files: int
    image_hashes_verified: int
    backup_path: str
    staging_path: str

    def to_dict(self) -> dict:
        return asdict(self)


class ImageCatalogMigrationService:
    """Explicitly migrate legacy catalog data to record-oriented schema v3."""

    def __init__(self, path_service):
        self.path_service = path_service
        self.repository = ImageCatalogRepository(path_service)
        self.root = path_service.image_catalog_root()
        self.manifest_path = path_service.image_catalog_inventory_path()
        self.staging_path = self.root / ".migration-v3"
        self.progress_path = self.staging_path / "progress.json"
        self.backup_path = self.root / "_backup" / "ImageCatalog.pre-v3.json"

    @staticmethod
    def _read_object(path: Path, description: str) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ImageCatalogMigrationError(f"Unable to read {description} at {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ImageCatalogMigrationError(f"{description} must contain a JSON object: {path}")
        return value

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

    def _adopt_auxiliary(self, payload: dict) -> None:
        legacy_path = self.path_service.auxiliary_resource_inventory_path()
        if not legacy_path.is_file():
            legacy_path = self.path_service.auxiliary_resource_inventory_default_path()
        if not legacy_path.is_file():
            return
        legacy = self._read_object(legacy_path, "AuxiliaryResources.json")
        resources = legacy.get("resources")
        if not isinstance(resources, list):
            raise ImageCatalogMigrationError("AuxiliaryResources.json must contain a resources list.")
        category_map = {"person": "Person", "place": "Place", "thing": "Object"}
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            set_id = str(resource.get("resource_id") or "").strip()
            if not set_id or set_id in payload["reference_sets"]:
                raise ImageCatalogMigrationError(f"Duplicate or missing auxiliary resource id: {set_id!r}")
            category = str(resource.get("category") or "thing").strip().lower()
            template = self.path_service.resolve_path(str(resource.get("template_path") or ""))
            payload["reference_sets"][set_id] = {
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
                catalog_id = self.repository.catalog_id(source_key)
                if not image_id or catalog_id in payload["managed_images"]:
                    raise ImageCatalogMigrationError(f"Duplicate or missing auxiliary image id in {set_id}.")
                image_path = self.path_service.resolve_path(str(image.get("image_path") or ""))
                payload["managed_images"][catalog_id] = {
                    "catalog_id": catalog_id,
                    "source_key": source_key,
                    "label": str(image.get("label") or image_id),
                    "image_path": str(image_path),
                    "mime_type": {
                        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"
                    }.get(image_path.suffix.lower(), "image/png"),
                    "tag": str(image.get("tag") or f"{{{{AUX:{category}:{set_id}:{image_id}}}}}"),
                    "semantic_category": category_map.get(category, "Object"),
                    "reference_set_id": set_id,
                    "created_at": str(image.get("created_at") or resource.get("created_at") or ""),
                    "updated_at": str(image.get("updated_at") or resource.get("updated_at") or ""),
                }

    def _legacy_payload(self) -> tuple[dict, bytes]:
        original = b""
        if self.manifest_path.is_file():
            original = self.manifest_path.read_bytes()
            payload = self._read_object(self.manifest_path, "legacy ImageCatalog.json")
            version = int(payload.get("schema_version") or 1)
            if version == self.repository.SCHEMA_VERSION:
                self.repository.load()
                return payload, original
            if version > 2:
                raise ImageCatalogMigrationError(f"Unsupported legacy catalog schema version: {version}")
        else:
            payload = {"schema_version": 1, "items": {}, "collections": [], "keywords": []}
        for name, default in (("items", {}), ("managed_images", {}), ("reference_sets", {}), ("collections", []), ("keywords", [])):
            payload.setdefault(name, default.copy() if isinstance(default, dict) else list(default))
        if not isinstance(payload["items"], dict) or not isinstance(payload["managed_images"], dict) or not isinstance(payload["reference_sets"], dict):
            raise ImageCatalogMigrationError("Legacy catalog items, managed_images, and reference_sets must be objects.")
        if int(payload.get("schema_version") or 1) < 2:
            self._adopt_auxiliary(payload)
        payload["schema_version"] = self.repository.SCHEMA_VERSION
        return payload, original

    def _portable_path(self, raw_path: str) -> tuple[str, str, Path]:
        resolved = self.path_service.resolve_path(raw_path).resolve()
        library = Path(self.path_service.config.base_library_path).resolve()
        try:
            relative = resolved.relative_to(library).as_posix()
            return relative, "library", resolved
        except ValueError:
            return str(resolved), "external", resolved

    def _preflight(self, payload: dict) -> dict[str, str]:
        source_keys: set[str] = set()
        image_hashes: dict[str, str] = {}
        reference_ids = set(payload["reference_sets"])
        for set_id, record in payload["reference_sets"].items():
            if not isinstance(record, dict):
                raise ImageCatalogMigrationError(f"Reference set {set_id!r} must be an object.")
            existing_id = str(record.get("reference_set_id") or set_id)
            if existing_id != set_id:
                raise ImageCatalogMigrationError(f"Reference set {set_id!r} has mismatched id {existing_id!r}.")
            record["reference_set_id"] = set_id
        for key, record in payload["managed_images"].items():
            if not isinstance(record, dict):
                raise ImageCatalogMigrationError(f"Managed image {key!r} must be an object.")
            catalog_id = str(record.get("catalog_id") or key)
            source_key = str(record.get("source_key") or "")
            if key != catalog_id or not source_key or source_key in source_keys:
                raise ImageCatalogMigrationError(f"Managed image {key!r} has a duplicate/mismatched id or source key.")
            source_keys.add(source_key)
            set_id = str(record.get("reference_set_id") or "")
            if set_id and set_id not in reference_ids:
                raise ImageCatalogMigrationError(f"Managed image {catalog_id} references missing set {set_id}.")
            portable, kind, resolved = self._portable_path(str(record.get("image_path") or ""))
            if not resolved.is_file():
                raise ImageCatalogMigrationError(f"Managed image file is missing: {resolved}")
            record["image_path"] = portable
            record["image_path_kind"] = kind
            if "content_type" in record and "mime_type" not in record:
                record["mime_type"] = record.pop("content_type")
            image_hashes[catalog_id] = hashlib.sha256(resolved.read_bytes()).hexdigest()
        for source_key, metadata in payload["items"].items():
            if not isinstance(metadata, dict):
                raise ImageCatalogMigrationError(f"Catalog metadata for {source_key!r} must be an object.")
            managed = next(
                (
                    record for record in payload["managed_images"].values()
                    if isinstance(record, dict) and str(record.get("source_key") or "") == source_key
                ),
                None,
            )
            catalog_id = str(
                metadata.get("catalog_id")
                or (managed or {}).get("catalog_id")
                or self.repository.catalog_id(source_key)
            )
            metadata["catalog_id"] = catalog_id
            if managed is not None and (
                str(managed.get("source_key") or "") != source_key
                or str(managed.get("catalog_id") or "") != catalog_id
            ):
                raise ImageCatalogMigrationError(f"Catalog id {catalog_id} has conflicting source keys.")
        self.repository.record_payloads(payload)
        return image_hashes

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _write_stage(self, payload: dict, fingerprint: str, interrupt_after: int | None) -> None:
        progress = {"source_fingerprint": fingerprint, "completed": []}
        if self.progress_path.is_file():
            progress = self._read_object(self.progress_path, "migration progress")
            if progress.get("source_fingerprint") != fingerprint:
                raise ImageCatalogMigrationError("Legacy catalog changed after migration staging began; restore or remove the staging directory before retrying.")
        completed = set(progress.get("completed") or [])
        records = self.repository.record_payloads(payload)
        work: list[tuple[str, Path, dict]] = []
        for catalog_id, record in sorted(records.items()):
            work.append((f"record:{catalog_id}", self.staging_path / "Records" / f"{catalog_id}.json", record))
        for set_id, record in sorted(payload["reference_sets"].items()):
            work.append((f"reference:{set_id}", self.staging_path / "ReferenceSets" / self.repository.reference_filename(set_id), {**record, "record_version": 1}))
        work.extend([
            ("organization", self.staging_path / "Organization.json", {
                "schema_version": 1, "collections": payload["collections"], "keywords": payload["keywords"]
            }),
            ("manifest", self.staging_path / "ImageCatalog.json", self.repository.MANIFEST),
        ])
        checkpoints = 0
        for key, path, value in work:
            if key not in completed:
                path.parent.mkdir(parents=True, exist_ok=True)
                write_json_atomic(path, path.with_suffix(".tmp"), value)
                completed.add(key)
                progress["completed"] = sorted(completed)
                self.progress_path.parent.mkdir(parents=True, exist_ok=True)
                write_json_atomic(self.progress_path, self.progress_path.with_suffix(".tmp"), progress)
                checkpoints += 1
                if interrupt_after is not None and checkpoints >= interrupt_after:
                    raise ImageCatalogMigrationInterrupted("Injected interruption after a durable migration checkpoint.")
        for _, path, expected in work:
            if self._read_object(path, "staged migration record") != expected:
                raise ImageCatalogMigrationError(f"Staged migration verification failed: {path}")

    def _install(self, original: bytes) -> None:
        for folder in ("Records", "ReferenceSets"):
            destination = self.root / folder
            destination.mkdir(parents=True, exist_ok=True)
            for source in (self.staging_path / folder).glob("*.json"):
                target = destination / source.name
                expected = source.read_bytes()
                if target.exists() and target.read_bytes() != expected:
                    raise ImageCatalogMigrationError(f"Migration destination conflicts with staged data: {target}")
                if not target.exists():
                    shutil.copy2(source, target)
        organization = self.staging_path / "Organization.json"
        target_organization = self.root / "Organization.json"
        if target_organization.exists() and target_organization.read_bytes() != organization.read_bytes():
            raise ImageCatalogMigrationError(f"Migration destination conflicts with staged data: {target_organization}")
        if not target_organization.exists():
            shutil.copy2(organization, target_organization)
        for folder in ("Records", "ReferenceSets"):
            staged = {path.name: path.read_bytes() for path in (self.staging_path / folder).glob("*.json")}
            installed = {path.name: path.read_bytes() for path in (self.root / folder).glob("*.json")}
            if installed != staged:
                raise ImageCatalogMigrationError(f"Installed {folder} do not exactly match the staged representation.")
        if original and not self.backup_path.exists():
            self.backup_path.parent.mkdir(parents=True, exist_ok=True)
            self.backup_path.write_bytes(original)
        write_json_atomic(self.manifest_path, self.manifest_path.with_suffix(".tmp"), self.repository.MANIFEST)
        self.repository.load()

    def run(self, *, dry_run: bool = False, interrupt_after: int | None = None) -> ImageCatalogMigrationReport:
        if self.manifest_path.is_file():
            current = self._read_object(self.manifest_path, "ImageCatalog.json")
            if current.get("schema_version") == self.repository.SCHEMA_VERSION:
                payload = self.repository.load()
                return self._report("no-op", dry_run, payload, 0)
        payload, original = self._legacy_payload()
        image_hashes = self._preflight(payload)
        report = self._report("dry-run" if dry_run else "migrated", dry_run, payload, len(image_hashes))
        if dry_run:
            return report
        if original and self.backup_path.exists() and self.backup_path.read_bytes() != original:
            raise ImageCatalogMigrationError(
                f"Existing migration backup does not match the current legacy manifest: {self.backup_path}"
            )
        fingerprint = self._fingerprint(payload)
        self._write_stage(payload, fingerprint, interrupt_after)
        self._install(original)
        loaded = self.repository.load()
        if self._fingerprint(loaded) != fingerprint:
            raise ImageCatalogMigrationError("Final catalog verification did not match the staged representation.")
        for catalog_id, expected in image_hashes.items():
            record = loaded["managed_images"][catalog_id]
            resolved = self.path_service.resolve_path(record["image_path"])
            if hashlib.sha256(resolved.read_bytes()).hexdigest() != expected:
                raise ImageCatalogMigrationError(f"Image hash changed during migration: {catalog_id}")
        return report

    def _report(self, status: str, dry_run: bool, payload: dict, verified: int) -> ImageCatalogMigrationReport:
        return ImageCatalogMigrationReport(
            status=status,
            dry_run=dry_run,
            catalog_records=len(self.repository.record_payloads(payload)),
            reference_sets=len(payload["reference_sets"]),
            organization_entries=len(payload["collections"]) + len(payload["keywords"]),
            image_files=len(payload["managed_images"]),
            image_hashes_verified=verified,
            backup_path=str(self.backup_path),
            staging_path=str(self.staging_path),
        )
