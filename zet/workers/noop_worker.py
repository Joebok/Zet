from datetime import datetime

from zet.models.worker import WorkerResult


def run(asset, context) -> WorkerResult:
    context.pipeline_path.mkdir(parents=True, exist_ok=True)
    noop_path = context.pipeline_path / "_worker_noop.txt"
    history_path = context.pipeline_path / "_worker_history.log"
    head_view = asset.head_view if asset.head_view and asset.head_view.strip() else "_"

    noop_path.write_text(
        "No-op worker executed.\n\n"
        f"AssetID: {asset.asset_id}\n"
        f"Character: {asset.character}\n"
        f"Phase: {asset.phase}\n"
        f"Pipeline: {asset.pipeline}\n"
        f"BodyView: {asset.body_view}\n"
        f"HeadView: {head_view}\n"
        f"PipelineStage: {asset.pipeline_stage}\n"
        f"Actor: {asset.actor}\n",
        encoding="utf-8",
    )

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{timestamp} | Asset {asset.asset_id} | No-op worker executed at stage {asset.pipeline_stage}\n"
        )

    return WorkerResult(
        success=True,
        message="No-op worker executed.",
        output_files=[noop_path.name, history_path.name],
        advance_stage=True,
    )
