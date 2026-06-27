import json
import shutil
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.services.path_service import PathService


class AssetRepositoryError(Exception):
    pass


class AssetRepository:
    def __init__(self, path_service: PathService):
        self.path_service = path_service

    def _assets_json_path(self, character: str, phase: str) -> Path:
        return self.path_service.character_path(character, phase) / "Assets.json"

    def _load_payload(self, character: str, phase: str) -> dict:
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
        required = [field.name for field in fields(Asset)]
        missing = sorted(set(required) - set(record))
        if missing:
            raise AssetRepositoryError(f"Asset record is missing required fields: {', '.join(missing)}")
        return Asset(**{name: record[name] for name in required})

    def _serialize_asset(self, asset: Asset) -> dict:
        return {field.name: getattr(asset, field.name) for field in fields(Asset)}

    def list_assets(self, character: str, phase: str) -> list[Asset]:
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
        for asset in self.list_assets(character, phase):
            if asset.asset_id == asset_id:
                return asset
        raise AssetRepositoryError(f"Asset {asset_id} not found for {character}/{phase}")

    def save_asset(self, asset: Asset) -> None:
        path = self._assets_json_path(asset.character, asset.phase)
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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = path.with_name(f"Assets.backup.{timestamp}.json")
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
