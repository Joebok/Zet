"""Harvest-driven snapshots for the shared Candidate Board."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from threading import Lock

from zet.services.atomic_file_service import write_json_atomic
from zet.services.runtime_state_service import workflow_root
from zet.services.workflow_storage import file_lock


_subscriber_lock = Lock()
_subscribers = {}


class RecentRenderStore:
    def __init__(self, app):
        self.universe = app.universe_id
        self.path = (workflow_root(app.config) / "RecentRenders" / self.universe / "renders.json").resolve()

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"revision": 0, "images": []}

    def _snapshot(self, state):
        boards = {}
        for row in state["images"]:
            board = boards.setdefault(row["board"], {
                "label": row["label"], "route": row["route"], "count": 0,
            })
            board["count"] += 1
        return {"universe_id": self.universe, "revision": state["revision"], "boards": list(boards.values())}

    def snapshot(self):
        with file_lock(self.path.with_suffix(".lock"), shared=True):
            return self._snapshot(self._read())

    @contextmanager
    def subscribe(self, callback):
        with _subscriber_lock:
            _subscribers.setdefault(self.path, set()).add(callback)
        try:
            yield
        finally:
            with _subscriber_lock:
                callbacks = _subscribers[self.path]
                callbacks.remove(callback)
                if not callbacks:
                    del _subscribers[self.path]

    def record(self, attempts, route, label, *, board_id=None, now=None):
        now = now or datetime.now(timezone.utc)
        timestamp = now.astimezone(timezone.utc).isoformat(timespec="microseconds")
        board = board_id or json.dumps(route, sort_keys=True)
        with file_lock(self.path.with_suffix(".lock"), shared=True):
            state = self._read()
            images = {row["id"]: row for row in state["images"]}
            additions = {
                attempt: {"id": attempt, "board": board, "route": route, "label": label,
                          "harvested_at": timestamp}
                for attempt in attempts if attempt not in images
            }
            if not additions:
                return
            images.update(additions)
            ordered = sorted(images.values(), key=lambda row: (row["harvested_at"], row["id"]), reverse=True)
            latest = datetime.fromisoformat(ordered[0]["harvested_at"])
            cutoff = (latest - timedelta(hours=24)).isoformat(timespec="microseconds")
            retained = [
                row for index, row in enumerate(ordered) if index < 8 or row["harvested_at"] > cutoff
            ]
            if retained == state["images"]:
                return
            state = {"revision": state["revision"] + 1, "images": retained}
            write_json_atomic(self.path, state)
            snapshot = self._snapshot(state)
            with _subscriber_lock:
                for callback in _subscribers.get(self.path, ()):
                    callback(snapshot)
