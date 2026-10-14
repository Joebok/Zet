"""Preview or deactivate one logical reference bound to an archived image."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.config_service import Config
from zet.services.entity_library_service import EntityLibraryService, EntityLibraryServiceError
from zet.services.path_service import PathService


def _backup_catalog(database_path: Path) -> Path:
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"catalog-before-reference-repair-{stamp}.sqlite3"
    source = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
        violations = destination.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or violations:
            raise RuntimeError("Catalog backup failed its integrity or foreign-key check.")
    finally:
        destination.close()
        source.close()
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-root", required=True, type=Path,
                        help="Explicit universe directory containing universe.json and catalog.sqlite3")
    parser.add_argument("--reference-key", required=True)
    parser.add_argument("--expected-asset-id", required=True)
    parser.add_argument("--apply", action="store_true", help="Back up and apply the deactivation")
    args = parser.parse_args()

    root = args.universe_root.expanduser().resolve()
    marker = root / "universe.json"
    database_path = root / "catalog.sqlite3"
    if not marker.is_file() or not database_path.is_file():
        parser.error("universe root must already contain universe.json and catalog.sqlite3")
    try:
        descriptor = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read universe descriptor: {exc}")
    if not descriptor.get("universe_id"):
        parser.error("universe descriptor has no universe_id")

    config = Config(base_library_path=str(root), base_character_path="", base_asset_path="",
                    base_pipeline_path="", base_ai_queue_path="")
    service = EntityLibraryService(PathService(config), EntityLibraryRepository(database_path))
    try:
        if not args.apply:
            print(json.dumps(service.deactivate_archived_reference(
                args.reference_key, args.expected_asset_id, dry_run=True), indent=2))
            return 0
        preview = service.deactivate_archived_reference(
            args.reference_key, args.expected_asset_id, dry_run=True)
        if preview["action"] == "already_inactive":
            preview["dry_run"] = False
            print(json.dumps(preview, indent=2))
            return 0
        backup = _backup_catalog(database_path)
        result = service.deactivate_archived_reference(
            args.reference_key, args.expected_asset_id, dry_run=False)
        result["backup_path"] = str(backup)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, sqlite3.DatabaseError, RuntimeError, EntityLibraryServiceError) as exc:
        parser.exit(1, f"repair failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
