"""Read-only compatibility for locked character/auxiliary image references.
Story authoring and rendering are retired; Narrative owns the active workflow.
"""
from __future__ import annotations
from pathlib import Path
import re
from zet.models.asset import Asset
from zet.models.auxiliary_resource import AuxiliaryResource
from zet.models.identity_key import IdentityKey
from zet.models.turnaround import TurnaroundSheet
from zet.models.story import ImageReferenceRow, SceneBuilderDocument, SceneDocument, SceneRecord, StoryDocument, StoryGitResult, StoryRecord, StoryRenderTask
from zet.services.story_reference_service import StoryReferenceService

class StoryServiceError(ValueError):
    pass

class StoryService:
    def __init__(self, path_service, asset_repository, auxiliary_resource_repository, identity_key_repository=None, turnaround_repository=None):
        self.path_service = path_service
        self.asset_repository = asset_repository
        self.auxiliary_resource_repository = auxiliary_resource_repository
        self.identity_key_repository = identity_key_repository
        self.turnaround_repository = turnaround_repository
        self.image_catalog_service = None
        self.story_reference_service = StoryReferenceService(path_service, asset_repository, auxiliary_resource_repository, identity_key_repository, StoryServiceError, turnaround_repository)

    def _scene_reference_rows(self):
        return []

    def list_stories(self):
        return []

    def list_scenes(self, story):
        return []

    def safe_slug(self, value: str) -> str:
        """Return a filename-safe slug for stories and scenes."""
        text = str(value or "").strip()
        safe = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
        return safe or "Untitled"


    def image_reference_rows(
        self,
        character_filter: str = "",
        text_filter: str = "",
        phase_filter: str = "",
        costume_filter: str = "",
        scope: str = "all",
        include_unavailable: bool = True,
    ) -> list[ImageReferenceRow]:
        """List copyable image reference rows for scenes."""
        rows: list[ImageReferenceRow] = []
        normalized_character = str(character_filter or "").strip().lower()
        normalized_phase = str(phase_filter or "").strip().lower()
        normalized_costume = self._normalize_costume(costume_filter)
        normalized_filter = str(text_filter or "").strip().lower()
        contextual = scope == "context"
        if scope not in {"all", "context"}:
            raise StoryServiceError(f"Unsupported image reference scope: {scope}")
        if not contextual:
            for resource in self.auxiliary_resource_repository.list_resources():
                rows.extend(self._aux_resource_rows(resource))
            rows.extend(self._scene_reference_rows())
        base_character_root = Path(self.path_service.config.base_character_path)
        characters = (
            sorted(
                item.name
                for item in base_character_root.iterdir()
                if item.is_dir() and not item.name.startswith("_")
            )
            if base_character_root.exists()
            else []
        )
        for character in characters:
            if contextual and normalized_character and character.lower() != normalized_character:
                continue
            for phase_dir in sorted(item for item in (base_character_root / character).iterdir() if item.is_dir() and not item.name.startswith("_")):
                if contextual and normalized_phase and phase_dir.name.lower() != normalized_phase:
                    continue
                for asset in self._locked_assets(character, phase_dir.name):
                    rows.append(self._asset_reference_row(asset))
                for sheet in self._turnarounds(character, phase_dir.name):
                    rows.append(self._turnaround_reference_row(sheet))
                for identity_key in self._identity_keys(character, phase_dir.name):
                    rows.append(self._identity_reference_row(identity_key))
        if contextual and normalized_costume:
            rows = [
                row
                for row in rows
                if not row.costume
                or self._normalize_costume(row.costume) == normalized_costume
            ]
        if not include_unavailable:
            rows = [row for row in rows if row.available]
        rows = [row for row in rows if self._matches_filter(row, normalized_filter)]
        return sorted(rows, key=lambda row: (row.character.lower(), row.phase.lower(), row.kind.lower(), row.label.lower()))


    def _matches_filter(self, row: ImageReferenceRow, normalized_filter: str) -> bool:
        """Return whether one image reference row matches a text filter."""
        if not normalized_filter:
            return True
        haystack = " ".join([
            row.tag,
            row.label,
            row.character,
            row.phase,
            row.kind,
            row.pipeline,
            row.costume,
            row.view,
        ]).lower()
        return all(term in haystack for term in normalized_filter.split())


    @staticmethod
    def _normalize_costume(value: str) -> str:
        return " ".join(
            str(value or "").replace("-", " ").replace("_", " ").lower().split()
        )


    def _aux_resource_rows(self, resource: AuxiliaryResource) -> list[ImageReferenceRow]:
        """Return picker rows for auxiliary resource images."""
        rows = []
        for image in resource.images:
            image_path = self.path_service.resolve_path(str(image.get("image_path") or ""))
            rows.append(ImageReferenceRow(
                tag=str(image.get("tag") or ""),
                label=f"{resource.label} - {image.get('label') or image.get('image_id')}",
                character="",
                phase="",
                kind=f"aux:{resource.category}",
                pipeline="Auxiliary Resource",
                image_path=str(image_path),
                thumbnail_path=str(image_path),
            ))
        return rows


    def _locked_assets(self, character: str, phase: str) -> list[Asset]:
        """List locked assets for one character phase."""
        try:
            assets = self.asset_repository.list_assets(character, phase)
        except Exception:
            return []
        return [asset for asset in assets if asset.asset_state == "LOCKED" and asset.pipeline_stage == "LOCKED"]


    def _identity_keys(self, character: str, phase: str) -> list[IdentityKey]:
        """List identity keys for one character phase."""
        if self.identity_key_repository is None:
            return []
        try:
            return self.identity_key_repository.list_identity_keys(character, phase)
        except Exception:
            return []


    def _turnarounds(self, character: str, phase: str) -> list[TurnaroundSheet]:
        """List full turnaround sheets that have a stable descriptive tag."""
        if self.turnaround_repository is None:
            return []
        try:
            sheets = self.turnaround_repository.list_sheets(character, phase)
        except Exception:
            return []
        return [
            sheet
            for sheet in sheets
            if sheet.sheet_type == "full"
            and sheet.source_asset_ids
        ]


    def _asset_reference_row(self, asset: Asset) -> ImageReferenceRow:
        """Return one picker row for a locked asset."""
        label_parts = [asset.pipeline, asset.body_view]
        if asset.pipeline == "Scene-Appearance":
            label_parts = ["Scene Appearance", asset.scene_appearance or "", asset.costume or "", asset.body_view]
        if asset.head_view and asset.head_view != asset.body_view:
            label_parts.append(asset.head_view)
        if asset.scene_appearance and asset.pipeline != "Scene-Appearance":
            label_parts.append(asset.scene_appearance)
        if asset.costume and asset.pipeline != "Scene-Appearance":
            label_parts.append(asset.costume)
        if asset.expression:
            label_parts.append(asset.expression)
        image_path = self.path_service.locked_image_path(asset)
        available = image_path.is_file()
        tag_parts = [self._asset_reference_pipeline_code(asset.pipeline), asset.body_view]
        if asset.pipeline == "Costume-Dressing" and asset.costume:
            tag_parts.append(asset.costume)
        if asset.pipeline == "Scene-Appearance" and asset.scene_appearance:
            tag_parts.extend([asset.scene_appearance, asset.costume or ""])
        if asset.pipeline == "Expression" and asset.expression:
            tag_parts.append(asset.expression)
        return ImageReferenceRow(
            tag=f"{{{{ASSET:{asset.character}:{asset.phase}:{asset.asset_id}:{' | '.join(part for part in tag_parts if part)}}}}}",
            label=" / ".join(part for part in label_parts if part) if asset.pipeline == "Scene-Appearance" else " | ".join(part for part in label_parts if part),
            character=asset.character,
            phase=asset.phase,
            kind="locked-asset",
            pipeline=asset.pipeline,
            image_path=str(image_path),
            thumbnail_path=str(image_path),
            costume=asset.costume or "",
            view=asset.body_view or "",
            default_reference_roles=["internal arrangement"] if asset.pipeline == "Scene-Appearance" else [],
            available=available,
            disabled_reason="" if available else "Locked asset image is missing.",
        )


    def _turnaround_reference_row(self, sheet: TurnaroundSheet) -> ImageReferenceRow:
        """Return one picker row for a full locked turnaround sheet."""
        detail_parts = [self._asset_reference_pipeline_code(sheet.source_pipeline), "Turnaround"]
        if sheet.expression:
            detail_parts.append(sheet.expression)
        if sheet.scene_appearance:
            detail_parts.append(sheet.scene_appearance)
        if sheet.costume:
            detail_parts.append(sheet.costume)
        image_path = self.path_service.resolve_path(str(sheet.locked_image_path or ""))
        available = image_path.is_file()
        return ImageReferenceRow(
            tag=(f"{{{{ASSET:{sheet.character}:{sheet.phase}:{sheet.source_asset_ids[0]}:{' | '.join(detail_parts)}}}}}"
                 if sheet.source_asset_ids else f"{{{{TURNAROUND:{sheet.character}:{sheet.phase}:{sheet.turnaround_id}}}}}"),
            label=(
                " / ".join(["Scene Appearance", *detail_parts[2:], "Turnaround"])
                if sheet.source_pipeline == "Scene-Appearance"
                else " | ".join([sheet.source_pipeline, "Turnaround", *detail_parts[2:]])
            ),
            character=sheet.character,
            phase=sheet.phase,
            kind="locked-turnaround",
            pipeline=sheet.source_pipeline,
            image_path=str(image_path),
            thumbnail_path=str(image_path),
            costume=sheet.costume or "",
            default_reference_roles=["internal arrangement"] if sheet.source_pipeline == "Scene-Appearance" else [],
            available=available,
            disabled_reason="" if available else "Turnaround has no locked image.",
        )


    def _asset_reference_pipeline_code(self, pipeline: str) -> str:
        """Return the short pipeline label used in scene reference tags."""
        return {
            "Body-Reference": "Body",
            "Head-Image": "Head",
            "Character-Assembly": "Character",
            "Costume-Dressing": "Costume",
            "Scene-Appearance": "Scene Appearance",
            "Expression": "Expression",
        }.get(pipeline, pipeline)


    def _identity_reference_row(self, identity_key: IdentityKey) -> ImageReferenceRow:
        """Return one picker row for an identity key."""
        image_path = self.path_service.resolve_path(identity_key.image_path)
        available = image_path.is_file()
        return ImageReferenceRow(
            tag=f"{{{{IDENTITY:{identity_key.character}:{identity_key.phase}:{identity_key.identity_key_id}}}}}",
            label=identity_key.label,
            character=identity_key.character,
            phase=identity_key.phase,
            kind="identity-key",
            pipeline="Identity Key",
            image_path=str(image_path),
            thumbnail_path=str(image_path),
            costume=identity_key.source_costume or "",
            view=identity_key.source_body_view or "",
            available=available,
            disabled_reason="" if available else "Identity Key image is missing.",
        )
