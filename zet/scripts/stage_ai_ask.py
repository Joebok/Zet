import argparse
import sys

from zet.app import ZetApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage a Zet AI ask for an asset")
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
        ask_path = asset_ref.stage_ai_ask()
        asset = asset_ref.get()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"AI ask staged for Asset {asset.asset_id}:")
    print(f"  Pipeline: {asset.pipeline}")
    print(f"  Stage: {asset.pipeline_stage}")
    print(f"  AskPath: {ask_path}")
    print(f"  AI_State: {asset.ai_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
