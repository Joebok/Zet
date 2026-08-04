from __future__ import annotations

import re
from dataclasses import dataclass, replace
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


@dataclass(frozen=True)
class ExpressionUpdateResult:
    """Describe an updated expression definition and asset."""
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

    def _write_text_atomic(self, path: Path, contents: str) -> None:
        """Replace a text file without exposing a partial write."""
        temp_path = path.with_name(f"{path.name}.tmp")
        try:
            temp_path.write_text(contents, encoding="utf-8")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

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

    def _default_expression_markdown(self) -> str:
        """Return the shared expression template contents."""
        template_path = self.path_service.shared_expression_template_path()
        if not template_path.exists():
            raise ExpressionServiceError(f"Shared expression template is missing: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def _sync_expression_label(self, markdown: str, label: str, path: Path) -> str:
        """Return markdown with basic expression metadata set to the dashboard values."""
        text = str(markdown or "")
        replacements = {
            r"^\s*Expression label\s*:\s*.+?\s*$": f"Expression label: {label}.",
            r"^\s*Expression definition\s*:\s*.+?\s*$": f"Expression definition: {path}.",
        }
        for pattern, replacement in replacements.items():
            compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            if compiled.search(text):
                text = compiled.sub(lambda _match, value=replacement: value, text, count=1)
        return text

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

        cleaned_markdown = str(markdown or "").strip() or self._default_expression_markdown()
        contents = self._sync_expression_label(cleaned_markdown, display_label, definition_path).rstrip() + "\n"
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
        self._write_text_atomic(definition_path, contents)
        try:
            created = self.asset_repository.create_assets([asset])[0]
        except Exception:
            definition_path.unlink(missing_ok=True)
            raise
        return ExpressionCreateResult(
            expression=self._definition_from_path(character, phase, definition_path),
            asset=created,
        )

    def update_expression(
        self,
        character: str,
        phase: str,
        asset_id: int,
        label: str,
        identity_key_id: str,
    ) -> ExpressionUpdateResult:
        """Update an expression label, definition path, and identity-key binding."""
        cleaned_label = str(label or "").strip()
        cleaned_key = str(identity_key_id or "").strip()
        if not cleaned_label:
            raise ExpressionServiceError("Expression label is required.")
        if not cleaned_key:
            raise ExpressionServiceError("Identity Key is required.")

        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Expression":
            raise ExpressionServiceError(f"Asset {asset_id} is not an Expression asset.")
        identity_key = self.identity_key_repository.get_identity_key(character, phase, cleaned_key)

        root = self.path_service.expressions_path(character, phase)
        root.mkdir(parents=True, exist_ok=True)
        new_slug = self.safe_expression_slug(cleaned_label)
        display_label = self.expression_label_from_slug(new_slug)
        old_path = self.path_service.resolve_path(asset.expression_definition_path) if asset.expression_definition_path else root / f"{self.safe_expression_slug(asset.expression or display_label)}.md"
        new_path = root / f"{new_slug}.md"
        if old_path != new_path and new_path.exists():
            raise ExpressionServiceError(f"Expression definition already exists: {new_path.name}")

        old_path_existed = old_path.exists()
        contents = old_path.read_text(encoding="utf-8") if old_path_existed else self._default_expression_markdown()
        updated_contents = self._sync_expression_label(contents, display_label, new_path)
        updated_asset = replace(asset)
        updated_asset.expression = display_label
        updated_asset.identity_key_id = identity_key.identity_key_id
        updated_asset.body_view = identity_key.source_body_view
        updated_asset.head_view = identity_key.source_head_view
        updated_asset.costume = identity_key.source_costume
        updated_asset.expression_definition_path = str(new_path)
        updated_asset.final_image_output = f"Expression_{new_slug}.png"
        updated_asset.updated_at = self._timestamp()
        new_contents = updated_contents.rstrip() + "\n"
        if old_path != new_path:
            self._write_text_atomic(new_path, new_contents)
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                new_path.unlink(missing_ok=True)
                raise
        else:
            self._write_text_atomic(old_path, new_contents)
        try:
            self.asset_repository.save_assets([updated_asset])
        except Exception:
            if old_path != new_path:
                if old_path_existed:
                    self._write_text_atomic(old_path, contents)
                new_path.unlink(missing_ok=True)
            elif not old_path_existed:
                old_path.unlink(missing_ok=True)
            else:
                self._write_text_atomic(old_path, contents)
            raise

        return ExpressionUpdateResult(
            expression=self._definition_from_path(character, phase, new_path),
            asset=updated_asset,
        )
