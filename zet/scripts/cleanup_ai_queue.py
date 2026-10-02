"""Report legacy shared AI queue payloads without deleting them."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from zet.app import ZetApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report obsolete AI queue payloads without deleting files.")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config.toml"))
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--report", type=Path, help="Write the complete candidate list as JSON to this local file.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    app = ZetApp.from_config(args.config, validate_catalog=False)
    report = app.cleanup_ai_queue()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    totals = defaultdict(lambda: {"candidates": 0, "files": 0, "bytes": 0})
    for item in report["candidates"]:
        group = totals[item["reason"]]
        group["candidates"] += 1
        group["files"] += item["files"]
        group["bytes"] += item["bytes"]
    print(json.dumps({
        "dry_run": True,
        "candidate_count": report["candidate_count"],
        "files": report["files"],
        "bytes": report["bytes"],
        "by_reason": totals,
        "unresolved": report["unresolved"],
        "full_report": str(args.report.resolve()) if args.report else "Pass --report <local-path> for every candidate.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
