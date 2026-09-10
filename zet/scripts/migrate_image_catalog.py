import argparse
import json

from zet.services.config_service import ConfigService
from zet.services.image_catalog_migration_service import ImageCatalogMigrationService
from zet.services.path_service import PathService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate the Zet image catalog to record-oriented schema v3.")
    parser.add_argument("--config", default="config.toml", help="Path to the Zet config.toml file.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing any files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ConfigService.load(args.config)
    paths = PathService(config)
    report = ImageCatalogMigrationService(paths).run(dry_run=args.dry_run)
    print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
