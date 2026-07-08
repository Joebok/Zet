import dataclasses
import json
import shutil
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from zet.models.turnaround import TurnaroundSheet
from zet.services.path_service import PathService


class TurnaroundRepositoryError(Exception):
    """Report invalid or missing turnaround storage."""


class TurnaroundRepository:
    """Persist turnaround sheet records in the character phase folder."""

    def __init__(self, path_service: PathService):
        """Initialize the repository with project path conventions."""
        self.path_service = path_service

    def _turnarounds_json_path(self, character: str, phase: str) -> Path:
        """Return the JSON storage path for a character phase."""
        return self.path_service.character_path(character, phase) / "TurnaroundSheets.json"

    def _backup_dir(self, character: str, phase: str) -> Path:
        """Return the backup folder for turnaround storage writes."""
        return self.path_service.character_backup_path(character, phase)

    def _empty_payload(self) -> dict:
        """Return an empty turnaround storage payload."""
        return {"schema_version": 1, "turnarounds": []}

    def _load_payload(self, character: str, phase: str) -> dict:
        """Load turnaround storage or return an empty payload when absent."""
        path = self._turnarounds_json_path(character, phase)
        if not path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TurnaroundRepositoryError(f"TurnaroundSheets.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise TurnaroundRepositoryError(f"TurnaroundSheets.json must contain a JSON object at {path}")
        payload.setdefault("schema_version", 1)
        payload.setdefault("turnarounds", [])
        if not isinstance(payload["turnarounds"], list):
            raise TurnaroundRepositoryError("TurnaroundSheets.json must contain a 'turnarounds' list")
        return payload

    def _sheet_from_dict(self, record: dict) -> TurnaroundSheet:
        """Convert a JSON record into a turnaround model."""
        model_fields = list(fields(TurnaroundSheet))
        required = [
            field.name
            for field in model_fields
            if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
        ]
        missing = sorted(set(required) - set(record))
        if missing:
            raise TurnaroundRepositoryError(f"Turnaround record is missing required fields: {', '.join(missing)}")
        values = {}
        for field in model_fields:
            if field.name in record:
                values[field.name] = record[field.name]
            elif field.default is not dataclasses.MISSING:
                values[field.name] = field.default
            elif field.default_factory is not dataclasses.MISSING:
                values[field.name] = field.default_factory()
        return TurnaroundSheet(**values)

    def _serialize_sheet(self, sheet: TurnaroundSheet) -> dict:
        """Convert a turnaround model into a JSON record."""
        return {field.name: getattr(sheet, field.name) for field in fields(TurnaroundSheet)}

    def _write_payload(self, character: str, phase: str, payload: dict) -> None:
        """Write turnaround storage atomically with a timestamped backup."""
        path = self._turnarounds_json_path(character, phase)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = self._backup_dir(character, phase)
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_dir / f"TurnaroundSheets.backup.{timestamp}.json")
        temp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
        serialized = json.dumps(payload, indent=2)
        if not serialized.endswith("\n"):
            serialized += "\n"
        temp_path.write_text(serialized, encoding="utf-8")
        json.loads(temp_path.read_text(encoding="utf-8"))
        temp_path.replace(path)

    def list_sheets(self, character: str, phase: str) -> list[TurnaroundSheet]:
        """List all tracked turnaround sheets for a character phase."""
        payload = self._load_payload(character, phase)
        return [self._sheet_from_dict(record) for record in payload["turnarounds"] if isinstance(record, dict)]

    def get_sheet(self, character: str, phase: str, turnaround_id: str) -> TurnaroundSheet:
        """Return one tracked turnaround sheet by id."""
        for sheet in self.list_sheets(character, phase):
            if sheet.turnaround_id == turnaround_id:
                return sheet
        raise TurnaroundRepositoryError(f"Turnaround {turnaround_id} not found for {character}/{phase}")

    def save_sheet(self, sheet: TurnaroundSheet) -> None:
        """Insert or replace a tracked turnaround sheet."""
        payload = self._load_payload(sheet.character, sheet.phase)
        replacement = self._serialize_sheet(sheet)
        replaced = False
        records = []
        for record in payload["turnarounds"]:
            if isinstance(record, dict) and record.get("turnaround_id") == sheet.turnaround_id:
                records.append(replacement)
                replaced = True
            else:
                records.append(record)
        if not replaced:
            records.append(replacement)
        payload["turnarounds"] = records
        self._write_payload(sheet.character, sheet.phase, payload)

    def delete_sheet(self, character: str, phase: str, turnaround_id: str) -> TurnaroundSheet:
        """Delete a tracked turnaround sheet and return the removed model."""
        payload = self._load_payload(character, phase)
        removed = None
        records = []
        for record in payload["turnarounds"]:
            if isinstance(record, dict) and record.get("turnaround_id") == turnaround_id:
                removed = self._sheet_from_dict(record)
            else:
                records.append(record)
        if removed is None:
            raise TurnaroundRepositoryError(f"Turnaround {turnaround_id} not found for {character}/{phase}")
        payload["turnarounds"] = records
        self._write_payload(character, phase, payload)
        return removed
