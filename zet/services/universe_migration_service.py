"""Resumable migration of the configured library root into its Moonsea universe."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


class UniverseMigrationError(RuntimeError):
    """A migration could not be completed safely."""


class UniverseMigrationService:
    """Journaled, collision-checked migration preserving original files for rollback."""

    LAYOUT = {
        "Experiments": "PipelineCandidates",
        "Pipelines": "PipelineCandidates/LegacyPipelines",
        "AuxiliaryResources": "_state/AuxiliaryResources",
        "ImageCatalog": "_state/ImageCatalog",
    }
    TOP_LEVEL = {"Characters", "Stories", "Assets", "ImageCatalog", "catalog.sqlite3", "images",
                 "Experiments", "Pipelines", "AuxiliaryResources", "CostumePrompt", ".gitignore"}

    def __init__(self, container: str | Path, journal_path: str | Path, queue_root: str | Path | None = None,
                 config_path: str | Path | None = None):
        self.container = Path(container).expanduser().resolve()
        self.root = self.container / "Moonsea"
        self.journal_path = Path(journal_path).expanduser().resolve()
        self.queue_root = Path(queue_root).expanduser().resolve() if queue_root else None
        self.config_path = Path(config_path).expanduser().resolve() if config_path else None
        self.backup_root = self.journal_path.with_suffix("")

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def dry_run(self) -> dict[str, Any]:
        if (self.root / "universe.json").is_file():
            return {"status": "already_migrated", "universe_root": str(self.root), "actions": [], "collisions": []}
        actions, collisions = [], []
        if self.root.exists():
            raise UniverseMigrationError(f"Target exists without a universe descriptor: {self.root}")
        for source in sorted(self.container.iterdir(), key=lambda item: item.name.casefold()):
            if source.name not in self.TOP_LEVEL:
                continue
            relative = self.LAYOUT.get(source.name, source.name)
            destination = self.root / relative
            count = sum(1 for _ in source.rglob("*")) if source.is_dir() else 1
            actions.append({"source": str(source), "destination": str(destination), "entries": count})
            if destination.exists():
                collisions.append({"source": str(source), "destination": str(destination), "reason": "destination already exists"})
        image_count = sum(1 for path in self.container.rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"})
        return {"status": "ready" if not collisions else "blocked", "container": str(self.container),
                "universe_root": str(self.root), "actions": actions, "collisions": collisions,
                "image_files_to_preserve": image_count, "journal": str(self.journal_path)}

    def apply(self) -> dict[str, Any]:
        if self.journal_path.is_file():
            journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
            if journal.get("status") == "complete":
                return self.verify()
            if journal.get("status") == "rolled_back":
                raise UniverseMigrationError("The migration journal was rolled back; remove it before starting a new migration.")
        else:
            report = self.dry_run()
            if report["status"] == "already_migrated":
                return self.verify()
            if report["status"] != "ready":
                raise UniverseMigrationError(f"Migration preflight failed: {report['collisions']}")
            journal = {"status": "applying", "container": str(self.container), "root": str(self.root),
                       "actions": [{**action, "state": "pending"} for action in report["actions"]],
                       "moved": [], "hashes": {}, "queue_backups": {}, "data_backups": {},
                       "configuration": str(self.config_path or self.journal_path)}
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_journal(journal)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        catalog_source = self.container / "catalog.sqlite3"
        catalog_backup = self.backup_root / "catalog.sqlite3"
        if catalog_source.is_file() and not catalog_backup.is_file():
            shutil.copy2(catalog_source, catalog_backup)
        if self.config_path and self.config_path.is_file():
            config_backup = self.backup_root / "config.toml"
            if not config_backup.exists():
                shutil.copy2(self.config_path, config_backup)
        journal["catalog_backup"] = str(catalog_backup) if catalog_backup.is_file() else ""
        journal["backup_root"] = str(self.backup_root)
        images_source = self.container / "images"
        images_backup = self.backup_root / "images"
        journal["images_existed"] = images_source.is_dir()
        if images_source.is_dir() and not images_backup.exists():
            shutil.copytree(images_source, images_backup)
        journal["images_backup"] = str(images_backup) if images_backup.is_dir() else ""
        self._write_journal(journal)
        self.root.mkdir(parents=True)
        for action in journal.get("actions", []):
            if action.get("state") == "moved":
                continue
            source, destination = Path(action["source"]), Path(action["destination"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not source.exists():
                action["state"] = "moved"
                journal.setdefault("moved", []).append({"source": str(source), "destination": str(destination)})
                self._write_journal(journal)
                continue
            if destination.exists() or not source.exists():
                raise UniverseMigrationError(f"Cannot safely resume {source} -> {destination}.")
            if source.is_dir():
                shutil.move(str(source), str(destination))
            else:
                shutil.move(str(source), str(destination))
            action["state"] = "moved"
            journal["moved"].append({"source": str(source), "destination": str(destination)})
            self._write_journal(journal)
        for folder in ("Characters", "Stories", "PipelineCandidates", "_state", "images"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "universe.json").write_text(json.dumps({"universe_id": "Moonsea", "name": "Moonsea", "layout_version": 1}, indent=2) + "\n", encoding="utf-8")
        self._rewrite_queued_jobs(journal)
        selection_path = self.journal_path.parent / "universe-selection.json"
        if str(selection_path) not in journal.setdefault("data_backups", {}):
            journal["data_backups"][str(selection_path)] = selection_path.read_text(encoding="utf-8") if selection_path.is_file() else None
            self._write_journal(journal)
        from zet.services.universe_service import UniverseService
        UniverseService(self.container, selection_path).select("Moonsea")
        from types import SimpleNamespace
        from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
        from zet.services.auxiliary_resource_service import AuxiliaryResourceService
        from zet.services.path_service import PathService
        paths = PathService(SimpleNamespace(base_library_path=str(self.root)), self.root)
        resource_service = AuxiliaryResourceService(AuxiliaryResourceRepository(paths), paths)
        inventory_path = paths.auxiliary_resource_inventory_path()
        journal.setdefault("data_backups", {}).setdefault(
            str(inventory_path), inventory_path.read_text(encoding="utf-8") if inventory_path.is_file() else None
        )
        self._write_journal(journal)
        journal["auxiliary_import"] = resource_service.migrate_legacy_images(self.container)
        self._archive_auxiliary_store(resource_service, journal)
        self._rewrite_run_ownership(journal)
        path_rewrite_report = self.repair_paths()
        journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
        journal["path_rewrite_report"] = path_rewrite_report
        journal["status"] = "verifying"
        self._write_journal(journal)
        result = self.verify()
        if result["status"] != "verified":
            raise UniverseMigrationError(f"Post-migration verification failed: {result}")
        journal["status"] = "complete"
        self._write_journal(journal)
        return result

    def _archive_auxiliary_store(self, resource_service, journal: dict[str, Any]) -> None:
        """Keep legacy templates in the new layout and move the old store into backup."""
        legacy_root = self.root / "_state" / "AuxiliaryResources"
        if not legacy_root.exists():
            return
        template_root = self.root / "_state" / "ResourceTemplates"
        for resource in resource_service.repository.list_resources():
            old_template = Path(str(resource.template_path or ""))
            if old_template.is_file():
                destination = template_root / resource.resource_id / f"{resource.resource_id}_Template.md"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    journal.setdefault("data_backups", {})[str(destination)] = None
                    self._write_journal(journal)
                    shutil.copy2(old_template, destination)
                resource.resource_path = str(destination.parent)
                resource.template_path = str(destination)
                resource_service.repository.save_resource(resource)
        archive = self.backup_root / "AuxiliaryResources"
        if archive.exists():
            raise UniverseMigrationError(f"AUX migration archive already exists: {archive}")
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_root), str(archive))
        for action in journal.get("actions", []):
            if Path(action["destination"]) == legacy_root:
                action["destination"] = str(archive)
        for moved in journal.get("moved", []):
            if Path(moved["destination"]) == legacy_root:
                moved["destination"] = str(archive)
        journal["auxiliary_archive"] = str(archive)
        self._write_journal(journal)

    def _rewrite_queued_jobs(self, journal: dict[str, Any]) -> None:
        if not self.queue_root or not self.queue_root.exists():
            return
        for record in self.queue_root.rglob("*.json"):
            if record.name not in {"ask_manifest.json", "answer_manifest.json", "job.json"} and "Routes" not in record.parts:
                continue
            try:
                original = record.read_text(encoding="utf-8")
                payload = json.loads(original)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            changed = False
            is_route = "Routes" in record.parts
            has_moonsea_path = False
            for key in ("target_output_dir", "artifact_output_dir", "prompt_condense_template", "pipeline_path", "target_output_file"):
                value = payload.get(key)
                if not isinstance(value, str) or not Path(value).is_absolute():
                    continue
                source = Path(value)
                try:
                    relative = source.resolve().relative_to(self.container)
                except ValueError:
                    continue
                has_moonsea_path = True
                payload[key] = str(self.root.joinpath(*relative.parts))
                changed = True
            if is_route and has_moonsea_path:
                payload["universe_id"] = "Moonsea"
                changed = True
            elif record.name == "ask_manifest.json" and has_moonsea_path:
                payload["universe_id"] = "Moonsea"
                changed = True
            if changed:
                if str(record) not in journal["queue_backups"]:
                    journal["queue_backups"][str(record)] = original
                    self._write_journal(journal)
                record.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _rewrite_run_ownership(self, journal: dict[str, Any]) -> None:
        root = self.root / "PipelineCandidates"
        if not root.is_dir():
            return
        journal.setdefault("data_backups", {})
        for path in root.rglob("*.json"):
            if path.name not in {"spec.json", "state.json"}:
                continue
            try:
                original = path.read_text(encoding="utf-8")
                payload = json.loads(original)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict) or not (payload.get("run_id") or payload.get("candidates")):
                continue
            if payload.get("universe_id"):
                continue
            payload["universe_id"] = "Moonsea"
            if str(path) not in journal["data_backups"]:
                journal["data_backups"][str(path)] = original
                self._write_journal(journal)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_journal(self, journal: dict[str, Any]) -> None:
        temporary = self.journal_path.with_suffix(self.journal_path.suffix + ".tmp")
        temporary.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.journal_path)

    def repair_paths(self) -> dict[str, Any]:
        """Rebase persisted paths from the old container layout into Moonsea."""
        if not self.journal_path.is_file():
            raise UniverseMigrationError(f"Migration journal is missing: {self.journal_path}")
        journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
        mappings: list[tuple[str, str]] = []
        for action in journal.get("actions", []):
            source, destination = Path(action["source"]), Path(action["destination"])
            mappings.extend(((str(source), str(destination)), (source.as_posix(), destination.as_posix())))
        mappings.sort(key=lambda item: len(item[0]), reverse=True)
        extensions = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml", ".toml", ".csv", ".log"}
        backups = journal.setdefault("path_rewrites", {})
        changed_files = changed_references = 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            try:
                original = path.read_bytes()
                rewritten = original.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            count = 0
            for old_root, new_root in mappings:
                for old, new in ((old_root, new_root), (old_root.replace("\\", "\\\\"), new_root.replace("\\", "\\\\"))):
                    occurrences = rewritten.count(old)
                    if occurrences:
                        rewritten = rewritten.replace(old, new)
                        count += occurrences
            if not count:
                continue
            relative_key = path.relative_to(self.root).as_posix()
            if relative_key not in backups:
                backup = self.backup_root / "PathRewrite" / Path(relative_key)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
                backups[relative_key] = {"backup_path": str(backup), "sha256_before": self._hash(path)}
                self._write_journal(journal)
            temporary = path.with_name(path.name + ".path-rewrite.tmp")
            temporary.write_text(rewritten, encoding="utf-8", newline="")
            os.replace(temporary, path)
            changed_files += 1
            changed_references += count
        journal["path_rewrite_report"] = {"status": "repaired", "files": changed_files, "references": changed_references}
        journal["local_asset_migration"] = self._migrate_local_asset_stores(journal)
        self._write_journal(journal)
        return journal["path_rewrite_report"]

    def _migrate_local_asset_stores(self, journal: dict[str, Any]) -> dict[str, int]:
        """Move old lock mappings to _state and publish their locked images."""
        from zet.services.local_asset_store_service import LocalAssetStoreService

        store = LocalAssetStoreService(self.root)
        migrated = published = unresolved = 0
        source_root = self.root / "PipelineCandidates" / "Character-Pipeline"
        if not source_root.is_dir():
            return {"stores": 0, "published_images": 0, "unresolved_locks": 0}
        for source in source_root.glob("*/*/local_assets.json"):
            character, phase = source.parent.parent.name, source.parent.name
            target = store.workspace_path(character, phase)
            if not source.is_file():
                continue
            try:
                legacy_data = json.loads(source.read_text(encoding="utf-8"))
                data = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {
                    "schema_version": 1, "character": character, "phase": phase, "assets": {},
                }
            except (OSError, json.JSONDecodeError) as exc:
                raise UniverseMigrationError(f"Cannot migrate local asset stores {source} / {target}: {exc}") from exc
            target_assets = data.setdefault("assets", {})
            for key, record in (legacy_data.get("assets") or {}).items():
                current = target_assets.get(key)
                if record.get("locked") or current is None:
                    target_assets[key] = record
            if str(target) not in journal.setdefault("data_backups", {}):
                journal["data_backups"][str(target)] = target.read_text(encoding="utf-8") if target.is_file() else None
                self._write_journal(journal)
            for record in target_assets.values():
                if not isinstance(record, dict) or not record.get("locked"):
                    continue
                checksum = str(record.get("image_sha256") or "")
                image = Path(str(record.get("image_path") or ""))
                if not image.is_file() or store._image_hash(image) != checksum:
                    image = Path(str(record.get("locked_image_path") or ""))
                if not checksum or not image.is_file() or store._image_hash(image) != checksum:
                    unresolved += 1
                    continue
                try:
                    asset = store._publish(
                        image, character=character, phase=phase,
                        pipeline=str(record.get("pipeline") or "local"), checksum=checksum,
                    )
                except Exception as exc:
                    raise UniverseMigrationError(f"Cannot publish locked local image from {image}: {exc}") from exc
                record["locked_image_path"] = asset["image_path"]
                record["entity_library_asset_id"] = asset["asset_id"]
                published += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".migration.tmp")
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, target)
            self._write_journal(journal)
            source.unlink()
            migrated += 1
        return {"stores": migrated, "published_images": published, "unresolved_locks": unresolved}

    def verify(self) -> dict[str, Any]:
        descriptor = self.root / "universe.json"
        if not descriptor.is_file():
            return {"status": "unverified", "reason": f"Missing {descriptor}"}
        data = json.loads(descriptor.read_text(encoding="utf-8"))
        if data.get("universe_id") != "Moonsea":
            return {"status": "unverified", "reason": "Universe descriptor ID is not Moonsea."}
        forbidden = [str(path) for path in (self.root / "Experiments", self.root / "AuxiliaryResources",
                                             self.root / "_state" / "AuxiliaryResources") if path.exists()]
        expected = [self.root / name for name in ("Characters", "Stories", "PipelineCandidates", "_state", "images")]
        missing = [str(path) for path in expected if not path.is_dir()]
        return {"status": "verified" if not (forbidden or missing) else "unverified", "universe_root": str(self.root),
                "forbidden_legacy_roots": forbidden, "missing_layout_roots": missing,
                "images": sum(1 for path in (self.root / "images").rglob("*") if path.is_file())}

    def rollback(self) -> dict[str, Any]:
        if not self.journal_path.is_file():
            raise UniverseMigrationError(f"Migration journal is missing: {self.journal_path}")
        journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
        failures = []
        moved = journal.get("moved") or [item for item in journal.get("actions", []) if item.get("state") == "moved"]
        for item in moved:
            source, destination = Path(item["source"]), Path(item["destination"])
            if source.exists() and destination.exists():
                failures.append({"source": str(source), "destination": str(destination), "reason": "rollback would overwrite source"})
        if failures:
            return {"status": "blocked", "failures": failures}
        for record, contents in journal.get("queue_backups", {}).items():
            Path(record).write_text(contents, encoding="utf-8")
        for record, contents in journal.get("data_backups", {}).items():
            if contents is None:
                Path(record).unlink(missing_ok=True)
            else:
                Path(record).write_text(contents, encoding="utf-8")
        for item in reversed(moved):
            source, destination = Path(item["source"]), Path(item["destination"])
            if not destination.exists():
                continue
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(source))
        for relative, metadata in journal.get("path_rewrites", {}).items():
            backup = Path(metadata["backup_path"])
            target = self.root / Path(relative)
            if backup.is_file():
                for action in journal.get("actions", []):
                    destination = Path(action["destination"])
                    try:
                        suffix = target.relative_to(destination)
                    except ValueError:
                        continue
                    target = Path(action["source"]) / suffix
                    break
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
        if journal.get("catalog_backup"):
            shutil.copy2(journal["catalog_backup"], self.container / "catalog.sqlite3")
        if journal.get("images_backup"):
            images = self.container / "images"
            if images.exists():
                shutil.rmtree(images)
            shutil.copytree(journal["images_backup"], images)
        elif not journal.get("images_existed"):
            shutil.rmtree(self.container / "images", ignore_errors=True)
        descriptor = self.root / "universe.json"
        descriptor.unlink(missing_ok=True)
        for folder in ("Characters", "Stories", "PipelineCandidates", "_state", "images"):
            path = self.root / folder
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        try:
            self.root.rmdir()
        except OSError:
            pass
        journal["status"] = "rolled_back"
        self._write_journal(journal)
        return {"status": "rolled_back", "restored_entries": len(journal.get("moved", []))}
