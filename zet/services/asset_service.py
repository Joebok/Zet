from dataclasses import replace
from datetime import datetime

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.housekeeping_service import HousekeepingService
from zet.services.state_machine import StateMachine

VALID_ACTORS = {"PYTHON", "AI_AGENT", "HUMAN_AGENT"}


class AssetServiceError(Exception):
    pass


class AssetService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        state_machine: StateMachine,
        housekeeping_service: HousekeepingService,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.state_machine = state_machine
        self.housekeeping_service = housekeeping_service

    def move_next(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage == "ERROR":
            raise AssetServiceError(f"Asset {asset_id} is in ERROR stage and cannot move next")

        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        next_stage = self.state_machine.next_stage(pipeline, asset.pipeline_stage)

        next_actor = pipeline.actor_by_stage.get(next_stage)
        if next_actor is None:
            raise AssetServiceError(f"Pipeline {pipeline.name} has no actor defined for stage {next_stage}")
        if next_actor not in VALID_ACTORS:
            raise AssetServiceError(f"Pipeline {pipeline.name} uses invalid actor {next_actor} for stage {next_stage}")

        updated_asset = replace(asset)
        updated_asset.pipeline_stage = next_stage
        updated_asset.actor = next_actor
        updated_asset.updated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        if asset.pipeline_stage == "MANIFEST" and next_stage != "MANIFEST":
            updated_asset.asset_state = "IN_PROGRESS"

        if next_actor == "AI_AGENT":
            updated_asset.ai_state = "ASKED"
        else:
            updated_asset.ai_state = None

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset
