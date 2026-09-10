from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence


class LibraryIndexError(Exception):
    """Base error for the rebuildable machine-local library index."""


class LibraryIndexCorruptError(LibraryIndexError):
    """Raised when SQLite reports that the local index is corrupt."""


@dataclass(frozen=True)
class IndexSnapshot:
    sources: Sequence[Mapping] = field(default_factory=tuple)
    stories: Sequence[Mapping] = field(default_factory=tuple)
    scenes: Sequence[Mapping] = field(default_factory=tuple)
    render_targets: Sequence[Mapping] = field(default_factory=tuple)
    catalog_records: Sequence[Mapping] = field(default_factory=tuple)
    reference_relationships: Sequence[Mapping] = field(default_factory=tuple)
    work_items: Sequence[Mapping] = field(default_factory=tuple)
    job_summaries: Sequence[Mapping] = field(default_factory=tuple)
    errors: Sequence[Mapping] = field(default_factory=tuple)
    source_payloads: Sequence[Mapping] = field(default_factory=tuple)


@dataclass(frozen=True)
class IndexPage:
    items: list[dict]
    next_cursor: str | None


class LibraryIndexRepository:
    """Own a rebuildable SQLite index for one canonical authored-library root."""

    SCHEMA_VERSION = 1

    def __init__(self, library_root: str | Path, *, index_root: str | Path | None = None):
        self.library_root = Path(library_root).resolve()
        root = Path(index_root).resolve() if index_root is not None else self.default_index_root()
        self._validate_index_root(root)
        canonical = os.path.normcase(str(self.library_root))
        self.library_key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.index_root = root
        self.database_path = root / f"{self.library_key}.sqlite3"

    @staticmethod
    def default_index_root() -> Path:
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return (base / "Zet" / "Indexes").resolve()

    def _validate_index_root(self, root: Path) -> None:
        if root == self.library_root or self.library_root in root.parents:
            raise LibraryIndexError("The machine-local index must be outside the authored library.")
        if any(part.casefold().startswith("dropbox") for part in root.parts):
            raise LibraryIndexError("The machine-local index must be outside Dropbox.")
        for parent in (root, *root.parents):
            if (parent / ".git").exists():
                raise LibraryIndexError("The machine-local index must be outside Git working trees.")

    def _corrupt(self, exc: sqlite3.DatabaseError) -> LibraryIndexCorruptError:
        return LibraryIndexCorruptError(
            f"The machine-local Zet index is unreadable at {self.database_path}: {exc}. "
            "Delete this database and run `python -m zet.scripts.rebuild_library_index --config <config.toml>` "
            "to rebuild it; authored library files are not stored in the index."
        )

    def _connect(self) -> sqlite3.Connection:
        self.index_root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generations (
                generation INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sources (
                generation INTEGER NOT NULL, source_path TEXT NOT NULL, source_kind TEXT NOT NULL,
                fingerprint TEXT NOT NULL, parse_status TEXT NOT NULL,
                PRIMARY KEY (generation, source_path)
            );
            CREATE TABLE IF NOT EXISTS stories (
                generation INTEGER NOT NULL, story_slug TEXT NOT NULL, name TEXT NOT NULL,
                source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, story_slug)
            );
            CREATE TABLE IF NOT EXISTS scenes (
                generation INTEGER NOT NULL, story_slug TEXT NOT NULL, scene_slug TEXT NOT NULL,
                name TEXT NOT NULL, position INTEGER NOT NULL, source_path TEXT NOT NULL,
                fingerprint TEXT NOT NULL, PRIMARY KEY (generation, story_slug, scene_slug)
            );
            CREATE TABLE IF NOT EXISTS render_targets (
                generation INTEGER NOT NULL, story_slug TEXT NOT NULL, scene_slug TEXT NOT NULL,
                target_id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, enabled INTEGER NOT NULL,
                position INTEGER NOT NULL, source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, story_slug, scene_slug, target_id)
            );
            CREATE TABLE IF NOT EXISTS catalog_records (
                generation INTEGER NOT NULL, catalog_id TEXT NOT NULL, source_key TEXT NOT NULL,
                name TEXT NOT NULL, semantic_category TEXT NOT NULL, reference_set_id TEXT NOT NULL,
                source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, catalog_id)
            );
            CREATE TABLE IF NOT EXISTS reference_relationships (
                generation INTEGER NOT NULL, reference_set_id TEXT NOT NULL, catalog_id TEXT NOT NULL,
                source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, reference_set_id, catalog_id)
            );
            CREATE TABLE IF NOT EXISTS work_items (
                generation INTEGER NOT NULL, work_id TEXT NOT NULL, scope_kind TEXT NOT NULL,
                story_slug TEXT NOT NULL, scene_slug TEXT NOT NULL, render_target_id TEXT NOT NULL,
                status TEXT NOT NULL, name TEXT NOT NULL, source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, work_id, source_path)
            );
            CREATE TABLE IF NOT EXISTS job_summaries (
                generation INTEGER NOT NULL, job_id TEXT NOT NULL, scope_kind TEXT NOT NULL,
                story_slug TEXT NOT NULL, scene_slug TEXT NOT NULL, render_target_id TEXT NOT NULL,
                status TEXT NOT NULL, name TEXT NOT NULL, completed_at TEXT NOT NULL,
                source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, job_id, source_path)
            );
            CREATE TABLE IF NOT EXISTS index_errors (
                generation INTEGER NOT NULL, source_path TEXT NOT NULL, source_kind TEXT NOT NULL,
                message TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY (generation, source_path)
            );
            CREATE TABLE IF NOT EXISTS source_payloads (
                source_path TEXT NOT NULL, fingerprint TEXT NOT NULL,
                parsed_json TEXT, error_message TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (source_path, fingerprint)
            );
            CREATE TABLE IF NOT EXISTS dependency_edges (
                scope_key TEXT NOT NULL, dependency_path TEXT NOT NULL,
                dependency_fingerprint TEXT NOT NULL,
                PRIMARY KEY (scope_key, dependency_path)
            );
            CREATE TABLE IF NOT EXISTS compilation_cache (
                scope_key TEXT PRIMARY KEY, compiler_version TEXT NOT NULL,
                dependency_fingerprint TEXT NOT NULL, result_fingerprint TEXT NOT NULL,
                compiled_at TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS scenes_scope_order ON scenes(generation, story_slug, position, scene_slug);
            CREATE INDEX IF NOT EXISTS targets_scope_order ON render_targets(generation, story_slug, scene_slug, position, target_id);
            CREATE INDEX IF NOT EXISTS catalog_query ON catalog_records(generation, reference_set_id, semantic_category, name, catalog_id);
            CREATE INDEX IF NOT EXISTS work_query ON work_items(generation, status, story_slug, scene_slug, name, work_id);
            CREATE INDEX IF NOT EXISTS jobs_query ON job_summaries(generation, status, story_slug, scene_slug, completed_at, job_id);
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', ?)",
            (str(self.SCHEMA_VERSION),),
        )
        connection.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('library_key', ?)", (self.library_key,)
        )
        compilation_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(compilation_cache)")
        }
        if "result_json" not in compilation_columns:
            connection.execute(
                "ALTER TABLE compilation_cache ADD COLUMN result_json TEXT NOT NULL DEFAULT '{}'"
            )
        schema_version = self._metadata(connection, "schema_version")
        library_key = self._metadata(connection, "library_key")
        if schema_version != str(self.SCHEMA_VERSION):
            raise LibraryIndexError(
                f"Unsupported machine-local index schema {schema_version!r}; delete {self.database_path} and rebuild it."
            )
        if library_key != self.library_key:
            raise LibraryIndexError("The machine-local index belongs to a different authored library.")
        connection.commit()

    def _run(self, operation: Callable[[sqlite3.Connection], object]):
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            self._initialize(connection)
            return operation(connection)
        except sqlite3.DatabaseError as exc:
            raise self._corrupt(exc) from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _metadata(connection: sqlite3.Connection, key: str) -> str | None:
        row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return str(row[0]) if row else None

    def begin_rebuild(self) -> int:
        def operation(connection: sqlite3.Connection) -> int:
            previous = self._metadata(connection, "building_generation")
            if previous is not None:
                connection.execute(
                    "UPDATE generations SET status = 'failed', completed_at = CURRENT_TIMESTAMP "
                    "WHERE generation = ? AND status = 'building'",
                    (int(previous),),
                )
            row = connection.execute("SELECT COALESCE(MAX(generation), 0) + 1 FROM generations").fetchone()
            generation = int(row[0])
            connection.execute(
                "INSERT INTO generations(generation, status) VALUES (?, 'building')", (generation,)
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES ('building_generation', ?)",
                (str(generation),),
            )
            connection.commit()
            return generation

        return int(self._run(operation))

    def fail_rebuild(self, generation: int, message: str) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                "UPDATE generations SET status = 'failed', completed_at = CURRENT_TIMESTAMP WHERE generation = ?",
                (generation,),
            )
            connection.execute("DELETE FROM metadata WHERE key = 'building_generation'")
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES ('last_build_error', ?)", (message,)
            )
            connection.commit()

        self._run(operation)

    def publish(
        self,
        generation: int,
        snapshot: IndexSnapshot,
        *,
        before_activate: Callable[[], None] | None = None,
    ) -> None:
        table_rows = {
            "sources": snapshot.sources,
            "stories": snapshot.stories,
            "scenes": snapshot.scenes,
            "render_targets": snapshot.render_targets,
            "catalog_records": snapshot.catalog_records,
            "reference_relationships": snapshot.reference_relationships,
            "work_items": snapshot.work_items,
            "job_summaries": snapshot.job_summaries,
            "index_errors": snapshot.errors,
        }

        def operation(connection: sqlite3.Connection) -> None:
            row = connection.execute(
                "SELECT status FROM generations WHERE generation = ?", (generation,)
            ).fetchone()
            if not row or row[0] != "building":
                raise LibraryIndexError(f"Generation {generation} is not available for publication.")
            connection.execute("BEGIN IMMEDIATE")
            try:
                for table, rows in table_rows.items():
                    for row_data in rows:
                        values = {"generation": generation, **dict(row_data)}
                        columns = tuple(values)
                        placeholders = ", ".join("?" for _ in columns)
                        connection.execute(
                            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                            tuple(values[column] for column in columns),
                        )
                if snapshot.source_payloads:
                    connection.executemany(
                        "INSERT OR REPLACE INTO source_payloads "
                        "(source_path, fingerprint, parsed_json, error_message) VALUES (?, ?, ?, ?)",
                        [
                            (
                                str(payload["source_path"]),
                                str(payload["fingerprint"]),
                                payload.get("parsed_json"),
                                str(payload.get("error_message") or ""),
                            )
                            for payload in snapshot.source_payloads
                        ],
                    )
                if before_activate is not None:
                    before_activate()
                connection.execute(
                    "UPDATE generations SET status = 'complete', completed_at = CURRENT_TIMESTAMP WHERE generation = ?",
                    (generation,),
                )
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES ('active_generation', ?)",
                    (str(generation),),
                )
                connection.execute("DELETE FROM metadata WHERE key IN ('building_generation', 'last_build_error')")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        self._run(operation)

    def cached_source_payload(self, source_path: str, fingerprint: str) -> dict | None:
        def operation(connection: sqlite3.Connection) -> dict | None:
            row = connection.execute(
                "SELECT parsed_json, error_message FROM source_payloads "
                "WHERE source_path = ? AND fingerprint = ?",
                (source_path, fingerprint),
            ).fetchone()
            return dict(row) if row else None

        return self._run(operation)

    def active_source_fingerprints(self) -> dict[str, str]:
        def operation(connection: sqlite3.Connection) -> dict[str, str]:
            generation = self._active_generation(connection)
            if generation is None:
                return {}
            return {
                str(row["source_path"]): str(row["fingerprint"])
                for row in connection.execute(
                    "SELECT source_path, fingerprint FROM sources WHERE generation = ?", (generation,)
                )
            }

        return dict(self._run(operation))

    def complete_reconciliation(
        self,
        *,
        generation: int,
        completed_at: str,
        cursor: str,
        changed_sources: Sequence[str],
        errors: Sequence[Mapping],
    ) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            values = {
                "reconciliation_generation": str(generation),
                "reconciliation_last_completed_at": completed_at,
                "reconciliation_cursor": cursor,
                "reconciliation_changed_sources": json.dumps(list(changed_sources), separators=(",", ":")),
                "reconciliation_errors": json.dumps(list(errors), separators=(",", ":")),
            }
            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", values.items()
            )
            connection.commit()

        self._run(operation)

    def fail_reconciliation(self, *, completed_at: str, message: str) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (
                    ("reconciliation_last_completed_at", completed_at),
                    ("reconciliation_errors", json.dumps([{"message": message}], separators=(",", ":"))),
                ),
            )
            connection.commit()

        self._run(operation)

    def record_compilation(
        self,
        scope_key: str,
        *,
        compiler_version: str,
        dependency_fingerprint: str,
        result_fingerprint: str,
        compiled_at: str,
        dependencies: Mapping[str, str],
        result: Mapping | None = None,
    ) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM dependency_edges WHERE scope_key = ?", (scope_key,))
            connection.executemany(
                "INSERT INTO dependency_edges(scope_key, dependency_path, dependency_fingerprint) "
                "VALUES (?, ?, ?)",
                [(scope_key, path, fingerprint) for path, fingerprint in dependencies.items()],
            )
            connection.execute(
                "INSERT OR REPLACE INTO compilation_cache "
                "(scope_key, compiler_version, dependency_fingerprint, result_fingerprint, compiled_at, result_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    scope_key,
                    compiler_version,
                    dependency_fingerprint,
                    result_fingerprint,
                    compiled_at,
                    json.dumps(dict(result or {}), separators=(",", ":"), ensure_ascii=False),
                ),
            )
            connection.commit()

        self._run(operation)

    def compilation(self, scope_key: str) -> dict | None:
        def operation(connection: sqlite3.Connection) -> dict | None:
            row = connection.execute(
                "SELECT * FROM compilation_cache WHERE scope_key = ?", (scope_key,)
            ).fetchone()
            if row is None:
                return None
            value = dict(row)
            value["result"] = json.loads(value.pop("result_json"))
            return value

        return self._run(operation)

    def dependencies(self, scope_key: str) -> dict[str, str]:
        def operation(connection: sqlite3.Connection) -> dict[str, str]:
            return {
                str(row["dependency_path"]): str(row["dependency_fingerprint"])
                for row in connection.execute(
                    "SELECT dependency_path, dependency_fingerprint FROM dependency_edges WHERE scope_key = ?",
                    (scope_key,),
                )
            }

        return dict(self._run(operation))

    def all_dependencies(self) -> dict[str, str]:
        def operation(connection: sqlite3.Connection) -> dict[str, str]:
            return {
                str(row["dependency_path"]): str(row["dependency_fingerprint"])
                for row in connection.execute(
                    "SELECT dependency_path, dependency_fingerprint FROM dependency_edges"
                )
            }

        return dict(self._run(operation))

    def invalidate_dependencies(self, changed_paths: Sequence[str]) -> list[str]:
        if not changed_paths:
            return []

        def operation(connection: sqlite3.Connection) -> list[str]:
            placeholders = ", ".join("?" for _ in changed_paths)
            scopes = [
                str(row[0])
                for row in connection.execute(
                    f"SELECT DISTINCT scope_key FROM dependency_edges WHERE dependency_path IN ({placeholders})",
                    tuple(changed_paths),
                )
            ]
            if scopes:
                scope_placeholders = ", ".join("?" for _ in scopes)
                connection.execute(
                    f"DELETE FROM compilation_cache WHERE scope_key IN ({scope_placeholders})", tuple(scopes)
                )
            connection.commit()
            return scopes

        return list(self._run(operation))

    def status(self) -> dict:
        def operation(connection: sqlite3.Connection) -> dict:
            active = self._metadata(connection, "active_generation")
            building = self._metadata(connection, "building_generation")
            return {
                "state": "ready" if active else "building",
                "active_generation": int(active) if active else None,
                "building_generation": int(building) if building else None,
                "rebuild_in_progress": building is not None,
                "last_build_error": self._metadata(connection, "last_build_error"),
                "database_path": str(self.database_path),
                "library_key": self.library_key,
                "last_reconciliation_completed_at": self._metadata(
                    connection, "reconciliation_last_completed_at"
                ),
                "reconciliation_generation": int(reconciliation_generation)
                if (reconciliation_generation := self._metadata(connection, "reconciliation_generation"))
                else None,
                "reconciliation_cursor": self._metadata(connection, "reconciliation_cursor"),
                "reconciliation_changed_sources": json.loads(
                    self._metadata(connection, "reconciliation_changed_sources") or "[]"
                ),
                "reconciliation_errors": json.loads(
                    self._metadata(connection, "reconciliation_errors") or "[]"
                ),
            }

        return dict(self._run(operation))

    @staticmethod
    def _encode_cursor(values: Sequence) -> str:
        raw = json.dumps(list(values), separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str | None, size: int) -> list | None:
        if not cursor:
            return None
        try:
            values = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        except Exception as exc:
            raise LibraryIndexError("Invalid index pagination cursor.") from exc
        if not isinstance(values, list) or len(values) != size:
            raise LibraryIndexError("Invalid index pagination cursor.")
        return values

    def _active_generation(self, connection: sqlite3.Connection) -> int | None:
        value = self._metadata(connection, "active_generation")
        return int(value) if value else None

    def _page(
        self,
        table: str,
        *,
        filters: Mapping[str, object] | None,
        order: Sequence[tuple[str, str]],
        cursor: str | None,
        limit: int,
    ) -> IndexPage:
        if limit < 1 or limit > 500:
            raise LibraryIndexError("Index page limit must be between 1 and 500.")

        def operation(connection: sqlite3.Connection) -> IndexPage:
            generation = self._active_generation(connection)
            if generation is None:
                return IndexPage([], None)
            clauses = ["generation = ?"]
            params: list[object] = [generation]
            for column, value in (filters or {}).items():
                if value is not None:
                    clauses.append(f"{column} = ?")
                    params.append(value)
            cursor_values = self._decode_cursor(cursor, len(order))
            if cursor_values is not None:
                terms = []
                for index, (column, _direction) in enumerate(order):
                    equal = " AND ".join(f"{prior[0]} = ?" for prior in order[:index])
                    comparison = f"{column} > ?"
                    terms.append(f"({equal + ' AND ' if equal else ''}{comparison})")
                    params.extend(cursor_values[:index])
                    params.append(cursor_values[index])
                clauses.append("(" + " OR ".join(terms) + ")")
            order_sql = ", ".join(f"{column} {direction}" for column, direction in order)
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY {order_sql} LIMIT ?",
                (*params, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            items = [{key: row[key] for key in row.keys() if key != "generation"} for row in rows]
            next_cursor = None
            if has_more and rows:
                next_cursor = self._encode_cursor([rows[-1][column] for column, _ in order])
            return IndexPage(items, next_cursor)

        return self._run(operation)

    def query_stories(self, *, name: str | None = None, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("stories", filters={"name": name}, order=(("name", "ASC"), ("story_slug", "ASC")), cursor=cursor, limit=limit)

    def query_scenes(self, *, story_slug: str | None = None, name: str | None = None, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("scenes", filters={"story_slug": story_slug, "name": name}, order=(("story_slug", "ASC"), ("position", "ASC"), ("scene_slug", "ASC")), cursor=cursor, limit=limit)

    def query_render_targets(self, *, story_slug: str | None = None, scene_slug: str | None = None, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("render_targets", filters={"story_slug": story_slug, "scene_slug": scene_slug}, order=(("story_slug", "ASC"), ("scene_slug", "ASC"), ("position", "ASC"), ("target_id", "ASC")), cursor=cursor, limit=limit)

    def query_catalog(self, *, reference_set_id: str | None = None, semantic_category: str | None = None, name: str | None = None, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("catalog_records", filters={"reference_set_id": reference_set_id, "semantic_category": semantic_category, "name": name}, order=(("name", "ASC"), ("catalog_id", "ASC")), cursor=cursor, limit=limit)

    def query_active_work(self, *, status: str | None = None, story_slug: str | None = None, scene_slug: str | None = None, name: str | None = None, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("work_items", filters={"status": status, "story_slug": story_slug, "scene_slug": scene_slug, "name": name}, order=(("name", "ASC"), ("work_id", "ASC"), ("source_path", "ASC")), cursor=cursor, limit=limit)

    def query_job_history(self, *, status: str | None = None, story_slug: str | None = None, scene_slug: str | None = None, name: str | None = None, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("job_summaries", filters={"status": status, "story_slug": story_slug, "scene_slug": scene_slug, "name": name}, order=(("completed_at", "ASC"), ("job_id", "ASC"), ("source_path", "ASC")), cursor=cursor, limit=limit)

    def query_errors(self, *, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("index_errors", filters=None, order=(("source_path", "ASC"),), cursor=cursor, limit=limit)
