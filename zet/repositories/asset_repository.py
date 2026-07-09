import dataclasses
import json
import shutil
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.services.path_service import PathService


class AssetRepositoryError(Exception):
    """Report invalid or missing asset storage."""
    pass


class AssetRepository:
    """Persist pipeline assets in the character phase Assets.json file."""

    def __init__(self, path_service: PathService):
        """Create an asset repository for a path service."""
        self.path_service = path_service

    def _assets_json_path(self, character: str, phase: str) -> Path:
        """Return the Assets.json path for a character phase."""
        return self.path_service.character_path(character, phase) / "Assets.json"

    def _backup_dir(self, character: str, phase: str) -> Path:
        """Return the backup folder for asset writes."""
        return self.path_service.character_backup_path(character, phase)

    def _load_payload(self, character: str, phase: str) -> dict:
        """Load the raw asset storage payload."""
        path = self._assets_json_path(character, phase)
        if not path.exists():
            raise AssetRepositoryError(f"Assets.json not found at {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise AssetRepositoryError(f"Assets.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise AssetRepositoryError(f"Assets.json must contain a JSON object at {path}")
        return payload

    def _asset_from_dict(self, record: dict) -> Asset:
        """Convert a JSON record into an Asset model."""
        model_fields = list(fields(Asset))
        required = [
            field.name
            for field in model_fields
            if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
        ]
        missing = sorted(set(required) - set(record))
        if missing:
            raise AssetRepositoryError(f"Asset record is missing required fields: {', '.join(missing)}")
        values = {}
        for field in model_fields:
            if field.name in record:
                values[field.name] = record[field.name]
            elif field.default is not dataclasses.MISSING:
                values[field.name] = field.default
            elif field.default_factory is not dataclasses.MISSING:
                values[field.name] = field.default_factory()
        return Asset(**values)

    def _serialize_asset(self, asset: Asset) -> dict:
        """Convert an Asset model into a JSON record."""
        return {field.name: getattr(asset, field.name) for field in fields(Asset)}

    def _write_payload(self, character: str, phase: str, payload: dict) -> None:
        """Write asset storage atomically with a timestamped backup."""
        path = self._assets_json_path(character, phase)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_dir = self._backup_dir(character, phase)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"Assets.backup.{timestamp}.json"
        temp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")

        serialized = json.dumps(payload, indent=2)
        if not serialized.endswith("\n"):
            serialized += "\n"

        shutil.copy2(path, backup_path)
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(serialized)
            with temp_path.open("r", encoding="utf-8") as handle:
                json.load(handle)
            temp_path.replace(path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def list_assets(self, character: str, phase: str) -> list[Asset]:
        """List all assets for a character phase."""
        payload = self._load_payload(character, phase)
        records = payload.get("assets")
        if not isinstance(records, list):
            raise AssetRepositoryError("Assets.json must contain an 'assets' list")
        assets = []
        for record in records:
            if not isinstance(record, dict):
                raise AssetRepositoryError("Each asset record in Assets.json must be an object")
            assets.append(self._asset_from_dict(record))
        return assets

    def get_asset(self, character: str, phase: str, asset_id: int) -> Asset:
        """Return one asset by id."""
        for asset in self.list_assets(character, phase):
            if asset.asset_id == asset_id:
                return asset
        raise AssetRepositoryError(f"Asset {asset_id} not found for {character}/{phase}")

    def save_asset(self, asset: Asset) -> None:
        """Replace an existing asset record."""
        payload = self._load_payload(asset.character, asset.phase)
        records = payload.get("assets")
        if not isinstance(records, list):
            raise AssetRepositoryError("Assets.json must contain an 'assets' list")

        replacement = self._serialize_asset(asset)
        found = False
        updated_records = []
        for record in records:
            if not isinstance(record, dict):
                raise AssetRepositoryError("Each asset record in Assets.json must be an object")
            if record.get("asset_id") == asset.asset_id:
                updated_records.append(replacement)
                found = True
            else:
                updated_records.append(record)

        if not found:
            raise AssetRepositoryError(f"Asset {asset.asset_id} not found for {asset.character}/{asset.phase}")

        payload["assets"] = updated_records
        self._write_payload(asset.character, asset.phase, payload)

    def create_asset(self, asset: Asset) -> Asset:
        """Append a new asset and advance next_asset_id."""
        payload = self._load_payload(asset.character, asset.phase)
        records = payload.get("assets")
        if not isinstance(records, list):
            raise AssetRepositoryError("Assets.json must contain an 'assets' list")
        next_asset_id = int(payload.get("next_asset_id") or 1)
        if asset.asset_id <= 0:
            asset.asset_id = next_asset_id
        if any(isinstance(record, dict) and record.get("asset_id") == asset.asset_id for record in records):
            raise AssetRepositoryError(f"Asset {asset.asset_id} already exists for {asset.character}/{asset.phase}")
        payload["next_asset_id"] = max(next_asset_id, asset.asset_id + 1)
        records.append(self._serialize_asset(asset))
        payload["assets"] = records
        self._write_payload(asset.character, asset.phase, payload)
        return asset
