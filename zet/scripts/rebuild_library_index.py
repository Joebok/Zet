import argparse
import json

from zet.services.config_service import ConfigService
from zet.services.library_index_service import LibraryIndexService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the machine-local Zet library index.")
    parser.add_argument("--config", default="config.toml", help="Path to the Zet config.toml file.")
    parser.add_argument("--index-root", help="Override the machine-local index directory (primarily for tests).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ConfigService.load(args.config)
    report = LibraryIndexService(config, index_root=args.index_root).rebuild()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
