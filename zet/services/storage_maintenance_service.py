"""Read-only storage inventory and conservative local-state retention."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import shutil
import time
import uuid

from zet.services.atomic_file_service import write_json_atomic
from zet.services.storage_path_service import StoragePathService


class StorageMaintenanceService:
    REPORT_NAME = "latest.json"

    def __init__(self, config):
        self.config = config
        self.paths = StoragePathService(config)
        self.cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(1, int(config.storage_completed_retention_days))
        )

    @staticmethod
    def _read(path: Path) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _completed(record: dict) -> datetime | None:
        for key in ("completed_at", "harvested_at", "recorded_at", "created_at"):
            stamp = record.get(key)
            if not stamp:
                continue
            try:
                value = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                continue
        return None

    @staticmethod
    def _verified_completed(record: dict) -> bool:
        status = str(record.get("status") or "").upper()
        answer_status = str(record.get("answer_status") or "").upper()
        execution_status = str(record.get("execution_status") or "").upper()
        if any(value in {"FAILED", "ERROR", "HARVEST_FAILED", "INVALID"}
               for value in (status, answer_status, execution_status)):
            return False
        if record.get("error_message") or record.get("failure_stage"):
            return False
        if status in {"APPLIED", "COMPLETE", "COMPLETED", "SUCCESS"}:
            return True
        return status.endswith("_APPLIED") and not status.endswith("_APPLIED_RENDER_QUEUE_FAILED")

    @staticmethod
    def _linked(path: Path) -> bool:
        try:
            return path.is_symlink() or getattr(path.lstat(), "st_reparse_tag", 0) == 0xA0000003
        except FileNotFoundError:
            return False
        except OSError:
            return True

    @classmethod
    def _safe_child(cls, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
        except (OSError, ValueError):
            return False
        relative = path.absolute().relative_to(root.absolute())
        current = root
        for part in relative.parts:
            current = current / part
            if cls._linked(current):
                return False
        return True

    @classmethod
    def _safe_lexical_child(cls, path: Path, root: Path) -> bool:
        """Validate a trusted-root child without resolving OS virtualization aliases."""
        try:
            absolute_path = Path(os.path.abspath(path))
            absolute_root = Path(os.path.abspath(root))
            relative = absolute_path.relative_to(absolute_root)
        except (OSError, ValueError):
            return False
        current = absolute_root
        if cls._linked(current):
            return False
        for part in relative.parts:
            current = current / part
            if cls._linked(current):
                return False
        return True

    @classmethod
    def _tree_size(cls, root: Path, *, max_files: int = 100_000, max_seconds: float = 30) -> dict:
        if not root.exists():
            return {"path": str(root), "exists": False, "files": 0, "bytes": 0}
        total = count = 0
        errors = 0
        started = time.monotonic()
        truncated = False
        for base, directories, files in os.walk(root, followlinks=False):
            if time.monotonic() - started >= max_seconds:
                truncated = True
                break
            safe_directories = []
            for name in directories:
                if time.monotonic() - started >= max_seconds:
                    truncated = True
                    break
                candidate = Path(base) / name
                if not cls._linked(candidate):
                    safe_directories.append(name)
            directories[:] = safe_directories
            for name in files:
                if count >= max_files or time.monotonic() - started >= max_seconds:
                    truncated = True
                    break
                path = Path(base) / name
                if cls._linked(path):
                    continue
                try:
                    total += path.stat().st_size
                    count += 1
                except OSError:
                    errors += 1
            if truncated:
                break
        return {"path": str(root), "exists": True, "files": count, "bytes": total,
                "errors": errors, "truncated": truncated, "max_files": max_files,
                "max_seconds": max_seconds}

    @classmethod
    def _file_manifest(cls, root: Path, *, max_files: int = 100_000, max_seconds: float = 300,
                       checksums: bool = False) -> dict:
        if not root.is_dir() or cls._linked(root):
            return {"files": [], "truncated": False, "exists": root.is_dir()}
        result = []
        started = time.monotonic()
        truncated = False
        skipped_links = []
        for base, directories, files in os.walk(root, followlinks=False):
            if time.monotonic() - started >= max_seconds:
                truncated = True
                break
            safe_directories = []
            for name in directories:
                if time.monotonic() - started >= max_seconds:
                    truncated = True
                    break
                candidate = Path(base) / name
                if cls._linked(candidate):
                    skipped_links.append(str(candidate))
                else:
                    safe_directories.append(name)
            directories[:] = safe_directories
            for name in files:
                if len(result) >= max_files or time.monotonic() - started >= max_seconds:
                    truncated = True
                    break
                path = Path(base) / name
                if cls._linked(path):
                    skipped_links.append(str(path))
                    continue
                try:
                    stat = path.stat()
                    entry = {"source": os.path.normpath(str(path)), "relative": path.relative_to(root).as_posix(),
                             "bytes": stat.st_size}
                    if checksums:
                        digest = hashlib.sha256()
                        with path.open("rb") as handle:
                            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                                digest.update(chunk)
                        current = path.stat()
                        if (stat.st_size, stat.st_mtime_ns) != (current.st_size, current.st_mtime_ns):
                            entry["changed_during_scan"] = True
                        entry["sha256"] = digest.hexdigest()
                    result.append(entry)
                except (OSError, ValueError):
                    continue
            if truncated:
                break
        return {"files": sorted(result, key=lambda item: item["relative"]), "truncated": truncated,
                "exists": True, "max_files": max_files, "max_seconds": max_seconds,
                "skipped_links": skipped_links}

    @classmethod
    def _index_report(cls, root: Path) -> dict:
        result = {"path": str(root), "databases": [], "errors": []}
        if not root.is_dir():
            result["exists"] = False
            return result
        result["exists"] = True
        try:
            files = sorted(path for path in root.glob("*.sqlite3") if path.is_file() and not cls._linked(path))
        except OSError as exc:
            result["errors"].append(str(exc))
            return result
        for path in files:
            record = {"path": str(path), "bytes": path.stat().st_size}
            connection = None
            try:
                connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=1)
                page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
                free_pages = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
                active = connection.execute("SELECT value FROM metadata WHERE key='active_generation'").fetchone()
                generations = int(connection.execute("SELECT COUNT(*) FROM generations").fetchone()[0])
                record.update({"page_count": page_count, "free_pages": free_pages,
                               "active_generation": active[0] if active else None,
                               "generations": generations})
            except sqlite3.Error as exc:
                record["error"] = str(exc)
            finally:
                if connection is not None:
                    connection.close()
            result["databases"].append(record)
        result["database_count"] = len(result["databases"])
        result["bytes"] = sum(item["bytes"] for item in result["databases"])
        result["errors"].extend(item["error"] for item in result["databases"] if item.get("error"))
        return result

    def _legacy_root(self) -> Path:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "Zet"
        return Path.home() / ("Library/Application Support" if os.name == "posix" else "AppData/Local") / "Zet"

    def _receipt_map(self, queue_root: Path) -> dict[tuple[str, str, str], tuple[Path, dict]]:
        result = {}
        if not queue_root.is_dir():
            return result
        for queue_hash in queue_root.iterdir():
            if not queue_hash.is_dir() or self._linked(queue_hash):
                continue
            for host in queue_hash.iterdir():
                if not host.is_dir() or self._linked(host):
                    continue
                receipts = host / "Receipts"
                if not receipts.is_dir() or self._linked(receipts):
                    continue
                for path in receipts.glob("*.json"):
                    if not self._safe_child(path, receipts):
                        continue
                    receipt = self._read(path)
                    ask_id = str(receipt.get("ask_id") or "")
                    if ask_id:
                        result[(queue_hash.name, host.name, ask_id)] = (path, receipt)
        return result

    @staticmethod
    def _string_values(value) -> set[str]:
        if isinstance(value, dict):
            return {str(item) for child in value.values() for item in StorageMaintenanceService._string_values(child)}
        if isinstance(value, list):
            return {str(item) for child in value for item in StorageMaintenanceService._string_values(child)}
        return {value} if isinstance(value, str) else set()

    def _active_workflows(self, host: Path) -> tuple[set[str], int]:
        root = host / "Workflows"
        ids = set()
        ambiguous = 0
        if not root.is_dir() or self._linked(root):
            return ids, ambiguous
        for path in root.glob("*.json"):
            if not self._safe_child(path, root):
                ambiguous += 1
                continue
            record = self._read(path)
            if not record:
                ambiguous += 1
                continue
            status = str(record.get("status") or "").upper()
            if not status:
                ambiguous += 1
            elif status != "COMPLETE":
                ids.update(self._string_values(record))
        return ids, ambiguous

    def report(self, *, include_archive: bool = False, include_legacy: bool = True) -> dict:
        self.paths.require_available()
        areas = {
            name: self._tree_size(self.paths.child(name))
            for name in StoragePathService.CHILDREN
        }
        legacy = self._tree_size(self._legacy_root()) if include_legacy else {"scan": "not requested"}
        shared_queue = self._tree_size(Path(self.config.base_ai_queue_path)) if include_legacy else {"scan": "not requested"}
        archive_path = str(self.config.ai_harvest_archive_path or "")
        archive = Path(archive_path) if archive_path else Path(self.config.base_ai_queue_path) / "Zet_File_Proxy_State/Archive/Harvested"
        if not archive.is_absolute():
            archive = Path(self.config.base_ai_queue_path) / archive
        archive_info = self._tree_size(archive, max_files=20_000, max_seconds=15) if include_archive else {
            "path": str(archive), "exists": archive.is_dir(), "scan": "not requested"
        }
        candidates = self._expired_candidates()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "storage_root": str(self.paths.root),
            "retention_days": self.config.storage_completed_retention_days,
            "areas": areas,
            "index_databases": self._index_report(self.paths.child("indexes")),
            "legacy_appdata": legacy,
            "shared_queue": shared_queue,
            "legacy_archive": archive_info,
            "cleanup": {"dry_run": True, "candidate_count": len(candidates),
                        "files": sum(item["files"] for item in candidates),
                        "bytes": sum(item["bytes"] for item in candidates), "candidates": candidates},
            "protected_records": self._protected_records(),
        }

    def _expired_candidates(self) -> list[dict]:
        candidates = []
        root = self.paths.child("queue_state")
        receipts = self._receipt_map(root)
        for queue_hash in root.iterdir() if root.is_dir() else ():
            if not queue_hash.is_dir() or self._linked(queue_hash):
                continue
            for host in queue_hash.iterdir():
                if not host.is_dir() or self._linked(host):
                    continue
                active_workflow_values, ambiguous_workflows = self._active_workflows(host)
                jobs = host / "Jobs"
                if jobs.is_dir() and not self._linked(jobs):
                    for path in jobs.glob("*.json"):
                        if not self._safe_child(path, jobs):
                            continue
                        record = self._read(path)
                        job_id = str(record.get("ask_id") or "")
                        pair = receipts.get((queue_hash.name, host.name, job_id))
                        if not pair:
                            continue
                        completed = self._completed(pair[1])
                        if (completed is None or completed >= self.cutoff
                                or not self._verified_completed(pair[1]) or ambiguous_workflows
                                or job_id in active_workflow_values):
                            continue
                        candidates.append({"path": str(path), "reason": "completed request detail older than retention",
                                           "files": 1, "bytes": path.stat().st_size, "ask_id": job_id})
                for (receipt_queue, receipt_host, job_id), (path, receipt) in receipts.items():
                    if receipt_queue != queue_hash.name or receipt_host != host.name:
                        continue
                    completed = self._completed(receipt)
                    if (completed is None or completed >= self.cutoff or receipt.get("retention_compacted")
                            or not self._verified_completed(receipt) or ambiguous_workflows
                            or job_id in active_workflow_values):
                        continue
                    if not path.exists() or not self._safe_child(path, path.parent):
                        continue
                    candidates.append({"path": str(path), "reason": "completed receipt eligible for compaction",
                                       "files": 1, "bytes": path.stat().st_size, "ask_id": job_id})
                    structured = host / "StructuredResults" / f"{job_id}.json"
                    if (structured.is_file() and self._safe_child(structured, host / "StructuredResults")
                            and not ambiguous_workflows and job_id not in active_workflow_values):
                        candidates.append({"path": str(structured), "reason": "consumed structured result older than retention",
                                           "files": 1, "bytes": structured.stat().st_size, "ask_id": job_id})
                workflows = host / "Workflows"
                if workflows.is_dir() and not self._linked(workflows):
                    for path in workflows.glob("*.json"):
                        if not self._safe_child(path, workflows):
                            continue
                        record = self._read(path)
                        completed = self._completed(record)
                        if (record.get("status") == "COMPLETE" and completed is not None
                                and completed < self.cutoff and self._safe_child(path, workflows)):
                            candidates.append({"path": str(path), "reason": "completed continuation older than retention",
                                               "files": 1, "bytes": path.stat().st_size})
        return candidates

    def _protected_records(self) -> dict:
        root = self.paths.child("queue_state")
        receipts = self._receipt_map(root)
        counts = {"jobs_without_receipt": 0, "unresolved_or_unknown_receipts": 0,
                  "receipts_without_completion_time": 0, "jobs_referenced_by_active_workflows": 0,
                  "ambiguous_workflows": 0}
        for queue_hash in root.iterdir() if root.is_dir() else ():
            if not queue_hash.is_dir() or self._linked(queue_hash):
                continue
            for host in queue_hash.iterdir():
                if not host.is_dir() or self._linked(host):
                    continue
                active_values, ambiguous = self._active_workflows(host)
                counts["ambiguous_workflows"] += ambiguous
                jobs = host / "Jobs"
                if not jobs.is_dir() or self._linked(jobs):
                    continue
                for path in jobs.glob("*.json"):
                    if not self._safe_child(path, jobs):
                        counts["unresolved_or_unknown_receipts"] += 1
                        continue
                    record = self._read(path)
                    job_id = str(record.get("ask_id") or path.stem)
                    receipt_pair = receipts.get((queue_hash.name, host.name, job_id))
                    if receipt_pair is None:
                        counts["jobs_without_receipt"] += 1
                        continue
                    receipt = receipt_pair[1]
                    if job_id in active_values:
                        counts["jobs_referenced_by_active_workflows"] += 1
                    if not self._verified_completed(receipt):
                        counts["unresolved_or_unknown_receipts"] += 1
                    if self._completed(receipt) is None:
                        counts["receipts_without_completion_time"] += 1
        return counts

    def maintain(self, *, apply: bool = False) -> dict:
        report = self.report(include_legacy=False)
        if not apply:
            return report
        completed = []
        failures = []
        roots = [self.paths.child("queue_state")]
        for root in roots:
            for candidate in report["cleanup"]["candidates"]:
                path = Path(candidate["path"])
                if not self._safe_child(path, root):
                    failures.append({"path": str(path), "error": "path no longer belongs to configured queue state"})
                    continue
                try:
                    if candidate["reason"] == "completed receipt eligible for compaction":
                        receipt = self._read(path)
                        applied = receipt.get("applied_artifact") or {}
                        image_evidence = applied if applied.get("image") and applied.get("sha256") else None
                        compact = {key: receipt[key] for key in (
                            "ask_id", "universe_id", "status", "answer_status", "execution_status",
                            "completed_at", "harvested_at", "recorded_at", "task_type", "asset_id",
                            "story_slug", "scene_slug", "render_target_id",
                        ) if key in receipt}
                        if image_evidence:
                            compact["applied_artifact"] = image_evidence
                        compact["retention_compacted"] = True
                        write_json_atomic(path, compact)
                        completed.append(candidate)
                    else:
                        path.unlink(missing_ok=True)
                        completed.append(candidate)
                except OSError as exc:
                    failures.append({"path": str(path), "error": str(exc)})
        report["cleanup"].update({"dry_run": False, "completed": completed, "failures": failures})
        latest = self.paths.ensure_available("queue_state") / "Maintenance" / self.REPORT_NAME
        write_json_atomic(latest, {
            "generated_at": report["generated_at"], "storage_root": report["storage_root"],
            "retention_days": report["retention_days"], "protected_records": report["protected_records"],
            "cleanup": {"dry_run": False, "candidate_count": report["cleanup"]["candidate_count"],
                        "files": report["cleanup"]["files"], "bytes": report["cleanup"]["bytes"],
                        "completed_count": len(completed), "failures": failures},
        })
        return report

    def run_if_due(self) -> dict | None:
        state_root = self.paths.ensure_available("queue_state")
        from zet.services.workflow_storage import file_lock
        with file_lock(state_root / "Locks" / "coordinator.lock", timeout=0):
            return self._run_if_due_locked(state_root)

    def _run_if_due_locked(self, state_root: Path) -> dict | None:
        marker = state_root / "Maintenance" / "last-run.json"
        previous = self._read(marker)
        last = self._completed(previous)
        interval = timedelta(hours=max(1, int(self.config.storage_maintenance_interval_hours)))
        now = datetime.now(timezone.utc)
        if last is not None and now - last < interval:
            return None
        result = self.maintain(apply=True)
        write_json_atomic(marker, {"completed_at": now.isoformat()})
        return result

    def preview_cutover(self, *, include_archive: bool = False) -> dict:
        report = self.report(include_archive=include_archive, include_legacy=True)
        legacy_root = self._legacy_root()
        legacy_indexes_root = legacy_root / "Indexes"
        legacy_indexes = self._tree_size(legacy_indexes_root)
        legacy_queue_root = self._legacy_root() / "AI_Queue"
        copy_roots = {
            "queue_state": legacy_queue_root,
            "migration_state": self._legacy_root() / "LibraryReferenceUpdates",
            "workflow_state": self._legacy_root() / "TaskWorkflow",
        }
        proposed_copy = {
            name: {"root": str(root), **self._file_manifest(root, checksums=True)}
            for name, root in copy_roots.items() if root.is_dir()
        }
        proposed_copy["file_count"] = sum(len(item["files"]) for item in proposed_copy.values() if isinstance(item, dict))
        proposed_copy["bytes"] = sum(entry["bytes"] for item in proposed_copy.values() if isinstance(item, dict)
                                     for entry in item["files"])
        deletion_indexes = self._file_manifest(legacy_indexes_root)
        deletion_operational = [entry for name, item in proposed_copy.items() if isinstance(item, dict)
                                for entry in item["files"]]
        from dataclasses import replace
        legacy_config = replace(self.config, storage_root=str(legacy_root))
        legacy_state_maintenance = StorageMaintenanceService(legacy_config)
        legacy_retention = legacy_state_maintenance._expired_candidates()
        legacy_protected = legacy_state_maintenance._protected_records()
        report["cutover"] = {
            "dry_run": True,
            "snapshot_requires_quiescence_and_repreview": True,
            "copy": proposed_copy,
            "rebuild_indexes": True,
            "do_not_copy_indexes": {**legacy_indexes, **deletion_indexes,
                                    "database_report": self._index_report(legacy_indexes_root)},
            "delete_after_successful_verification": {
                "indexes": [entry["source"] for entry in deletion_indexes["files"]],
                "copied_operational_state": [entry["source"] for entry in deletion_operational],
            },
            "legacy_queue_state_retention_preview": {
                "candidate_count": len(legacy_retention),
                "candidate_files": legacy_retention,
                "protected_records": legacy_protected,
                "apply_after_copy_and_verification_only": True,
            },
            "source_preserved": True,
            "approval_required_for_copy_or_removal": True,
            "manifest_complete": (not any(item.get("truncated") or any(entry.get("changed_during_scan")
                                                for entry in item.get("files", []))
                                                or item.get("skipped_links")
                                                for item in proposed_copy.values() if isinstance(item, dict))
                                  and not deletion_indexes.get("truncated", False)
                                  and not deletion_indexes.get("skipped_links")),
        }
        return report

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def migrate_from_manifest(self, manifest_path: str | Path) -> dict:
        """Copy verified operational files into configured storage; retain sources."""
        try:
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read cutover manifest: {exc}") from exc
        cutover = manifest.get("cutover") if isinstance(manifest, dict) else None
        if (not isinstance(manifest, dict) or manifest.get("storage_root") != str(self.paths.root)
                or not isinstance(cutover, dict)
                or not cutover.get("manifest_complete")):
            raise ValueError("The manifest is incomplete or targets a different Storage.Root.")
        roots = {
            "queue_state": self._legacy_root() / "AI_Queue",
            "migration_state": self._legacy_root() / "LibraryReferenceUpdates",
            "workflow_state": self._legacy_root() / "TaskWorkflow",
        }
        areas = cutover.get("copy", {})
        results = []
        total_bytes = copied = skipped = 0
        for area, source_root in roots.items():
            listing = areas.get(area)
            if not isinstance(listing, dict):
                continue
            if listing.get("truncated") or listing.get("skipped_links"):
                raise ValueError(f"The {area} manifest is truncated; create a complete preview after shutdown.")
            expected_root = Path(str(listing.get("root") or "")).resolve()
            if expected_root != source_root.resolve():
                raise ValueError(f"The {area} source root does not match the current legacy location.")
            entries = listing.get("files")
            if not isinstance(entries, list):
                raise ValueError(f"The {area} file list is malformed.")
            current = self._file_manifest(source_root, checksums=False)
            if current.get("truncated"):
                raise ValueError(f"Could not completely re-inventory {area}; source was not copied.")
            expected_set = {(str(entry.get("relative")), int(entry.get("bytes", -1)))
                            for entry in entries if isinstance(entry, dict)}
            current_set = {(str(entry.get("relative")), int(entry.get("bytes", -1)))
                           for entry in current["files"]}
            if current_set != expected_set:
                raise ValueError(f"{area} changed after preview; stop writers and create a new cutover manifest.")
            destination_root = self.paths.ensure_available(area)
            area_copied = area_skipped = area_bytes = 0
            for entry in entries:
                relative = Path(str(entry.get("relative") or ""))
                source = Path(os.path.normpath(str(entry.get("source") or "")))
                digest = str(entry.get("sha256") or "")
                expected_source = Path(os.path.normpath(str(source_root / relative)))
                if (relative.is_absolute() or not relative.parts or ".." in relative.parts
                        or os.path.normcase(str(source)) != os.path.normcase(str(expected_source))
                        or not self._safe_lexical_child(expected_source, source_root) or len(digest) != 64):
                    raise ValueError(f"Unsafe or incomplete {area} manifest entry: {entry}")
                source = expected_source
                if self._sha256(source) != digest:
                    raise ValueError(f"Source changed after preview: {source}")
                target = destination_root / relative
                if not self._safe_child(target, destination_root):
                    raise ValueError(f"Unsafe destination path: {target}")
                if target.is_file():
                    if self._sha256(target) != digest:
                        raise ValueError(f"Destination already contains different data; preserved both: {target}")
                    area_skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.copying")
                try:
                    shutil.copy2(source, temporary)
                    if self._sha256(temporary) != digest:
                        raise OSError(f"Checksum mismatch while copying {source}")
                    if target.exists():
                        raise FileExistsError(f"Destination appeared during cutover; preserved it: {target}")
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                area_copied += 1
                area_bytes += int(entry["bytes"])
            copied += area_copied
            skipped += area_skipped
            total_bytes += area_bytes
            results.append({"area": area, "copied_files": area_copied, "already_verified": area_skipped,
                            "copied_bytes": area_bytes})
        return {"storage_root": str(self.paths.root), "copied_files": copied,
                "already_verified_files": skipped, "copied_bytes": total_bytes,
                "areas": results, "source_preserved": True,
                "next_step": "Rebuild indexes, restart Zet, and verify live workflows before approving source removal."}

    @staticmethod
    def verify_database(database: Path) -> dict:
        if not database.is_file():
            return {"path": str(database), "exists": False}
        connection = None
        try:
            import sqlite3
            connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"SQLite integrity check failed: {integrity}")
            return {"path": str(database), "exists": True, "integrity": integrity,
                    "bytes": database.stat().st_size}
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def compact_database(database: Path) -> dict:
        if not database.is_file():
            return {"path": str(database), "exists": False}
        before = database.stat().st_size
        connection = None
        try:
            import sqlite3
            connection = sqlite3.connect(f"file:{database.as_posix()}?mode=rw", uri=True)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"SQLite integrity check failed: {integrity}")
            connection.execute("VACUUM")
            connection.close()
            connection = None
            after = database.stat().st_size
            return {"path": str(database), "before_bytes": before, "after_bytes": after,
                    "reclaimed_bytes": max(0, before - after), "integrity": integrity}
        finally:
            if connection is not None:
                connection.close()

