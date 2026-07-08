import argparse
from dataclasses import fields

from zet.app import ZetApp


def format_value(value):
    return "-" if value is None else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a Zet asset")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = ZetApp.from_config(args.config)
    asset_ref = app.asset(args.character, args.phase, args.asset_id)
    asset = asset_ref.get()
    print(f"Asset {asset.asset_id} for {asset.character}/{asset.phase}")
    print("Fields")
    print("-" * 40)
    for field in fields(asset):
        field_name = field.name
        value = getattr(asset, field_name)
        print(f"{field_name:<18}: {format_value(value)}")
    print()
    print("Paths")
    print("-" * 40)
    print(f"{'PipelinePath':<18}: {asset_ref.pipeline_path()}")
    print(f"{'CandidateImagePath':<18}: {asset_ref.candidate_image_path()}")
    print(f"{'LockedImagePath':<18}: {asset_ref.locked_image_path()}")


if __name__ == "__main__":
    main()
