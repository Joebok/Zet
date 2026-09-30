"""Durable selected and locked assets for local character pipelines."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class LocalAssetStoreError(ValueError):
    pass


class LocalAssetStoreService:
    """Store local selections next to experiment batches, separate from canonical assets."""

    def __init__(self, library_root: str | Path):
        self.library_root = Path(library_root).resolve()
        self.root = self.library_root / "PipelineCandidates" / "Character-Pipeline"
        self._entity_library = None

    def _publish(self, image: Path, *, character: str, phase: str, pipeline: str, checksum: str) -> dict[str, Any]:
        if self._entity_library is None:
            from zet.repositories.entity_library_repository import EntityLibraryRepository
            from zet.services.entity_library_service import EntityLibraryService
            from zet.services.path_service import PathService
            paths = PathService(SimpleNamespace(base_library_path=str(self.library_root)), self.library_root)
            repository = EntityLibraryRepository(paths.entity_library_database_path())
            repository.initialize()
            self._entity_library = EntityLibraryService(paths, repository)
        return self._entity_library.register_locked_pipeline_image(
            image, label=image.stem, pipeline=pipeline, character=character, phase=phase, checksum=checksum,
        )

    @staticmethod
    def key(pipeline: str, view: str, qualifier: str = "") -> str:
        pipeline_key = str(pipeline).strip().lower()
        qualifier_key = re.sub(r"[^a-z0-9_-]+", "_", str(qualifier or "").strip().lower()).strip("_")
        view_key = str(view).strip().upper()
        return f"{pipeline_key}:{qualifier_key}:{view_key}" if qualifier_key else f"{pipeline_key}:{view_key}"

    @staticmethod
    def _safe(value: str) -> str:
        result = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
        if not result or result in {".", ".."}:
            raise LocalAssetStoreError("Character and phase are required.")
        return result

    def workspace_path(self, character: str, phase: str) -> Path:
        return self.library_root / "_state" / "LocalAssets" / self._safe(character) / self._safe(phase) / "local_assets.json"

    def _read(self, character: str, phase: str) -> dict[str, Any]:
        path = self.workspace_path(character, phase)
        if not path.is_file():
            return {"schema_version": 1, "character": character, "phase": phase, "assets": {}}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalAssetStoreError(f"Local asset store is unreadable: {path}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("assets", {}), dict):
            raise LocalAssetStoreError(f"Local asset store has an invalid format: {path}")
        return value

    def detail(self, character: str, phase: str) -> dict[str, Any]:
        value = self._read(character, phase)
        return {"character": character, "phase": phase, "assets": value.get("assets", {})}

    def locked_assets(self, character: str, phase: str, pipeline: str = "", qualifier: str = "") -> list[dict[str, Any]]:
        """Return only verified locked assets for downstream local pipelines."""
        records = self.detail(character, phase)["assets"]
        result = []
        for key, record in records.items():
            if pipeline and record.get("pipeline", "").lower() != pipeline.lower():
                continue
            if qualifier and str(record.get("qualifier") or "").lower() != qualifier.lower():
                continue
            if not record.get("locked") or record.get("stale"):
                continue
            path = Path(str(record.get("locked_image_path") or "")).resolve()
            if not path.is_file() or self._image_hash(path) != record.get("image_sha256"):
                continue
            result.append({"key": key, **record, "image_path": str(path)})
        return sorted(result, key=lambda item: item["key"])

    @staticmethod
    def _image_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _locked_dependents(self, assets: dict[str, Any], parent_key: str) -> list[str]:
        return sorted(
            key for key, item in assets.items()
            if item.get("locked") and any(dep.get("key") == parent_key for dep in item.get("dependencies", []))
        )

    def assert_change_allowed(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> None:
        # Upstream edits are allowed. Batch lineage warnings explain downstream drift.
        return None

    def assert_batch_change_allowed(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> None:
        """Batch work changes run state; shared asset locks do not restrict it."""

    def record_batch_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None, qualifier: str = "",
    ) -> dict[str, Any] | None:
        """Keep a batch selection in its run when the shared asset cannot be changed."""
        current = self.detail(character, phase)["assets"].get(self.key(pipeline, view, qualifier), {})
        if current.get("locked"):
            return None
        try:
            self.assert_change_allowed(character, phase, pipeline, view, qualifier)
        except LocalAssetStoreError:
            return None
        return self.record_selection(
            character, phase, pipeline, view, candidate_id=candidate_id,
            image_path=image_path, batch_id=batch_id,
            dependencies=dependencies, qualifier=qualifier,
        )

    def lock_batch_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None, qualifier: str = "",
    ) -> dict[str, Any]:
        """Publish a reviewed batch selection only when its view can be locked."""
        self.assert_change_allowed(character, phase, pipeline, view, qualifier)
        self.record_selection(
            character, phase, pipeline, view, candidate_id=candidate_id,
            image_path=image_path, batch_id=batch_id,
            dependencies=dependencies, qualifier=qualifier,
        )
        return self.lock(character, phase, pipeline, view, qualifier)

    def clear_batch_selection(self, character: str, phase: str, pipeline: str, view: str,
                              batch_id: str, qualifier: str = "") -> None:
        """Clear the shared selection only when this batch owns it and it is unlocked."""
        key = self.key(pipeline, view, qualifier)
        record = self.detail(character, phase)["assets"].get(key) or {}
        if record.get("batch_id") == batch_id and not record.get("locked"):
            self.clear_selection(character, phase, pipeline, view, qualifier)

    def record_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None,
        qualifier: str = "",
    ) -> dict[str, Any]:
        image = Path(image_path).resolve()
        if not image.is_file():
            raise LocalAssetStoreError(f"Selected local image is missing: {image}")
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            current = assets.get(key, {})
            digest = self._image_hash(image)
            changed = current.get("candidate_id") != candidate_id or current.get("image_sha256") != digest
            if changed:
                for child in assets.values():
                    if any(dep.get("key") == key for dep in child.get("dependencies", [])) and not child.get("locked"):
                        child["stale"] = True
                        child["stale_reason"] = f"Upstream selection {key} changed."
            record = {
                **current,
                "pipeline": str(pipeline), "view": str(view).upper(),
                "qualifier": str(qualifier or ""),
                "candidate_id": str(candidate_id), "batch_id": str(batch_id),
                "image_path": str(image), "image_sha256": digest,
                "dependencies": list(dependencies or []),
                "selected": True, "stale": False,
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            assets[key] = record
            write_json_atomic(path, value)
            return dict(record)

    def clear_selection(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            current = assets.get(key)
            if not current:
                return value
            assets.pop(key)
            for child in assets.values():
                if any(dep.get("key") == key for dep in child.get("dependencies", [])) and not child.get("locked"):
                    child["stale"] = True
                    child["stale_reason"] = f"Upstream selection {key} was cleared."
            write_json_atomic(path, value)
            return value

    def lock(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            record = value.get("assets", {}).get(key)
            if not record or not record.get("selected") or record.get("stale"):
                raise LocalAssetStoreError(f"Select a reviewed {key} candidate before locking it.")
            source = Path(str(record.get("image_path") or "")).resolve()
            if not source.is_file() or self._image_hash(source) != record.get("image_sha256"):
                raise LocalAssetStoreError(f"Selected image for {key} is missing or has changed; review it again.")
            try:
                published = self._publish(source, character=character, phase=phase, pipeline=pipeline, checksum=record["image_sha256"])
            except Exception as exc:
                raise LocalAssetStoreError(f"Could not publish selected image for {key}: {exc}") from exc
            locked_path = Path(published["image_path"])
            record.update({
                "locked": True, "locked_image_path": str(locked_path), "entity_library_asset_id": published["asset_id"],
                "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "lock_history": [*record.get("lock_history", []), {
                    "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "image_sha256": record["image_sha256"],
                }],
            })
            write_json_atomic(path, value)
            return dict(record)

    def promote_chain(self, character: str, phase: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Atomically publish a preflighted set of selected local assets as locked."""
        path = self.workspace_path(character, phase)
        staged: list[tuple[str, dict[str, Any], Path, Path, str]] = []
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            for item in records:
                pipeline, view = str(item["pipeline"]), str(item["view"]).upper()
                qualifier = str(item.get("qualifier") or "")
                image = Path(str(item["image_path"])).resolve()
                digest = str(item["image_sha256"])
                if not image.is_file() or self._image_hash(image) != digest:
                    raise LocalAssetStoreError(f"Selected image for {pipeline} {view} is missing or changed.")
                key = self.key(pipeline, view, qualifier)
                staged.append((key, item, image, Path(), digest))

            published_assets = []
            for key, item, image, _locked_path, digest in staged:
                try:
                    published = self._publish(image, character=character, phase=phase,
                                              pipeline=str(item["pipeline"]), checksum=digest)
                except Exception as exc:
                    raise LocalAssetStoreError(f"Could not publish selected image for {key}: {exc}") from exc
                locked_path = Path(published["image_path"])
                if self._image_hash(locked_path) != digest:
                    raise LocalAssetStoreError(f"Could not verify permanent image for {key}.")
                published_assets.append((key, item, image, locked_path, digest, published["asset_id"]))
            result = []
            for key, item, image, locked_path, digest, catalog_asset_id in published_assets:
                current = assets.get(key, {})
                record = {
                    **current, "pipeline": str(item["pipeline"]), "view": str(item["view"]).upper(),
                    "qualifier": str(item.get("qualifier") or ""),
                    "candidate_id": str(item["candidate_id"]), "batch_id": str(item["batch_id"]),
                    "batch_name": str(item.get("batch_name") or ""),
                    "image_path": str(image), "image_sha256": digest,
                    "dependencies": list(item.get("dependencies") or []), "selected": True, "stale": False,
                    "locked": True, "locked_image_path": str(locked_path), "entity_library_asset_id": catalog_asset_id,
                    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
                if current.get("image_sha256") != digest or current.get("candidate_id") != record["candidate_id"]:
                    record["lock_history"] = [*current.get("lock_history", []), {
                        "locked_at": record["locked_at"], "image_sha256": digest,
                        "batch_id": record["batch_id"], "candidate_id": record["candidate_id"],
                    }]
                assets[key] = record
                result.append(dict(record))
            write_json_atomic(path, value)
            return result

    def unlock(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.get("assets", {})
            record = assets.get(key)
            if not record or not record.get("locked"):
                raise LocalAssetStoreError(f"{key} is not locked.")
            record.update({"locked": False, "unlocked_at": datetime.now().astimezone().isoformat(timespec="seconds")})
            write_json_atomic(path, value)
            return dict(record)
