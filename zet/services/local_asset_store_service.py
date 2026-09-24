"""Durable selected and locked assets for local character pipelines."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class LocalAssetStoreError(ValueError):
    pass


class LocalAssetStoreService:
    """Store local selections next to experiment batches, separate from canonical assets."""

    def __init__(self, library_root: str | Path):
        self.root = Path(library_root).resolve() / "Experiments" / "Character-Pipeline"

    @staticmethod
    def key(pipeline: str, view: str) -> str:
        return f"{str(pipeline).strip().lower()}:{str(view).strip().upper()}"

    @staticmethod
    def _safe(value: str) -> str:
        result = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
        if not result or result in {".", ".."}:
            raise LocalAssetStoreError("Character and phase are required.")
        return result

    def workspace_path(self, character: str, phase: str) -> Path:
        return self.root / self._safe(character) / self._safe(phase) / "local_assets.json"

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

    def locked_assets(self, character: str, phase: str) -> list[dict[str, Any]]:
        """Return only verified locked assets for downstream local pipelines."""
        records = self.detail(character, phase)["assets"]
        result = []
        for key, record in records.items():
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

    def assert_change_allowed(self, character: str, phase: str, pipeline: str, view: str) -> None:
        value = self._read(character, phase)
        key = self.key(pipeline, view)
        current = value.get("assets", {}).get(key, {})
        if current.get("locked"):
            raise LocalAssetStoreError(f"{key} is locked. Unlock it before changing its selection.")
        dependents = self._locked_dependents(value.get("assets", {}), key)
        if dependents:
            raise LocalAssetStoreError(
                f"Cannot change {key}; unlock downstream local assets first: {', '.join(dependents)}."
            )

    def record_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        image = Path(image_path).resolve()
        if not image.is_file():
            raise LocalAssetStoreError(f"Selected local image is missing: {image}")
        key = self.key(pipeline, view)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            current = assets.get(key, {})
            digest = self._image_hash(image)
            changed = current.get("candidate_id") != candidate_id or current.get("image_sha256") != digest
            if changed:
                if current.get("locked"):
                    raise LocalAssetStoreError(f"{key} is locked. Unlock it before changing its selection.")
                dependents = self._locked_dependents(assets, key)
                if dependents:
                    raise LocalAssetStoreError(
                        f"Cannot change {key}; unlock downstream local assets first: {', '.join(dependents)}."
                    )
                for child in assets.values():
                    if any(dep.get("key") == key for dep in child.get("dependencies", [])) and not child.get("locked"):
                        child["stale"] = True
                        child["stale_reason"] = f"Upstream selection {key} changed."
            record = {
                **current,
                "pipeline": str(pipeline), "view": str(view).upper(),
                "candidate_id": str(candidate_id), "batch_id": str(batch_id),
                "image_path": str(image), "image_sha256": digest,
                "dependencies": list(dependencies or []),
                "selected": True, "stale": False,
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            assets[key] = record
            write_json_atomic(path, value)
            return dict(record)

    def clear_selection(self, character: str, phase: str, pipeline: str, view: str) -> dict[str, Any]:
        key = self.key(pipeline, view)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            current = assets.get(key)
            if not current:
                return value
            if current.get("locked"):
                raise LocalAssetStoreError(f"{key} is locked. Unlock it before clearing its selection.")
            dependents = self._locked_dependents(assets, key)
            if dependents:
                raise LocalAssetStoreError(
                    f"Cannot clear {key}; unlock downstream local assets first: {', '.join(dependents)}."
                )
            assets.pop(key)
            for child in assets.values():
                if any(dep.get("key") == key for dep in child.get("dependencies", [])) and not child.get("locked"):
                    child["stale"] = True
                    child["stale_reason"] = f"Upstream selection {key} was cleared."
            write_json_atomic(path, value)
            return value

    def lock(self, character: str, phase: str, pipeline: str, view: str) -> dict[str, Any]:
        key = self.key(pipeline, view)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            record = value.get("assets", {}).get(key)
            if not record or not record.get("selected") or record.get("stale"):
                raise LocalAssetStoreError(f"Select a reviewed {key} candidate before locking it.")
            source = Path(str(record.get("image_path") or "")).resolve()
            if not source.is_file() or self._image_hash(source) != record.get("image_sha256"):
                raise LocalAssetStoreError(f"Selected image for {key} is missing or has changed; review it again.")
            for dependency in record.get("dependencies", []):
                parent = value.get("assets", {}).get(str(dependency.get("key") or ""), {})
                if not parent.get("selected") or parent.get("stale"):
                    raise LocalAssetStoreError(f"Required local dependency {dependency.get('key')} is not current.")
                if parent.get("image_sha256") != dependency.get("image_sha256"):
                    raise LocalAssetStoreError(f"Required local dependency {dependency.get('key')} changed.")
            locked_root = path.parent / "locked" / self._safe(pipeline) / self._safe(view)
            locked_path = locked_root / f"{record['image_sha256'][:16]}_{source.name}"
            locked_root.mkdir(parents=True, exist_ok=True)
            if not locked_path.exists():
                shutil.copy2(source, locked_path)
            if self._image_hash(locked_path) != record["image_sha256"]:
                raise LocalAssetStoreError(f"Could not verify immutable local image copy for {key}.")
            record.update({
                "locked": True, "locked_image_path": str(locked_path),
                "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "lock_history": [*record.get("lock_history", []), {
                    "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "image_sha256": record["image_sha256"],
                }],
            })
            write_json_atomic(path, value)
            return dict(record)

    def unlock(self, character: str, phase: str, pipeline: str, view: str) -> dict[str, Any]:
        key = self.key(pipeline, view)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.get("assets", {})
            record = assets.get(key)
            if not record or not record.get("locked"):
                raise LocalAssetStoreError(f"{key} is not locked.")
            dependents = self._locked_dependents(assets, key)
            if dependents:
                raise LocalAssetStoreError(
                    f"Unlock downstream local assets first: {', '.join(dependents)}."
                )
            record.update({"locked": False, "unlocked_at": datetime.now().astimezone().isoformat(timespec="seconds")})
            write_json_atomic(path, value)
            return dict(record)
