"""Inspect retained answers without constructing ZetApp or changing live state."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from zet.services.ai_job_recovery_service import AIJobRecoveryService
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.config_service import ConfigService
from zet.services.universe_service import UniverseService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--universe", default="Moonsea")
    parser.add_argument("--queue-root", help="Explicit queue root for read-only inspection without loading a runtime config")
    parser.add_argument("--library-root", help="Explicit universe library root; requires --queue-root")
    args = parser.parse_args()
    if args.queue_root or args.library_root:
        if not args.queue_root or not args.library_root:
            parser.error("--queue-root and --library-root must be supplied together")
        config = SimpleNamespace(base_ai_queue_path=args.queue_root, base_library_path=args.library_root, universe_id=args.universe)
    else:
        config = ConfigService.load(args.config)
        universes = UniverseService(config.base_library_path, Path(args.config).parent / "unused-selection.json")
        config = universes.bind_config(config, args.universe)
    print(json.dumps(AIJobRecoveryService(AIProxyPathService(config)).report(), indent=2))


if __name__ == "__main__":
    main()
