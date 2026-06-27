from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.services.path_service import PathService


class HousekeepingService:
    def __init__(self, path_service: PathService):
        self.path_service = path_service

    def prepare_stage(self, asset: Asset) -> Path:
        pipeline_path = self.path_service.pipeline_path(asset)
        pipeline_path.mkdir(parents=True, exist_ok=True)

        stage_path = pipeline_path / "_stage.txt"
        history_path = pipeline_path / "_history.log"

        stage_path.write_text(self._stage_contents(asset), encoding="utf-8")

        history_entry = self._history_entry(asset)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(history_entry)

        return pipeline_path

    def _stage_contents(self, asset: Asset) -> str:
        head_view = asset.head_view if asset.head_view and asset.head_view.strip() else "_"
        ai_state = "None" if asset.ai_state is None else asset.ai_state
        updated_at = "None" if asset.updated_at is None else asset.updated_at
        return (
            f"AssetID: {asset.asset_id}\n"
            f"Character: {asset.character}\n"
            f"Phase: {asset.phase}\n"
            f"Pipeline: {asset.pipeline}\n"
            f"BodyView: {asset.body_view}\n"
            f"HeadView: {head_view}\n"
            f"PipelineStage: {asset.pipeline_stage}\n"
            f"Actor: {asset.actor}\n"
            f"AssetState: {asset.asset_state}\n"
            f"AI_State: {ai_state}\n"
            f"UpdatedAt: {updated_at}\n"
        )

    def _history_entry(self, asset: Asset) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        ai_state = "None" if asset.ai_state is None else asset.ai_state
        return (
            f"{timestamp} | Asset {asset.asset_id} | Stage={asset.pipeline_stage} | "
            f"Actor={asset.actor} | AssetState={asset.asset_state} | AI_State={ai_state}\n"
        )
