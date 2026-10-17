import argparse
import sys
import time
from datetime import datetime

from zet.app import ZetApp
from zet.services.config_service import ConfigService


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Continuously harvest Zet AI proxy answer folders.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--interval-seconds", type=int, default=None, help="Override AIHarvest.IntervalSeconds")
    parser.add_argument("--once", action="store_true", help="Harvest once and exit")
    parser.add_argument("--debug", action="store_true", help="Keep completed queue payloads locally for recovery.")
    return parser


def configured_interval(config_path: str, override: int | None) -> int:
    if override is not None:
        return max(0, override)
    config = ConfigService.load(config_path)
    if not config.ai_harvest_auto_enabled:
        return 0
    return max(0, int(config.ai_harvest_interval_seconds))


def harvest_once(config_path: str, coordinator=None) -> int:
    app = ZetApp.from_config(config_path) if coordinator is None else coordinator.app
    from zet.services.ai_job_coordinator import AIJobCoordinator
    results = (coordinator or AIJobCoordinator(app)).sweep()
    print(f"{timestamp()} Collected {len(results)} AI result(s).", flush=True)
    for result in results:
        print(f"  {result.get('status', '')} | {result.get('ask_id', '')}", flush=True)
    return len(results)


def main() -> int:
    args = build_parser().parse_args()
    import os
    from pathlib import Path
    os.environ["ZET_CONFIG_PATH"] = str(Path(args.config).resolve())
    if args.debug:
        import os
        os.environ["ZET_AI_QUEUE_DEBUG"] = "1"

    if args.once:
        try:
            harvest_once(args.config)
            return 0
        except Exception as exc:
            print(f"{timestamp()} Error: {exc}", file=sys.stderr, flush=True)
            return 1

    interval = configured_interval(args.config, args.interval_seconds)
    if interval <= 0:
        print(f"{timestamp()} Auto harvest is disabled or has a non-positive interval.", flush=True)
        return 0

    print(f"{timestamp()} Auto harvest worker running every {interval} seconds.", flush=True)
    from zet.services.ai_job_coordinator import AIJobCoordinator
    coordinator = None
    while True:
        try:
            from zet.services.storage_health_service import storage_health
            health = storage_health(ConfigService.load(args.config))
            if not health.poll()["available"]:
                time.sleep(2)
                continue
            if coordinator is None:
                coordinator = AIJobCoordinator(ZetApp.from_config(args.config))
            harvest_once(args.config, coordinator)
            interval = configured_interval(args.config, args.interval_seconds)
            if interval <= 0:
                print(f"{timestamp()} Auto harvest disabled by config. Exiting.", flush=True)
                return 0
        except Exception as exc:
            print(f"{timestamp()} Error: {exc}", file=sys.stderr, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
