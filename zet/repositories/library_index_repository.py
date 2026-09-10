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
    list_items: Sequence[Mapping] = field(default_factory=tuple)


@dataclass(frozen=True)
class IndexPage:
    items: list[dict]
    next_cursor: str | None
    total: int = 0
    generation: int | None = None
    freshness: dict = field(default_factory=dict)


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
                source_path TEXT NOT NULL, fingerprint TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}',
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
            CREATE TABLE IF NOT EXISTS indexed_list_items (
                generation INTEGER NOT NULL, list_kind TEXT NOT NULL, item_key TEXT NOT NULL,
                sort_key TEXT NOT NULL, character_name TEXT NOT NULL DEFAULT '',
                phase TEXT NOT NULL DEFAULT '', story_slug TEXT NOT NULL DEFAULT '',
                scene_slug TEXT NOT NULL DEFAULT '', source_key TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '', source_type TEXT NOT NULL DEFAULT '',
                semantic_category TEXT NOT NULL DEFAULT '', costume TEXT NOT NULL DEFAULT '',
                pipeline TEXT NOT NULL DEFAULT '', subscene_id TEXT NOT NULL DEFAULT '',
                collections_text TEXT NOT NULL DEFAULT '', keywords_text TEXT NOT NULL DEFAULT '',
                search_text TEXT NOT NULL DEFAULT '', is_base INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (generation, list_kind, item_key)
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
            CREATE INDEX IF NOT EXISTS indexed_list_query ON indexed_list_items(
                generation, list_kind, character_name, phase, story_slug, scene_slug, source_key, status, sort_key, item_key
            );
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
        indexed_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(indexed_list_items)")
        }
        for column, declaration in {
            "source_type": "TEXT NOT NULL DEFAULT ''",
            "semantic_category": "TEXT NOT NULL DEFAULT ''",
            "costume": "TEXT NOT NULL DEFAULT ''",
            "pipeline": "TEXT NOT NULL DEFAULT ''",
            "subscene_id": "TEXT NOT NULL DEFAULT ''",
            "collections_text": "TEXT NOT NULL DEFAULT ''",
            "keywords_text": "TEXT NOT NULL DEFAULT ''",
            "search_text": "TEXT NOT NULL DEFAULT ''",
            "is_base": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if column not in indexed_columns:
                connection.execute(f"ALTER TABLE indexed_list_items ADD COLUMN {column} {declaration}")
        job_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(job_summaries)")}
        if "payload_json" not in job_columns:
            connection.execute(
                "ALTER TABLE job_summaries ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}'"
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
            "indexed_list_items": snapshot.list_items,
        }

        def operation(connection: sqlite3.Connection) -> None:
            row = connection.execute(
                "SELECT status FROM generations WHERE generation = ?", (generation,)
            ).fetchone()
            if not row or row[0] != "building":
                raise LibraryIndexError(f"Generation {generation} is not available for publication.")
            try:
                connection.execute("BEGIN IMMEDIATE")
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
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            if before_activate is not None:
                before_activate()
            try:
                connection.execute("BEGIN IMMEDIATE")
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

    def _snapshot_token(self, connection: sqlite3.Connection, generation: int) -> str:
        return f"{generation}:{self._metadata(connection, 'index_revision') or '0'}"

    def _page(
        self,
        table: str,
        *,
        filters: Mapping[str, object] | None,
        order: Sequence[tuple[str, str]],
        cursor: str | None,
        limit: int,
        extra_clauses: Sequence[str] = (),
        extra_params: Sequence[object] = (),
    ) -> IndexPage:
        if limit < 1 or limit > 500:
            raise LibraryIndexError("Index page limit must be between 1 and 500.")

        def operation(connection: sqlite3.Connection) -> IndexPage:
            generation = self._active_generation(connection)
            if generation is None:
                return IndexPage([], None, 0, None, self._freshness(connection, None))
            clauses = ["generation = ?"]
            params: list[object] = [generation]
            for column, value in (filters or {}).items():
                if value is not None:
                    clauses.append(f"{column} = ?")
                    params.append(value)
            clauses.extend(extra_clauses)
            params.extend(extra_params)
            count_clauses = list(clauses)
            count_params = list(params)
            decoded = self._decode_cursor(cursor, len(order) + 1)
            cursor_values = None
            if decoded is not None:
                cursor_generation, *cursor_values = decoded
                if cursor_generation != self._snapshot_token(connection, generation):
                    raise LibraryIndexError(
                        "The index changed while paging; discard the stale cursor and reload the first page."
                    )
            if cursor_values is not None:
                terms = []
                for index, (column, direction) in enumerate(order):
                    equal = " AND ".join(f"{prior[0]} = ?" for prior in order[:index])
                    comparison = f"{column} {'<' if direction.upper() == 'DESC' else '>'} ?"
                    terms.append(f"({equal + ' AND ' if equal else ''}{comparison})")
                    params.extend(cursor_values[:index])
                    params.append(cursor_values[index])
                clauses.append("(" + " OR ".join(terms) + ")")
            order_sql = ", ".join(f"{column} {direction}" for column, direction in order)
            total = int(connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {' AND '.join(count_clauses)}",
                tuple(count_params),
            ).fetchone()[0])
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY {order_sql} LIMIT ?",
                (*params, limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            items = [{key: row[key] for key in row.keys() if key != "generation"} for row in rows]
            next_cursor = None
            if has_more and rows:
                next_cursor = self._encode_cursor(
                    [self._snapshot_token(connection, generation), *[rows[-1][column] for column, _ in order]]
                )
            return IndexPage(
                items, next_cursor, total, generation, self._freshness(connection, generation)
            )

        return self._run(operation)

    def _freshness(self, connection: sqlite3.Connection, generation: int | None) -> dict:
        errors = []
        if generation is not None:
            errors = [
                {"source_path": str(row[0]), "message": str(row[1])}
                for row in connection.execute(
                    "SELECT source_path, message FROM index_errors WHERE generation = ? "
                    "ORDER BY source_path LIMIT 20",
                    (generation,),
                )
            ]
        return {
            "state": "ready" if generation is not None else "building",
            "last_completed_at": self._metadata(connection, "reconciliation_last_completed_at"),
            "errors": errors,
        }

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

    def query_job_history(self, *, status: str | None = None, story_slug: str | None = None, scene_slug: str | None = None, name: str | None = None, harvested_only: bool = False, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page(
            "job_summaries",
            filters={"status": status, "story_slug": story_slug, "scene_slug": scene_slug, "name": name},
            order=(("completed_at", "DESC"), ("job_id", "DESC"), ("source_path", "DESC")),
            cursor=cursor,
            limit=limit,
            extra_clauses=("payload_json <> '{}'",) if harvested_only else (),
        )

    def query_errors(self, *, cursor: str | None = None, limit: int = 100) -> IndexPage:
        return self._page("index_errors", filters=None, order=(("source_path", "ASC"),), cursor=cursor, limit=limit)

    def query_indexed_list(
        self,
        list_kind: str,
        *,
        character: str | None = None,
        phase: str | None = None,
        story_slug: str | None = None,
        scene_slug: str | None = None,
        source_key: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
        semantic_category: str | None = None,
        costume: str | None = None,
        pipeline: str | None = None,
        subscene_id: str | None = None,
        collection: str | None = None,
        keyword: str | None = None,
        q: str | None = None,
        include_base: bool = True,
        cursor: str | None = None,
        limit: int = 50,
    ) -> IndexPage:
        if limit < 1 or limit > 200:
            raise LibraryIndexError("Indexed list page limit must be between 1 and 200.")
        page = self._page(
            "indexed_list_items",
            filters={
                "list_kind": list_kind,
                "character_name": character,
                "phase": phase,
                "story_slug": story_slug,
                "scene_slug": scene_slug,
                "source_key": source_key,
                "status": status,
                "source_type": source_type,
                "semantic_category": semantic_category,
                "costume": costume,
                "pipeline": pipeline,
                "subscene_id": subscene_id,
            },
            order=(("sort_key", "ASC"), ("item_key", "ASC")),
            cursor=cursor,
            limit=limit,
            extra_clauses=tuple(
                (["collections_text LIKE ?"] if collection else [])
                + (["keywords_text LIKE ?"] if keyword else [])
                + (["is_base = 0"] if not include_base else [])
                + ["search_text LIKE ?" for _ in str(q or "").split()]
            ),
            extra_params=tuple(
                ([f"%|{collection}|%"] if collection else [])
                + ([f"%|{keyword}|%"] if keyword else [])
                + [f"%{term.casefold()}%" for term in str(q or "").split()]
            ),
        )
        return IndexPage(
            [json.loads(str(item["payload_json"])) for item in page.items],
            page.next_cursor,
            page.total,
            page.generation,
            page.freshness,
        )

    def indexed_list_counts(self, scopes: Mapping[str, Mapping[str, object]]) -> tuple[int | None, dict[str, int], dict]:
        """Count several list scopes against one active-generation transaction."""
        allowed = {
            "list_kind", "character_name", "phase", "story_slug", "scene_slug", "source_key", "status"
        }

        def operation(connection: sqlite3.Connection):
            generation = self._active_generation(connection)
            if generation is None:
                return None, {name: 0 for name in scopes}, self._freshness(connection, None)
            counts = {}
            for name, filters in scopes.items():
                clauses = ["generation = ?"]
                params: list[object] = [generation]
                for column, value in filters.items():
                    if column not in allowed:
                        raise LibraryIndexError(f"Unsupported indexed count field: {column}")
                    if value is not None:
                        clauses.append(f"{column} = ?")
                        params.append(value)
                counts[name] = int(connection.execute(
                    f"SELECT COUNT(*) FROM indexed_list_items WHERE {' AND '.join(clauses)}",
                    tuple(params),
                ).fetchone()[0])
            return generation, counts, self._freshness(connection, generation)

        return self._run(operation)

    def upsert_job_history(self, rows: Sequence[Mapping], *, cursor: str, complete: bool) -> None:
        """Persist one explicit history-backfill batch into the active generation."""
        def operation(connection: sqlite3.Connection) -> None:
            generation = self._active_generation(connection)
            if generation is None:
                raise LibraryIndexError("Build the library index before backfilling history.")
            connection.executemany(
                "INSERT OR REPLACE INTO job_summaries "
                "(generation, job_id, scope_kind, story_slug, scene_slug, render_target_id, "
                "status, name, completed_at, source_path, fingerprint, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        generation,
                        row["job_id"], row["scope_kind"], row["story_slug"], row["scene_slug"],
                        row["render_target_id"], row["status"], row["name"], row["completed_at"],
                        row["source_path"], row["fingerprint"], str(row.get("payload_json") or "{}"),
                    )
                    for row in rows
                ],
            )
            connection.executemany(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (
                    ("history_backfill_cursor", cursor),
                    ("history_backfill_complete", "1" if complete else "0"),
                ),
            )
            revision = int(self._metadata(connection, "index_revision") or "0") + 1
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES ('index_revision', ?)",
                (str(revision),),
            )
            connection.commit()

        self._run(operation)

    def history_backfill_status(self) -> dict:
        def operation(connection: sqlite3.Connection) -> dict:
            return {
                "cursor": self._metadata(connection, "history_backfill_cursor") or "",
                "complete": self._metadata(connection, "history_backfill_complete") == "1",
            }

        return dict(self._run(operation))
