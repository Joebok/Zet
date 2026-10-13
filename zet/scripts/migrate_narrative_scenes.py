"""Offline migration: stop the dashboard before apply/resume."""
import argparse
import json

from zet.services.narrative_migration_service import NarrativeMigrationService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "dry-run", "apply", "resume", "verify"))
    for name in ("source", "destination", "legacy-library", "manifest", "universe"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    service = NarrativeMigrationService(args.source, args.destination, args.legacy_library, args.manifest, args.universe)
    result = service.apply() if args.mode in ("apply", "resume") else service.verify() if args.mode == "verify" else service.prepare()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
