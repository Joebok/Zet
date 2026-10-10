from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from zet.models.asset import Asset
from zet.models.turnaround import TurnaroundSheet
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.repositories.turnaround_repository import TurnaroundRepository
from zet.services.character_grid_service import CharacterGridOptions, CharacterGridService
from zet.services.image_sheet_service import letter_landscape_height
from zet.services.path_service import PathService
from zet.services.turnaround_views import TURNAROUND_VIEW_ORDER
from zet.services.local_asset_source_service import LocalAssetSourceService

DEFAULT_DETECTION_TOLERANCE = 50.0


class TurnaroundServiceError(Exception):
    """Report turnaround discovery, generation, or promotion failures."""


@dataclass(frozen=True)
class AuxiliaryTurnaroundRow:
    """Describe one auxiliary partial turnaround sheet."""
    turnaround_id: str
    parent_turnaround_id: str
    label: str
    crop_percent: float
    detection_tolerance: float
    status: str
    candidate_image_path: Optional[str]
    candidate_image_exists: bool
    locked_image_path: Optional[str]
    locked_image_exists: bool
    analysis_path: Optional[str]
    diagnostics_path: Optional[str]
    updated_at: Optional[str]
    deletable: bool


@dataclass(frozen=True)
class TurnaroundRow:
    """Describe one dashboard row for a possible turnaround sheet."""
    turnaround_id: str
    character: str
    phase: str
    source_pipeline: str
    costume: Optional[str]
    expression: Optional[str]
    scene_appearance_id: Optional[str]
    scene_appearance: Optional[str]
    label: str
    status: str
    ready: bool
    detection_tolerance: float
    locked_count: int
    missing_views: list[str]
    source_asset_ids: list[int]
    source_local_keys: list[str]
    candidate_image_path: Optional[str]
    candidate_image_exists: bool
    locked_image_path: Optional[str]
    locked_image_exists: bool
    analysis_path: Optional[str]
    diagnostics_path: Optional[str]
    updated_at: Optional[str]
    auxiliary_sheets: list[AuxiliaryTurnaroundRow]


class TurnaroundService:
    """Coordinate turnaround sheet discovery, generation, and promotion."""

    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        turnaround_repository: TurnaroundRepository,
        path_service: PathService,
        grid_service: CharacterGridService | None = None,
        local_sources: LocalAssetSourceService | None = None,
    ):
        """Initialize the service with repositories and path helpers."""
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.turnaround_repository = turnaround_repository
        self.path_service = path_service
        self.grid_service = grid_service or CharacterGridService()
        self.local_sources = local_sources

    def _timestamp(self) -> str:
        """Return the current timestamp for persisted records."""
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _validated_detection_tolerance(self, value: Optional[float]) -> float:
        """Return a valid foreground detection tolerance for turnaround assembly."""
        if value is None:
            return DEFAULT_DETECTION_TOLERANCE
        tolerance = float(value)
        if tolerance < 1 or tolerance > 200:
            raise TurnaroundServiceError("Detection tolerance must be between 1 and 200.")
        return tolerance

    def _grid_options(
        self,
        tolerance: float,
        crop_height_percent: Optional[float] = None,
    ) -> CharacterGridOptions:
        """Build fixed US Letter turnaround panel settings from project config."""
        width = int(getattr(self.path_service.config, "turnaround_width", 3960))
        if width <= 0 or width % 44:
            raise TurnaroundServiceError("Turnaround width must be a positive multiple of 44 pixels.")
        height = letter_landscape_height(width)
        return CharacterGridOptions(
            tolerance=tolerance,
            crop_height_percent=crop_height_percent,
            crop_width_to_character=True,
            fixed_panel_width=width // 4,
            fixed_panel_height=height // 2,
            page_margin=int(getattr(self.path_service.config, "zine_page_margin", 4)),
            print_scale=float(getattr(self.path_service.config, "zine_print_scale", 0.978)),
        )

    def _sheet_detection_tolerance(self, sheet: TurnaroundSheet | None) -> float:
        """Return the stored foreground detection tolerance for a sheet."""
        return self._validated_detection_tolerance(sheet.detection_tolerance if sheet else DEFAULT_DETECTION_TOLERANCE)

    def _slug(self, value: str) -> str:
        """Normalize a label segment for path-safe turnaround ids."""
        return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-") or "default"

    def _group_key(self, asset: Asset) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Return the grouping key that defines one turnaround source set."""
        return asset.pipeline, asset.costume, asset.expression, asset.scene_appearance_id

    def _turnaround_id(self, pipeline: str, costume: Optional[str], expression: Optional[str], scene_appearance_id: Optional[str] = None) -> str:
        """Build the stable id for one turnaround source set."""
        parts = [self._slug(pipeline)]
        if costume:
            parts.append(self._slug(costume))
        if expression:
            parts.append(self._slug(expression))
        if scene_appearance_id:
            parts.append(self._slug(scene_appearance_id))
        return "_".join(parts)

    def _label(
        self,
        pipeline: str,
        costume: Optional[str],
        expression: Optional[str],
        scene_appearance: Optional[str] = None,
    ) -> str:
        """Build a human-readable label for one turnaround source set."""
        parts = ["Scene Appearance" if pipeline == "Scene-Appearance" else pipeline]
        if costume:
            parts.append(costume)
        if expression:
            parts.append(expression)
        if scene_appearance:
            parts.insert(1, scene_appearance)
        return " / ".join(parts)

    def _locked_assets_by_view(
        self,
        assets: list[Asset],
        key: tuple[str, Optional[str], Optional[str], Optional[str]],
    ) -> dict[str, Asset]:
        """Map locked source assets for one group by body view."""
        matches = {}
        for asset in assets:
            if self._group_key(asset) != key:
                continue
            if asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
                continue
            if asset.body_view in TURNAROUND_VIEW_ORDER:
                matches[asset.body_view] = asset
        return matches

    def _sheet_for_id(self, sheets: list[TurnaroundSheet], turnaround_id: str) -> TurnaroundSheet | None:
        """Find an existing sheet model by id."""
        for sheet in sheets:
            if sheet.turnaround_id == turnaround_id:
                return sheet
        return None

    def _stored_path(self, path_text: str | None) -> Path | None:
        """Resolve a stored turnaround path through current library configuration."""
        if not path_text:
            return None
        return self.path_service.resolve_path(path_text)

    def _auxiliary_rows(self, sheets: list[TurnaroundSheet], parent_turnaround_id: str) -> list[AuxiliaryTurnaroundRow]:
        """Build auxiliary sheet rows for one full turnaround group."""
        rows = []
        for sheet in sheets:
            if sheet.parent_turnaround_id != parent_turnaround_id or sheet.sheet_type != "partial":
                continue
            candidate_path = self._stored_path(sheet.candidate_image_path)
            locked_path = self._stored_path(sheet.locked_image_path)
            candidate_exists = bool(candidate_path and candidate_path.exists())
            locked_exists = bool(locked_path and locked_path.exists())
            rows.append(
                AuxiliaryTurnaroundRow(
                    turnaround_id=sheet.turnaround_id,
                    parent_turnaround_id=parent_turnaround_id,
                    label=sheet.label or sheet.turnaround_id,
                    crop_percent=float(sheet.crop_percent or 0),
                    detection_tolerance=self._sheet_detection_tolerance(sheet),
                    status=sheet.status,
                    candidate_image_path=str(candidate_path) if candidate_path else sheet.candidate_image_path,
                    candidate_image_exists=candidate_exists,
                    locked_image_path=str(locked_path) if locked_path else sheet.locked_image_path,
                    locked_image_exists=locked_exists,
                    analysis_path=sheet.analysis_path,
                    diagnostics_path=sheet.diagnostics_path,
                    updated_at=sheet.updated_at,
                    deletable=bool(sheet.deletable),
                )
            )
        return sorted(rows, key=lambda row: (row.label.lower(), row.turnaround_id))

    def _row_from_group(
        self,
        character: str,
        phase: str,
        key: tuple[str, Optional[str], Optional[str], Optional[str]],
        assets_by_view: dict[str, Asset],
        sheet: TurnaroundSheet | None,
        sheets: list[TurnaroundSheet],
    ) -> TurnaroundRow:
        """Create a dashboard row for one possible turnaround group."""
        pipeline, costume, expression, scene_appearance_id = key
        turnaround_id = self._turnaround_id(pipeline, costume, expression, scene_appearance_id)
        scene_appearance = next((item.scene_appearance for item in assets_by_view.values() if item.scene_appearance), None)
        missing_views = [view for view in TURNAROUND_VIEW_ORDER if view not in assets_by_view]
        source_asset_ids = [assets_by_view[view].asset_id for view in TURNAROUND_VIEW_ORDER if view in assets_by_view]
        candidate_path = self._stored_path(sheet.candidate_image_path) if sheet else None
        locked_path = self._stored_path(sheet.locked_image_path) if sheet else self.path_service.turnaround_locked_image_path(character, phase, turnaround_id)
        candidate_exists = bool(candidate_path and candidate_path.exists())
        locked_exists = bool(locked_path and locked_path.exists())
        if locked_exists or (sheet and sheet.status == "LOCKED"):
            status = "locked"
        elif sheet and sheet.status == "RENDER_REVIEW" and candidate_exists:
            status = "candidate ready for review"
        elif missing_views:
            status = "missing locked assets"
        else:
            status = "ready for turnaround"
        return TurnaroundRow(
            turnaround_id=turnaround_id,
            character=character,
            phase=phase,
            source_pipeline=pipeline,
            costume=costume,
            expression=expression,
            scene_appearance_id=scene_appearance_id,
            scene_appearance=scene_appearance,
            label=self._label(pipeline, costume, expression, scene_appearance),
            status=status,
            ready=not missing_views,
            detection_tolerance=self._sheet_detection_tolerance(sheet),
            locked_count=len(assets_by_view),
            missing_views=missing_views,
            source_asset_ids=source_asset_ids,
            source_local_keys=[],
            candidate_image_path=str(candidate_path) if candidate_path else None,
            candidate_image_exists=candidate_exists,
            locked_image_path=str(locked_path) if locked_path else None,
            locked_image_exists=locked_exists,
            analysis_path=sheet.analysis_path if sheet else None,
            diagnostics_path=sheet.diagnostics_path if sheet else None,
            updated_at=sheet.updated_at if sheet else None,
            auxiliary_sheets=self._auxiliary_rows(sheets, turnaround_id),
        )

    @staticmethod
    def _local_view_label(value: str) -> str:
        labels = {
            "FRONT": "Front", "FRONT_LEFT_3_4": "Front-Left-3-4", "FRONT_RIGHT_3_4": "Front-Right-3-4",
            "LEFT_PROFILE": "Left-Profile", "RIGHT_PROFILE": "Right-Profile",
            "BACK_LEFT_3_4": "Back-Left-3-4", "BACK_RIGHT_3_4": "Back-Right-3-4", "BACK": "Back",
        }
        return labels.get(str(value).upper(), str(value))

    def _local_rows(self, character: str, phase: str, sheets: list[TurnaroundSheet]) -> list[TurnaroundRow]:
        if self.local_sources is None:
            return []
        names = {"body-reference": "Body-Reference", "character-assembly": "Character-Assembly",
                 "costume-dressing": "Costume-Dressing"}
        grouped: dict[tuple[str, str], dict[str, dict]] = {}
        for source in self.local_sources.list_sources(character, phase):
            pipeline = names.get(str(source["pipeline"]).lower())
            if not pipeline:
                continue
            key = (pipeline, str(source.get("costume") or ""))
            grouped.setdefault(key, {})[self._local_view_label(source["view"])] = source
        rows = []
        for (pipeline, costume), assets_by_view in sorted(grouped.items()):
            missing = [view for view in TURNAROUND_VIEW_ORDER if view not in assets_by_view]
            turnaround_id = self._turnaround_id(f"Local-{pipeline}", costume, None)
            sheet = self._sheet_for_id(sheets, turnaround_id)
            candidate = self._stored_path(sheet.candidate_image_path) if sheet else None
            locked = self._stored_path(sheet.locked_image_path) if sheet else self.path_service.turnaround_locked_image_path(character, phase, turnaround_id)
            sources = [assets_by_view[view] for view in TURNAROUND_VIEW_ORDER if view in assets_by_view]
            rows.append(TurnaroundRow(
                turnaround_id=turnaround_id, character=character, phase=phase, source_pipeline=pipeline,
                costume=costume or None, expression=None, scene_appearance_id=None, scene_appearance=None,
                label=self._label(pipeline, costume or None, None),
                status="locked" if locked and locked.exists() else "candidate ready for review" if candidate and candidate.exists() else "missing locked assets" if missing else "ready for turnaround",
                ready=not missing, detection_tolerance=self._sheet_detection_tolerance(sheet), locked_count=len(sources),
                missing_views=missing, source_asset_ids=[], source_local_keys=[item["source_key"] for item in sources],
                candidate_image_path=str(candidate) if candidate else None, candidate_image_exists=bool(candidate and candidate.exists()),
                locked_image_path=str(locked) if locked else None, locked_image_exists=bool(locked and locked.exists()),
                analysis_path=sheet.analysis_path if sheet else None, diagnostics_path=sheet.diagnostics_path if sheet else None,
                updated_at=sheet.updated_at if sheet else None, auxiliary_sheets=self._auxiliary_rows(sheets, turnaround_id),
            ))
        return rows

    def _historical_rows(self, character: str, phase: str, sheets: list[TurnaroundSheet]) -> list[TurnaroundRow]:
        """Keep saved sheets visible without offering regeneration from retired sources."""
        rows = []
        for sheet in sheets:
            if sheet.sheet_type != "full" or sheet.turnaround_id.startswith("Local-"):
                continue
            candidate = self._stored_path(sheet.candidate_image_path)
            locked = self._stored_path(sheet.locked_image_path)
            candidate_exists = bool(candidate and candidate.is_file())
            locked_exists = bool(locked and locked.is_file())
            rows.append(TurnaroundRow(
                turnaround_id=sheet.turnaround_id, character=character, phase=phase,
                source_pipeline=sheet.source_pipeline, costume=sheet.costume, expression=sheet.expression,
                scene_appearance_id=sheet.scene_appearance_id, scene_appearance=sheet.scene_appearance,
                label=sheet.label or self._label(sheet.source_pipeline, sheet.costume, sheet.expression, sheet.scene_appearance),
                status="locked" if locked_exists or sheet.status == "LOCKED" else "candidate ready for review" if candidate_exists else "historical",
                ready=False, detection_tolerance=self._sheet_detection_tolerance(sheet),
                locked_count=len(sheet.source_asset_ids or sheet.source_local_keys),
                missing_views=list(TURNAROUND_VIEW_ORDER), source_asset_ids=list(sheet.source_asset_ids),
                source_local_keys=list(sheet.source_local_keys),
                candidate_image_path=str(candidate) if candidate else sheet.candidate_image_path,
                candidate_image_exists=candidate_exists,
                locked_image_path=str(locked) if locked else sheet.locked_image_path,
                locked_image_exists=locked_exists, analysis_path=sheet.analysis_path,
                diagnostics_path=sheet.diagnostics_path, updated_at=sheet.updated_at,
                auxiliary_sheets=self._auxiliary_rows(sheets, sheet.turnaround_id),
            ))
        return rows

    def list_rows(self, character: str, phase: str) -> list[TurnaroundRow]:
        """List local-source groups and preserve historical sheets as read-only rows."""
        sheets = self.turnaround_repository.list_sheets(character, phase)
        return self._local_rows(character, phase, sheets) + self._historical_rows(character, phase, sheets)

    def get_row(self, character: str, phase: str, turnaround_id: str) -> TurnaroundRow:
        """Return one turnaround dashboard row by id."""
        for row in self.list_rows(character, phase):
            if row.turnaround_id == turnaround_id:
                return row
        raise TurnaroundServiceError(f"Turnaround {turnaround_id} not found for {character}/{phase}")

    def _assets_for_turnaround(self, character: str, phase: str, turnaround_id: str) -> list[Asset]:
        """Return ordered locked source assets for a turnaround id."""
        row = self.get_row(character, phase, turnaround_id)
        if not row.ready:
            raise TurnaroundServiceError(f"Missing locked assets: {', '.join(row.missing_views)}")
        if turnaround_id.startswith("Local-"):
            if self.local_sources is None:
                raise TurnaroundServiceError("Local turnaround sources are unavailable.")
            row = self.get_row(character, phase, turnaround_id)
            sources = self.local_sources.list_sources(character, phase)
            source_keys = set(row.source_local_keys)
            by_key = {item["source_key"]: item for item in sources}
            if not source_keys.issubset(by_key):
                raise TurnaroundServiceError("One or more locked local turnaround sources are stale.")
            from types import SimpleNamespace
            local = [by_key[key] for key in row.source_local_keys]
            labels = {"body-reference": "Body-Reference", "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing"}
            return [SimpleNamespace(asset_id=0, pipeline=labels[item["pipeline"].lower()], costume=item["costume"] or None,
                                    expression=None, scene_appearance_id=None, scene_appearance=None,
                                    body_view=self._local_view_label(item["view"]), image_path=item["image_path"],
                                    source_key=item["source_key"]) for item in local]
        assets = self.asset_repository.list_assets(character, phase)
        key = (row.source_pipeline, row.costume, row.expression, row.scene_appearance_id)
        assets_by_view = self._locked_assets_by_view(assets, key)
        return [assets_by_view[view] for view in TURNAROUND_VIEW_ORDER]

    def _source_image_path(self, asset) -> Path:
        return Path(asset.image_path) if getattr(asset, "image_path", None) else self.path_service.locked_image_path(asset)

    def generate_candidate(
        self,
        character: str,
        phase: str,
        turnaround_id: str,
        detection_tolerance: Optional[float] = None,
    ) -> TurnaroundRow:
        """Generate a new review candidate image for a turnaround sheet."""
        source_assets = self._assets_for_turnaround(character, phase, turnaround_id)
        first = source_assets[0]
        existing_sheet = self._sheet_for_id(self.turnaround_repository.list_sheets(character, phase), turnaround_id)
        tolerance = self._validated_detection_tolerance(
            detection_tolerance if detection_tolerance is not None else self._sheet_detection_tolerance(existing_sheet)
        )
        work_path = self.path_service.turnaround_work_path(character, phase, turnaround_id)
        candidate_dir = work_path / "Candidate"
        if candidate_dir.exists():
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = self.path_service.character_backup_path(character, phase) / "TurnaroundCandidates"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate_dir), str(backup_dir / f"{turnaround_id}.{backup_suffix}"))
        image_paths = [self._source_image_path(asset) for asset in source_assets]
        result = self.grid_service.assemble_grid(
            image_paths,
            candidate_dir,
            self._grid_options(tolerance),
            output_name=f"{turnaround_id}.png",
        )
        sheet = TurnaroundSheet(
            turnaround_id=turnaround_id,
            character=character,
            phase=phase,
            source_pipeline=first.pipeline,
            costume=first.costume,
            expression=first.expression,
            scene_appearance_id=first.scene_appearance_id,
            scene_appearance=first.scene_appearance,
            status="RENDER_REVIEW",
            source_asset_ids=[] if getattr(first, "source_key", None) else [asset.asset_id for asset in source_assets],
            source_local_keys=[asset.source_key for asset in source_assets if getattr(asset, "source_key", None)],
            candidate_image_path=str(result.grid_path),
            locked_image_path=str(self.path_service.turnaround_locked_image_path(character, phase, turnaround_id)),
            label=self._label(first.pipeline, first.costume, first.expression, first.scene_appearance),
            sheet_type="full",
            parent_turnaround_id=None,
            crop_percent=None,
            detection_tolerance=tolerance,
            deletable=False,
            analysis_path=str(result.analysis_path),
            diagnostics_path=str(result.diagnostics_path),
            updated_at=self._timestamp(),
        )
        self.turnaround_repository.save_sheet(sheet)
        return self.get_row(character, phase, turnaround_id)

    def _partial_turnaround_id(self, parent_turnaround_id: str, label: str) -> str:
        """Build a stable id for a partial turnaround under a full sheet."""
        return f"{parent_turnaround_id}__partial__{self._slug(label)}"

    def _partial_locked_path(self, character: str, phase: str, partial_id: str) -> Path:
        """Return the locked reference path for a partial turnaround."""
        return self.path_service.turnaround_locked_image_path(character, phase, partial_id)

    def upsert_partial_sheet(
        self,
        character: str,
        phase: str,
        parent_turnaround_id: str,
        label: str,
        crop_percent: float,
        detection_tolerance: Optional[float] = None,
    ) -> TurnaroundRow:
        """Create or update and render an auxiliary partial turnaround sheet."""
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise TurnaroundServiceError("Partial turnaround label is required.")
        crop_value = float(crop_percent)
        if crop_value <= 0 or crop_value > 100:
            raise TurnaroundServiceError("Partial turnaround percent must be greater than 0 and less than or equal to 100.")
        existing_sheet = self._sheet_for_id(self.turnaround_repository.list_sheets(character, phase), self._partial_turnaround_id(parent_turnaround_id, cleaned_label))
        parent_sheet = self._sheet_for_id(self.turnaround_repository.list_sheets(character, phase), parent_turnaround_id)
        tolerance = self._validated_detection_tolerance(
            detection_tolerance
            if detection_tolerance is not None
            else self._sheet_detection_tolerance(existing_sheet or parent_sheet)
        )

        source_assets = self._assets_for_turnaround(character, phase, parent_turnaround_id)
        first = source_assets[0]
        partial_id = self._partial_turnaround_id(parent_turnaround_id, cleaned_label)
        work_path = self.path_service.turnaround_work_path(character, phase, partial_id)
        candidate_dir = work_path / "Candidate"
        if candidate_dir.exists():
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = self.path_service.character_backup_path(character, phase) / "TurnaroundCandidates"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate_dir), str(backup_dir / f"{partial_id}.{backup_suffix}"))

        image_paths = [self._source_image_path(asset) for asset in source_assets]
        result = self.grid_service.assemble_grid(
            image_paths,
            candidate_dir,
            self._grid_options(tolerance, crop_value),
            output_name=f"{partial_id}.png",
        )
        sheet = TurnaroundSheet(
            turnaround_id=partial_id,
            character=character,
            phase=phase,
            source_pipeline=first.pipeline,
            costume=first.costume,
            expression=first.expression,
            scene_appearance_id=first.scene_appearance_id,
            scene_appearance=first.scene_appearance,
            label=cleaned_label,
            sheet_type="partial",
            parent_turnaround_id=parent_turnaround_id,
            crop_percent=crop_value,
            detection_tolerance=tolerance,
            deletable=True,
            status="RENDER_REVIEW",
            source_asset_ids=[] if getattr(first, "source_key", None) else [asset.asset_id for asset in source_assets],
            source_local_keys=[asset.source_key for asset in source_assets if getattr(asset, "source_key", None)],
            candidate_image_path=str(result.grid_path),
            locked_image_path=str(self._partial_locked_path(character, phase, partial_id)),
            analysis_path=str(result.analysis_path),
            diagnostics_path=str(result.diagnostics_path),
            updated_at=self._timestamp(),
        )
        self.turnaround_repository.save_sheet(sheet)
        return self.get_row(character, phase, parent_turnaround_id)

    def update_partial_sheet(
        self,
        character: str,
        phase: str,
        partial_turnaround_id: str,
        label: str,
        crop_percent: float,
        detection_tolerance: Optional[float] = None,
    ) -> TurnaroundRow:
        """Update and regenerate an existing auxiliary partial turnaround sheet."""
        sheet = self.turnaround_repository.get_sheet(character, phase, partial_turnaround_id)
        if sheet.sheet_type != "partial" or not sheet.parent_turnaround_id:
            raise TurnaroundServiceError("Only auxiliary partial turnaround sheets can be updated.")
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise TurnaroundServiceError("Partial turnaround label is required.")
        crop_value = float(crop_percent)
        if crop_value <= 0 or crop_value > 100:
            raise TurnaroundServiceError("Partial turnaround percent must be greater than 0 and less than or equal to 100.")
        tolerance = self._validated_detection_tolerance(
            detection_tolerance if detection_tolerance is not None else self._sheet_detection_tolerance(sheet)
        )

        source_assets = self._assets_for_turnaround(character, phase, sheet.parent_turnaround_id)
        candidate_dir = self.path_service.turnaround_work_path(character, phase, partial_turnaround_id) / "Candidate"
        if candidate_dir.exists():
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = self.path_service.character_backup_path(character, phase) / "TurnaroundCandidates"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate_dir), str(backup_dir / f"{partial_turnaround_id}.{backup_suffix}"))

        image_paths = [self._source_image_path(asset) for asset in source_assets]
        result = self.grid_service.assemble_grid(
            image_paths,
            candidate_dir,
            self._grid_options(tolerance, crop_value),
            output_name=f"{partial_turnaround_id}.png",
        )
        sheet.label = cleaned_label
        sheet.crop_percent = crop_value
        sheet.detection_tolerance = tolerance
        sheet.status = "RENDER_REVIEW"
        sheet.source_asset_ids = [] if getattr(source_assets[0], "source_key", None) else [asset.asset_id for asset in source_assets]
        sheet.source_local_keys = [asset.source_key for asset in source_assets if getattr(asset, "source_key", None)]
        sheet.candidate_image_path = str(result.grid_path)
        sheet.analysis_path = str(result.analysis_path)
        sheet.diagnostics_path = str(result.diagnostics_path)
        sheet.updated_at = self._timestamp()
        self.turnaround_repository.save_sheet(sheet)
        return self.get_row(character, phase, sheet.parent_turnaround_id)

    def delete_partial_sheet(self, character: str, phase: str, partial_turnaround_id: str) -> TurnaroundRow:
        """Delete an auxiliary partial turnaround sheet and its generated files."""
        sheet = self.turnaround_repository.get_sheet(character, phase, partial_turnaround_id)
        if sheet.sheet_type != "partial" or not sheet.deletable or not sheet.parent_turnaround_id:
            raise TurnaroundServiceError("Only auxiliary partial turnaround sheets can be deleted.")
        removed = self.turnaround_repository.delete_sheet(character, phase, partial_turnaround_id)
        for path_text in (removed.candidate_image_path, removed.locked_image_path, removed.analysis_path):
            if path_text:
                self.path_service.resolve_path(path_text).unlink(missing_ok=True)
        if removed.diagnostics_path:
            shutil.rmtree(self.path_service.resolve_path(removed.diagnostics_path), ignore_errors=True)
        shutil.rmtree(self.path_service.turnaround_work_path(character, phase, partial_turnaround_id), ignore_errors=True)
        return self.get_row(character, phase, removed.parent_turnaround_id)

    def promote_to_locked(self, character: str, phase: str, turnaround_id: str, replace_existing: bool = False) -> TurnaroundRow:
        """Promote a candidate turnaround sheet to the locked reference location."""
        sheet = self.turnaround_repository.get_sheet(character, phase, turnaround_id)
        candidate_path = self._stored_path(sheet.candidate_image_path)
        if not candidate_path or not candidate_path.exists():
            raise TurnaroundServiceError("Cannot promote: candidate turnaround image does not exist.")
        locked_path = self._stored_path(sheet.locked_image_path) or self.path_service.turnaround_locked_image_path(character, phase, turnaround_id)
        if locked_path.exists() and not replace_existing:
            raise TurnaroundServiceError("A locked turnaround already exists. Confirm replacement before promoting.")
        locked_path.parent.mkdir(parents=True, exist_ok=True)
        if locked_path.exists():
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = self.path_service.character_backup_path(character, phase) / "Turnarounds"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(locked_path, backup_dir / f"{locked_path.stem}.backup.{backup_suffix}{locked_path.suffix}")
        shutil.copy2(candidate_path, locked_path)
        sheet.status = "LOCKED"
        sheet.locked_image_path = str(locked_path)
        sheet.updated_at = self._timestamp()
        self.turnaround_repository.save_sheet(sheet)
        return self.get_row(character, phase, sheet.parent_turnaround_id or turnaround_id)
