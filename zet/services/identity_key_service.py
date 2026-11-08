from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from zet.models.asset import Asset
from zet.models.identity_key import IdentityKey
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.services.character_grid_service import CharacterGridOptions, CharacterGridService
from zet.services.entity_library_service import EntityLibraryService
from zet.services.path_service import PathService
from zet.services.local_asset_source_service import LocalAssetSourceService
from zet.services.workflow_storage import file_lock


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
        entity_library: EntityLibraryService,
        local_sources: LocalAssetSourceService | None = None,
    ):
        """Create an identity key service."""
        self.asset_repository = asset_repository
        self.identity_key_repository = identity_key_repository
        self.path_service = path_service
        self.entity_library = entity_library
        self.local_sources = local_sources
        self.grid_service = CharacterGridService()

    def _slug(self, value: str) -> str:
        """Return a filesystem-safe slug."""
        text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-")
        return text or "Identity-Key"

    def _timestamp(self) -> str:
        """Return an ISO timestamp for metadata updates."""
        return datetime.now().isoformat(timespec="microseconds")

    @staticmethod
    def _reference_key(key: IdentityKey) -> str:
        scope = json.dumps([key.character, key.phase, key.identity_key_id])
        return f"identity-key.{hashlib.sha256(scope.encode()).hexdigest()}"

    def _with_publication(self, key: IdentityKey) -> IdentityKey:
        key.inventory_asset_id = self.entity_library.identity_key_publication(self._reference_key(key))
        return key

    def _write_lock(self, character: str, phase: str):
        if any(not part or part in {".", ".."} or re.search(r"[/\\:]", part) for part in (character, phase)):
            raise IdentityKeyServiceError("Invalid Identity Key character or phase.")
        path = self.path_service.resolve_served_path(self.path_service.character_path(character, phase))
        if not path.is_relative_to(self.path_service.entity_library_root()):
            raise IdentityKeyServiceError("The Identity Key phase is outside this universe.")
        return file_lock(path / "IdentityKeys.lock")

    def _publish(self, key: IdentityKey, *, update: bool = False) -> IdentityKey:
        operation_id = uuid4().hex
        key.inventory_asset_id = self.entity_library.publish_identity_key(
            key, self.path_service.resolve_path(key.image_path), self._reference_key(key),
            operation_id=operation_id,
            before_commit=(
                lambda: self.identity_key_repository.save_identity_key(key, publication_id=operation_id)
            ) if update else None,
        )
        return key

    def set_locked(self, character: str, phase: str, identity_key_id: str, locked: bool) -> IdentityKey:
        with self._write_lock(character, phase):
            key = self.get_identity_key(character, phase, identity_key_id)
            if locked:
                return key if key.inventory_asset_id else self._publish(key)
            self.entity_library.unpublish_identity_key(self._reference_key(key))
            key.inventory_asset_id = None
            return key

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
        return [
            self._with_publication(key)
            for key in self.identity_key_repository.list_identity_keys(character, phase)
        ]

    def get_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        """Return one identity key by id."""
        return self._with_publication(self.identity_key_repository.get_identity_key(character, phase, identity_key_id))

    def _current_source(self, character: str, phase: str, source_local_key: str) -> dict:
        if self.local_sources is None:
            raise IdentityKeyServiceError("Local Identity Key sources are unavailable.")
        category_key = source_local_key.removeprefix("final:")
        return self.local_sources.get_category_source(character, phase, category_key)

    def preview_identity_key(
        self,
        character: str,
        phase: str,
        source_asset_id: int | None,
        label: str,
        crop_percent: float,
        identity_key_id: str | None = None,
        source_local_key: str | None = None,
    ) -> IdentityKeyPreview:
        """Generate a temporary identity key preview crop."""
        if not str(label or "").strip():
            raise IdentityKeyServiceError("Identity Key label is required.")
        if not source_local_key:
            raise IdentityKeyServiceError("Traditional pipeline assets are retired. Select a locked local image source.")
        local_source = self._current_source(character, phase, source_local_key)
        source_path = Path(local_source["image_path"])
        slug = self._slug(label)
        source_id = self._slug(local_source["source_key"])
        preview_id = f"preview_{source_id}_{slug}"
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
        source_asset_id: int | None,
        label: str,
        crop_percent: float,
        identity_key_id: str | None = None,
        source_local_key: str | None = None,
    ) -> IdentityKey:
        """Create or update a saved identity key."""
        with self._write_lock(character, phase):
            previous = self.get_identity_key(character, phase, identity_key_id) if identity_key_id else None
            return self._save_crop(character, phase, label, crop_percent, previous, source_local_key)

    def _save_crop(
        self, character: str, phase: str, label: str, crop_percent: float,
        previous: IdentityKey | None, source_local_key: str | None,
    ) -> IdentityKey:
        label = str(label or "").strip()
        if not label:
            raise IdentityKeyServiceError("Identity Key label is required.")
        if not source_local_key:
            raise IdentityKeyServiceError("Traditional pipeline assets are retired. Select a locked local image source.")
        local_source = self._current_source(character, phase, source_local_key)
        source_path = Path(local_source["image_path"])
        revision = uuid4().hex
        key_id = previous.identity_key_id if previous else f"IK_{revision}"
        output_path = self.path_service.identity_key_image_path(character, phase, revision)
        output_path = output_path.parent / revision / "crop.png"
        result = self._crop(source_path, output_path.parent, output_path.name, crop_percent)
        identity_key = IdentityKey(
            identity_key_id=key_id,
            character=character,
            phase=phase,
            label=label,
            crop_percent=crop_percent,
            source_asset_id=None,
            source_pipeline=local_source["pipeline"],
            source_body_view=local_source["view"],
            source_costume=local_source["costume"] or None,
            source_local_key=local_source["source_key"],
            source_render_mode=local_source["render_mode"],
            source_sha256=local_source["image_sha256"],
            source_inventory_asset_id=local_source["inventory_asset_id"],
            image_path=str(result.image_path),
            source_image_path=str(source_path),
            analysis_path=str(result.analysis_path),
            crop_box=list(result.crop_box),
            updated_at=self._timestamp(),
        )
        if previous and previous.inventory_asset_id:
            return self._publish(identity_key, update=True)
        self.identity_key_repository.save_identity_key(identity_key)
        return identity_key

    def delete_identity_key(self, character: str, phase: str, identity_key_id: str) -> IdentityKey:
        """Delete an identity key image and metadata record."""
        with self._write_lock(character, phase):
            identity_key = self.get_identity_key(character, phase, identity_key_id)
            if identity_key.inventory_asset_id:
                raise IdentityKeyServiceError("Unlock the Identity Key before deleting it.")
            self.identity_key_repository.delete_identity_key(character, phase, identity_key_id)
            if identity_key.image_path:
                self.path_service.resolve_path(identity_key.image_path).unlink(missing_ok=True)
            return identity_key
