import argparse
import sys

from zet.app import ZetApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harvest Zet AI proxy answer folders")
    parser.add_argument("--config", default="config.toml")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        app = ZetApp.from_config(args.config)
        results = app.harvest_ai_answers()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("No AI answer folders found.")
        return 0

    print("Harvested AI answer folders:")
    for result in results:
        asset_label = "unknown" if result.asset_id is None else result.asset_id
        print(f"  Asset {asset_label} | {result.status} | {result.ask_id}")
        print(f"    {result.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
