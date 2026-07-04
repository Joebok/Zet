from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.models.costume import Costume
from zet.repositories.asset_repository import AssetRepository
from zet.services.path_service import PathService
from zet.services.turnaround_service import TURNAROUND_VIEW_ORDER


@dataclass(frozen=True)
class CostumeCreateResult:
    """Describe a newly saved costume and its generated assets."""
    costume: Costume
    assets: list[Asset]


class CostumeServiceError(Exception):
    """Report costume workflow failures."""


class CostumeService:
    """Manage costume templates and related Costume-Dressing assets."""

    def __init__(self, asset_repository: AssetRepository, path_service: PathService):
        """Create a costume service."""
        self.asset_repository = asset_repository
        self.path_service = path_service

    def _timestamp(self) -> str:
        """Return an ISO timestamp for generated assets."""
        return datetime.now().isoformat(timespec="seconds")

    def safe_costume_slug(self, costume_name: str) -> str:
        """Return the canonical costume filename slug."""
        text = str(costume_name or "").strip()
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in text)
        safe = "_".join(part for part in safe.replace("-", "_").split("_") if part)
        return safe or "Costume"

    def costume_name_from_slug(self, slug: str) -> str:
        """Return a display costume name from a canonical filename slug."""
        return " ".join(part for part in str(slug or "").replace("-", "_").split("_") if part)

    def _extract_template_field(self, contents: str, labels: list[str]) -> str:
        """Extract a bracketed or plain metadata field from markdown."""
        for label in labels:
            pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
            match = pattern.search(contents)
            if match:
                value = match.group(1).strip().strip("` ").strip()
                bracketed = re.match(r"^\[(.*)\]$", value)
                return (bracketed.group(1) if bracketed else value).strip("` ").strip()
        return ""

    def _costume_from_path(self, character: str, phase: str, path: Path) -> Costume:
        """Create a costume summary from a markdown path."""
        contents = path.read_text(encoding="utf-8")
        name = self.costume_name_from_slug(path.stem.removeprefix("Costume_"))
        role = self._extract_template_field(contents, ["Costume Role", "Role"]) or None
        assets = [
            asset
            for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Costume-Dressing" and asset.costume == name
        ]
        return Costume(
            name=name,
            slug=self.safe_costume_slug(name),
            path=str(path),
            role=role,
            asset_count=len(assets),
        )

    def _sync_costume_name(self, markdown: str, costume_name: str) -> str:
        """Return markdown with the Costume Name field set to the dashboard name."""
        replacement = f"Costume Name: `[{costume_name}]`"
        pattern = re.compile(r"^\s*Costume Name\s*:\s*.+?\s*$", re.IGNORECASE | re.MULTILINE)
        if pattern.search(markdown):
            return pattern.sub(replacement, markdown, count=1)
        lines = markdown.splitlines()
        if lines and lines[0].startswith("#"):
            lines.insert(1, "")
            lines.insert(2, replacement)
            return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")
        return f"{replacement}\n\n{markdown}"

    def list_costumes(self, character: str, phase: str) -> list[Costume]:
        """List costume templates for a character phase."""
        root = self.path_service.character_path(character, phase)
        costumes = [self._costume_from_path(character, phase, path) for path in sorted(root.glob("Costume_*.md"))]
        return sorted(costumes, key=lambda costume: costume.name.lower())

    def create_costume(self, character: str, phase: str, costume_name: str, markdown: str) -> CostumeCreateResult:
        """Save a new costume template and create its eight Costume-Dressing assets."""
        costume_name = str(costume_name or "").strip()
        if not costume_name:
            raise CostumeServiceError("Costume name is required.")
        if not str(markdown or "").strip():
            raise CostumeServiceError("Costume markdown is required.")
        costume_slug = self.safe_costume_slug(costume_name)
        display_name = self.costume_name_from_slug(costume_slug)
        costume_path = self.path_service.costume_template_path(character, phase, display_name)
        if costume_path.exists():
            raise CostumeServiceError(f"Costume template already exists: {costume_path.name}")
        existing = [
            asset
            for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == "Costume-Dressing" and asset.costume == display_name
        ]
        if existing:
            raise CostumeServiceError(f"Costume-Dressing assets already exist for {display_name}.")
        costume_path.write_text(self._sync_costume_name(markdown, display_name), encoding="utf-8")
        assets = []
        for view in TURNAROUND_VIEW_ORDER:
            output_name = f"Costume-Dressing_{view}_{view}_{costume_slug.replace('_', '-')}.png"
            asset = Asset(
                asset_id=0,
                character=character,
                phase=phase,
                pipeline="Costume-Dressing",
                body_view=view,
                head_view=view,
                costume=display_name,
                expression=None,
                asset_state="NEW",
                pipeline_stage="ADD_REF",
                actor="PYTHON",
                ai_state=None,
                final_image_output=output_name,
                updated_at=self._timestamp(),
                costume_path=str(costume_path),
            )
            assets.append(self.asset_repository.create_asset(asset))
        return CostumeCreateResult(
            costume=self._costume_from_path(character, phase, costume_path),
            assets=assets,
        )
