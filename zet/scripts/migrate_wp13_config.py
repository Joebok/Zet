from __future__ import annotations

import argparse

from zet.services.config_service import ConfigService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Split the legacy Prompt Evolution model assignment into WP13 vision and text roles."
    )
    parser.add_argument("--config", default="config.toml", help="Path to the Zet config.toml file.")
    args = parser.parse_args(argv)
    backup = ConfigService.migrate_prompt_evolution_roles(args.config)
    if backup is None:
        print("Config already uses the WP13 Prompt Evolution role contract.")
    else:
        print(f"Migrated Prompt Evolution roles. Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
