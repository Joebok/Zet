import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.housekeeping_service import HousekeepingService
from zet.services.path_service import PathService
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
        path_service: PathService,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.state_machine = state_machine
        self.housekeeping_service = housekeeping_service
        self.path_service = path_service

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _validate_actor(self, pipeline_name: str, stage: str, actor: str | None) -> str:
        if actor is None:
            raise AssetServiceError(f"Pipeline {pipeline_name} has no actor defined for stage {stage}")
        if actor not in VALID_ACTORS:
            raise AssetServiceError(f"Pipeline {pipeline_name} uses invalid actor {actor} for stage {stage}")
        return actor

    def move_next(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage == "ERROR":
            raise AssetServiceError(f"Asset {asset_id} is in ERROR stage and cannot move next")

        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        next_stage = self.state_machine.next_stage(pipeline, asset.pipeline_stage)

        next_actor = self._validate_actor(pipeline.name, next_stage, pipeline.actor_by_stage.get(next_stage))

        updated_asset = replace(asset)
        updated_asset.pipeline_stage = next_stage
        updated_asset.actor = next_actor
        updated_asset.updated_at = self._timestamp()

        if asset.pipeline_stage == "MANIFEST" and next_stage != "MANIFEST":
            updated_asset.asset_state = "IN_PROGRESS"

        if next_actor == "AI_AGENT":
            updated_asset.ai_state = "ASKED"
        else:
            updated_asset.ai_state = None

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def run_housekeeping(self, character: str, phase: str, asset_id: int) -> Path:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        return self.housekeeping_service.prepare_stage(asset)

    def retry_ai(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.actor != "AI_AGENT":
            raise AssetServiceError("Retry AI is only available when Actor is AI_AGENT.")

        updated_asset = replace(asset)
        updated_asset.ai_state = "ASKED"
        updated_asset.last_ai_update = f"Retry requested from dashboard at {self._timestamp()}"
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def regenerate(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        manifest_actor = self._validate_actor(
            pipeline.name,
            "MANIFEST",
            pipeline.actor_by_stage.get("MANIFEST"),
        )

        updated_asset = replace(asset)
        updated_asset.asset_state = "IN_PROGRESS"
        updated_asset.pipeline_stage = "MANIFEST"
        updated_asset.actor = manifest_actor
        updated_asset.ai_state = "ASKED" if manifest_actor == "AI_AGENT" else None
        updated_asset.error_code = None
        updated_asset.error_message = None
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def promote_to_locked(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        candidate_image_path = self.path_service.candidate_image_path(asset)
        locked_image_path = self.path_service.locked_image_path(asset)

        if not candidate_image_path.exists():
            raise AssetServiceError("Cannot promote: candidate image does not exist.")

        locked_image_path.parent.mkdir(parents=True, exist_ok=True)
        if locked_image_path.exists():
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_name = f"{locked_image_path.stem}.backup.{backup_suffix}{locked_image_path.suffix}"
            shutil.copy2(locked_image_path, locked_image_path.with_name(backup_name))

        shutil.copy2(candidate_image_path, locked_image_path)

        final_stage = pipeline.stages[-1]
        updated_asset = replace(asset)
        updated_asset.asset_state = "LOCKED"
        updated_asset.pipeline_stage = final_stage
        updated_asset.actor = "HUMAN_AGENT"
        updated_asset.ai_state = None
        updated_asset.error_code = None
        updated_asset.error_message = None
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset
