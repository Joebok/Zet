"""Dry-run or apply the backed-up local character gate data retirement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from zet.services.local_gate_retirement_service import LocalGateRetirementService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-root", required=True, type=Path)
    parser.add_argument("--queue-root", type=Path, help="Shared File Proxy queue to inventory/retire owned gate jobs")
    parser.add_argument("--apply", action="store_true", help="Back up and rewrite candidate pipeline records.")
    parser.add_argument("--backup-root", type=Path)
    args = parser.parse_args()
    service = LocalGateRetirementService(args.library_root, args.queue_root)
    if args.apply:
        if not args.backup_root:
            parser.error("--apply requires --backup-root outside the library root")
        report = service.apply(args.backup_root)
    else:
        report = service.inventory()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 2 if report.get("apply_blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
