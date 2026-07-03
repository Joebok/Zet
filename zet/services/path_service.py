from pathlib import Path

from zet.models.asset import Asset
from zet.services.config_service import Config


class PathService:
    def __init__(self, config: Config):
        self.config = config

    def character_path(self, character: str, phase: str) -> Path:
        return Path(self.config.base_character_path) / character / phase

    def character_asset_path(self, character: str, phase: str) -> Path:
        return Path(self.config.base_asset_path) / character / phase

    def character_backup_path(self, character: str, phase: str) -> Path:
        return self.character_path(character, phase) / "_backup"

    def pipeline_base_path(self, character: str, phase: str) -> Path:
        return Path(self.config.base_pipeline_path) / character / phase

    def pipeline_path(self, asset: Asset) -> Path:
        head_view = asset.head_view if asset.head_view and asset.head_view.strip() else "_"
        return (
            self.pipeline_base_path(asset.character, asset.phase)
            / asset.pipeline
            / asset.body_view
            / head_view
            / f"Asset_{asset.asset_id}"
        )

    def candidate_image_path(self, asset: Asset) -> Path:
        if not asset.final_image_output:
            raise ValueError(f"Asset {asset.asset_id} has no final_image_output")
        return self.pipeline_path(asset) / asset.final_image_output

    def locked_image_path(self, asset: Asset) -> Path:
        if not asset.final_image_output:
            raise ValueError(f"Asset {asset.asset_id} has no final_image_output")
        return self.character_asset_path(asset.character, asset.phase) / asset.final_image_output

    def turnaround_work_path(self, character: str, phase: str, turnaround_id: str) -> Path:
        """Return the pipeline work folder for a turnaround sheet."""
        return self.pipeline_base_path(character, phase) / "Turnaround" / turnaround_id

    def turnaround_locked_image_path(self, character: str, phase: str, turnaround_id: str) -> Path:
        """Return the locked reference image path for a turnaround sheet."""
        return self.character_asset_path(character, phase) / "Turnarounds" / f"{turnaround_id}.png"
