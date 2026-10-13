"""Machine-local capture receipts, worker claims and cached integration status."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


class TaskWorkflowRepository:
    def __init__(self, state_root: str | Path):
        self.root = Path(state_root).expanduser().resolve()
        if any((parent / ".git").exists() for parent in (self.root, *self.root.parents)):
            raise ValueError("Task workflow state must be outside Git working trees.")
        self.path = self.root / "task-workflow.sqlite3"

    @contextmanager
    def transaction(self):
        self.root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=60)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS records (scope TEXT, key TEXT, payload TEXT NOT NULL, PRIMARY KEY(scope,key))")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def read(db, scope: str, key: str, default=None):
        row = db.execute("SELECT payload FROM records WHERE scope=? AND key=?", (scope, key)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def write(db, scope: str, key: str, value):
        db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(scope,key) DO UPDATE SET payload=excluded.payload",
                   (scope, key, json.dumps(value, allow_nan=False)))

    def get(self, scope, key, default=None):
        with self.transaction() as db:
            return self.read(db, scope, key, default)

    def put(self, scope, key, value):
        with self.transaction() as db:
            self.write(db, scope, key, value)

    def entries(self, scope):
        with self.transaction() as db:
            return {key: json.loads(payload) for key, payload in db.execute("SELECT key,payload FROM records WHERE scope=?", (scope,))}
