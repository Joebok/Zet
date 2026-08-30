import json
import shutil
from datetime import datetime

from zet.repositories.json_storage import write_json_atomic


class ImageCatalogRepositoryError(Exception):
    """Report invalid image-catalog storage."""


class ImageCatalogRepository:
    """Persist user-managed image metadata without owning image files."""

    SCHEMA_VERSION = 1

    def __init__(self, path_service):
        self.path_service = path_service

    def empty_payload(self) -> dict:
        return {"schema_version": self.SCHEMA_VERSION, "items": {}, "collections": [], "keywords": []}

    def load(self) -> dict:
        path = self.path_service.image_catalog_inventory_path()
        if not path.exists():
            return self.empty_payload()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ImageCatalogRepositoryError(f"ImageCatalog.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items", {}), dict):
            raise ImageCatalogRepositoryError("ImageCatalog.json must contain an items object.")
        payload.setdefault("schema_version", self.SCHEMA_VERSION)
        payload.setdefault("collections", [])
        payload.setdefault("keywords", [])
        return payload

    def save(self, payload: dict) -> None:
        path = self.path_service.image_catalog_inventory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = path.parent / "_backup"
            backup.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(path, backup / f"ImageCatalog.backup.{stamp}.json")
        write_json_atomic(path, path.with_suffix(".tmp"), payload)

