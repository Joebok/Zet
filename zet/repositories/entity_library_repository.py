from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


class EntityLibraryRepositoryError(Exception):
    """Report an entity-library database error."""


class EntityLibraryRepository:
    """Store the authoritative entity-centered image catalog in SQLite."""

    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path).resolve()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.database_path.is_file()
        connection = self._connect()
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > self.SCHEMA_VERSION:
                raise EntityLibraryRepositoryError(
                    f"Image library database version {version} is newer than supported version {self.SCHEMA_VERSION}."
                )
            if existed and version < self.SCHEMA_VERSION:
                backup_dir = self.database_path.parent / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                shutil.copy2(self.database_path, backup_dir / f"catalog-v{version}-{stamp}.sqlite3")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY, name TEXT NOT NULL, entity_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS entity_name_type ON entities(lower(name), entity_type);
                CREATE TABLE IF NOT EXISTS variants (
                    variant_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
                    name TEXT NOT NULL, variant_type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(entity_id, name, variant_type)
                );
                CREATE TABLE IF NOT EXISTS entity_relations (
                    source_entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
                    target_entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
                    relation_type TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(source_entity_id, target_entity_id, relation_type),
                    CHECK(source_entity_id <> target_entity_id)
                );
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT '', checksum TEXT NOT NULL, file_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL, width INTEGER, height INTEGER, origin TEXT NOT NULL,
                    origin_key TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'approved', rating INTEGER,
                    notes TEXT NOT NULL DEFAULT '', derived_from_asset_id TEXT REFERENCES assets(asset_id),
                    replacement_for_asset_id TEXT REFERENCES assets(asset_id), created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS asset_checksum ON assets(checksum);
                CREATE INDEX IF NOT EXISTS asset_status ON assets(status, origin);
                CREATE TABLE IF NOT EXISTS asset_entities (
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
                    variant_id TEXT REFERENCES variants(variant_id) ON DELETE SET NULL,
                    role TEXT NOT NULL, PRIMARY KEY(asset_id, entity_id, role, variant_id)
                );
                CREATE TABLE IF NOT EXISTS reference_sets (
                    set_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, set_type TEXT NOT NULL DEFAULT 'general',
                    description TEXT NOT NULL DEFAULT '', entity_id TEXT REFERENCES entities(entity_id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reference_set_assets (
                    set_id TEXT NOT NULL REFERENCES reference_sets(set_id) ON DELETE CASCADE,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    role TEXT NOT NULL DEFAULT 'member', sort_order INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(set_id, asset_id)
                );
                CREATE TABLE IF NOT EXISTS descriptors (
                    descriptor_id TEXT PRIMARY KEY, owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL, descriptor_type TEXT NOT NULL, text TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS descriptor_owner ON descriptors(owner_type, owner_id, descriptor_type);
                CREATE TABLE IF NOT EXISTS facets (
                    facet_id TEXT PRIMARY KEY, namespace TEXT NOT NULL, value TEXT NOT NULL,
                    controlled INTEGER NOT NULL DEFAULT 1, UNIQUE(namespace, value)
                );
                CREATE TABLE IF NOT EXISTS asset_facets (
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    facet_id TEXT NOT NULL REFERENCES facets(facet_id) ON DELETE CASCADE,
                    PRIMARY KEY(asset_id, facet_id)
                );
                CREATE TABLE IF NOT EXISTS asset_tags (
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    tag TEXT NOT NULL, PRIMARY KEY(asset_id, tag)
                );
                CREATE TABLE IF NOT EXISTS logical_references (
                    reference_key TEXT PRIMARY KEY, label TEXT NOT NULL,
                    asset_id TEXT REFERENCES assets(asset_id) ON DELETE SET NULL,
                    set_id TEXT REFERENCES reference_sets(set_id) ON DELETE SET NULL,
                    status TEXT NOT NULL DEFAULT 'active', updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS legacy_image_references (
                    reference_tag TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_usages (
                    usage_id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets(asset_id) ON DELETE SET NULL,
                    reference_key TEXT REFERENCES logical_references(reference_key) ON DELETE SET NULL,
                    consumer_type TEXT NOT NULL, consumer_id TEXT NOT NULL, locator TEXT NOT NULL,
                    last_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'current',
                    CHECK(asset_id IS NOT NULL OR reference_key IS NOT NULL)
                );
                CREATE INDEX IF NOT EXISTS usage_asset ON asset_usages(asset_id, status);
                CREATE INDEX IF NOT EXISTS usage_reference ON asset_usages(reference_key, status);
                CREATE TABLE IF NOT EXISTS provenance (
                    provenance_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    relation_type TEXT NOT NULL, source_asset_id TEXT REFERENCES assets(asset_id),
                    details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
                );
                PRAGMA user_version = 1;
                """
            )
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise EntityLibraryRepositoryError(f"Image library integrity check failed: {result}")
        except sqlite3.DatabaseError as exc:
            raise EntityLibraryRepositoryError(f"Image library database is unreadable: {exc}") from exc
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def fetchall(self, sql: str, parameters: tuple = ()) -> list[dict]:
        connection = self._connect()
        try:
            return [dict(row) for row in connection.execute(sql, parameters).fetchall()]
        finally:
            connection.close()

    def fetchone(self, sql: str, parameters: tuple = ()) -> dict | None:
        connection = self._connect()
        try:
            row = connection.execute(sql, parameters).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()
