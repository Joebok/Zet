import dataclasses
import json
import shutil
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from zet.models.identity_key import IdentityKey
from zet.services.path_service import PathService


class IdentityKeyRepositoryError(Exception):
    """Report invalid or missing identity key storage."""


class IdentityKeyRepository:
    """Persist identity key records in the character phase folder."""

    def __init__(self, path_service: PathService):
        """Create an identity key repository for a path service."""
        self.path_service = path_service

    def _identity_json_path(self, character: str, phase: str) -> Path:
        """Return the IdentityKeys.json path for a character phase."""
        return self.path_service.character_path(character, phase) / "IdentityKeys.json"

    def _empty_payload(self) -> dict:
        """Return an empty identity key storage payload."""
        return {"schema_version": 1, "identity_keys": []}

    def _load_payload(self, character: str, phase: str) -> dict:
        """Load identity key storage or return an empty payload when absent."""
        path = self._identity_json_path(character, phase)
        if not path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise IdentityKeyRepositoryError(f"IdentityKeys.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise IdentityKeyRepositoryError(f"IdentityKeys.json must contain a JSON object at {path}")
        payload.setdefault("identity_keys", [])
        if not isinstance(payload["identity_keys"], list):
            raise IdentityKeyRepositoryError("IdentityKeys.json must contain an 'identity_keys' list")
        return payload

    def _identity_from_dict(self, record: dict) -> IdentityKey:
        """Convert a JSON record into an identity key model."""
        model_fields = list(fields(IdentityKey))
        required = [
            field.name
            for field in model_fields
            if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
        ]
        missing = sorted(set(required) - set(record))
        if missing:
            raise IdentityKeyRepositoryError(f"Identity key record is missing required fields: {', '.join(missing)}")
        values = {}
        for field in model_fields:
            if field.name in record:
                values[field.name] = record[field.name]
            elif field.default is not dataclasses.MISSING:
                values[field.name] = field.default
            elif field.default_factory is not dataclasses.MISSING:
                values[field.name] = field.default_factory()
        return IdentityKey(**values)

    def _serialize_identity(self, identity_key: IdentityKey) -> dict:
        """Convert an identity key model into a JSON record."""
        return {field.name: getattr(identity_key, field.name) for field in fields(IdentityKey)}

    def _write_payload(self, character: str, phase: str, payload: dict) -> None:
        """Write identity key storage atomically with a timestamped backup."""
        path = self._identity_json_path(character, phase)
        path.parent.mkdir(parents=True, exist_ok=True)
        backup_dir = self.path_service.character_backup_path(character, phase)
        backup_dir.mkdir(parents=True, exist_ok=True)
        if path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(path, backup_dir / f"IdentityKeys.backup.{timestamp}.json")
        temp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
        temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        json.loads(temp_path.read_text(encoding="utf-8"))
        temp_path.replace(path)

    def list_identity_keys(self, character: str, phase: str) -> list[IdentityKey]:
        """List all identity keys for a character phase."""
        payload = self._load_payload(character, phase)
        return [self._identity_from_dict(record) for record in payload["identity_keys"] if isinstance(record, dict)]

    def get_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        """Return one identity key by id."""
        for identity_key in self.list_identity_keys(character, phase):
            if identity_key.identity_key_id == identity_key_id:
                return identity_key
        raise IdentityKeyRepositoryError(f"Identity key {identity_key_id} not found for {character}/{phase}")

    def save_identity_key(self, identity_key: IdentityKey) -> None:
        """Insert or replace one identity key record."""
        payload = self._load_payload(identity_key.character, identity_key.phase)
        records = []
        found = False
        for record in payload["identity_keys"]:
            if isinstance(record, dict) and record.get("identity_key_id") == identity_key.identity_key_id:
                records.append(self._serialize_identity(identity_key))
                found = True
            else:
                records.append(record)
        if not found:
            records.append(self._serialize_identity(identity_key))
        payload["identity_keys"] = records
        self._write_payload(identity_key.character, identity_key.phase, payload)

    def delete_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        """Delete one identity key record and return the removed model."""
        payload = self._load_payload(character, phase)
        records = []
        removed = None
        for record in payload["identity_keys"]:
            if isinstance(record, dict) and record.get("identity_key_id") == identity_key_id:
                removed = self._identity_from_dict(record)
            else:
                records.append(record)
        if removed is None:
            raise IdentityKeyRepositoryError(f"Identity key {identity_key_id} not found for {character}/{phase}")
        payload["identity_keys"] = records
        self._write_payload(character, phase, payload)
        return removed
