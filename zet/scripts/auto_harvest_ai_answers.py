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
    return parser


def configured_interval(config_path: str, override: int | None) -> int:
    if override is not None:
        return max(0, override)
    config = ConfigService.load(config_path)
    if not config.ai_harvest_auto_enabled:
        return 0
    return max(0, int(config.ai_harvest_interval_seconds))


def harvest_once(config_path: str) -> int:
    app = ZetApp.from_config(config_path)
    results = app.harvest_ai_answers()
    if not results:
        print(f"{timestamp()} No AI answer folders found.", flush=True)
        return 0

    print(f"{timestamp()} Harvested {len(results)} AI answer folder(s):", flush=True)
    for result in results:
        asset_label = "unknown" if result.asset_id is None else result.asset_id
        print(f"  Asset {asset_label} | {result.status} | {result.ask_id}", flush=True)
        print(f"    {result.message}", flush=True)
    return len(results)


def active_prompt_evolution_runs(config_path: str) -> bool:
    app = ZetApp.from_config(config_path)
    terminal = {"COMPLETE", "ABORTED", "FAILED", "AWAITING_USER"}
    return any(run.get("status") not in terminal for run in app.list_prompt_evolution_runs())


def main() -> int:
    args = build_parser().parse_args()

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
    while True:
        try:
            harvest_once(args.config)
            interval = configured_interval(args.config, args.interval_seconds)
            if interval <= 0:
                print(f"{timestamp()} Auto harvest disabled by config. Exiting.", flush=True)
                return 0
        except Exception as exc:
            print(f"{timestamp()} Error: {exc}", file=sys.stderr, flush=True)
        time.sleep(min(interval, 5) if active_prompt_evolution_runs(args.config) else interval)


if __name__ == "__main__":
    raise SystemExit(main())
