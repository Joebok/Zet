from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from zet.services.atomic_file_service import write_json_atomic


class LibraryDeletionServiceError(ValueError):
    """Report an invalid or incomplete library deletion."""


class LibraryDeletionService:
    """Move character phases and costumes into the library deleted folder."""

    def __init__(self, path_service, local_sources, entity_repository):
        self.paths = path_service
        self.local_sources = local_sources
        self.entity_repository = entity_repository

    @staticmethod
    def _name(value: str, label: str) -> str:
        value = str(value or "").strip()
        if not value or value in {".", ".."} or Path(value).name != value or "/" in value or "\\" in value:
            raise LibraryDeletionServiceError(f"Invalid {label}.")
        return value

    def _archive(self, character: str, phase: str, kind: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{character}_{phase}_{kind}").strip("_")
        destination = self.paths.library_path("deleted", f"{stamp}_{safe}")
        destination.mkdir(parents=True, exist_ok=False)
        return destination

    @staticmethod
    def _move(source: Path, destination: Path) -> None:
        if not source.exists():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise LibraryDeletionServiceError(f"Deleted-folder destination already exists: {destination}")
        shutil.move(str(source), str(destination))

    def _purge_assets(self, ids: list[str], archive: Path) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        rows = self.entity_repository.fetchall(
            f"SELECT asset_id,file_name FROM assets WHERE asset_id IN ({placeholders})", tuple(ids)
        )
        for row in rows:
            source = self.paths.entity_library_images_path() / f"{row['asset_id']}{Path(row['file_name']).suffix.lower()}"
            self._move(source, archive / "entity-library-images" / row["file_name"])
        with self.entity_repository.transaction() as connection:
            connection.execute(
                f"DELETE FROM asset_usages WHERE reference_key IN (SELECT reference_key FROM logical_references WHERE asset_id IN ({placeholders}))",
                tuple(ids),
            )
            connection.execute(f"DELETE FROM asset_usages WHERE asset_id IN ({placeholders})", tuple(ids))
            connection.execute(f"DELETE FROM logical_references WHERE asset_id IN ({placeholders})", tuple(ids))
            connection.execute(f"DELETE FROM provenance WHERE source_asset_id IN ({placeholders})", tuple(ids))
            connection.execute(f"UPDATE assets SET derived_from_asset_id=NULL WHERE derived_from_asset_id IN ({placeholders})", tuple(ids))
            connection.execute(f"UPDATE assets SET replacement_for_asset_id=NULL WHERE replacement_for_asset_id IN ({placeholders})", tuple(ids))
            connection.execute(f"DELETE FROM assets WHERE asset_id IN ({placeholders})", tuple(ids))

    def delete_phase(self, character: str, phase: str) -> str:
        character, phase = self._name(character, "character"), self._name(phase, "phase")
        phase_path = self.paths.character_path(character, phase)
        if not phase_path.is_dir():
            raise LibraryDeletionServiceError(f"Character phase not found: {character} / {phase}")
        archive = self._archive(character, phase, "phase")
        self._move(phase_path, archive / "Characters" / character / phase)
        self._move(self.paths.character_asset_path(character, phase), archive / "Assets" / character / phase)
        self._move(self.paths.pipeline_base_path(character, phase), archive / "Pipelines" / character / phase)
        self._move(self.paths.pipeline_candidates_path("Character-Pipeline", character, phase), archive / "PipelineCandidates" / character / phase)
        self._move(self.local_sources.store.workspace_path(character, phase).parent, archive / "LocalAssets" / character / phase)

        character_entity = self.entity_repository.fetchone(
            "SELECT entity_id FROM entities WHERE lower(name)=lower(?) AND entity_type='character'", (character,)
        )
        variant = self.entity_repository.fetchone(
            "SELECT variant_id FROM variants WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'",
            (character_entity["entity_id"], phase),
        ) if character_entity else None
        ids = [row["asset_id"] for row in self.entity_repository.fetchall(
            "SELECT DISTINCT a.asset_id FROM assets a JOIN asset_entities ae ON ae.asset_id=a.asset_id WHERE ae.variant_id=?",
            (variant["variant_id"],),
        )] if variant else []
        self._purge_assets(ids, archive)
        if variant:
            with self.entity_repository.transaction() as connection:
                connection.execute("DELETE FROM variants WHERE variant_id=?", (variant["variant_id"],))
        return str(archive)

    def delete_costume(self, character: str, phase: str, costume_slug: str) -> str:
        character, phase = self._name(character, "character"), self._name(phase, "phase")
        costume_slug = self._name(costume_slug, "costume")
        costumes = self.paths.character_path(character, phase).glob("Costume_*.md")
        # Resolve only against canonical template filenames, never an arbitrary request path.
        match = next((path for path in costumes if path.stem.removeprefix("Costume_") == costume_slug), None)
        if match is None:
            raise LibraryDeletionServiceError(f"Costume not found: {costume_slug}")
        costume_name = self.paths_costume_name(costume_slug)
        archive = self._archive(character, phase, f"costume_{costume_slug}")
        self._move(match, archive / "Templates" / match.name)

        slug_dir = re.sub(r"[^A-Za-z0-9_-]+", "_", costume_name).strip("_") or "Costume"
        candidate_root = self.paths.pipeline_candidates_path("Character-Pipeline", character, phase)
        self._move(candidate_root / "Costume-Dressing" / slug_dir, archive / "PipelineCandidates" / "Costume-Dressing" / slug_dir)
        self._move(candidate_root / "locked" / "Costume-Dressing" / slug_dir, archive / "PipelineCandidates" / "locked" / "Costume-Dressing" / slug_dir)

        turnaround_path = self.paths.character_path(character, phase) / "TurnaroundSheets.json"
        old_turnaround = f"Local-Costume-Dressing_{re.sub(r'[^A-Za-z0-9]+', '-', costume_name).strip('-') or 'default'}"
        if turnaround_path.is_file():
            data = json.loads(turnaround_path.read_text(encoding="utf-8"))
            rows = data.get("turnarounds", [])
            removed = [row for row in rows if isinstance(row, dict) and row.get("turnaround_id") == old_turnaround]
            data["turnarounds"] = [row for row in rows if row not in removed]
            if removed:
                write_json_atomic(turnaround_path, data)
        self._move(self.paths.pipeline_base_path(character, phase) / "Turnaround" / old_turnaround,
                   archive / "Pipelines" / "Turnaround" / old_turnaround)
        self._move(self.paths.character_asset_path(character, phase) / "Turnarounds" / f"{old_turnaround}.png",
                   archive / "Assets" / "Turnarounds" / f"{old_turnaround}.png")

        store_path = self.local_sources.store.workspace_path(character, phase)
        if store_path.is_file():
            data = json.loads(store_path.read_text(encoding="utf-8"))
            records = data.get("assets", {})
            qualifier = costume_name.casefold()
            removed_keys = [key for key, row in records.items() if str(row.get("pipeline", "")).casefold() == "costume-dressing"
                            and str(row.get("qualifier") or "").casefold() == qualifier]
            for key in removed_keys:
                record = records.pop(key)
                for field in ("image_path", "locked_image_path"):
                    source = Path(str(record.get(field) or ""))
                    if source.is_file():
                        self._move(source, archive / "LocalAssets" / source.name)
            # Remove dangling lineage edges from any remaining local asset records.
            removed_set = set(removed_keys)
            for row in records.values():
                row["dependencies"] = [dep for dep in row.get("dependencies", [])
                                       if not isinstance(dep, dict) or dep.get("key") not in removed_set]
            write_json_atomic(store_path, data)

        entity_assets = self.entity_repository.fetchall(
            """SELECT DISTINCT a.asset_id FROM assets a
               LEFT JOIN asset_entities ae ON ae.asset_id=a.asset_id
               LEFT JOIN entities e ON e.entity_id=ae.entity_id
               WHERE a.origin_key LIKE ?
                  OR (e.entity_type='costume' AND lower(e.name)=lower(?) AND EXISTS (
                      SELECT 1 FROM asset_entities subject
                      JOIN entities character_entity ON character_entity.entity_id=subject.entity_id
                      JOIN variants phase_variant ON phase_variant.variant_id=subject.variant_id
                      WHERE subject.asset_id=a.asset_id AND character_entity.entity_type='character'
                        AND lower(character_entity.name)=lower(?) AND phase_variant.variant_type='life_stage'
                        AND lower(phase_variant.name)=lower(?)
                  ))""",
            (f"local:Costume-Dressing:{character}:{phase}:%", costume_name, character, phase),
        )
        self._purge_assets([row["asset_id"] for row in entity_assets], archive)
        return str(archive)

    @staticmethod
    def paths_costume_name(slug: str) -> str:
        return " ".join(part for part in slug.replace("-", "_").split("_") if part)
