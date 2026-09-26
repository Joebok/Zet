import argparse
import sys
from pathlib import Path

from zet.app import ZetApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive harvested Zet AI proxy answer folders.")
    default_config = Path(__file__).resolve().parents[2] / "config.toml"
    parser.add_argument("--config", default=str(default_config))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        app = ZetApp.from_config(args.config, validate_catalog=False)
        result = app.archive_harvested_answers()
    except Exception as exc:
        print(f"Error archiving harvested AI answers: {exc}", file=sys.stderr)
        return 1

    print(
        f"Archived {result['moved_count']} harvested answer folder(s); "
        f"skipped {result['skipped_count']} unharvested folder(s)."
    )
    for item in result["moved"]:
        print(f"  {item['name']} -> {item['archived_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
