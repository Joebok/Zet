import argparse
import sys

from zet.app import ZetApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run housekeeping for a Zet asset")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        app = ZetApp.from_config(args.config)
        pipeline_path = app.asset(args.character, args.phase, args.asset_id).run_housekeeping()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Housekeeping complete for Asset {args.asset_id}:")
    print(f"  PipelinePath: {pipeline_path}")
    print("  Wrote: _stage.txt")
    print("  Appended: _history.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
