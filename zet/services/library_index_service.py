from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from zet.repositories.image_catalog_repository import ImageCatalogRepository
from zet.repositories.library_index_repository import IndexSnapshot, LibraryIndexRepository
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.config_service import Config
from zet.services.path_service import PathService
from zet.services.workflow_storage import task_state_path


class LibraryIndexService:
    """Build complete index generations from authored and queue records."""

    def __init__(
        self,
        config: Config,
        *,
        index_root: str | Path | None = None,
        project_root: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ):
        self.config = config
        self.paths = PathService(config, project_root or Path.cwd())
        self.queue_paths = AIProxyPathService(config)
        self.repository = LibraryIndexRepository(config.base_library_path, index_root=index_root)
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._sources: list[dict] = []
        self._errors: list[dict] = []
        self._source_payloads: list[dict] = []
        self._reconcile_lock = threading.Lock()
        self.last_scan_metrics = {"parsed_sources": 0, "reused_sources": 0}

    @staticmethod
    def _fingerprint(contents: bytes) -> str:
        return hashlib.sha256(contents).hexdigest()

    def _source_name(self, path: Path, *, queue: bool = False) -> str:
        base = Path(self.config.base_ai_queue_path).resolve() if queue else self.paths.library_path().resolve()
        prefix = "queue" if queue else "library"
        try:
            relative = path.resolve().relative_to(base).as_posix()
        except ValueError:
            relative = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()
        return f"{prefix}/{relative}"

    def _read_json(self, path: Path, source_kind: str, *, queue: bool = False) -> tuple[dict | None, str, str]:
        source_path = self._source_name(path, queue=queue)
        try:
            contents = path.read_bytes()
        except OSError as exc:
            fingerprint = "unreadable"
            self._record_error(source_path, source_kind, fingerprint, str(exc))
            return None, source_path, fingerprint
        fingerprint = self._fingerprint(contents)
        cached = self.repository.cached_source_payload(source_path, fingerprint)
        if cached is not None:
            self.last_scan_metrics["reused_sources"] += 1
            if cached["parsed_json"] is None:
                self._record_error(
                    source_path, source_kind, fingerprint, str(cached["error_message"] or "Invalid JSON.")
                )
                return None, source_path, fingerprint
            value = json.loads(str(cached["parsed_json"]))
            self._sources.append(
                {
                    "source_path": source_path,
                    "source_kind": source_kind,
                    "fingerprint": fingerprint,
                    "parse_status": "valid",
                }
            )
            return value, source_path, fingerprint
        self.last_scan_metrics["parsed_sources"] += 1
        try:
            value = json.loads(contents)
            if not isinstance(value, dict):
                raise ValueError("the JSON root must be an object")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._source_payloads.append(
                {
                    "source_path": source_path,
                    "fingerprint": fingerprint,
                    "parsed_json": None,
                    "error_message": str(exc),
                }
            )
            self._record_error(source_path, source_kind, fingerprint, str(exc))
            return None, source_path, fingerprint
        self._source_payloads.append(
            {
                "source_path": source_path,
                "fingerprint": fingerprint,
                "parsed_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
                "error_message": "",
            }
        )
        self._sources.append(
            {
                "source_path": source_path,
                "source_kind": source_kind,
                "fingerprint": fingerprint,
                "parse_status": "valid",
            }
        )
        return value, source_path, fingerprint

    def _record_error(self, source_path: str, source_kind: str, fingerprint: str, message: str) -> None:
        existing_source = next((item for item in self._sources if item["source_path"] == source_path), None)
        if existing_source is None:
            self._sources.append(
                {
                    "source_path": source_path,
                    "source_kind": source_kind,
                    "fingerprint": fingerprint,
                    "parse_status": "error",
                }
            )
        else:
            existing_source["parse_status"] = "error"
        existing_error = next((item for item in self._errors if item["source_path"] == source_path), None)
        if existing_error is None:
            self._errors.append(
                {
                    "source_path": source_path,
                    "source_kind": source_kind,
                    "message": message,
                    "fingerprint": fingerprint,
                }
            )
        elif message not in existing_error["message"]:
            existing_error["message"] += f"; {message}"

    def _scan_stories(self) -> tuple[list[dict], list[dict], list[dict]]:
        stories: list[dict] = []
        scenes: list[dict] = []
        targets: list[dict] = []
        indexed_story_slugs: set[str] = set()
        root = self.paths.stories_path()
        if not root.is_dir():
            return stories, scenes, targets
        for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("_")):
            duplicate_story = False
            story_candidates = sorted(folder.glob("*.story.json"))
            story_data: dict[str, Any] | None = None
            story_slug = folder.name
            story_source = self._source_name(folder / f"{story_slug}.story.json")
            story_fingerprint = "missing"
            if story_candidates:
                story_data, story_source, story_fingerprint = self._read_json(story_candidates[0], "story")
            else:
                self._record_error(story_source, "story", story_fingerprint, "Story settings record is missing.")
            if story_data is not None:
                story = story_data.get("story")
                if not isinstance(story, dict):
                    self._record_error(story_source, "story", story_fingerprint, "Story settings are missing the story object.")
                else:
                    story_slug = str(story.get("slug") or folder.name)
                    if story_slug in indexed_story_slugs:
                        self._record_error(story_source, "story", story_fingerprint, f"Duplicate story slug {story_slug!r}.")
                        duplicate_story = True
                    else:
                        indexed_story_slugs.add(story_slug)
                        stories.append(
                            {
                                "story_slug": story_slug,
                                "name": str(story.get("title") or story_slug),
                                "source_path": story_source,
                                "fingerprint": story_fingerprint,
                            }
                        )
            if duplicate_story:
                continue
            indexed_order = story_data.get("scene_index", []) if story_data else []
            if not isinstance(indexed_order, list):
                self._record_error(story_source, "story", story_fingerprint, "scene_index must be an array.")
                indexed_order = []
            scene_paths = {path.name.removesuffix(".scene.json"): path for path in folder.glob("*.scene.json")}
            missing_scenes = [str(value) for value in indexed_order if str(value) not in scene_paths]
            if missing_scenes:
                self._record_error(
                    story_source,
                    "story",
                    story_fingerprint,
                    f"scene_index references missing records: {', '.join(missing_scenes)}.",
                )
            ordered_slugs = []
            for value in indexed_order:
                slug = str(value)
                if slug in scene_paths and slug not in ordered_slugs:
                    ordered_slugs.append(slug)
                elif slug in ordered_slugs:
                    self._record_error(story_source, "story", story_fingerprint, f"Duplicate scene_index entry {slug!r}.")
            ordered_slugs.extend(sorted(set(scene_paths) - set(ordered_slugs)))
            indexed_scene_slugs: set[str] = set()
            for position, scene_slug in enumerate(ordered_slugs):
                data, source_path, fingerprint = self._read_json(scene_paths[scene_slug], "scene")
                if data is None:
                    continue
                scene = data.get("scene")
                if not isinstance(scene, dict):
                    self._record_error(source_path, "scene", fingerprint, "Scene record is missing the scene object.")
                    continue
                actual_slug = str(scene.get("slug") or scene_slug)
                scene_name = str(scene.get("name") or actual_slug)
                if actual_slug in indexed_scene_slugs:
                    self._record_error(source_path, "scene", fingerprint, f"Duplicate scene slug {actual_slug!r}.")
                    continue
                indexed_scene_slugs.add(actual_slug)
                scenes.append(
                    {
                        "story_slug": story_slug,
                        "scene_slug": actual_slug,
                        "name": scene_name,
                        "position": position,
                        "source_path": source_path,
                        "fingerprint": fingerprint,
                    }
                )
                targets.append(
                    {
                        "story_slug": story_slug,
                        "scene_slug": actual_slug,
                        "target_id": "main",
                        "name": "Full Scene",
                        "kind": "main",
                        "enabled": 1,
                        "position": 0,
                        "source_path": source_path,
                        "fingerprint": fingerprint,
                    }
                )
                raw_targets = data.get("subscenes") or []
                if not isinstance(raw_targets, list):
                    self._record_error(source_path, "scene", fingerprint, "subscenes must be an array.")
                    continue
                indexed_target_ids = {"main"}
                for target_position, target in enumerate(raw_targets, start=1):
                    if not isinstance(target, dict) or not str(target.get("id") or ""):
                        self._record_error(source_path, "scene", fingerprint, "A render target is malformed.")
                        continue
                    target_id = str(target["id"])
                    if target_id in indexed_target_ids:
                        self._record_error(source_path, "scene", fingerprint, f"Duplicate render target {target_id!r}.")
                        continue
                    indexed_target_ids.add(target_id)
                    targets.append(
                        {
                            "story_slug": story_slug,
                            "scene_slug": actual_slug,
                            "target_id": target_id,
                            "name": str(target.get("name") or target_id),
                            "kind": str(target.get("kind") or "subscene"),
                            "enabled": int(target.get("enabled", True) is not False),
                            "position": target_position,
                            "source_path": source_path,
                            "fingerprint": fingerprint,
                        }
                    )
        return stories, scenes, targets

    def _scan_catalog(self) -> tuple[list[dict], list[dict]]:
        records: list[dict] = []
        relationships: list[dict] = []
        catalog_root = self.paths.image_catalog_root()
        manifest_path = self.paths.image_catalog_inventory_path()
        if manifest_path.is_file():
            manifest, source_path, fingerprint = self._read_json(manifest_path, "catalog_manifest")
            if manifest is not None and manifest != ImageCatalogRepository.MANIFEST:
                self._record_error(source_path, "catalog_manifest", fingerprint, "Catalog manifest format is invalid.")
        organization = catalog_root / "Organization.json"
        if organization.is_file():
            value, source_path, fingerprint = self._read_json(organization, "catalog_organization")
            if value is not None and (
                value.get("schema_version") != ImageCatalogRepository.ORGANIZATION_VERSION
                or not isinstance(value.get("collections"), list)
                or not isinstance(value.get("keywords"), list)
            ):
                self._record_error(
                    source_path, "catalog_organization", fingerprint, "Catalog organization format is invalid."
                )
        reference_sources: dict[str, tuple[str, str]] = {}
        reference_root = catalog_root / "ReferenceSets"
        if reference_root.is_dir():
            for path in sorted(reference_root.glob("*.json")):
                value, source_path, fingerprint = self._read_json(path, "catalog_reference_set")
                if value is None:
                    continue
                reference_set_id = str(value.get("reference_set_id") or "")
                valid_filename = ImageCatalogRepository.reference_filename(reference_set_id) if reference_set_id else ""
                if (
                    value.get("record_version") != ImageCatalogRepository.RECORD_VERSION
                    or not reference_set_id
                    or path.name != valid_filename
                    or reference_set_id in reference_sources
                ):
                    self._record_error(
                        source_path, "catalog_reference_set", fingerprint, "Reference-set record format is invalid."
                    )
                    continue
                reference_sources[reference_set_id] = (source_path, fingerprint)
        records_root = catalog_root / "Records"
        if not records_root.is_dir():
            return records, relationships
        catalog_ids: set[str] = set()
        source_keys: set[str] = set()
        for path in sorted(records_root.glob("*.json")):
            value, source_path, fingerprint = self._read_json(path, "catalog_record")
            if value is None:
                continue
            catalog_id = str(value.get("catalog_id") or "")
            source_key = str(value.get("source_key") or "")
            if (
                value.get("record_version") != ImageCatalogRepository.RECORD_VERSION
                or not catalog_id
                or not source_key
                or path.name != f"{catalog_id}.json"
                or catalog_id in catalog_ids
                or source_key in source_keys
            ):
                self._record_error(source_path, "catalog_record", fingerprint, "Catalog ID/source key or filename is invalid.")
                continue
            raw_managed = value.get("managed_image")
            raw_metadata = value.get("metadata")
            if raw_managed is not None and (
                not isinstance(raw_managed, dict) or str(raw_managed.get("catalog_id") or "") != catalog_id
            ):
                self._record_error(source_path, "catalog_record", fingerprint, "Managed-image data is invalid.")
                continue
            if raw_metadata is not None and not isinstance(raw_metadata, dict):
                self._record_error(source_path, "catalog_record", fingerprint, "Catalog metadata is invalid.")
                continue
            catalog_ids.add(catalog_id)
            source_keys.add(source_key)
            managed = raw_managed or {}
            metadata = raw_metadata or {}
            reference_set_id = str(managed.get("reference_set_id") or "")
            name = str(managed.get("label") or metadata.get("label") or source_key)
            records.append(
                {
                    "catalog_id": catalog_id,
                    "source_key": source_key,
                    "name": name,
                    "semantic_category": str(managed.get("semantic_category") or metadata.get("semantic_category") or ""),
                    "reference_set_id": reference_set_id,
                    "source_path": source_path,
                    "fingerprint": fingerprint,
                }
            )
            if reference_set_id:
                relationships.append(
                    {
                        "reference_set_id": reference_set_id,
                        "catalog_id": catalog_id,
                        "source_path": source_path,
                        "fingerprint": fingerprint,
                    }
                )
                if reference_set_id not in reference_sources:
                    self._record_error(source_path, "catalog_record", fingerprint, f"Missing reference set {reference_set_id!r}.")
        return records, relationships

    @staticmethod
    def _scope(manifest: dict) -> tuple[str, str, str, str]:
        story = str(manifest.get("story_slug") or "")
        scene = str(manifest.get("scene_slug") or "")
        target = str(manifest.get("render_target_id") or ("main" if scene else ""))
        if story or scene:
            return "scene", story, scene, target
        if manifest.get("character") or manifest.get("asset_id") is not None:
            return "asset", "", "", ""
        return "global", "", "", ""

    def _queue_folders(self, root: Path) -> list[Path]:
        if not root.is_dir():
            return []
        return sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))

    def _scan_jobs(self) -> tuple[list[dict], list[dict]]:
        active: list[dict] = []
        history: list[dict] = []
        active_roots = (
            (self.queue_paths.ask_root(), "queued"),
            (self.queue_paths.running_root(), "running"),
            (self.queue_paths.manual_ask_root(), "queued"),
        )
        for root, status in active_roots:
            for folder in self._queue_folders(root):
                if root == self.queue_paths.manual_ask_root() and (
                    (folder / "submission.json").is_file()
                    or (self.queue_paths.manual_answer_root() / folder.name / "answer_manifest.json").is_file()
                    or task_state_path(Path(self.config.base_ai_queue_path), "Superseded", folder.name).is_file()
                ):
                    continue
                path = folder / "ask_manifest.json"
                if not path.is_file():
                    self._record_error(self._source_name(path, queue=True), "active_work", "missing", "ask_manifest.json is missing.")
                    continue
                manifest, source_path, fingerprint = self._read_json(path, "active_work", queue=True)
                if manifest is None:
                    continue
                work_id = str(manifest.get("ask_id") or manifest.get("job_id") or folder.name)
                scope_kind, story, scene, target = self._scope(manifest)
                active.append(
                    {
                        "work_id": work_id,
                        "scope_kind": scope_kind,
                        "story_slug": story,
                        "scene_slug": scene,
                        "render_target_id": target,
                        "status": status,
                        "name": str(manifest.get("task_type") or manifest.get("worker_type") or work_id),
                        "source_path": source_path,
                        "fingerprint": fingerprint,
                    }
                )
        history_roots = (
            self.queue_paths.answer_root(),
            self.queue_paths.manual_answer_root(),
            self.queue_paths.archive_root(),
        )
        seen_paths: set[Path] = set()
        for root in history_roots:
            if not root.is_dir():
                continue
            for answer_path in sorted(root.rglob("answer_manifest.json")):
                resolved = answer_path.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                answer, source_path, fingerprint = self._read_json(answer_path, "job_history", queue=True)
                if answer is None:
                    continue
                ask_path = answer_path.parent / "ask_manifest.json"
                ask: dict = {}
                if ask_path.is_file():
                    loaded, _, _ = self._read_json(ask_path, "job_history_ask", queue=True)
                    ask = loaded or {}
                job_id = str(answer.get("ask_id") or ask.get("ask_id") or answer_path.parent.name)
                scope_kind, story, scene, target = self._scope(ask)
                history.append(
                    {
                        "job_id": job_id,
                        "scope_kind": scope_kind,
                        "story_slug": story,
                        "scene_slug": scene,
                        "render_target_id": target,
                        "status": str(answer.get("status") or "unknown").lower(),
                        "name": str(ask.get("task_type") or ask.get("worker_type") or job_id),
                        "completed_at": str(answer.get("completed_at") or ""),
                        "source_path": source_path,
                        "fingerprint": fingerprint,
                    }
                )
        return active, history

    def snapshot(self) -> IndexSnapshot:
        self._sources = []
        self._errors = []
        self._source_payloads = []
        self.last_scan_metrics = {"parsed_sources": 0, "reused_sources": 0}
        stories, scenes, targets = self._scan_stories()
        catalog, relationships = self._scan_catalog()
        work, history = self._scan_jobs()
        return IndexSnapshot(
            sources=tuple(self._sources),
            stories=tuple(stories),
            scenes=tuple(scenes),
            render_targets=tuple(targets),
            catalog_records=tuple(catalog),
            reference_relationships=tuple(relationships),
            work_items=tuple(work),
            job_summaries=tuple(history),
            errors=tuple(self._errors),
            source_payloads=tuple(self._source_payloads),
        )

    @staticmethod
    def _cursor(fingerprints: Mapping[str, str]) -> str:
        encoded = json.dumps(sorted(fingerprints.items()), separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _completed_at(self) -> str:
        value = self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def reconcile(self) -> dict:
        """Publish changed authored/queue sources and invalidate only their dependents."""
        with self._reconcile_lock:
            return self._reconcile()

    def _reconcile(self) -> dict:
        previous = self.repository.active_source_fingerprints()
        if self.repository.status()["active_generation"] is None:
            report = self.rebuild()
            current = self.repository.active_source_fingerprints()
            self.repository.complete_reconciliation(
                generation=int(report["active_generation"]),
                completed_at=self._completed_at(),
                cursor=self._cursor(current),
                changed_sources=tuple(sorted(current)),
                errors=tuple(self.repository.query_errors(limit=500).items),
            )
            return {**self.repository.status(), "changed_sources": sorted(current), **self.last_scan_metrics}

        try:
            snapshot = self.snapshot()
            current = {str(row["source_path"]): str(row["fingerprint"]) for row in snapshot.sources}
            changed_authored = {
                path for path in set(previous) | set(current) if previous.get(path) != current.get(path)
            }
            changed_dependencies = {
                path
                for path, expected in self.repository.all_dependencies().items()
                if self._dependency_fingerprint(path) != expected
            }
            changed = sorted(changed_authored | changed_dependencies)
            if changed_authored:
                generation = self.repository.begin_rebuild()
                try:
                    self.repository.publish(generation, snapshot)
                except Exception as exc:
                    self.repository.fail_rebuild(generation, str(exc))
                    raise
            else:
                generation = int(self.repository.status()["active_generation"])
            invalidated = self.repository.invalidate_dependencies(changed)
            self.repository.complete_reconciliation(
                generation=generation,
                completed_at=self._completed_at(),
                cursor=self._cursor(current),
                changed_sources=changed,
                errors=tuple(snapshot.errors),
            )
            return {
                **self.repository.status(),
                "changed_sources": changed,
                "invalidated_scopes": invalidated,
                **self.last_scan_metrics,
            }
        except Exception as exc:
            self.repository.fail_reconciliation(completed_at=self._completed_at(), message=str(exc))
            raise

    def dependency_path(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        roots = (
            (self.paths.library_path().resolve(), "library"),
            (Path(self.config.base_ai_queue_path).resolve(), "queue"),
            (self.project_root, "project"),
        )
        for root, prefix in roots:
            try:
                return f"{prefix}/{resolved.relative_to(root).as_posix()}"
            except ValueError:
                pass
        return "external/" + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()

    def dependency_fingerprints(self, paths: Sequence[str | Path]) -> dict[str, str]:
        result: dict[str, str] = {}
        for path in paths:
            resolved = Path(path).resolve()
            key = self.dependency_path(resolved)
            try:
                result[key] = self._fingerprint(resolved.read_bytes())
            except OSError:
                result[key] = "missing"
        return result

    def _dependency_absolute_path(self, path: str) -> Path | None:
        if path.startswith("library/"):
            return self.paths.library_path() / path.removeprefix("library/")
        if path.startswith("queue/"):
            return Path(self.config.base_ai_queue_path) / path.removeprefix("queue/")
        if path.startswith("project/"):
            return self.project_root / path.removeprefix("project/")
        return None

    def _dependency_fingerprint(self, path: str) -> str:
        resolved = self._dependency_absolute_path(path)
        if resolved is None:
            return "unresolvable"
        try:
            return self._fingerprint(resolved.read_bytes())
        except OSError:
            return "missing"

    def record_compilation(
        self,
        story_slug: str,
        scene_slug: str,
        target_id: str,
        *,
        dependency_paths: Sequence[str | Path],
        compiler_version: str,
        result_fingerprint: str,
        result: Mapping | None = None,
    ) -> dict:
        dependencies = self.dependency_fingerprints(dependency_paths)
        combined = self._cursor({"compiler": compiler_version, **dependencies})
        scope_key = f"scene:{story_slug}:{scene_slug}:{target_id}"
        self.repository.record_compilation(
            scope_key,
            compiler_version=compiler_version,
            dependency_fingerprint=combined,
            result_fingerprint=result_fingerprint,
            compiled_at=self._completed_at(),
            dependencies=dependencies,
            result=result,
        )
        return dict(self.repository.compilation(scope_key) or {})

    def compilation_is_current(self, story_slug: str, scene_slug: str, target_id: str) -> bool:
        scope_key = f"scene:{story_slug}:{scene_slug}:{target_id}"
        cached = self.repository.compilation(scope_key)
        if cached is None:
            return False
        dependencies = self.repository.dependencies(scope_key)
        actual: dict[str, str] = {}
        for path in dependencies:
            actual[path] = self._dependency_fingerprint(path)
        expected = self._cursor({"compiler": str(cached["compiler_version"]), **actual})
        return expected == cached["dependency_fingerprint"]

    def rebuild(self) -> dict:
        generation = self.repository.begin_rebuild()
        try:
            snapshot = self.snapshot()
            self.repository.publish(generation, snapshot)
        except Exception as exc:
            self.repository.fail_rebuild(generation, str(exc))
            raise
        status = self.repository.status()
        status["counts"] = {
            "stories": len(snapshot.stories),
            "scenes": len(snapshot.scenes),
            "render_targets": len(snapshot.render_targets),
            "catalog_records": len(snapshot.catalog_records),
            "reference_relationships": len(snapshot.reference_relationships),
            "active_work": len(snapshot.work_items),
            "job_summaries": len(snapshot.job_summaries),
            "errors": len(snapshot.errors),
        }
        return status


class LibraryIndexReconciler:
    """One restartable loop whose delay begins after each completed scan."""

    def __init__(
        self,
        service: LibraryIndexService,
        *,
        interval_seconds: float = 60.0,
        wait: Callable[[float], bool] | None = None,
    ):
        self.service = service
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._thread: threading.Thread | None = None

    def run_cycle(self) -> dict:
        return self.service.reconcile()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_cycle()
            except Exception:
                pass
            if self._wait(self.interval_seconds):
                break

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="zet-library-index-reconciler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
