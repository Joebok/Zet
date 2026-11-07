"""Available published local character image sources for derived workflows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from zet.services.local_asset_store_service import LocalAssetStoreService, LocalAssetStoreError


class LocalAssetSourceService:
    """Expose locked local pipeline images at their recorded locations."""

    def __init__(self, store: LocalAssetStoreService):
        self.store = store

    def _container_sources(self, character: str, phase: str, pipeline: str = "") -> list[dict[str, Any]]:
        root = self.store.library_root / "_state" / "CharacterAssetContainers"
        root = root.resolve()
        character_dir = (root / quote(character, safe="-_.")).resolve()
        phase_dir = (character_dir / quote(phase, safe="-_.")).resolve()
        if character_dir.parent != root or phase_dir.parent != character_dir:
            return []
        if not phase_dir.is_dir():
            return []
        database = self.store.library_root / "catalog.sqlite3"
        if not database.is_file():
            return []
        from zet.repositories.entity_library_repository import EntityLibraryRepository
        catalog = EntityLibraryRepository(database)
        output = []
        for pipeline_dir in phase_dir.iterdir():
            if not pipeline_dir.is_dir() or (pipeline and pipeline_dir.name.casefold() != pipeline.casefold()):
                continue
            if pipeline_dir.resolve().parent != phase_dir:
                continue
            pipeline_name = pipeline_dir.name
            for scope_dir in pipeline_dir.iterdir():
                if not scope_dir.is_dir():
                    continue
                if scope_dir.resolve().parent != pipeline_dir.resolve():
                    continue
                container_path = scope_dir / "container.json"
                if not container_path.is_file() or container_path.resolve().parent != scope_dir.resolve():
                    continue
                try:
                    container = json.loads(container_path.read_text(encoding="utf-8"))
                    operation = container.get("_pending_publication_id")
                    if operation:
                        if len(operation) != 32 or any(c not in "0123456789abcdef" for c in operation):
                            continue
                        receipt = catalog.fetchone(
                            "SELECT operation_id FROM catalog_publication_receipts WHERE operation_id=?", (operation,))
                        if not receipt:
                            journal = scope_dir / "publications" / f"{operation}.json"
                            try:
                                container = json.loads(journal.read_text(encoding="utf-8"))["previous"]
                            except FileNotFoundError:
                                container = json.loads(container_path.read_text(encoding="utf-8"))
                                if container.get("_pending_publication_id"):
                                    continue
                    scope = container.get("scope") or {}
                    if (scope.get("character") != character or scope.get("phase") != phase
                            or scope.get("pipeline") != pipeline_name):
                        continue
                    costume_slug = str(scope.get("costume") or "")
                    qualifier = "" if costume_slug == "_" else costume_slug
                    if scope_dir.name != quote(qualifier or "_", safe="-_."):
                        continue
                    for view, board in (container.get("boards") or {}).items():
                        candidate_id = str(board.get("selected_id") or "")
                        candidate = (board.get("candidates") or {}).get(candidate_id) or {}
                        asset_id = str(candidate.get("inventory_asset_id") or "")
                        if not candidate.get("locked") or not candidate_id or not asset_id:
                            continue
                        asset = catalog.fetchone(
                            "SELECT status FROM assets WHERE asset_id=?", (asset_id,)
                        )
                        image = Path(str(candidate.get("locked_image_path") or "")).resolve()
                        if (not asset or asset["status"] != "approved"
                                or not image.is_relative_to(self.store.library_root)
                                or not image.is_file()):
                            continue
                        digest = str(candidate.get("image_sha256") or "")
                        if not digest:
                            digest = hashlib.sha256(image.read_bytes()).hexdigest()
                        source_key = f"inventory:{asset_id}"
                        output.append({
                            "source_key": source_key,
                            "category_key": LocalAssetStoreService.key(pipeline_name, view, qualifier),
                            "pipeline": pipeline_name,
                            "view": view,
                            "costume": qualifier.replace("_", " "),
                            "image_path": str(image),
                            "image_sha256": digest,
                            "inventory_asset_id": asset_id,
                            "candidate_id": candidate_id,
                            "container_id": str(container.get("container_id") or ""),
                            "render_mode": str(candidate.get("render_mode") or "draft"),
                            "dependencies": [],
                            "updated_at": str(candidate.get("locked_at") or candidate.get("prepared_at") or ""),
                        })
                except (OSError, ValueError, TypeError, AttributeError):
                    continue
        return output

    def list_sources(self, character: str, phase: str, pipeline: str = "", *, include_all: bool = False) -> list[dict[str, Any]]:
        container_sources = self._container_sources(character, phase, pipeline)
        if not include_all:
            preferred = {}
            for source in container_sources:
                key = (source["pipeline"].lower(), source["costume"].casefold(), source["view"])
                if key not in preferred or source["render_mode"] == "final":
                    preferred[key] = source
            return list(preferred.values())

        # Include legacy lock rows only for saved old keys and migration diagnostics.
        sources = []
        for record in self.store.locked_assets(character, phase, pipeline=pipeline, render_mode=None):
            image = Path(record["image_path"])
            category_key = LocalAssetStoreService.key(record.get("pipeline", ""), record.get("view", ""),
                                                       record.get("qualifier", ""))
            sources.append({"source_key": record["key"], "category_key": category_key,
                "pipeline": record.get("pipeline", ""), "view": record.get("view", ""),
                "costume": record.get("qualifier", ""), "image_path": str(image),
                "image_sha256": record.get("image_sha256", ""),
                "inventory_asset_id": record.get("entity_library_asset_id"),
                "batch_id": record.get("batch_id", ""), "candidate_id": record.get("candidate_id", ""),
                "render_mode": record.get("render_mode", "draft"),
                "dependencies": list(record.get("dependencies") or []), "updated_at": record.get("updated_at", "")})
        if include_all:
            return sources + container_sources
        return container_sources

    def get_source(self, character: str, phase: str, source_key: str) -> dict[str, Any]:
        """Resolve a current lock with an available permanent file."""
        for source in self.list_sources(character, phase, include_all=True):
            if source["source_key"] == source_key:
                return source
        if source_key.startswith("inventory:"):
            asset_id = source_key.removeprefix("inventory:")
            try:
                asset = self.store._ensure_entity_library().get_asset(asset_id)
                origin_key = str(asset.get("origin_key") or "")
                origin_parts = origin_key.split(":", 4)
                if (asset.get("origin") != "pipeline" or len(origin_parts) < 5
                        or origin_parts[0] != "local" or origin_parts[2] != character
                        or origin_parts[3] != phase):
                    raise ValueError("Inventory asset is outside this character phase's pipeline sources.")
                image = Path(asset["image_path"]).resolve()
                if not image.is_relative_to(self.store.library_root) or not image.is_file():
                    raise ValueError("Inventory image is unavailable.")
                parts = str(asset.get("origin_key") or "").split(":")
                pipeline = parts[1] if len(parts) > 1 and parts[0] == "local" else ""
                return {"source_key": source_key, "pipeline": pipeline or asset.get("label", "Inventory image"),
                        "view": "", "costume": "", "image_path": str(image),
                        "image_sha256": asset.get("checksum", ""),
                        "inventory_asset_id": asset_id, "render_mode": ""}
            except Exception as exc:
                raise LocalAssetStoreError(f"Saved Inventory source is unavailable: {source_key}") from exc
        raise LocalAssetStoreError(f"Local source is missing, unlocked, or stale: {source_key}")

    def get_category_source(self, character: str, phase: str, category_key: str) -> dict[str, Any]:
        """Resolve the latest available lock for one pipeline/qualifier/view category."""
        for source in self.list_sources(character, phase):
            if source["category_key"] == category_key:
                return source
        raise LocalAssetStoreError(f"No locked image is available for source: {category_key}")
