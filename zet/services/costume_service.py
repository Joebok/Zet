from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from zet.models.asset import Asset
from zet.models.costume import Costume
from zet.repositories.asset_repository import AssetRepository
from zet.services.path_service import PathService
from zet.services.turnaround_views import TURNAROUND_VIEW_ORDER
from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections
from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


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

    @staticmethod
    def _replace_costume_paths(value: Any, old_path: str, new_path: str, old_name: str, new_name: str) -> Any:
        """Update costume identity and moved workspace paths in structured metadata."""
        if isinstance(value, dict):
            return {
                key: CostumeService._replace_costume_paths(item, old_path, new_path, old_name, new_name)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [CostumeService._replace_costume_paths(item, old_path, new_path, old_name, new_name) for item in value]
        if isinstance(value, str):
            if value == old_name:
                return new_name
            return value.replace(old_path, new_path)
        return value

    def _rename_local_costume_data(self, character: str, phase: str, old_name: str, new_name: str) -> None:
        """Move costume-scoped local runs and update their path-bearing metadata."""
        if old_name == new_name:
            return
        old_folder = re.sub(r"[^A-Za-z0-9_-]+", "_", old_name).strip("_") or "Costume"
        new_folder = re.sub(r"[^A-Za-z0-9_-]+", "_", new_name).strip("_") or "Costume"
        experiment_root = self.path_service.library_path("Experiments", "Character-Pipeline", character, phase)
        old_workspace = experiment_root / "Costume-Dressing" / old_folder
        new_workspace = experiment_root / "Costume-Dressing" / new_folder
        old_locked = experiment_root / "locked" / "Costume-Dressing" / old_folder
        new_locked = experiment_root / "locked" / "Costume-Dressing" / new_folder
        if old_workspace.exists() and new_workspace.exists():
            raise CostumeServiceError(f"Local Costume-Dressing workspace already exists: {new_workspace}")
        if old_locked.exists() and new_locked.exists():
            raise CostumeServiceError(f"Local locked Costume-Dressing assets already exist: {new_locked}")
        if old_workspace.exists() and old_workspace != new_workspace:
            old_template = f"Costume_{old_folder}.md"
            new_template = f"Costume_{new_folder}.md"
            if any(path.with_name(new_template).exists() for path in old_workspace.rglob(old_template)):
                raise CostumeServiceError(f"Local costume template snapshot already exists under {new_workspace}")
            old_workspace.rename(new_workspace)
            old_root_text, new_root_text = str(old_workspace), str(new_workspace)
            for metadata_path in new_workspace.rglob("*.json"):
                if metadata_path.name not in {"spec.json", "state.json", "ask_manifest.json", "answer_manifest.json"}:
                    continue
                try:
                    data = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                updated = self._replace_costume_paths(data, old_root_text, new_root_text, old_name, new_name)
                updated = self._replace_costume_paths(updated, old_template, new_template, "", "")
                if updated != data:
                    write_json_atomic(metadata_path, updated)
            for snapshot in new_workspace.rglob(old_template):
                target = snapshot.with_name(new_template)
                text = snapshot.read_text(encoding="utf-8")
                text = re.sub(r"^(\s*Costume Name\s*:\s*`?\[?)" + re.escape(old_name) + r"(\]?`?\s*)$",
                              rf"\g<1>{new_name}\g<2>", text, count=1, flags=re.IGNORECASE | re.MULTILINE)
                self._write_text_atomic(snapshot, text)
                snapshot.rename(target)

        store_path = experiment_root / "local_assets.json"
        if not store_path.is_file():
            return
        with file_lock(store_path.with_suffix(".lock")):
            store = json.loads(store_path.read_text(encoding="utf-8"))
            assets = store.get("assets", {})
            old_qualifier = re.sub(r"[^a-z0-9_-]+", "_", old_name.strip().lower()).strip("_")
            new_qualifier = re.sub(r"[^a-z0-9_-]+", "_", new_name.strip().lower()).strip("_")
            for key, record in list(assets.items()):
                if str(record.get("pipeline", "")).lower() != "costume-dressing" or str(record.get("qualifier") or "").lower() != old_name.lower():
                    continue
                new_key = key.replace(f":{old_qualifier}:", f":{new_qualifier}:")
                if new_key != key and new_key in assets:
                    raise CostumeServiceError(f"Local costume asset already exists for {new_name}: {new_key}")
                updated = self._replace_costume_paths(record, str(old_workspace), str(new_workspace), old_name, new_name)
                updated = self._replace_costume_paths(updated, str(old_locked), str(new_locked), old_name, new_name)
                updated["qualifier"] = new_name
                assets.pop(key)
                assets[new_key] = updated
            write_json_atomic(store_path, store)
        if old_locked.exists() and old_locked != new_locked:
            old_locked.rename(new_locked)

    def _rename_turnaround_data(self, character: str, phase: str, old_name: str, new_name: str) -> None:
        """Keep tracked Costume-Dressing turnaround metadata and files aligned."""
        if old_name == new_name:
            return
        path = self.path_service.character_path(character, phase) / "TurnaroundSheets.json"
        if not path.is_file():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("turnarounds", [])
        old_slug = re.sub(r"[^A-Za-z0-9]+", "-", old_name).strip("-") or "default"
        new_slug = re.sub(r"[^A-Za-z0-9]+", "-", new_name).strip("-") or "default"
        old_id = f"Costume-Dressing_{old_slug}"
        new_id = f"Costume-Dressing_{new_slug}"
        old_records = [record for record in records if isinstance(record, dict)
                       and record.get("source_pipeline") == "Costume-Dressing" and record.get("costume") == old_name]
        if not old_records:
            return
        has_new = any(isinstance(record, dict) and record.get("turnaround_id") == new_id for record in records)
        pipeline_root = self.path_service.pipeline_base_path(character, phase) / "Turnaround"
        old_pipeline = pipeline_root / old_id
        new_pipeline = pipeline_root / new_id
        locked_root = self.path_service.character_asset_path(character, phase) / "Turnarounds"
        old_locked = locked_root / f"{old_id}.png"
        new_locked = locked_root / f"{new_id}.png"
        if not has_new and old_pipeline.exists():
            if new_pipeline.exists():
                raise CostumeServiceError(f"Turnaround pipeline directory already exists: {new_pipeline}")
            for old_file in old_pipeline.rglob("*"):
                if old_file.is_file() and old_id in old_file.name:
                    new_file = old_file.with_name(old_file.name.replace(old_id, new_id))
                    if new_file.exists():
                        raise CostumeServiceError(f"Turnaround file already exists: {new_file}")
        if not has_new and old_locked.exists() and new_locked.exists():
            raise CostumeServiceError(f"Turnaround image already exists: {new_locked}")
        if old_pipeline.exists() and not has_new:
            old_pipeline.rename(new_pipeline)
            for old_file in list(new_pipeline.rglob("*")):
                if not old_file.is_file() or old_id not in old_file.name:
                    continue
                new_file = old_file.with_name(old_file.name.replace(old_id, new_id))
                old_file.rename(new_file)
            for metadata_path in new_pipeline.rglob("*.json"):
                try:
                    data = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                updated = self._replace_costume_paths(data, old_id, new_id, old_name, new_name)
                if updated != data:
                    write_json_atomic(metadata_path, updated)
        if old_locked.exists() and not has_new:
            old_locked.rename(new_locked)
        updated_records = []
        for record in records:
            if not isinstance(record, dict) or record.get("source_pipeline") != "Costume-Dressing" or record.get("costume") != old_name:
                updated_records.append(record)
                continue
            if has_new:
                continue
            updated = dict(record)
            updated["turnaround_id"] = new_id
            updated["costume"] = new_name
            updated["label"] = str(updated.get("label") or "").replace(old_name, new_name)
            for field in ("candidate_image_path", "locked_image_path", "analysis_path", "diagnostics_path"):
                if updated.get(field):
                    updated[field] = str(updated[field]).replace(old_id, new_id)
            updated_records.append(updated)
        payload["turnarounds"] = updated_records
        write_json_atomic(path, payload)

    def _rename_asset_images(self, assets: list[Asset], old_names: dict[int, str]) -> None:
        """Rename traditional pipeline and locked images without overwriting files."""
        moves: list[tuple[Path, Path]] = []
        for asset in assets:
            old_output = old_names.get(asset.asset_id)
            new_output = asset.final_image_output
            if not old_output or not new_output or old_output == new_output:
                continue
            moves.extend((
                (self.path_service.character_asset_path(asset.character, asset.phase) / old_output,
                 self.path_service.character_asset_path(asset.character, asset.phase) / new_output),
                (self.path_service.pipeline_path(asset) / old_output, self.path_service.pipeline_path(asset) / new_output),
            ))
        for source, destination in moves:
            if source.exists() and destination.exists():
                raise CostumeServiceError(f"Cannot rename costume image because the destination already exists: {destination}")
        for source, destination in moves:
            if source.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.rename(destination)
        for asset in assets:
            old_output = old_names.get(asset.asset_id)
            new_output = asset.final_image_output
            if not old_output or not new_output or old_output == new_output:
                continue
            asset_root = self.path_service.pipeline_path(asset)
            if not asset_root.is_dir():
                continue
            for metadata_path in asset_root.rglob("*.json"):
                try:
                    data = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                updated = self._replace_costume_paths(data, old_output, new_output, "", "")
                if updated != data:
                    write_json_atomic(metadata_path, updated)

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
        old_output_names: dict[int, str] = {}
        for asset in self.asset_repository.list_assets(character, phase):
            if asset.pipeline != "Costume-Dressing":
                continue
            stored_costume_path = self.path_service.resolve_path(asset.costume_path) if asset.costume_path else Path()
            if asset.costume != existing.name and stored_costume_path != old_path:
                continue
            updated_asset = replace(asset)
            if asset.asset_id > 0 and asset.final_image_output:
                old_output_names[asset.asset_id] = asset.final_image_output
            updated_asset.costume = display_name
            updated_asset.costume_path = str(new_path)
            updated_asset.final_image_output = f"Costume-Dressing_{asset.body_view}_{asset.body_view}_{new_slug.replace('_', '-')}.png"
            updated_asset.updated_at = self._timestamp()
            updated_assets.append(updated_asset)

        existing_views = {asset.body_view for asset in updated_assets}
        missing_assets = [
            Asset(
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
                final_image_output=f"Costume-Dressing_{view}_{view}_{new_slug.replace('_', '-')}.png",
                updated_at=self._timestamp(),
                costume_path=str(new_path),
            )
            for view in TURNAROUND_VIEW_ORDER
            if view not in existing_views
        ]

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

        created_assets = self.asset_repository.create_assets(missing_assets)
        self._rename_asset_images(updated_assets, old_output_names)
        self._rename_local_costume_data(character, phase, existing.name, display_name)
        self._rename_turnaround_data(character, phase, existing.name, display_name)

        return CostumeUpdateResult(
            costume=self._costume_from_path(character, phase, new_path),
            assets=updated_assets + created_assets,
        )
