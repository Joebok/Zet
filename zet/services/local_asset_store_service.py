"""Durable selected and locked assets for local character pipelines."""
from __future__ import annotations

from datetime import datetime
import copy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from zet.services.library_reference_service import read_library_json, write_library_json
from zet.services.workflow_storage import file_lock


class LocalAssetStoreError(ValueError):
    pass


class LocalAssetStoreService:
    """Store local selections next to experiment batches, separate from canonical assets."""

    def __init__(self, library_root: str | Path):
        self.library_root = Path(library_root).resolve()
        self.root = self.library_root / "PipelineCandidates" / "Character-Pipeline"
        self._entity_library = None
        from zet.services.local_asset_publication_recovery_service import LocalAssetPublicationRecoveryService
        self._publication_recovery = LocalAssetPublicationRecoveryService(
            self.library_root, self._ensure_entity_library
        )

    def _publish(self, image: Path, *, character: str, phase: str, pipeline: str, checksum: str,
                 label: str = "",
                 qualifier: str = "", view: str = "", reference_key: str = "") -> dict[str, Any]:
        self._ensure_entity_library()
        return self._entity_library.register_locked_pipeline_image(
            image, label=label.strip() or self._publication_label(character, phase, pipeline, qualifier, view),
            pipeline=pipeline, character=character, phase=phase, checksum=checksum,
            costume=qualifier, view=view, reference_key=reference_key,
        )

    def _ensure_entity_library(self):
        if self._entity_library is None:
            from zet.repositories.entity_library_repository import EntityLibraryRepository
            from zet.services.entity_library_service import EntityLibraryService
            from zet.services.path_service import PathService
            paths = PathService(SimpleNamespace(base_library_path=str(self.library_root)), self.library_root)
            repository = EntityLibraryRepository(paths.entity_library_database_path())
            repository.initialize()
            self._entity_library = EntityLibraryService(paths, repository)
        return self._entity_library

    def _publication_journal_root(self, character: str, phase: str) -> Path:
        return self.workspace_path(character, phase).parent / "publications"

    def _recover_publications_locked(self, character: str, phase: str) -> None:
        try:
            self._publication_recovery.recover_locked(character, phase)
        except (OSError, ValueError) as exc:
            raise LocalAssetStoreError(f"Cannot recover local asset publication: {exc}") from exc

    def recover_pending_publications(self) -> None:
        try:
            self._publication_recovery.recover_pending()
        except (OSError, ValueError) as exc:
            raise LocalAssetStoreError(f"Cannot recover local asset publication: {exc}") from exc

    @staticmethod
    def _publication_label(character: str, phase: str, pipeline: str, qualifier: str = "", view: str = "") -> str:
        pipeline_name = str(pipeline or "local").replace("-", " ").strip().title()
        return " · ".join(part for part in (str(character).strip(), str(phase).strip(),
                                               str(qualifier).strip(), pipeline_name,
                                               str(view).replace("_", " ").strip().title()) if part)

    @staticmethod
    def key(pipeline: str, view: str, qualifier: str = "") -> str:
        pipeline_key = str(pipeline).strip().lower()
        qualifier_key = re.sub(r"[^a-z0-9_-]+", "_", str(qualifier or "").strip().lower()).strip("_")
        view_key = str(view).strip().upper()
        return f"{pipeline_key}:{qualifier_key}:{view_key}" if qualifier_key else f"{pipeline_key}:{view_key}"

    @staticmethod
    def _safe(value: str) -> str:
        result = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
        if not result or result in {".", ".."}:
            raise LocalAssetStoreError("Character and phase are required.")
        return result

    def workspace_path(self, character: str, phase: str) -> Path:
        return self.library_root / "_state" / "LocalAssets" / self._safe(character) / self._safe(phase) / "local_assets.json"

    def _read(self, character: str, phase: str) -> dict[str, Any]:
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            try:
                self._recover_publications_locked(character, phase)
                if not path.is_file():
                    return {"schema_version": 1, "character": character, "phase": phase, "assets": {}}
                value = read_library_json(path, self.library_root)
            except (OSError, json.JSONDecodeError) as exc:
                raise LocalAssetStoreError(f"Local asset store is unreadable: {path}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("assets", {}), dict):
            raise LocalAssetStoreError(f"Local asset store has an invalid format: {path}")
        return value

    def detail(self, character: str, phase: str) -> dict[str, Any]:
        value = self._read(character, phase)
        return {"character": character, "phase": phase, "assets": value.get("assets", {})}

    def locked_assets(self, character: str, phase: str, pipeline: str = "", qualifier: str = "") -> list[dict[str, Any]]:
        """Return published locks whose permanent files are available."""
        records = self.detail(character, phase)["assets"]
        from zet.repositories.entity_library_repository import EntityLibraryRepository
        database = self.library_root / "catalog.sqlite3"
        archived = set()
        ids = {r["entity_library_asset_id"] for r in records.values() if r.get("entity_library_asset_id")}
        if ids and database.is_file():
            marks = ",".join("?" for _ in ids)
            archived = {row["asset_id"] for row in EntityLibraryRepository(database).fetchall(
                f"SELECT asset_id FROM assets WHERE status='archived' AND asset_id IN ({marks})", tuple(ids))}
        result = []
        for key, record in records.items():
            if pipeline and record.get("pipeline", "").lower() != pipeline.lower():
                continue
            if qualifier and str(record.get("qualifier") or "").lower() != qualifier.lower():
                continue
            if not record.get("locked") or record.get("entity_library_asset_id") in archived:
                continue
            path = Path(str(record.get("locked_image_path") or "")).resolve()
            if not path.is_relative_to(self.library_root) or not path.is_file():
                continue
            result.append({"key": key, **record, "image_path": str(path)})
        return sorted(result, key=lambda item: item["key"])

    def all_selected_views_locked(self, run: dict[str, Any], pipeline: str, *,
                                  qualifier: str = "", require_front_anchor: bool = True) -> bool:
        """Verify completed publication independently of advisory rankings."""
        views = run.get("views") or []
        selected = run.get("selected_views") or {}
        if not views or any(not selected.get(view) for view in views):
            return False
        if ((require_front_anchor or run.get("front_anchor"))
                and run.get("front_anchor") != selected.get("FRONT")):
            return False
        locks = {record["view"]: record for record in self.locked_assets(
            run["character"], run["phase"], pipeline=pipeline, qualifier=qualifier
        ) if str(record.get("qualifier") or "").casefold() == qualifier.casefold()}
        candidates = {item["candidate_id"]: item for item in run.get("candidates") or []}
        for view in views:
            record = locks.get(view) or {}
            candidate = candidates.get(selected[view]) or {}
            if (record.get("batch_id") != run["run_id"]
                    or record.get("candidate_id") != selected[view]
                    or (candidate and candidate.get("view") != view)):
                return False
        return True

    @staticmethod
    def _image_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _locked_dependents(self, assets: dict[str, Any], parent_key: str) -> list[str]:
        return sorted(
            key for key, item in assets.items()
            if item.get("locked") and any(dep.get("key") == parent_key for dep in item.get("dependencies", []))
        )

    def assert_change_allowed(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> None:
        # Upstream edits are allowed. Batch lineage warnings explain downstream drift.
        return None

    def assert_batch_change_allowed(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> None:
        """Batch work changes run state; shared asset locks do not restrict it."""

    def record_batch_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None, qualifier: str = "",
    ) -> dict[str, Any] | None:
        """Keep a batch selection in its run when the shared asset cannot be changed."""
        current = self.detail(character, phase)["assets"].get(self.key(pipeline, view, qualifier), {})
        if current.get("locked"):
            return None
        try:
            self.assert_change_allowed(character, phase, pipeline, view, qualifier)
        except LocalAssetStoreError:
            return None
        return self.record_selection(
            character, phase, pipeline, view, candidate_id=candidate_id,
            image_path=image_path, batch_id=batch_id,
            dependencies=dependencies, qualifier=qualifier,
        )

    def lock_batch_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None, qualifier: str = "",
        prompt_generator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish a reviewed batch selection only when its view can be locked."""
        self.assert_change_allowed(character, phase, pipeline, view, qualifier)
        self.record_selection(
            character, phase, pipeline, view, candidate_id=candidate_id,
            image_path=image_path, batch_id=batch_id,
            dependencies=dependencies, qualifier=qualifier, prompt_generator=prompt_generator,
        )
        return self.lock(character, phase, pipeline, view, qualifier)

    def clear_batch_selection(self, character: str, phase: str, pipeline: str, view: str,
                              batch_id: str, qualifier: str = "") -> None:
        """Clear the shared selection only when this batch owns it and it is unlocked."""
        key = self.key(pipeline, view, qualifier)
        record = self.detail(character, phase)["assets"].get(key) or {}
        if record.get("batch_id") == batch_id and not record.get("locked"):
            self.clear_selection(character, phase, pipeline, view, qualifier)

    def record_selection(
        self, character: str, phase: str, pipeline: str, view: str, *,
        candidate_id: str, image_path: str | Path, batch_id: str,
        dependencies: list[dict[str, str]] | None = None,
        qualifier: str = "", prompt_generator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        image = Path(image_path).resolve()
        if not image.is_file():
            raise LocalAssetStoreError(f"Selected local image is missing: {image}")
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            current = assets.get(key, {})
            digest = self._image_hash(image)
            changed = current.get("candidate_id") != candidate_id or current.get("image_sha256") != digest
            if changed:
                for child in assets.values():
                    if any(dep.get("key") == key for dep in child.get("dependencies", [])) and not child.get("locked"):
                        child["stale"] = True
                        child["stale_reason"] = f"Upstream selection {key} changed."
            record = {
                **current,
                "pipeline": str(pipeline), "view": str(view).upper(),
                "qualifier": str(qualifier or ""),
                "candidate_id": str(candidate_id), "batch_id": str(batch_id),
                "image_path": str(image), "image_sha256": digest,
                "dependencies": list(dependencies or []),
                "selected": True, "stale": False,
                **({"prompt_generator": copy.deepcopy(prompt_generator)} if prompt_generator else {}),
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            assets[key] = record
            write_library_json(path, value, self.library_root)
            return dict(record)

    def clear_selection(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            current = assets.get(key)
            if not current:
                return value
            assets.pop(key)
            for child in assets.values():
                if any(dep.get("key") == key for dep in child.get("dependencies", [])) and not child.get("locked"):
                    child["stale"] = True
                    child["stale_reason"] = f"Upstream selection {key} was cleared."
            write_library_json(path, value, self.library_root)
            return value

    def lock(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.key(pipeline, view, qualifier)
        record = self.detail(character, phase)["assets"].get(key)
        if not record or not record.get("selected") or record.get("stale"):
            raise LocalAssetStoreError(f"Select a reviewed {key} candidate before locking it.")
        return self.promote_chain(character, phase, [{
            **record, "pipeline": pipeline, "view": view.upper(), "qualifier": qualifier,
            "_require_current_selection": True,
        }])[0]

    def promote_chain(self, character: str, phase: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Publish a set of locks with idempotent recovery across catalog and workspace state."""
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.setdefault("assets", {})
            previous = copy.deepcopy(value)
            prepared = []
            for item in records:
                pipeline, view = str(item["pipeline"]), str(item["view"]).upper()
                qualifier = str(item.get("qualifier") or "")
                image = Path(str(item["image_path"])).resolve()
                if not image.is_relative_to(self.library_root) or not image.is_file():
                    raise LocalAssetStoreError(f"Selected image for {pipeline} {view} is missing.")
                digest = self._image_hash(image)
                key = self.key(pipeline, view, qualifier)
                if item.get("_require_current_selection"):
                    current = assets.get(key) or {}
                    if (not current.get("selected") or current.get("stale")
                            or current.get("candidate_id") != item.get("candidate_id")
                            or current.get("batch_id") != item.get("batch_id")):
                        raise LocalAssetStoreError(f"Selection for {key} changed before it could be locked.")
                if not item.get("candidate_id") or not item.get("batch_id"):
                    raise LocalAssetStoreError(f"Selected local image for {key} has no candidate or batch identity.")
                prepared.append({**item, "character": character, "phase": phase,
                                 "pipeline": pipeline, "view": view, "qualifier": qualifier,
                                 "label": str(item.get("label") or item.get("batch_name") or self._publication_label(
                                     character, phase, pipeline, qualifier, view)),
                                 "source": image, "checksum": digest, "reference_key": str(
                                     assets.get(key, {}).get("reference_key") or item.get("reference_key") or "")})

            operation_id = uuid4().hex
            journal_root = self._publication_journal_root(character, phase)
            journal_root.mkdir(parents=True, exist_ok=True)
            journal_path = journal_root / f"{operation_id}.json"
            from zet.services.atomic_file_service import write_json_atomic
            write_json_atomic(journal_path, {"operation_id": operation_id, "previous": previous, "next": None})
            result = []

            def publish_workspace_state(published_assets):
                next_state = copy.deepcopy(previous)
                next_records = next_state.setdefault("assets", {})
                next_result = []
                for item, published in zip(prepared, published_assets):
                    key = self.key(item["pipeline"], item["view"], item.get("qualifier", ""))
                    image = item["source"]
                    digest = item["checksum"]
                    current = next_records.get(key, {})
                    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
                    reference = published.get("logical_reference") or {}
                    record = {
                        **current, "pipeline": item["pipeline"], "view": item["view"],
                        "qualifier": item.get("qualifier", ""),
                        "candidate_id": str(item["candidate_id"]), "batch_id": str(item["batch_id"]),
                        "batch_name": str(item.get("batch_name") or ""),
                        "image_path": str(image), "image_sha256": digest,
                        "dependencies": list(item.get("dependencies") or []), "selected": True, "stale": False,
                        "locked": True, "locked_image_path": str(published["image_path"]),
                        "entity_library_asset_id": published["asset_id"],
                        "reference_key": (reference.get("reference_key") or item.get("reference_key")
                                          or current.get("reference_key") or ""),
                        "updated_at": stamp, "locked_at": stamp,
                    }
                    if item.get("prompt_generator"):
                        record["prompt_generator"] = copy.deepcopy(item["prompt_generator"])
                    if current.get("image_sha256") != digest or current.get("candidate_id") != record["candidate_id"]:
                        record["lock_history"] = [*current.get("lock_history", []), {
                            "locked_at": stamp, "image_sha256": digest,
                            "batch_id": record["batch_id"], "candidate_id": record["candidate_id"],
                        }]
                    next_records[key] = record
                    next_result.append(dict(record))
                write_json_atomic(journal_path, {"operation_id": operation_id,
                                                 "previous": previous, "next": next_state})
                write_library_json(path, next_state, self.library_root)
                result.extend(next_result)

            try:
                self._ensure_entity_library().register_locked_pipeline_images(
                    prepared, operation_id=operation_id, before_commit=publish_workspace_state,
                )
                journal_path.unlink(missing_ok=True)
                return result
            except Exception as exc:
                try:
                    self._recover_publications_locked(character, phase)
                except Exception as recovery_exc:
                    raise LocalAssetStoreError(
                        f"Local asset publication failed and recovery is pending: {recovery_exc}"
                    ) from exc
                if isinstance(exc, LocalAssetStoreError):
                    raise
                raise LocalAssetStoreError(f"Could not publish selected local assets: {exc}") from exc

    def unlock(self, character: str, phase: str, pipeline: str, view: str, qualifier: str = "") -> dict[str, Any]:
        key = self.key(pipeline, view, qualifier)
        path = self.workspace_path(character, phase)
        with file_lock(path.with_suffix(".lock")):
            value = self._read(character, phase)
            assets = value.get("assets", {})
            record = assets.get(key)
            if not record or not record.get("locked"):
                raise LocalAssetStoreError(f"{key} is not locked.")
            record.update({"locked": False, "unlocked_at": datetime.now().astimezone().isoformat(timespec="seconds")})
            write_library_json(path, value, self.library_root)
            return dict(record)
