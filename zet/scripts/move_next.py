import argparse
import sys

from zet.app import ZetApp


def format_value(value):
    return "None" if value is None else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Move a Zet asset to the next stage")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        app = ZetApp.from_config(args.config)
        asset_ref = app.asset(args.character, args.phase, args.asset_id)
        before = asset_ref.get()
        after = asset_ref.move_next()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Asset {after.asset_id} moved:")
    print(f"  Pipeline: {after.pipeline}")
    print(f"  Stage: {before.pipeline_stage} -> {after.pipeline_stage}")
    print(f"  Actor: {before.actor} -> {after.actor}")
    print(f"  AssetState: {before.asset_state} -> {after.asset_state}")
    print(f"  AI_State: {format_value(before.ai_state)} -> {format_value(after.ai_state)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
