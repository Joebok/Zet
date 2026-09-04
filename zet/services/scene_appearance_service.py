from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from zet.models.asset import Asset
from zet.models.scene_appearance import SceneAppearanceDefinition, SceneAppearanceReference
from zet.repositories.asset_repository import AssetRepository
from zet.services.atomic_file_service import write_text_atomic
from zet.services.path_service import PathService
from zet.services.turnaround_views import TURNAROUND_VIEW_ORDER


SCENE_APPEARANCE_SCHEMA_VERSION = 1
SCENE_APPEARANCE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")


@dataclass(frozen=True)
class SceneAppearanceCreateResult:
    appearance: SceneAppearanceDefinition
    assets: list[Asset]


@dataclass(frozen=True)
class SceneAppearanceUpdateResult:
    appearance: SceneAppearanceDefinition
    assets: list[Asset]
    render_changed: bool


class SceneAppearanceServiceError(Exception):
    """Report invalid Scene Appearance definitions or asset bindings."""


class SceneAppearanceService:
    """Manage reusable Scene Appearance definitions and their view assets."""

    def __init__(self, asset_repository: AssetRepository, path_service: PathService):
        self.asset_repository = asset_repository
        self.path_service = path_service

    @staticmethod
    def safe_id(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "scene-appearance"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _definition_path(self, character: str, phase: str, appearance_id: str) -> Path:
        return self.path_service.scene_appearance_definition_path(character, phase, appearance_id)

    def _reference(self, value: dict | SceneAppearanceReference) -> SceneAppearanceReference:
        if isinstance(value, SceneAppearanceReference):
            reference = value
        elif isinstance(value, dict):
            reference = SceneAppearanceReference(
                role=str(value.get("role") or "").strip(),
                label=str(value.get("label") or "").strip(),
                tag=str(value.get("tag") or "").strip(),
            )
        else:
            raise SceneAppearanceServiceError("Supporting references must be objects.")
        if not reference.role or not reference.label or not reference.tag:
            raise SceneAppearanceServiceError("Each supporting reference requires role, label, and tag.")
        return reference

    def _validated_values(
        self,
        character: str,
        phase: str,
        appearance_id: str,
        name: str,
        costume: str,
        instructions: str,
        supporting_references: list[dict | SceneAppearanceReference],
    ) -> tuple[str, str, str, str, list[SceneAppearanceReference]]:
        appearance_id = str(appearance_id or "").strip()
        name = str(name or "").strip()
        costume = str(costume or "").strip()
        instructions = str(instructions or "").strip()
        if not SCENE_APPEARANCE_ID_RE.fullmatch(appearance_id):
            raise SceneAppearanceServiceError("Scene Appearance ID must use lowercase letters, numbers, and hyphens.")
        if not name:
            raise SceneAppearanceServiceError("Scene Appearance name is required.")
        if not costume:
            raise SceneAppearanceServiceError("Base costume is required.")
        if not instructions:
            raise SceneAppearanceServiceError("Arrangement instructions are required.")
        references = [self._reference(item) for item in supporting_references]
        if not references:
            raise SceneAppearanceServiceError("At least one supporting reference is required.")
        roles = [item.role for item in references]
        if len(set(roles)) != len(roles):
            raise SceneAppearanceServiceError("Supporting reference roles must be unique.")
        try:
            resolved = auxiliary_references_for_texts(
                self.path_service.project_root,
                ["\n".join(item.tag for item in references)],
                [],
            )
        except Exception as exc:
            raise SceneAppearanceServiceError(str(exc)) from exc
        if len(resolved) != len(references):
            raise SceneAppearanceServiceError("Every supporting reference tag must resolve to one image.")
        source_assets = [
            asset
            for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Costume-Dressing" and asset.costume == costume
        ]
        source_views = {asset.body_view for asset in source_assets}
        missing = [view for view in TURNAROUND_VIEW_ORDER if view not in source_views]
        if missing:
            raise SceneAppearanceServiceError(
                f"Base costume {costume} is missing Costume-Dressing assets for: {', '.join(missing)}"
            )
        return appearance_id, name, costume, instructions, references

    def _payload(self, definition: SceneAppearanceDefinition) -> dict:
        return {
            "schema_version": SCENE_APPEARANCE_SCHEMA_VERSION,
            "appearance_id": definition.appearance_id,
            "name": definition.name,
            "character": definition.character,
            "phase": definition.phase,
            "costume": definition.costume,
            "instructions": definition.instructions,
            "supporting_references": [asdict(reference) for reference in definition.supporting_references],
        }

    def _write_definition(self, path: Path, definition: SceneAppearanceDefinition) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(path, json.dumps(self._payload(definition), indent=2) + "\n")

    def _from_path(self, character: str, phase: str, path: Path) -> SceneAppearanceDefinition:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SceneAppearanceServiceError(f"Invalid Scene Appearance definition {path}: {exc}") from exc
        if int(payload.get("schema_version") or 0) != SCENE_APPEARANCE_SCHEMA_VERSION:
            raise SceneAppearanceServiceError(f"Unsupported Scene Appearance schema version in {path}.")
        references = [self._reference(item) for item in payload.get("supporting_references") or []]
        appearance_id = str(payload.get("appearance_id") or path.stem).strip()
        assets = [
            asset
            for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Scene-Appearance" and asset.scene_appearance_id == appearance_id
        ]
        return SceneAppearanceDefinition(
            schema_version=SCENE_APPEARANCE_SCHEMA_VERSION,
            appearance_id=appearance_id,
            name=str(payload.get("name") or appearance_id).strip(),
            character=str(payload.get("character") or character).strip(),
            phase=str(payload.get("phase") or phase).strip(),
            costume=str(payload.get("costume") or "").strip(),
            instructions=str(payload.get("instructions") or "").strip(),
            supporting_references=references,
            path=str(path),
            asset_count=len(assets),
        )

    def list_definitions(self, character: str, phase: str) -> list[SceneAppearanceDefinition]:
        root = self.path_service.scene_appearances_path(character, phase)
        if not root.exists():
            return []
        return [self._from_path(character, phase, path) for path in sorted(root.glob("*.json")) if path.is_file()]

    def get_definition(self, character: str, phase: str, appearance_id: str) -> SceneAppearanceDefinition:
        path = self._definition_path(character, phase, appearance_id)
        if not path.is_file():
            raise SceneAppearanceServiceError(f"Scene Appearance not found: {appearance_id}")
        return self._from_path(character, phase, path)

    def create(
        self,
        character: str,
        phase: str,
        appearance_id: str,
        name: str,
        costume: str,
        instructions: str,
        supporting_references: list[dict | SceneAppearanceReference],
    ) -> SceneAppearanceCreateResult:
        appearance_id, name, costume, instructions, references = self._validated_values(
            character, phase, appearance_id, name, costume, instructions, supporting_references
        )
        path = self._definition_path(character, phase, appearance_id)
        if path.exists():
            raise SceneAppearanceServiceError(f"Scene Appearance already exists: {appearance_id}")
        existing = [
            asset for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Scene-Appearance" and asset.scene_appearance_id == appearance_id
        ]
        if existing:
            raise SceneAppearanceServiceError(f"Scene-Appearance assets already exist for {appearance_id}.")
        definition = SceneAppearanceDefinition(
            SCENE_APPEARANCE_SCHEMA_VERSION,
            appearance_id,
            name,
            character,
            phase,
            costume,
            instructions,
            references,
            str(path),
            len(TURNAROUND_VIEW_ORDER),
        )
        assets = [
            Asset(
                asset_id=0,
                character=character,
                phase=phase,
                pipeline="Scene-Appearance",
                body_view=view,
                head_view=view,
                costume=costume,
                asset_state="NEW",
                pipeline_stage="ADD_REF",
                actor="PYTHON",
                final_image_output=f"Scene-Appearance_{view}_{appearance_id}.png",
                updated_at=self._timestamp(),
                scene_appearance_id=appearance_id,
                scene_appearance=name,
                scene_appearance_definition_path=str(path),
            )
            for view in TURNAROUND_VIEW_ORDER
        ]
        self._write_definition(path, definition)
        try:
            created = self.asset_repository.create_assets(assets)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return SceneAppearanceCreateResult(replace(definition, asset_count=len(created)), created)

    def update(
        self,
        character: str,
        phase: str,
        appearance_id: str,
        name: str,
        costume: str,
        instructions: str,
        supporting_references: list[dict | SceneAppearanceReference],
    ) -> SceneAppearanceUpdateResult:
        current = self.get_definition(character, phase, appearance_id)
        appearance_id, name, costume, instructions, references = self._validated_values(
            character, phase, appearance_id, name, costume, instructions, supporting_references
        )
        path = self._definition_path(character, phase, appearance_id)
        render_changed = (
            current.costume != costume
            or current.instructions != instructions
            or current.supporting_references != references
        )
        assets = [
            asset for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Scene-Appearance" and asset.scene_appearance_id == appearance_id
        ]
        if {asset.body_view for asset in assets} != set(TURNAROUND_VIEW_ORDER):
            raise SceneAppearanceServiceError("Scene Appearance must have exactly one asset for every turnaround view.")
        updated_assets = []
        for asset in assets:
            updated = replace(
                asset,
                costume=costume,
                scene_appearance=name,
                scene_appearance_definition_path=str(path),
                updated_at=self._timestamp(),
            )
            if render_changed:
                updated = replace(
                    updated,
                    asset_state="IN_PROGRESS",
                    pipeline_stage="ADD_REF",
                    actor="PYTHON",
                    ai_state=None,
                    reference_files=[],
                    error_code=None,
                    error_message=None,
                )
            updated_assets.append(updated)
        definition = SceneAppearanceDefinition(
            SCENE_APPEARANCE_SCHEMA_VERSION,
            appearance_id,
            name,
            character,
            phase,
            costume,
            instructions,
            references,
            str(path),
            len(updated_assets),
        )
        original_text = path.read_text(encoding="utf-8")
        self._write_definition(path, definition)
        try:
            self.asset_repository.save_assets(updated_assets)
        except Exception:
            write_text_atomic(path, original_text)
            raise
        return SceneAppearanceUpdateResult(definition, updated_assets, render_changed)
