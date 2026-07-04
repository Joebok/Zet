from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.models.identity_key import IdentityKey
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.services.character_grid_service import CharacterGridOptions, CharacterGridService
from zet.services.path_service import PathService


@dataclass(frozen=True)
class IdentityKeyPreview:
    """Describe a generated identity key preview crop."""
    preview_path: str
    source_image_path: str
    crop_percent: float
    crop_box: list[int]
    analysis_path: str


class IdentityKeyServiceError(Exception):
    """Report identity key workflow failures."""


class IdentityKeyService:
    """Manage deterministic identity key crops derived from locked assets."""

    def __init__(
        self,
        asset_repository: AssetRepository,
        identity_key_repository: IdentityKeyRepository,
        path_service: PathService,
    ):
        """Create an identity key service."""
        self.asset_repository = asset_repository
        self.identity_key_repository = identity_key_repository
        self.path_service = path_service
        self.grid_service = CharacterGridService()

    def _slug(self, value: str) -> str:
        """Return a filesystem-safe slug."""
        text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-")
        return text or "Identity-Key"

    def _timestamp(self) -> str:
        """Return an ISO timestamp for metadata updates."""
        return datetime.now().isoformat(timespec="seconds")

    def _source_asset(self, character: str, phase: str, source_asset_id: int) -> Asset:
        """Return and validate a locked source asset."""
        asset = self.asset_repository.get_asset(character, phase, source_asset_id)
        if asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
            raise IdentityKeyServiceError("Identity Keys can only be created from LOCKED assets.")
        return asset

    def _source_image_path(self, asset: Asset) -> Path:
        """Return and validate the source locked image path."""
        source_path = self.path_service.locked_image_path(asset)
        if not source_path.exists():
            raise IdentityKeyServiceError(f"Locked image not found for Asset {asset.asset_id}: {source_path}")
        return source_path

    def _crop(self, source_path: Path, output_dir: Path, output_name: str, crop_percent: float):
        """Run the shared deterministic crop routine."""
        return self.grid_service.crop_identity_image(
            source_path,
            output_dir,
            output_name,
            crop_percent,
            CharacterGridOptions(
                tolerance=50.0,
                crop_width_to_character=True,
                crop_height_percent=crop_percent,
                diagnostics=True,
                debug_grid=False,
            ),
        )

    def list_identity_keys(self, character: str, phase: str) -> list[IdentityKey]:
        """List identity keys for a character phase."""
        return self.identity_key_repository.list_identity_keys(character, phase)

    def get_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        """Return one identity key by id."""
        return self.identity_key_repository.get_identity_key(character, phase, identity_key_id)

    def preview_identity_key(
        self,
        character: str,
        phase: str,
        source_asset_id: int,
        label: str,
        crop_percent: float,
        identity_key_id: str | None = None,
    ) -> IdentityKeyPreview:
        """Generate a temporary identity key preview crop."""
        if not str(label or "").strip():
            raise IdentityKeyServiceError("Identity Key label is required.")
        asset = self._source_asset(character, phase, source_asset_id)
        source_path = self._source_image_path(asset)
        slug = self._slug(label)
        preview_id = identity_key_id or f"preview_{asset.asset_id}_{slug}"
        output_dir = self.path_service.pipeline_base_path(character, phase) / "IdentityKeys" / preview_id
        result = self._crop(source_path, output_dir, f"{preview_id}.png", crop_percent)
        return IdentityKeyPreview(
            preview_path=str(result.image_path),
            source_image_path=str(source_path),
            crop_percent=crop_percent,
            crop_box=list(result.crop_box),
            analysis_path=str(result.analysis_path),
        )

    def save_identity_key(
        self,
        character: str,
        phase: str,
        source_asset_id: int,
        label: str,
        crop_percent: float,
        identity_key_id: str | None = None,
    ) -> IdentityKey:
        """Create or update a saved identity key."""
        label = str(label or "").strip()
        if not label:
            raise IdentityKeyServiceError("Identity Key label is required.")
        asset = self._source_asset(character, phase, source_asset_id)
        source_path = self._source_image_path(asset)
        key_id = identity_key_id or f"IK_{asset.asset_id}_{self._slug(label)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = self.path_service.identity_key_image_path(character, phase, key_id)
        result = self._crop(source_path, output_path.parent, output_path.name, crop_percent)
        identity_key = IdentityKey(
            identity_key_id=key_id,
            character=character,
            phase=phase,
            label=label,
            crop_percent=crop_percent,
            source_asset_id=asset.asset_id,
            source_pipeline=asset.pipeline,
            source_body_view=asset.body_view,
            source_head_view=asset.head_view,
            source_costume=asset.costume,
            source_expression=asset.expression,
            image_path=str(result.image_path),
            source_image_path=str(source_path),
            analysis_path=str(result.analysis_path),
            crop_box=list(result.crop_box),
            updated_at=self._timestamp(),
        )
        self.identity_key_repository.save_identity_key(identity_key)
        return identity_key

    def delete_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        """Delete an identity key image and metadata record."""
        identity_key = self.identity_key_repository.delete_identity_key(character, phase, identity_key_id)
        if identity_key.image_path:
            Path(identity_key.image_path).unlink(missing_ok=True)
        return identity_key
