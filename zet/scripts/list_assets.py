import argparse

from zet.app import ZetApp


def format_value(value):
    return "-" if value is None else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List Zet assets")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = ZetApp.from_config(args.config)
    assets = app.list_assets(args.character, args.phase)
    print(f"Assets for {args.character}/{args.phase}")
    print("asset_id | pipeline           | body_view          | head_view | asset_state | pipeline_stage | actor")
    print("-" * 90)
    for asset in assets:
        print(
            f"{asset.asset_id:<8} | "
            f"{asset.pipeline:<18} | "
            f"{asset.body_view:<18} | "
            f"{format_value(asset.head_view):<9} | "
            f"{asset.asset_state:<11} | "
            f"{asset.pipeline_stage:<14} | "
            f"{asset.actor}"
        )


if __name__ == "__main__":
    main()
