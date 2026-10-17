"""Inspect and safely bound machine-local Zet storage."""
from __future__ import annotations

import argparse
import json

from zet.services.config_service import ConfigService
from zet.services.storage_maintenance_service import StorageMaintenanceService
from zet.services.storage_path_service import StoragePathService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and manage machine-local Zet storage.")
    parser.add_argument("--config", default="config.toml", help="Path to Zet config.toml.")
    parser.add_argument("--apply", action="store_true", help="Apply safe completed-state retention cleanup.")
    parser.add_argument("--cutover-preview", action="store_true", help="List operational files proposed for migration; never copies or deletes.")
    parser.add_argument("--migrate-from", metavar="MANIFEST", help="Copy operational state from a complete preview and verify every checksum; sources remain untouched.")
    parser.add_argument("--confirm-offline", action="store_true", help="Assert Zet, collectors and relevant workers are stopped (required for migration).")
    parser.add_argument("--include-archive", action="store_true", help="Include the configured external harvest archive in the report.")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild the configured universe's disposable index now.")
    parser.add_argument("--universe", help="Rebuild this universe (only with --rebuild-index).")
    parser.add_argument("--all-universes", action="store_true", help="Rebuild every discovered universe (only with --rebuild-index).")
    parser.add_argument("--verify-indexes", action="store_true", help="Run read-only SQLite integrity checks on configured indexes.")
    parser.add_argument("--compact-indexes", action="store_true", help="Run SQLite integrity checks and VACUUM configured indexes now.")
    parser.add_argument("--json", action="store_true", help="Emit compact JSON instead of indented JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    selected = sum((args.apply, args.cutover_preview, bool(args.migrate_from), args.rebuild_index,
                    args.verify_indexes, args.compact_indexes))
    if selected > 1:
        parser.error("Choose only one storage operation.")
    if (args.universe or args.all_universes) and not args.rebuild_index:
        parser.error("--universe and --all-universes require --rebuild-index.")
    if args.universe and args.all_universes:
        parser.error("Choose either --universe or --all-universes.")
    if args.migrate_from and not args.confirm_offline:
        parser.error("--migrate-from requires --confirm-offline after every Zet writer has stopped.")
    if args.confirm_offline and not args.migrate_from:
        parser.error("--confirm-offline applies only to --migrate-from.")

    config = ConfigService.load(args.config)
    service = StorageMaintenanceService(config)
    if args.cutover_preview:
        report = service.preview_cutover(include_archive=args.include_archive)
    elif args.migrate_from:
        report = service.migrate_from_manifest(args.migrate_from)
    elif args.apply:
        paths = StoragePathService(config)
        state_root = paths.ensure_available("queue_state")
        from zet.services.workflow_storage import file_lock
        with file_lock(state_root / "Locks" / "coordinator.lock", timeout=0):
            report = service.maintain(apply=True)
    elif args.rebuild_index:
        from zet.scripts.rebuild_library_index import rebuild_indexes
        report = {"universes": rebuild_indexes(config, args.config, universe_id=args.universe,
                                                 all_universes=args.all_universes)}
    elif args.verify_indexes:
        index_root = StoragePathService(config).indexes
        databases = sorted(path for path in index_root.glob("*.sqlite3") if path.is_file()) if index_root.is_dir() else []
        report = {"path": str(index_root), "databases": [StorageMaintenanceService.verify_database(path)
                                                           for path in databases]}
    elif args.compact_indexes:
        index_root = StoragePathService(config).indexes
        databases = sorted(path for path in index_root.glob("*.sqlite3") if path.is_file()) if index_root.is_dir() else []
        report = {"path": str(index_root), "databases": []}
        for database in databases:
            report["databases"].append(StorageMaintenanceService.compact_database(database))
    else:
        report = service.report(include_archive=args.include_archive)

    print(json.dumps(report, indent=None if args.json else 2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
