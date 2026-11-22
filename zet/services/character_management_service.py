"""Rename a character or phase while retaining its stored workflow data."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class CharacterManagementService:
    def __init__(self, app):
        self.app = app
        self._recover_pending()

    def _journal_path(self):
        return Path(self.app.config.base_library_path) / "_state" / "CharacterManagement" / "rename.json"

    def _recover_pending(self):
        journal = self._journal_path()
        if not journal.is_file():
            return
        try:
            record = json.loads(journal.read_text(encoding="utf-8"))
            moves = [(Path(row[0]), Path(row[1])) for row in record["moves"]]
            for source, target in moves:
                if source.exists() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source.rename(target)
                elif source.exists() and target.exists():
                    raise ValueError("Rename recovery found both old and new locations present.")
            self._rewrite_json(moves, record["character"], record["phase"], record["new_name"], record["scope"])
            self._rename_catalog(record["character"], record["phase"], record["new_name"], record["scope"], moves)
            journal.unlink(missing_ok=True)
        except Exception as exc:
            raise ValueError(f"A character rename needs recovery before more changes: {exc}") from exc

    @staticmethod
    def _name(value, label):
        value = str(value or "").strip()
        if not value or not re.fullmatch(r"[A-Za-z0-9 _-]+", value):
            raise ValueError(f"{label} may only contain letters, numbers, spaces, underscores, and hyphens.")
        return value

    def rename(self, character, phase, *, new_name, scope):
        from zet.services.image_usage_service import usage_mutation
        character = self._name(character, "Character")
        phase = self._name(phase, "Phase")
        new_name = self._name(new_name, "New name")
        if scope not in {"character", "phase"}:
            raise ValueError("Choose character or phase rename.")
        root = Path(self.app.config.base_character_path).resolve()
        journal = self._journal_path()
        with file_lock(journal.with_suffix(".lock")):
            self._recover_pending()
            with usage_mutation(self.app.path_service, root / character, tree=True):
                return self._rename_locked(character, phase, new_name, scope, root)

    def _rename_locked(self, character, phase, new_name, scope, root):
        old_path = root / character if scope == "character" else root / character / phase
        new_path = root / new_name if scope == "character" else root / character / new_name
        if not old_path.is_dir():
            raise ValueError("The selected character or phase is unavailable.")
        if old_path == new_path:
            return {"character": character, "phase": phase, "name": new_name}
        if new_path.exists():
            raise ValueError("A character or phase with that name already exists.")

        if scope == "character":
            pairs = [(root / character, root / new_name)]
        else:
            pairs = [(root / character / phase, root / character / new_name)]
        if scope == "character":
            pairs.extend((base / character, base / new_name) for base in [Path(self.app.config.base_asset_path), Path(self.app.config.base_pipeline_path),
                          Path(self.app.config.base_library_path) / "PipelineCandidates" / "Character-Pipeline",
                          Path(self.app.config.base_library_path) / "_state" / "LocalAssets",
                          Path(self.app.config.base_library_path) / "_state" / "CharacterAssetContainers"])
        else:
            pairs.extend((base / character / phase, base / character / new_name) for base in [Path(self.app.config.base_asset_path), Path(self.app.config.base_pipeline_path),
                          Path(self.app.config.base_library_path) / "PipelineCandidates" / "Character-Pipeline",
                          Path(self.app.config.base_library_path) / "_state" / "LocalAssets",
                          Path(self.app.config.base_library_path) / "_state" / "CharacterAssetContainers"])

        moves = []
        for source, target in pairs:
            if source.exists():
                if target.exists():
                    raise ValueError(f"Rename destination already exists: {target}")
                moves.append((source, target))
        for source, _ in moves:
            for container in source.rglob("container.json") if source.exists() else []:
                try:
                    payload = json.loads(container.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(f"Cannot read active workflow state: {container}") from exc
                if payload.get("_pending_publication_id") or any((container.parent / "publications").glob("*.json")):
                    raise ValueError("Recover pending image publications before renaming.")
                for board in (payload.get("boards") or {}).values():
                    if any(candidate.get("status") in {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}
                           for candidate in (board.get("candidates") or {}).values()):
                        raise ValueError("Wait for active renders to finish before renaming.")
        moved = []
        journal = self._journal_path()
        try:
            write_json_atomic(journal, {"character": character, "phase": phase, "new_name": new_name,
                                        "scope": scope, "moves": [[str(a), str(b)] for a, b in moves]})
            for source, target in moves:
                source.rename(target)
                moved.append((source, target))
            self._rewrite_json(moves, character, phase, new_name, scope)
            self._rename_catalog(character, phase, new_name, scope, moves)
            journal.unlink(missing_ok=True)
        except Exception as error:
            # Preserve the journal and finish the rename on the next read if a
            # write fails after filesystem moves have started.
            if journal.is_file():
                self._recover_pending()
                return {"character": new_name if scope == "character" else character,
                        "phase": new_name if scope == "phase" else phase, "name": new_name}
            raise error
        return {"character": new_name if scope == "character" else character,
                "phase": new_name if scope == "phase" else phase, "name": new_name}

    @staticmethod
    def _rewrite_json(moves, character, phase, new_name, scope):
        for _, target in moves:
            for path in target.rglob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(f"Cannot update stored workflow metadata: {path}") from exc
                def update(value, key=""):
                    if isinstance(value, dict):
                        return {k: update(v, k) for k, v in value.items()}
                    if isinstance(value, list):
                        return [update(v, key) for v in value]
                    if isinstance(value, str):
                        if scope == "character" and key in {"character", "character_name"} and value == character:
                            return new_name
                        if scope == "phase" and key in {"phase", "source_phase"} and value == phase:
                            return new_name
                        if "path" in key.casefold() or key in {"directory", "workspace"}:
                            for source, target in moves:
                                value = value.replace(str(source), str(target)).replace(source.as_posix(), target.as_posix())
                    return value
                updated = update(data)
                if updated != data:
                    write_json_atomic(path, updated)
            for path in target.rglob("*.md"):
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError as exc:
                    raise ValueError(f"Cannot update character template metadata: {path}") from exc
                label = "Character Name" if scope == "character" else "Character Phase"
                old = character if scope == "character" else phase
                text = re.sub(rf"(?im)^(\s*{re.escape(label)}\s*:\s*){re.escape(old)}\s*$",
                              lambda match: match.group(1) + new_name, text)
                if text != path.read_text(encoding="utf-8"):
                    path.write_text(text, encoding="utf-8", newline="")

    def _rename_catalog(self, character, phase, new_name, scope, moves):
        repository = self.app.entity_library_service.repository
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with repository.transaction() as connection:
            library = Path(self.app.config.base_library_path).resolve()
            for source, target in moves:
                try:
                    old_prefix = source.resolve().relative_to(library).as_posix().rstrip("/") + "/"
                    new_prefix = target.resolve().relative_to(library).as_posix().rstrip("/") + "/"
                except ValueError:
                    continue
                connection.execute("UPDATE assets SET lock_path=? || substr(lock_path,length(?)+1) WHERE lock_path LIKE ?",
                                   (new_prefix, old_prefix, old_prefix + "%"))
            if scope == "character":
                entity = connection.execute("SELECT entity_id FROM entities WHERE lower(name)=lower(?) AND entity_type='character'", (character,)).fetchone()
                if entity:
                    connection.execute("INSERT OR IGNORE INTO entity_name_aliases VALUES(?,?,?)", (character, "character", entity["entity_id"]))
                    connection.execute("UPDATE entities SET name=?,updated_at=? WHERE entity_id=?", (new_name, stamp, entity["entity_id"]))
            else:
                entity = connection.execute("SELECT entity_id FROM entities WHERE lower(name)=lower(?) AND entity_type='character'", (character,)).fetchone()
                if entity:
                    variant = connection.execute("SELECT variant_id FROM variants WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'", (entity["entity_id"], phase)).fetchone()
                    if variant:
                        connection.execute("INSERT OR IGNORE INTO variant_name_aliases VALUES(?,?,?,?)", (entity["entity_id"], phase, "life_stage", variant["variant_id"]))
                        connection.execute("UPDATE variants SET name=?,updated_at=? WHERE variant_id=?", (new_name, stamp, variant["variant_id"]))
