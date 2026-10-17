"""Explicit deletion of failed, locally owned queue jobs; never library assets."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import socket

from zet.repositories.ai_job_repository import AIJobRepository, timestamp
from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock, task_state_path


class AIJobCleanupService:
    ELIGIBLE = {"HARVEST_FAILED", "RECOVERY_REQUIRED"}

    def __init__(self, paths):
        self.paths = paths
        self.lifecycle = paths.lifecycle
        self.client = paths.file_proxy_client
        self.repository = AIJobRepository(self.lifecycle.root)

    @staticmethod
    def _read(path):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _linked(path):
        try:
            # pathlib.is_junction is only available from Python 3.12 onward.
            return path.is_symlink() or getattr(path.lstat(), "st_reparse_tag", 0) == 0xA0000003
        except FileNotFoundError:
            return False

    @staticmethod
    def _safe(path, root):
        """Check absolute containment and links before any recursive deletion."""
        root = root.absolute()
        path = path.absolute()
        if path == root or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Cleanup path escapes its queue storage: {path}")
        for item in (path, *path.parents):
            if AIJobCleanupService._linked(item):
                raise ValueError(f"Linked cleanup paths are not allowed: {item}")
        if path.is_dir():
            for item in path.rglob("*"):
                if AIJobCleanupService._linked(item):
                    raise ValueError(f"Linked cleanup contents are not allowed: {item}")

    def delete(self, job_id):
        self.paths.jobs.validate_id(job_id)
        if job_id.endswith(".") or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", job_id, re.IGNORECASE):
            raise ValueError("Invalid AI job identifier for deletion.")
        with file_lock(self.lifecycle.root / "Locks/coordinator.lock"), file_lock(self.lifecycle.lock_path(job_id)):
            return self._delete(job_id)

    def _delete(self, job_id):
        from zet.services.ai_queue_query_service import AIQueueQueryService
        marker = self.repository.deletion_path(job_id)
        previous = self._read(marker)
        row = next((row for row in AIQueueQueryService(self.paths).rows() if row["ask_id"] == job_id), None)
        if not previous and (not row or row["status"] not in self.ELIGIBLE):
            raise ValueError("Only HARVEST_FAILED or RECOVERY_REQUIRED jobs can be deleted. Refresh the queue.")
        # Never race the external dispatcher or delete an executing request, even
        # if a stale local collection failure overrides its displayed status.
        if any((root / job_id).exists() for root in (self.client.ask_root, self.client.running_root)):
            raise ValueError("This job is queued or running and cannot be deleted.")

        local = self.lifecycle.root
        queue = self.lifecycle.queue_root
        targets = [(root / job_id, root) for root in (
            self.client.answer_root, self.paths.manual_ask_root(), self.paths.manual_answer_root(),
            self.lifecycle.inbox_root, self.lifecycle.debug_root,
            queue / "Zet_File_Proxy_State/Superseded_Asks")]
        targets += [(self.client.staging_path(job_id), self.client.ask_root),
                    (self.repository.path(job_id), local), (self.lifecycle.receipt_path(job_id), local),
                    (self.client.route_root / f"{job_id}.json", self.client.route_root),
                    (self.client.legacy_route_root / f"{job_id}.json", self.client.legacy_route_root),
                    (local / "StructuredResults" / f"{job_id}.json", local),
                    (self.client.route_root / f".{job_id}.json.tmp", self.client.route_root),
                    (task_state_path(queue, "Superseded", job_id, state_root=self.lifecycle.storage_root), local),
                    (task_state_path(queue, "Manual_Render_Publications", job_id, state_root=self.lifecycle.storage_root), local)]
        if self.lifecycle.inbox_root.is_dir():
            targets += [(path, local) for path in self.lifecycle.inbox_root.iterdir()
                        if path.name == f".{job_id}.legacy" or re.fullmatch(
                            re.escape(f".{job_id}.") + r"[0-9a-f]{32}\.partial", path.name)]
        archive = self.paths.harvested_archive_root()
        if archive.is_dir():
            for day in archive.iterdir():
                if day.is_dir():
                    targets.append((day / job_id, archive))
                    targets += [(path, archive) for path in day.iterdir() if re.fullmatch(
                        re.escape(job_id) + r"[._][0-9]{6}_[0-9]{6}", path.name)]
        # Followup reservations contain the parent identity, not arbitrary paths.
        followups = local / "Followups"
        if followups.is_dir():
            targets += [(path, followups) for path in followups.glob("*.json")
                        if self._read(path).get("parent_id") == job_id]

        record = self.repository.get(job_id)
        evidence = [record, previous]
        if (self.lifecycle.inbox_root / job_id).is_dir():
            evidence.append({"producer_id": socket.gethostname()})
        for path, root in targets:
            self._safe(path, root)
            if path.is_dir():
                envelope = self._read(path / "job.json")
                ask = self._read(path / "ask_manifest.json")
                if envelope.get("job_id") not in {None, "", job_id} or ask.get("ask_id") not in {None, "", job_id}:
                    raise ValueError(f"Job identity conflicts with its folder: {path}")
                evidence.append(envelope)
            elif path.suffix == ".json":
                evidence.append(self._read(path))
        producers = {str(item["producer_id"]).casefold() for item in evidence if item.get("producer_id")}
        if producers != {socket.gethostname().casefold()}:
            raise ValueError("Cannot verify that all job files belong to this machine. Restore ownership metadata before deleting.")
        self._safe(marker, local)
        deletion = {"version": 1, "ask_id": job_id, "producer_id": socket.gethostname(),
                    "universe_id": (row or previous).get("universe_id", ""),
                    "deleted_at": previous.get("deleted_at") or timestamp(), "cleanup_complete": False}
        write_json_atomic(marker, deletion)
        try:
            for path, root in targets:
                self._safe(path, root)
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            write_json_atomic(marker, {**deletion, "error": f"Cleanup incomplete: {exc}"})
            raise
        write_json_atomic(marker, {**deletion, "cleanup_complete": True})
        return {"ask_id": job_id, "deleted": True}
