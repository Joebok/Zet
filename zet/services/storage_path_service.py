"""Resolve and validate configured machine-local Zet storage locations."""
from __future__ import annotations

import os
from pathlib import Path


class StoragePathError(ValueError):
    """A configured application storage path is unsafe or unavailable."""


class StoragePathService:
    CHILDREN = {
        "indexes": "storage_indexes_path",
        "queue_state": "storage_queue_state_path",
        "migration_state": "storage_migration_state_path",
        "workflow_state": "storage_workflow_state_path",
    }

    def __init__(self, config):
        self.config = config
        self._root = Path(config.storage_root).expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def child(self, name: str) -> Path:
        attribute = self.CHILDREN.get(name)
        if attribute is None:
            raise StoragePathError(f"Unknown Zet storage area: {name}")
        path = Path(getattr(self.config, attribute)).expanduser()
        if path.is_absolute():
            raise StoragePathError(f"Storage.{name} must be relative to Storage.Root.")
        root = self._root
        resolved = (root / path).resolve()
        if resolved == root or root not in resolved.parents:
            raise StoragePathError(f"Storage.{name} escapes Storage.Root.")
        library = Path(self.config.base_library_path).expanduser().resolve()
        if resolved == library or resolved in library.parents or library in resolved.parents:
            raise StoragePathError("Machine-local storage must be outside the creative library.")
        queue = Path(self.config.base_ai_queue_path).expanduser().resolve()
        if resolved == queue or queue in resolved.parents or resolved in queue.parents:
            raise StoragePathError("Machine-local storage must be separate from the shared AI queue.")
        for other_name, other_attribute in self.CHILDREN.items():
            if other_name == name:
                continue
            other = Path(getattr(self.config, other_attribute)).expanduser()
            if other.is_absolute():
                continue
            other_resolved = (root / other).resolve()
            if resolved == other_resolved or resolved in other_resolved.parents or other_resolved in resolved.parents:
                raise StoragePathError(f"Storage.{name} overlaps Storage.{other_name}.")
        return resolved

    @property
    def indexes(self) -> Path:
        return self.child("indexes")

    @property
    def queue_state(self) -> Path:
        return self.child("queue_state")

    @property
    def migration_state(self) -> Path:
        return self.child("migration_state")

    @property
    def workflow_state(self) -> Path:
        return self.child("workflow_state")

    def require_available(self) -> None:
        drive = self._root.drive
        if drive and not Path(drive + os.sep).is_dir():
            raise StoragePathError(f"Configured Zet storage drive is unavailable: {drive}")

    def ensure_available(self, area: str) -> Path:
        self.require_available()
        path = self.child(area)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StoragePathError(f"Cannot create configured Zet storage at {path}: {exc}") from exc
        return path

