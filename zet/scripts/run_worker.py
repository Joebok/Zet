import argparse
import sys

from zet.app import ZetApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the current Zet worker for an asset")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        app = ZetApp.from_config(args.config)
        asset_ref = app.asset(args.character, args.phase, args.asset_id)
        before = asset_ref.get()
        after = asset_ref.run_current_worker()
        worker_name = app.asset_service.worker_service.last_worker_module_name or "unknown"
        result = app.asset_service.worker_service.last_worker_result
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Worker executed for Asset {after.asset_id}:")
    print(f"  Pipeline: {after.pipeline}")
    print(f"  Worker: {worker_name}")
    print(f"  Stage: {before.pipeline_stage} -> {after.pipeline_stage}")
    print(f"  Actor: {before.actor} -> {after.actor}")
    print(f"  AssetState: {before.asset_state} -> {after.asset_state}")
    if result is not None:
        print(f"  Result: {'success' if result.success else 'failure'}")
        print(f"  Message: {result.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
