"""Incremental, process-local metadata snapshots for one physical AI queue."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class AIQueueMetadataService:
    _instances: dict[str, "AIQueueMetadataService"] = {}
    _instances_lock = threading.RLock()

    def __init__(self, queue_key: str):
        self.queue_key = queue_key
        self._lock = threading.RLock()
        self._records: dict[Path, tuple[tuple[int, int, int, int, int, int], dict]] = {}
        self._next_scan: dict[Path, float] = {}
        self._last_complete: dict[Path, dict] = {}
        self._changes: dict[Path, set[str]] = {}
        self._storage_available: bool | None = None

    @classmethod
    def for_root(cls, root: Path) -> "AIQueueMetadataService":
        key = str(root.expanduser().resolve()).casefold()
        with cls._instances_lock:
            return cls._instances.setdefault(key, cls(key))

    @staticmethod
    def _signature(path: Path):
        info = path.stat()
        return (getattr(info, "st_dev", 0), getattr(info, "st_ino", 0), info.st_size,
                info.st_mtime_ns, info.st_ctime_ns, info.st_mode)

    def invalidate(self, path: Path | None = None) -> None:
        with self._lock:
            if path is None:
                self._next_scan.clear()
            else:
                self._records.pop(path.resolve(), None)
                self._next_scan.clear()

    def storage_state(self, available: bool) -> None:
        with self._lock:
            if available and self._storage_available is False:
                self._records.clear()
                self._next_scan.clear()
            self._storage_available = available

    def take_changes(self, root: Path) -> tuple[str, ...]:
        with self._lock:
            values = self._changes.pop(root.absolute(), set())
            return tuple(sorted(values))

    def read(self, path: Path) -> dict | None:
        """Metadata-guarded point read used for transport status JSON."""
        resolved = path.absolute()
        try:
            signature = self._signature(path)
        except OSError:
            return None
        with self._lock:
            cached = self._records.get(resolved)
            if cached is not None and cached[0] == signature:
                return cached[1]
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            after = self._signature(path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if isinstance(value, dict) and after == signature:
            with self._lock:
                self._records[resolved] = (signature, value)
            return value
        return None

    def snapshot(self, root: Path, *, recursive: bool = False, force: bool = False, projector=None) -> tuple[dict, ...]:
        root = root.absolute()
        now = time.monotonic()
        with self._lock:
            if now < self._next_scan.get(root, 0.0) and not force:
                return tuple(self._last_complete.get(root, {}).values())
            if not root.is_dir():
                self._next_scan[root] = now + 2.0
                return tuple(self._last_complete.get(root, {}).values())
            try:
                present = set()
                updated = {}
                changed_ids = set()
                pending = [root]
                while pending:
                    directory = pending.pop()
                    with os.scandir(directory) as entries:
                        for entry in entries:
                            if entry.is_dir(follow_symlinks=False):
                                if recursive:
                                    pending.append(Path(entry.path))
                                continue
                            if not entry.name.lower().endswith(".json") or not entry.is_file(follow_symlinks=False):
                                continue
                            path = Path(entry.path)
                            # Windows DirEntry.stat can report zero inode/device;
                            # Path.stat supplies the file identity used for replacement detection.
                            signature = self._signature(path)
                            resolved = path.absolute()
                            present.add(resolved)
                            previous = self._records.get(resolved)
                            if previous is not None and previous[0] == signature:
                                updated[resolved] = previous
                                continue
                            try:
                                value = json.loads(path.read_text(encoding="utf-8"))
                            except (OSError, UnicodeError, json.JSONDecodeError):
                                continue
                            if not isinstance(value, dict):
                                continue
                            try:
                                after = self._signature(path)
                            except OSError:
                                continue
                            if after == signature:
                                updated[resolved] = (signature, projector(value) if projector else value)
                                changed_ids.add(str(value.get("ask_id") or path.stem))
                # An interrupted directory walk must not evict the last complete view.
                self._records.update(updated)
                scoped = {path for path in self._records
                          if path.parent == root or (recursive and root in path.parents)}
                for path in scoped - present:
                    old = self._records.get(path)
                    if old:
                        changed_ids.add(str(old[1].get("ask_id") or path.stem))
                    self._records.pop(path, None)
                complete = {path: value for path, (_signature, value) in self._records.items()
                            if path.parent == root or (recursive and root in path.parents)}
                self._last_complete[root] = complete
                self._changes.setdefault(root, set()).update(changed_ids)
                self._next_scan[root] = now + 2.0
                return tuple(complete.values())
            except OSError:
                self._next_scan[root] = now + 2.0
                return tuple(self._last_complete.get(root, {}).values())
