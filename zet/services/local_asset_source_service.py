"""Verified local character image sources for derived asset workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zet.services.local_asset_store_service import LocalAssetStoreService, LocalAssetStoreError


class LocalAssetSourceService:
    """Expose only checksum-verified, locked local pipeline images."""

    def __init__(self, store: LocalAssetStoreService):
        self.store = store

    def list_sources(self, character: str, phase: str, pipeline: str = "") -> list[dict[str, Any]]:
        sources = []
        for record in self.store.locked_assets(character, phase, pipeline=pipeline):
            image = Path(record["image_path"])
            sources.append({
                "source_key": record["key"],
                "pipeline": record.get("pipeline", ""),
                "view": record.get("view", ""),
                "costume": record.get("qualifier", ""),
                "image_path": str(image),
                "image_sha256": record.get("image_sha256", ""),
                "batch_id": record.get("batch_id", ""),
                "candidate_id": record.get("candidate_id", ""),
                "dependencies": list(record.get("dependencies") or []),
                "updated_at": record.get("updated_at", ""),
            })
        return sources

    def get_source(self, character: str, phase: str, source_key: str) -> dict[str, Any]:
        """Resolve a current lock and reject stale or altered images."""
        for source in self.list_sources(character, phase):
            if source["source_key"] == source_key:
                return source
        raise LocalAssetStoreError(f"Local source is missing, unlocked, or stale: {source_key}")
