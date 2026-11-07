"""Dry-run by default; reviewed import of current character Final locks."""
import argparse
import json
from pathlib import Path

from zet.services.atomic_file_service import write_json_atomic
from zet.services.character_container_migration_service import CharacterContainerMigrationService
from zet.services.character_container_migration_service import CharacterContainerMigrationError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library_root", type=Path, help="One universe's entity-library root")
    parser.add_argument("character_root", type=Path, help="Matching universe character folder")
    parser.add_argument("--universe-id", default="", help="Canonical selected universe ID (defaults to library folder name)")
    parser.add_argument("--report", type=Path, required=True, help="Write/read the dry-run report JSON")
    parser.add_argument("--apply", action="store_true", help="Apply this reviewed report")
    parser.add_argument("--backup-dir", type=Path, help="Verified backup directory containing files")
    parser.add_argument("--backup-verified", action="store_true", help="Confirm the backup was verified")
    parser.add_argument("--legacy-quiesced", action="store_true", help="Confirm legacy work is quiesced")
    parser.add_argument("--approved", action="store_true", help="Separate approval to apply this migration")
    args = parser.parse_args()
    service = CharacterContainerMigrationService(args.library_root, args.character_root, args.universe_id)
    try:
        if not args.apply:
            report = service.dry_run()
            write_json_atomic(args.report, report)
            counts = {"import": 0, "empty": 0}
            for item in report["decisions"]:
                counts[item["status"]] += 1
            print(json.dumps({"report": str(args.report.resolve()), "state_fingerprint": report["state_fingerprint"],
                              "views_to_import": counts["import"], "empty_views": counts["empty"],
                              "active_legacy_work": report["active_legacy_work"],
                              "skipped_records": sum(len(item["skipped"]) for item in report["decisions"])}, indent=2))
            return 0
        report = json.loads(args.report.read_text(encoding="utf-8"))
        result = service.apply(report, reviewed_report=args.report, backup_dir=args.backup_dir,
                               backup_verified=args.backup_verified, legacy_quiesced=args.legacy_quiesced,
                               approved=args.approved)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Character container migration stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
