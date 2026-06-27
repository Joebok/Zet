import json
from dataclasses import fields
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
        required = {field.name for field in fields(Asset)}
        missing = sorted(required - set(record))
        if missing:
            raise AssetRepositoryError(f"Asset record is missing required fields: {', '.join(missing)}")
        return Asset(**{name: record[name] for name in required})

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
