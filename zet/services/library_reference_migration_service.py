"""Offline migration of saved library paths to configured-universe-relative references."""
from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from typing import Any

from zet.services.atomic_file_service import write_json_atomic
from zet.services.config_service import ConfigService
from zet.services.file_proxy_client import FileProxyClient
from zet.services.library_reference_service import (
    LIBRARY_PATH_FORMAT_VERSION, LibraryReferenceError, count_untyped_library_occurrences,
    migrate_library_document,
)
from zet.services.universe_service import UniverseService
from zet.services.workflow_storage import file_lock


_DATA_FOLDERS = ("Assets", "Characters", "ImageCatalog", "NarrativeStories", "PipelineCandidates",
                 "_state", "images")
_EXCLUDED_PARTS = {
    ".git", "backups", "_backup", "deleted", "archive", "_archive", "_trash", "legacy_review_v1",
    "logs", "log", "debug", "transport", "bundles", "narrativemigration", "universemigration",
}
_ROUTE_FIELDS = {"target_output_dir", "artifact_output_dir", "prompt_condense_template",
                 "pipeline_path", "target_output_file"}
_WAIVED_FIRSTDAY_BATCHES = {
    "a1ed3b000f824a14892001cf69d4bbec",
    "cdfddb1726d94299b43ac5a2c9045c9b",
    "b0eb6b5b168e49c9bfaf64ec4ac9fd36",
}
_WAIVED_TEST_RENDER_RECORDS = {
    "pipelinecandidates/character-pipeline/tsaeytte/adult/costume-dressing/formal_gown/beaf20c0a6724dd9acfd61f222f1fbb1/state.json",
    "pipelinecandidates/character-pipeline/tsaeytte/adult/costume-dressing/paladin/26fb60482f6a47b38ac2316627780125/state.json",
    "pipelinecandidates/character-pipeline/tsaeytte/adult/costume-dressing/romulan_dress/e2d138272b044178b3b9370ced4fa891/state.json",
    "pipelinecandidates/character-pipeline/tsaeytte/elder/costume-dressing/everyday/ac469f53f1244434b59d7967089b4dab/state.json",
}


class LibraryReferenceMigrationError(RuntimeError):
    """The library migration could not safely complete."""


class LibraryReferenceMigrationService:
    def __init__(self, config_path: str | Path, *, old_library_roots: tuple[str | Path, ...] = (),
                 route_roots: tuple[str | Path, ...] = ()):
        self.config_path = Path(config_path).expanduser().resolve()
        self.config = ConfigService.load(self.config_path)
        self.container = Path(self.config.base_library_path).expanduser().resolve()
        self.old_roots = tuple(Path(item).expanduser().resolve() for item in old_library_roots)
        self.route_roots = tuple(Path(item).expanduser().resolve() for item in route_roots)
        identity = hashlib.sha256(os.path.normcase(str(self.container)).encode("utf-8")).hexdigest()[:20]
        from zet.services.storage_path_service import StoragePathService
        state_root = StoragePathService(self.config).ensure_available("migration_state")
        self.report_path = state_root / f"{identity}.json"
        self.lock_path = self.report_path.with_suffix(".lock")
        self.universes = UniverseService(self.container, self.config.state_file(self.config_path.parent, "universe-selection.json"))
        self._fingerprinter = hashlib.sha256()

    @staticmethod
    def _excluded(path: Path) -> bool:
        return any(part.casefold() in _EXCLUDED_PARTS for part in path.parts)

    @staticmethod
    def _is_approved_historical_reference(path: Path, root: Path, reference: str) -> bool:
        """Keep Joe-approved missing FirstDay/test-render references out of blockers."""
        field, separator, value = reference.partition(": ")
        if not separator:
            return False
        try:
            record = path.relative_to(root).as_posix().casefold()
        except ValueError:
            return False
        target = value.replace("\\", "/").casefold()
        if field in {"path", "source_path"} and record.startswith("pipelinecandidates/stories/firstday/"):
            for batch_id in _WAIVED_FIRSTDAY_BATCHES:
                batch = f"/local_batches/{batch_id}/"
                if batch in record and batch in target:
                    return True
        if field == "image_path" and record in _WAIVED_TEST_RENDER_RECORDS:
            return "/local_test_renders/" in target
        return False

    def _universe_roots(self) -> list[tuple[str, Path]]:
        result = []
        for item in self.universes.list_universes():
            root = Path(item["root"]).resolve()
            if root.is_dir():
                result.append((str(item["universe_id"]), root))
        if not result and self.container.is_dir():
            result.append(("Moonsea", self.container))
        return result

    def _migrate_record(self, path: Path, root: Path, report: dict[str, Any], *, fields=None) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            report["errors"].append({"path": str(path), "error": f"Could not read JSON: {exc}"})
            return
        if not isinstance(raw, dict):
            return
        report["excluded_historical_occurrences"] += count_untyped_library_occurrences(
            raw, tuple(str(root) for root in (*self.old_roots, self.container))
        )
        if path.name == "Prompt_Source_Hashes.json" and "sources" not in raw:
            raw = {"sources": [{"path": key, "sha256": value}
                               for key, value in raw.items()
                               if isinstance(key, str) and isinstance(value, str)]}
        migration_input = raw if fields is None else {
            key: value for key, value in raw.items()
            if key in fields or key in {"universe_id", "_producer_id", "library_path_format_version"}
        }
        try:
            converted, count, unresolved = migrate_library_document(migration_input, root, self.old_roots)
        except LibraryReferenceError as exc:
            report["errors"].append({"path": str(path), "error": str(exc)})
            return
        for value in unresolved:
            item = {"path": str(path), "reference": value}
            if self._is_approved_historical_reference(path, root, value):
                report["exempted_historical_references"].append(item)
            else:
                report["unresolved"].append(item)
        before = deepcopy(raw)
        if fields is not None:
            raw.update(converted)
            converted = raw
        if converted != before:
            write_json_atomic(path, converted)
            report["changed_records"] += 1
        report["converted_references"] += count
        report["scanned_records"] += 1
        record_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        self._fingerprinter.update(os.path.normcase(str(path)).encode("utf-8"))
        self._fingerprinter.update(b"\0")
        self._fingerprinter.update(record_hash.encode("ascii"))

    def _migrate_universe(self, universe_id: str, root: Path, report: dict[str, Any]) -> None:
        report["universes"].append({"universe_id": universe_id, "root": str(root)})
        for folder_name in _DATA_FOLDERS:
            folder = root / folder_name
            if not folder.is_dir():
                continue
            for current, dirs, names in os.walk(folder):
                current_path = Path(current)
                dirs[:] = sorted(name for name in dirs if name.casefold() not in _EXCLUDED_PARTS)
                for name in sorted(names):
                    if not name.lower().endswith(".json") or name.endswith(".tmp"):
                        continue
                    record = current_path / name
                    if not self._excluded(record.relative_to(root)):
                        self._migrate_record(record, root, report)
        marker = root / "universe.json"
        if marker.is_file():
            self._migrate_record(marker, root, report)

    def _running_zet_processes(self) -> list[dict[str, Any]]:
        if os.name == "nt":
            command = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "
                       "'zet\\.web\\.app|zet\\.scripts\\.auto_harvest_ai_answers' } | "
                       "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                                    capture_output=True, text=True, timeout=15, check=True)
            payload = json.loads(result.stdout or "[]")
            processes = payload if isinstance(payload, list) else [payload] if payload else []
            return [item for item in processes if int(item.get("ProcessId") or 0) != os.getpid()]
        proc = Path("/proc")
        if proc.is_dir():
            result = []
            for entry in proc.iterdir():
                if not entry.name.isdigit() or int(entry.name) == os.getpid():
                    continue
                try:
                    command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
                except OSError:
                    continue
                if "zet.web.app" in command or "zet.scripts.auto_harvest_ai_answers" in command:
                    result.append({"ProcessId": int(entry.name), "CommandLine": command})
            return result
        return []

    def _route_roots(self) -> tuple[Path, ...]:
        client = FileProxyClient(
            self.config.base_ai_queue_path, storage_root=StoragePathService(self.config).ensure_available("queue_state")
        )
        roots = {client.route_root.resolve(), client.legacy_route_root.resolve(), *self.route_roots}
        return tuple(sorted(roots, key=lambda item: str(item).casefold()))

    def _migrate_routes(self, report: dict[str, Any]) -> None:
        roots_by_id = {universe_id: root for universe_id, root in self._universe_roots()}
        for route_root in self._route_roots():
            if not route_root.is_dir():
                continue
            for route_path in sorted(route_root.glob("*.json")):
                try:
                    route = json.loads(route_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    report["errors"].append({"path": str(route_path), "error": f"Could not read route: {exc}"})
                    continue
                if not isinstance(route, dict):
                    continue
                producer = str(route.get("_producer_id") or "").casefold()
                if producer != socket.gethostname().casefold():
                    continue
                owner = str(route.get("universe_id") or (next(iter(roots_by_id)) if len(roots_by_id) == 1 else ""))
                root = roots_by_id.get(owner)
                if root is None:
                    continue
                scoped = {key: value for key, value in route.items()
                          if key in _ROUTE_FIELDS or key in {"universe_id", "_producer_id", "library_path_format_version"}}
                self._migrate_record(route_path, root, report, fields=set(scoped))

    def _report(self) -> dict[str, Any]:
        return {"status": "running", "format_version": LIBRARY_PATH_FORMAT_VERSION,
                "library_container": str(self.container), "config_path": str(self.config_path),
                "producer": socket.gethostname(), "started_at": datetime.now(timezone.utc).isoformat(),
                "progress": "starting", "fingerprint": hashlib.sha256(b"").hexdigest(),
                "universes": [], "scanned_records": 0, "changed_records": 0,
                "converted_references": 0, "excluded_historical_occurrences": 0,
                "exempted_historical_references": [], "unresolved": [], "errors": []}

    def apply(self) -> dict[str, Any]:
        if not self.container.is_dir():
            raise LibraryReferenceMigrationError(f"Configured library container does not exist: {self.container}")
        try:
            running = self._running_zet_processes()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            raise LibraryReferenceMigrationError(f"Could not verify that Zet and its harvesters are stopped: {exc}") from exc
        if running:
            details = "; ".join(f"{item.get('ProcessId')}: {item.get('CommandLine')}" for item in running)
            raise LibraryReferenceMigrationError("Stop all Zet servers and harvesters before updating library paths: " + details)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock = file_lock(self.lock_path, timeout=0)
            lock.__enter__()
        except TimeoutError as exc:
            raise LibraryReferenceMigrationError("Another library-reference update is already running.") from exc
        try:
            report = self._report()
            self._fingerprinter = hashlib.sha256()
            write_json_atomic(self.report_path, report)
            universes = self._universe_roots()
            for universe_id, root in universes:
                self._migrate_universe(universe_id, root, report)
                report["progress"] = f"scanned universe {universe_id}"
                report["fingerprint"] = self._fingerprinter.hexdigest()
                write_json_atomic(self.report_path, report)
            self._migrate_routes(report)
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            report["status"] = "complete" if not report["unresolved"] and not report["errors"] else "needs_attention"
            if report["status"] == "complete":
                for universe_id, root in universes:
                    write_json_atomic(root / "_state" / "library-reference-format.json",
                                      {"library_path_format_version": LIBRARY_PATH_FORMAT_VERSION,
                                       "universe_id": universe_id})
            report["progress"] = "complete" if report["status"] == "complete" else "verification needs attention"
            report["fingerprint"] = self._fingerprinter.hexdigest()
            report["historical_excluded"] = (
                "Backup/deleted/archive/legacy-review/migration-journal/log/debug folders and immutable queue bundles "
                "are not rewritten; untyped strings in scanned JSON are counted and left unchanged. Joe explicitly "
                "approved preserving missing references in three old FirstDay local batches and four Tsaeytte "
                "Local_Test_Renders state records; these are listed in exempted_historical_references."
            )
            write_json_atomic(self.report_path, report)
            return report
        finally:
            lock.__exit__(None, None, None)
