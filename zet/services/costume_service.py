from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.models.costume import Costume
from zet.repositories.asset_repository import AssetRepository
from zet.services.path_service import PathService
from zet.services.turnaround_views import TURNAROUND_VIEW_ORDER
from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections


@dataclass(frozen=True)
class CostumeCreateResult:
    """Describe a newly saved costume and its generated assets."""
    costume: Costume
    assets: list[Asset]


@dataclass(frozen=True)
class CostumeUpdateResult:
    """Describe an updated costume and affected Costume-Dressing assets."""
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

    def _write_text_atomic(self, path: Path, contents: str) -> None:
        """Replace a text file without exposing a partial write."""
        temp_path = path.with_name(f"{path.name}.tmp")
        try:
            temp_path.write_text(contents, encoding="utf-8")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

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

    def _sync_costume_metadata(self, markdown: str, costume_name: str, character: str, phase: str) -> str:
        """Return costume markdown with canonical identifying metadata."""
        text = self._sync_costume_name(markdown, costume_name)
        for label, value in {"Character Name": character, "Character Phase": phase}.items():
            pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*.+?\s*$", re.IGNORECASE | re.MULTILINE)
            if pattern.search(text):
                text = pattern.sub(f"{label}: `[{value}]`", text, count=1)
        return text

    def _validate_costume_markdown(self, markdown: str) -> None:
        """Require uploaded costume markdown to follow the shared template structure."""
        template_path = self.path_service.shared_costume_template_path()
        try:
            shared_sections = load_template_sections(template_path)
            expected = set(shared_sections)
            with tempfile.TemporaryDirectory() as temp_dir:
                upload_path = Path(temp_dir) / "Costume.md"
                upload_path.write_text(markdown, encoding="utf-8")
                uploaded_sections = load_template_sections(upload_path)
                actual = set(uploaded_sections)
        except TemplateCompileError as exc:
            raise CostumeServiceError(str(exc)) from exc
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            raise CostumeServiceError(f"Costume template missing sections: {', '.join(missing)}")
        if extra:
            raise CostumeServiceError(f"Costume template has unsupported sections: {', '.join(extra)}")
        metadata_path = self.path_service.project_root / "Config" / "Prompt_Section_Metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")).get("sections", {})
        for name, record in metadata.items():
            if not isinstance(record, dict) or not record.get("required_content") or not name.startswith("COSTUME_"):
                continue
            names = [name.replace("{VIEW}", view) for view in TURNAROUND_VIEW_ORDER] if "{VIEW}" in name else [name]
            for canonical_name in names:
                if canonical_name not in expected:
                    continue
                value = str(uploaded_sections.get(canonical_name) or "").strip()
                if not value:
                    raise CostumeServiceError(f"{canonical_name} must be filled in.")
                if value == str(shared_sections.get(canonical_name) or "").strip():
                    raise CostumeServiceError(f"{canonical_name} still contains shared template placeholder text.")

    def _default_costume_markdown(self) -> str:
        """Return the shared costume template contents."""
        template_path = self.path_service.shared_costume_template_path()
        if not template_path.exists():
            raise CostumeServiceError(f"Shared costume template is missing: {template_path}")
        return template_path.read_text(encoding="utf-8")

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
        uploaded_markdown = str(markdown or "").strip()
        source_markdown = uploaded_markdown or self._default_costume_markdown()
        if uploaded_markdown:
            self._validate_costume_markdown(source_markdown)
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
            assets.append(asset)
        contents = self._sync_costume_metadata(source_markdown, display_name, character, phase).rstrip() + "\n"
        self._write_text_atomic(costume_path, contents)
        try:
            assets = self.asset_repository.create_assets(assets)
        except Exception:
            costume_path.unlink(missing_ok=True)
            raise
        return CostumeCreateResult(
            costume=self._costume_from_path(character, phase, costume_path),
            assets=assets,
        )

    def update_costume(self, character: str, phase: str, costume_slug: str, costume_name: str) -> CostumeUpdateResult:
        """Rename a costume template and update related Costume-Dressing assets."""
        cleaned_name = str(costume_name or "").strip()
        if not cleaned_name:
            raise CostumeServiceError("Costume name is required.")
        existing = None
        for costume in self.list_costumes(character, phase):
            if costume.slug == costume_slug or costume.name == costume_slug:
                existing = costume
                break
        if existing is None:
            raise CostumeServiceError(f"Costume not found: {costume_slug}")

        new_slug = self.safe_costume_slug(cleaned_name)
        display_name = self.costume_name_from_slug(new_slug)
        old_path = self.path_service.resolve_path(existing.path)
        new_path = self.path_service.costume_template_path(character, phase, display_name)
        if old_path != new_path and new_path.exists():
            raise CostumeServiceError(f"Costume template already exists: {new_path.name}")

        old_path_existed = old_path.exists()
        contents = old_path.read_text(encoding="utf-8") if old_path_existed else self._default_costume_markdown()
        updated_contents = self._sync_costume_name(contents, display_name)
        updated_assets = []
        for asset in self.asset_repository.list_assets(character, phase):
            if asset.pipeline != "Costume-Dressing":
                continue
            stored_costume_path = self.path_service.resolve_path(asset.costume_path) if asset.costume_path else Path()
            if asset.costume != existing.name and stored_costume_path != old_path:
                continue
            updated_asset = replace(asset)
            updated_asset.costume = display_name
            updated_asset.costume_path = str(new_path)
            updated_asset.final_image_output = f"Costume-Dressing_{asset.body_view}_{asset.body_view}_{new_slug.replace('_', '-')}.png"
            updated_asset.updated_at = self._timestamp()
            updated_assets.append(updated_asset)

        if old_path != new_path:
            self._write_text_atomic(new_path, updated_contents)
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                new_path.unlink(missing_ok=True)
                raise
        else:
            self._write_text_atomic(old_path, updated_contents)
        try:
            self.asset_repository.save_assets(updated_assets)
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

        return CostumeUpdateResult(
            costume=self._costume_from_path(character, phase, new_path),
            assets=updated_assets,
        )
