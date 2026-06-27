import argparse
import sys

from zet.app import ZetApp
from zet.services.state_machine import StateMachineError


def format_value(value):
    return "-" if value is None else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show pipeline details for a Zet asset")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        app = ZetApp.from_config(args.config)
        asset = app.asset(args.character, args.phase, args.asset_id).get()
        pipeline = app.pipeline_repository.get_pipeline(args.character, args.phase, asset.pipeline)
        try:
            next_stage = app.asset_service.state_machine.next_stage(pipeline, asset.pipeline_stage)
        except StateMachineError as exc:
            next_stage = str(exc)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Asset {asset.asset_id} pipeline details")
    print(f"  Character/Phase: {asset.character}/{asset.phase}")
    print(f"  Pipeline: {pipeline.name}")
    print(f"  CurrentStage: {asset.pipeline_stage}")
    print(f"  CurrentActor: {asset.actor}")
    print(f"  NextStage: {next_stage}")
    print()
    print("Stages")
    print("stage            | actor        | worker")
    print("-" * 72)
    for stage in pipeline.stages:
        actor = pipeline.actor_by_stage.get(stage, "-")
        worker = pipeline.worker_by_stage.get(stage, "-")
        marker = " <==" if stage == asset.pipeline_stage else ""
        print(f"{stage:<16} | {actor:<12} | {format_value(worker)}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
