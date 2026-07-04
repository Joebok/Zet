from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.models.expression import ExpressionDefinition
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.services.path_service import PathService


@dataclass(frozen=True)
class ExpressionCreateResult:
    """Describe a newly saved expression definition and asset."""
    expression: ExpressionDefinition
    asset: Asset


class ExpressionServiceError(Exception):
    """Report expression workflow failures."""


class ExpressionService:
    """Manage expression definitions and related Expression pipeline assets."""

    def __init__(
        self,
        asset_repository: AssetRepository,
        identity_key_repository: IdentityKeyRepository,
        path_service: PathService,
    ):
        """Create an expression service."""
        self.asset_repository = asset_repository
        self.identity_key_repository = identity_key_repository
        self.path_service = path_service

    def _timestamp(self) -> str:
        """Return an ISO timestamp for generated assets."""
        return datetime.now().isoformat(timespec="seconds")

    def safe_expression_slug(self, label: str) -> str:
        """Return the canonical expression filename slug."""
        text = str(label or "").strip()
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in text)
        safe = "_".join(part for part in safe.replace("-", "_").split("_") if part)
        return safe or "Expression"

    def expression_label_from_slug(self, slug: str) -> str:
        """Return a display expression label from a filename slug."""
        return " ".join(part for part in str(slug or "").replace("-", "_").split("_") if part)

    def _definition_from_path(self, character: str, phase: str, path: Path) -> ExpressionDefinition:
        """Create an expression definition summary from a markdown path."""
        label = self.expression_label_from_slug(path.stem)
        assets = [
            asset
            for asset in self.list_expression_assets(character, phase)
            if asset.expression == label and asset.expression_definition_path == str(path)
        ]
        return ExpressionDefinition(
            label=label,
            slug=self.safe_expression_slug(label),
            path=str(path),
            asset_count=len(assets),
        )

    def list_expression_assets(self, character: str, phase: str) -> list[Asset]:
        """List Expression assets for a character phase."""
        return [
            asset
            for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Expression"
        ]

    def list_expression_definitions(self, character: str, phase: str) -> list[ExpressionDefinition]:
        """List expression definition markdown files for a character phase."""
        root = self.path_service.expressions_path(character, phase)
        if not root.exists():
            return []
        return [
            self._definition_from_path(character, phase, path)
            for path in sorted(root.glob("*.md"))
            if path.is_file()
        ]

    def create_expression(
        self,
        character: str,
        phase: str,
        label: str,
        identity_key_id: str,
        markdown: str,
    ) -> ExpressionCreateResult:
        """Save a new expression definition and create one Expression asset."""
        label = str(label or "").strip()
        identity_key_id = str(identity_key_id or "").strip()
        if not label:
            raise ExpressionServiceError("Expression label is required.")
        if not identity_key_id:
            raise ExpressionServiceError("Identity Key is required.")
        if not str(markdown or "").strip():
            raise ExpressionServiceError("Expression markdown is required.")

        identity_key = self.identity_key_repository.get_identity_key(character, phase, identity_key_id)
        root = self.path_service.expressions_path(character, phase)
        root.mkdir(parents=True, exist_ok=True)
        slug = self.safe_expression_slug(label)
        display_label = self.expression_label_from_slug(slug)
        definition_path = root / f"{slug}.md"
        if definition_path.exists():
            raise ExpressionServiceError(f"Expression definition already exists: {definition_path.name}")

        existing = [
            asset
            for asset in self.list_expression_assets(character, phase)
            if asset.expression == display_label and asset.identity_key_id == identity_key_id
        ]
        if existing:
            raise ExpressionServiceError(f"Expression asset already exists for {display_label} with this Identity Key.")

        definition_path.write_text(str(markdown).strip() + "\n", encoding="utf-8")
        output_name = f"Expression_{slug}.png"
        asset = Asset(
            asset_id=0,
            character=character,
            phase=phase,
            pipeline="Expression",
            body_view=identity_key.source_body_view,
            head_view=identity_key.source_head_view,
            costume=identity_key.source_costume,
            expression=display_label,
            asset_state="NEW",
            pipeline_stage="MANIFEST",
            actor="PYTHON",
            ai_state=None,
            final_image_output=output_name,
            updated_at=self._timestamp(),
            identity_key_id=identity_key.identity_key_id,
            expression_definition_path=str(definition_path),
        )
        created = self.asset_repository.create_asset(asset)
        return ExpressionCreateResult(
            expression=self._definition_from_path(character, phase, definition_path),
            asset=created,
        )
