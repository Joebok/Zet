from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Optional

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository, AssetRepositoryError
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.path_service import PathService


COMPARABLE_PIPELINES = [
    "Body-Reference",
    "Head-Image",
    "Head-Fitment",
    "Character-Assembly",
    "Costume-Dressing",
    "Expression",
]


@dataclass(frozen=True)
class PhaseComparisonSide:
    """Describe one side of a phase comparison slot."""

    phase: str
    asset_id: Optional[int]
    image_path: Optional[str]
    image_exists: bool
    label: str
    body_view: Optional[str]
    head_view: Optional[str]
    costume: Optional[str]
    expression: Optional[str]
    updated_at: Optional[str]


@dataclass(frozen=True)
class PhaseComparisonRow:
    """Describe one matched comparison slot across phases."""

    slot_key: str
    slot_label: str
    pipeline: str
    left: PhaseComparisonSide
    right: PhaseComparisonSide


@dataclass(frozen=True)
class PhaseComparisonResult:
    """Return all phase comparison rows and the selected row."""

    character: str
    left_phase: str
    right_phase: str
    pipeline: str
    available_pipelines: list[str]
    left_costumes: list[str]
    right_costumes: list[str]
    selected_left_costume: str
    selected_right_costume: str
    rows: list[PhaseComparisonRow]
    selected_index: int
    selected_row: Optional[PhaseComparisonRow]


class PhaseComparisonService:
    """Build read-only locked-asset comparisons across phases."""

    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        path_service: PathService,
        project_root: Path,
    ):
        """Create a phase comparison service from repositories and paths."""
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.path_service = path_service
        self.project_root = project_root

    def compare(
        self,
        character: str,
        left_phase: str,
        right_phase: str,
        pipeline: str = "",
        selected_index: int = 0,
        selected_slot_key: str = "",
        left_costume: str = "",
        right_costume: str = "",
    ) -> PhaseComparisonResult:
        """Build comparison rows for two phases and one pipeline."""
        available = self.available_pipelines(character, left_phase, right_phase)
        selected_pipeline = pipeline if pipeline in available else (available[0] if available else "")
        if not selected_pipeline:
            return PhaseComparisonResult(
                character=character,
                left_phase=left_phase,
                right_phase=right_phase,
                pipeline="",
                available_pipelines=[],
                left_costumes=[],
                right_costumes=[],
                selected_left_costume="",
                selected_right_costume="",
                rows=[],
                selected_index=0,
                selected_row=None,
            )

        left_assets = self._locked_assets(character, left_phase, selected_pipeline)
        right_assets = self._locked_assets(character, right_phase, selected_pipeline)
        left_costumes = self._costume_options(left_assets)
        right_costumes = self._costume_options(right_assets)
        selected_left_costume = left_costume if left_costume in left_costumes else (left_costumes[0] if left_costumes else "")
        selected_right_costume = right_costume if right_costume in right_costumes else (right_costumes[0] if right_costumes else "")
        if selected_pipeline == "Costume-Dressing":
            left_assets = [asset for asset in left_assets if str(asset.costume or "") == selected_left_costume]
            right_assets = [asset for asset in right_assets if str(asset.costume or "") == selected_right_costume]
        rows = self._comparison_rows(selected_pipeline, left_phase, right_phase, left_assets, right_assets)
        index = self._selected_index(rows, selected_index, selected_slot_key)
        return PhaseComparisonResult(
            character=character,
            left_phase=left_phase,
            right_phase=right_phase,
            pipeline=selected_pipeline,
            available_pipelines=available,
            left_costumes=left_costumes if selected_pipeline == "Costume-Dressing" else [],
            right_costumes=right_costumes if selected_pipeline == "Costume-Dressing" else [],
            selected_left_costume=selected_left_costume if selected_pipeline == "Costume-Dressing" else "",
            selected_right_costume=selected_right_costume if selected_pipeline == "Costume-Dressing" else "",
            rows=rows,
            selected_index=index,
            selected_row=rows[index] if rows else None,
        )

    def available_pipelines(self, character: str, left_phase: str, right_phase: str) -> list[str]:
        """Return comparable pipelines present in either selected phase."""
        names: set[str] = set()
        for phase in (left_phase, right_phase):
            try:
                names.update(pipeline.name for pipeline in self.pipeline_repository.list_pipelines(character, phase))
            except Exception:
                continue
        return [name for name in COMPARABLE_PIPELINES if name in names]

    def _locked_assets(self, character: str, phase: str, pipeline: str) -> list[Asset]:
        """Return locked assets with existing locked images for one phase pipeline."""
        try:
            assets = self.asset_repository.list_assets(character, phase)
        except AssetRepositoryError:
            return []
        locked: list[Asset] = []
        for asset in assets:
            if asset.pipeline != pipeline:
                continue
            if asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
                continue
            if not asset.final_image_output:
                continue
            if self.path_service.locked_image_path(asset).exists():
                locked.append(asset)
        return locked

    def _comparison_rows(
        self,
        pipeline: str,
        left_phase: str,
        right_phase: str,
        left_assets: list[Asset],
        right_assets: list[Asset],
    ) -> list[PhaseComparisonRow]:
        """Build comparison rows from the union of locked slots."""
        left_by_slot = self._assets_by_slot(pipeline, left_assets)
        right_by_slot = self._assets_by_slot(pipeline, right_assets)
        slot_keys = sorted(
            set(left_by_slot) | set(right_by_slot),
            key=lambda key: self._slot_sort_key(pipeline, key, left_by_slot.get(key) or right_by_slot.get(key)),
        )
        rows: list[PhaseComparisonRow] = []
        for slot_key in slot_keys:
            left_asset = left_by_slot.get(slot_key)
            right_asset = right_by_slot.get(slot_key)
            rows.append(
                PhaseComparisonRow(
                    slot_key=slot_key,
                    slot_label=self._slot_label(pipeline, left_asset or right_asset),
                    pipeline=pipeline,
                    left=self._side_payload(left_phase, left_asset),
                    right=self._side_payload(right_phase, right_asset),
                )
            )
        return rows

    def _assets_by_slot(self, pipeline: str, assets: list[Asset]) -> dict[str, Asset]:
        """Index assets by normalized comparison slot."""
        indexed: dict[str, Asset] = {}
        for asset in sorted(assets, key=lambda item: item.asset_id):
            indexed.setdefault(self._slot_key(pipeline, asset), asset)
        return indexed

    def _slot_key(self, pipeline: str, asset: Asset) -> str:
        """Return the normalized matching key for an asset."""
        parts = [self._normalize_slot_part(asset.body_view)]
        if pipeline in {"Head-Image", "Head-Fitment", "Character-Assembly", "Costume-Dressing", "Expression"}:
            parts.append(self._normalize_slot_part(asset.head_view))
        if pipeline == "Expression":
            parts.append(self._normalize_slot_part(asset.expression))
        return "|".join(parts)

    def _slot_label(self, pipeline: str, asset: Asset | None) -> str:
        """Return a human-readable label for a comparison slot."""
        if asset is None:
            return "Unknown slot"
        parts = [str(asset.body_view or "")]
        if pipeline in {"Head-Image", "Head-Fitment", "Character-Assembly", "Costume-Dressing", "Expression"} and asset.head_view:
            parts.append(str(asset.head_view))
        if pipeline == "Expression" and asset.expression:
            parts.append(str(asset.expression))
        return " / ".join(part for part in parts if part)

    def _costume_options(self, assets: list[Asset]) -> list[str]:
        """Return sorted costume labels represented by locked assets."""
        return sorted({str(asset.costume or "") for asset in assets if str(asset.costume or "").strip()})

    def _side_payload(self, phase: str, asset: Asset | None) -> PhaseComparisonSide:
        """Return display data for one side of a comparison row."""
        if asset is None:
            return PhaseComparisonSide(
                phase=phase,
                asset_id=None,
                image_path=None,
                image_exists=False,
                label="No locked asset for this slot",
                body_view=None,
                head_view=None,
                costume=None,
                expression=None,
                updated_at=None,
            )
        image_path = self.path_service.locked_image_path(asset)
        return PhaseComparisonSide(
            phase=phase,
            asset_id=asset.asset_id,
            image_path=str(image_path),
            image_exists=image_path.exists(),
            label=self._asset_label(asset),
            body_view=asset.body_view,
            head_view=asset.head_view,
            costume=asset.costume,
            expression=asset.expression,
            updated_at=asset.updated_at,
        )

    def _asset_label(self, asset: Asset) -> str:
        """Return a compact asset label for display."""
        label_parts = [f"Asset {asset.asset_id}", asset.pipeline, asset.body_view]
        if asset.head_view:
            label_parts.append(asset.head_view)
        if asset.costume:
            label_parts.append(asset.costume)
        if asset.expression:
            label_parts.append(asset.expression)
        return " | ".join(str(part) for part in label_parts if part)

    def _slot_sort_key(self, pipeline: str, slot_key: str, asset: Asset | None) -> tuple:
        """Return a stable natural sort key for comparison slots."""
        body = asset.body_view if asset else slot_key.split("|")[0]
        head = asset.head_view if asset else ""
        return (
            self._view_sort_index(body),
            self._view_sort_index(head),
            str(asset.costume or "") if asset else "",
            str(asset.expression or "") if asset else "",
            asset.asset_id if asset else 0,
            slot_key,
        )

    def _view_sort_index(self, view: object) -> int:
        """Return the canonical order index for a view string."""
        order = self._view_order()
        normalized = self._normalize_view_key(view)
        return order.get(normalized, 999)

    def _view_order(self) -> dict[str, int]:
        """Read canonical view order from Prompt_View_Text.json."""
        path = self.project_root / "Config" / "Prompt_View_Text.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        views = data.get("views", {}) if isinstance(data, dict) else {}
        return {self._normalize_view_key(value.get("output_name_fragment") or value.get("folder_name") or key): index for index, (key, value) in enumerate(views.items()) if isinstance(value, dict)}

    def _selected_index(self, rows: list[PhaseComparisonRow], selected_index: int, selected_slot_key: str) -> int:
        """Return the selected row index after preserving slot when possible."""
        if not rows:
            return 0
        if selected_slot_key:
            for index, row in enumerate(rows):
                if row.slot_key == selected_slot_key:
                    return index
        return max(0, min(int(selected_index or 0), len(rows) - 1))

    def _normalize_slot_part(self, value: object) -> str:
        """Normalize one slot-key part."""
        return str(value or "").strip().casefold()

    def _normalize_view_key(self, value: object) -> str:
        """Normalize a view value to a canonical uppercase key."""
        return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")
