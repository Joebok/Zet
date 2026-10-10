"""Classify locked costume images and update matching scene references."""
import argparse
import json

from zet.app import ZetApp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--universe", default=None)
    parser.add_argument("--apply", action="store_true", help="Write the classifications and scene updates.")
    args = parser.parse_args(argv)
    app = ZetApp.from_config(args.config, universe_id=args.universe)
    print(json.dumps(app.entity_library_backfill_costume_references(dry_run=not args.apply), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
