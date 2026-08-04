import json
import shutil
from datetime import datetime
from pathlib import Path

from zet.models.auxiliary_resource import AuxiliaryResource
from zet.repositories.json_storage import (
    MissingDataclassFieldsError,
    dataclass_from_record,
    dataclass_to_record,
    write_json_atomic,
)
from zet.services.path_service import PathService


class AuxiliaryResourceRepositoryError(Exception):
    """Report invalid or missing auxiliary resource storage."""


class AuxiliaryResourceRepository:
    """Persist global auxiliary resource records."""

    def __init__(self, path_service: PathService):
        """Initialize the repository with global resource paths."""
        self.path_service = path_service

    def _empty_payload(self) -> dict:
        """Return an empty auxiliary resource payload."""
        return {"schema_version": 1, "resources": []}

    def _load_payload(self) -> dict:
        """Load the auxiliary resource inventory."""
        path = self.path_service.auxiliary_resource_inventory_path()
        if not path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuxiliaryResourceRepositoryError(f"AuxiliaryResources.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise AuxiliaryResourceRepositoryError(f"AuxiliaryResources.json must contain a JSON object at {path}")
        payload.setdefault("schema_version", 1)
        payload.setdefault("resources", [])
        if not isinstance(payload["resources"], list):
            raise AuxiliaryResourceRepositoryError("AuxiliaryResources.json must contain a 'resources' list")
        return payload

    def _resource_from_dict(self, record: dict) -> AuxiliaryResource:
        """Convert a JSON record into an auxiliary resource model."""
        try:
            return dataclass_from_record(AuxiliaryResource, record)
        except MissingDataclassFieldsError as exc:
            raise AuxiliaryResourceRepositoryError(
                f"Auxiliary resource is missing required fields: {', '.join(exc.missing_fields)}"
            ) from None

    def _serialize_resource(self, resource: AuxiliaryResource) -> dict:
        """Convert an auxiliary resource model into a JSON record."""
        return dataclass_to_record(resource)

    def _write_payload(self, payload: dict) -> None:
        """Write the auxiliary resource inventory atomically."""
        path = self.path_service.auxiliary_resource_inventory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup_dir = path.parent / "_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(path, backup_dir / f"AuxiliaryResources.backup.{timestamp}.json")
        temp_path = path.with_name(f"{path.name}.tmp")
        write_json_atomic(path, temp_path, payload)

    def list_resources(self) -> list[AuxiliaryResource]:
        """List all global auxiliary resources."""
        payload = self._load_payload()
        return [self._resource_from_dict(record) for record in payload["resources"] if isinstance(record, dict)]

    def get_resource(self, resource_id: str) -> AuxiliaryResource:
        """Return one auxiliary resource by id."""
        for resource in self.list_resources():
            if resource.resource_id == resource_id:
                return resource
        raise AuxiliaryResourceRepositoryError(f"Auxiliary resource {resource_id} not found.")

    def save_resource(self, resource: AuxiliaryResource) -> None:
        """Insert or replace one auxiliary resource."""
        payload = self._load_payload()
        replacement = self._serialize_resource(resource)
        records = []
        replaced = False
        for record in payload["resources"]:
            if isinstance(record, dict) and record.get("resource_id") == resource.resource_id:
                records.append(replacement)
                replaced = True
            else:
                records.append(record)
        if not replaced:
            records.append(replacement)
        payload["resources"] = records
        self._write_payload(payload)

    def delete_resource(self, resource_id: str) -> None:
        """Delete one auxiliary resource record."""
        payload = self._load_payload()
        payload["resources"] = [
            record
            for record in payload["resources"]
            if not isinstance(record, dict) or record.get("resource_id") != resource_id
        ]
        self._write_payload(payload)
