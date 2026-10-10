"""Dry-run or migrate the configured library into the Moonsea universe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from zet.services.config_service import ConfigService
from zet.services.universe_migration_service import UniverseMigrationService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--mode", choices=("dry-run", "apply", "verify", "repair-paths", "rollback"), default="dry-run")
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()
    config = ConfigService.load(config_path)
    container = Path(config.base_library_path)
    if not container.is_absolute():
        container = config_path.parent / container
    service = UniverseMigrationService(container, config_path.parent / "Config" / "Moonsea-migration.json",
                                       config.base_ai_queue_path, config_path)
    result = {"dry-run": service.dry_run, "apply": service.apply,
              "verify": service.verify, "repair-paths": service.repair_paths, "rollback": service.rollback}[args.mode]()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") in {"ready", "already_migrated", "verified", "repaired", "rolled_back"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
