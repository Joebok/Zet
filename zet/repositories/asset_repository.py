import json
import shutil
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.repositories.json_storage import (
    MissingDataclassFieldsError,
    dataclass_from_record,
    dataclass_to_record,
    write_json_atomic,
)
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
        try:
            return dataclass_from_record(Asset, record)
        except MissingDataclassFieldsError as exc:
            raise AssetRepositoryError(
                f"Asset record is missing required fields: {', '.join(exc.missing_fields)}"
            ) from None

    def _serialize_asset(self, asset: Asset) -> dict:
        """Convert an Asset model into a JSON record."""
        return dataclass_to_record(asset)

    def _write_payload(self, character: str, phase: str, payload: dict) -> None:
        """Write asset storage atomically with a timestamped backup."""
        path = self._assets_json_path(character, phase)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_dir = self._backup_dir(character, phase)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"Assets.backup.{timestamp}.json"
        temp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")

        write_json_atomic(
            path,
            temp_path,
            payload,
            before_write=lambda: shutil.copy2(path, backup_path),
            cleanup_temp_on_error=True,
        )

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
        self.save_assets([asset])

    def save_assets(self, assets: list[Asset]) -> None:
        """Replace existing asset records in one storage write."""
        if not assets:
            return
        character = assets[0].character
        phase = assets[0].phase
        if any(asset.character != character or asset.phase != phase for asset in assets):
            raise AssetRepositoryError("Batch assets must belong to the same character phase")
        replacements = {asset.asset_id: self._serialize_asset(asset) for asset in assets}
        if len(replacements) != len(assets):
            raise AssetRepositoryError("Batch assets must have unique asset ids")

        payload = self._load_payload(character, phase)
        records = payload.get("assets")
        if not isinstance(records, list):
            raise AssetRepositoryError("Assets.json must contain an 'assets' list")

        found = set()
        updated_records = []
        for record in records:
            if not isinstance(record, dict):
                raise AssetRepositoryError("Each asset record in Assets.json must be an object")
            asset_id = record.get("asset_id")
            if asset_id in replacements:
                updated_records.append(replacements[asset_id])
                found.add(asset_id)
            else:
                updated_records.append(record)

        missing = sorted(set(replacements) - found)
        if missing:
            raise AssetRepositoryError(f"Assets {', '.join(str(asset_id) for asset_id in missing)} not found for {character}/{phase}")

        payload["assets"] = updated_records
        self._write_payload(character, phase, payload)

    def create_asset(self, asset: Asset) -> Asset:
        """Append a new asset and advance next_asset_id."""
        return self.create_assets([asset])[0]

    def create_assets(self, assets: list[Asset]) -> list[Asset]:
        """Append assets and advance next_asset_id in one storage write."""
        if not assets:
            return []
        character = assets[0].character
        phase = assets[0].phase
        if any(asset.character != character or asset.phase != phase for asset in assets):
            raise AssetRepositoryError("Batch assets must belong to the same character phase")

        payload = self._load_payload(character, phase)
        records = payload.get("assets")
        if not isinstance(records, list):
            raise AssetRepositoryError("Assets.json must contain an 'assets' list")
        next_asset_id = int(payload.get("next_asset_id") or 1)
        used_ids = {
            record.get("asset_id")
            for record in records
            if isinstance(record, dict)
        }
        for asset in assets:
            if asset.asset_id <= 0:
                asset.asset_id = next_asset_id
            if asset.asset_id in used_ids:
                raise AssetRepositoryError(f"Asset {asset.asset_id} already exists for {character}/{phase}")
            used_ids.add(asset.asset_id)
            next_asset_id = max(next_asset_id, asset.asset_id + 1)
            records.append(self._serialize_asset(asset))
        payload["next_asset_id"] = next_asset_id
        payload["assets"] = records
        self._write_payload(character, phase, payload)
        return assets
