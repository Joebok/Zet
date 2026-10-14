"""Apply and verify conversion of saved library paths to universe-relative form."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from zet.services.library_reference_migration_service import (
    LibraryReferenceMigrationError, LibraryReferenceMigrationService,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Zet config used to select the library container and AI queue.")
    parser.add_argument("--old-library-root", type=Path, action="append", default=[],
                        help="Former library container whose absolute paths should be relocated; repeat as needed.")
    parser.add_argument("--route-root", type=Path, action="append", default=[],
                        help="Additional producer-local route folder to update; repeat as needed.")
    args = parser.parse_args()
    try:
        service = LibraryReferenceMigrationService(args.config, old_library_roots=tuple(args.old_library_root),
                                                    route_roots=tuple(args.route_root))
        report = service.apply()
    except (LibraryReferenceMigrationError, OSError, ValueError) as exc:
        print(f"Library reference update failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
