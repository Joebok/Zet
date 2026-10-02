"""Local durable storage and safe cleanup for shared AI proxy queue payloads."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.config_service import Config
from zet.services.file_proxy_client import FileProxyClient
from zet.services.ai_queue_paths import queue_local_state_root


class AIQueueLifecycleService:
    def __init__(self, config: Config):
        self.config = config
        self.queue_root = Path(config.base_ai_queue_path).expanduser().resolve()
        self.root = queue_local_state_root(self.queue_root)
        self.inbox_root = self.root / "Inbox"
        self.receipt_root = self.root / "Receipts"
        self.route_root = self.root / "Routes"
        self.debug_root = self.root / "Debug"

    @property
    def debug_enabled(self) -> bool:
        override = os.environ.get("ZET_AI_QUEUE_DEBUG", "").strip().lower()
        return override in {"1", "true", "yes", "on"} or bool(getattr(self.config, "ai_queue_debug", False))

    def receipt_path(self, job_id: str) -> Path:
        return self.receipt_root / f"{hashlib.sha256(job_id.encode('utf-8')).hexdigest()}.json"

    def read_receipt(self, job_id: str) -> dict:
        try:
            value = json.loads(self.receipt_path(job_id).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def write_receipt(self, job_id: str, receipt: dict) -> None:
        write_json_atomic(self.receipt_path(job_id), receipt)

    def drain_answer(self, source: Path, client: FileProxyClient) -> Path:
        """Copy a complete local-producer result to disk before unlinking Dropbox."""
        if source.parent.resolve() != client.answer_root.resolve():
            raise ValueError("Only direct File_Proxy answers can be drained.")
        if source.is_symlink():
            raise ValueError("Linked answer folders are not eligible for transfer.")
        if any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError("Linked answer contents are not eligible for transfer.")
        job = self._json(source / "job.json")
        if str(job.get("producer_id") or "").casefold() != socket.gethostname().casefold():
            raise ValueError("Answer belongs to a different producer.")
        if self.read_receipt(source.name):
            shutil.rmtree(source)
            return self.inbox_root / source.name
        if not client.answer_is_ready(source):
            raise ValueError(client.answer_blocked_reason(source))
        final = self.inbox_root / source.name
        self.inbox_root.mkdir(parents=True, exist_ok=True)
        if final.is_dir():
            self._verify_equal(source, final)
        else:
            temporary = self.inbox_root / f".{source.name}.{uuid4().hex}.partial"
            try:
                shutil.copytree(source, temporary)
                self._verify_equal(source, temporary)
                os.replace(temporary, final)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        try:
            shutil.rmtree(source)
        except OSError:
            # Keep the verified local copy available even if Dropbox is busy.
            pass
        return final

    def drain_ready_answers(self, client: FileProxyClient) -> list[Path]:
        """Drain only ready answers produced by this machine."""
        drained = []
        if not client.answer_root.is_dir():
            return drained
        for source in sorted(path for path in client.answer_root.iterdir()
                             if path.is_dir() and not path.name.startswith(".")):
            try:
                ask = self._json(source / "ask_manifest.json")
                if str(ask.get("consumer") or "zet").strip().lower() != "zet":
                    continue
                drained.append(self.drain_answer(source, client))
            except (OSError, ValueError):
                # Foreign, unrouted, and incomplete jobs remain shared for recovery.
                continue
        return drained

    def finish_answer(self, answer_path: Path, receipt: dict) -> None:
        """Persist completion before removing a duplicate payload or route."""
        job_id = answer_path.name
        receipt = {**receipt, "ask_id": job_id, "recorded_at": datetime.now(timezone.utc).isoformat()}
        self.write_receipt(job_id, receipt)
        try:
            if self.debug_enabled:
                self.debug_root.mkdir(parents=True, exist_ok=True)
                destination = self.debug_root / job_id
                if answer_path.is_dir() and answer_path.resolve() != destination.resolve():
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.move(str(answer_path), str(destination))
                self._prune_debug()
            elif answer_path.is_dir():
                shutil.rmtree(answer_path)
        finally:
            # Receipt durability is the completion barrier; route removal is idempotent.
            if not answer_path.exists() or self.read_receipt(job_id):
                self.file_proxy_client().remove_route(job_id)

    def fail_stale_gate_answer(self, answer_path: Path, client: FileProxyClient) -> dict:
        """Record and purge a terminal local gate answer whose destination is gone."""
        if answer_path.parent.resolve() != client.answer_root.resolve() or answer_path.is_symlink():
            raise ValueError("Only direct, unlinked proxy answers can be resolved as stale gates.")
        ask_id = answer_path.name
        if Path(ask_id).name != ask_id or ask_id in {"", ".", ".."}:
            raise ValueError("Invalid answer identifier.")
        if any(path.is_symlink() for path in answer_path.rglob("*")):
            raise ValueError("Linked answer contents cannot be resolved automatically.")
        job = self._json(answer_path / "job.json")
        ask = self._json(answer_path / "ask_manifest.json")
        answer = self._json(answer_path / "answer_manifest.json")
        result = self._json(answer_path / "proxy_result.json")
        if str(job.get("producer_id") or "").casefold() != socket.gethostname().casefold():
            raise ValueError("Answer belongs to another producer.")
        task_type = str(ask.get("task_type") or "")
        if ask.get("ask_id") != ask_id or task_type not in {"local_head_image_gate", "local_body_reference_gate"}:
            raise ValueError("Only identified local gate answers can be failed this way.")
        if str(ask.get("universe_id") or "") != str(getattr(self.config, "universe_id", "Moonsea")):
            raise ValueError("Gate answer does not belong to this universe.")
        if str(answer.get("status") or "").upper() != "SUCCESS" or str(result.get("status") or "").upper() != "SUCCEEDED":
            raise ValueError("Gate answer is not a terminal successful producer result.")
        if (client.ask_root / ask_id).exists() or (client.running_root / ask_id).exists():
            raise ValueError("Ask is still queued or running.")
        route = client.load_route(ask_id)
        if str(route.get("_producer_id") or "").casefold() != socket.gethostname().casefold():
            raise ValueError("Local producer route is missing or belongs to another producer.")
        target = Path(str(route.get("target_output_dir") or ""))
        if not target.is_absolute() or target.exists():
            raise ValueError("The routed output destination still exists or is invalid.")
        if str(route.get("universe_id") or "") != str(getattr(self.config, "universe_id", "Moonsea")):
            raise ValueError("The route belongs to another universe.")
        expected_output = str(answer.get("expected_output") or "")
        if not expected_output or Path(expected_output).name != expected_output:
            raise ValueError("Gate output filename is invalid.")
        output_path = answer_path / expected_output
        if not output_path.is_file():
            raise ValueError("Terminal gate output is missing.")
        verdict = output_path.read_text(encoding="utf-8").strip()
        if verdict.upper() not in {"TRUE", "FALSE"}:
            raise ValueError("Gate output is not a recognized terminal verdict.")

        # Save review evidence on this machine before making the Dropbox payload removable.
        evidence_root = self.root / "GateEvidence"
        evidence_root.mkdir(parents=True, exist_ok=True)
        evidence = evidence_root / ask_id
        if not evidence.exists():
            temporary = evidence_root / f".{ask_id}.{uuid4().hex}.partial"
            temporary.mkdir()
            try:
                names = {"job.json", "ask_manifest.json", "answer_manifest.json", "proxy_result.json",
                         "OLLAMA_PROMPT.md", expected_output}
                names.add("candidate.png")
                names.update(str(name) for name in (ask.get("image_files") or [])
                             if isinstance(name, str) and Path(name).name == name and name not in {"", ".", ".."})
                for name in names:
                    source = answer_path / name
                    if source.is_file():
                        shutil.copy2(source, temporary / name)
                os.replace(temporary, evidence)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        receipt = {
            "ask_id": ask_id, "status": "FAILED", "answer_status": "SUCCESS",
            "failure_code": "STALE_GATE_DESTINATION",
            "message": f"Gate answer completed with verdict {verdict}, but its routed run destination no longer exists. Rerun the job if it is still needed.",
            "task_type": task_type, "gate": ask.get("gate", ""),
            "run_id": ask.get("local_head_image_run_id", ""), "candidate_id": ask.get("candidate_id", ""),
            "producer_id": job.get("producer_id", ""), "completed_at": answer.get("completed_at", ""),
            "gate_verdict": verdict.upper(), "evidence_path": str(evidence), "queue_visible": True,
        }
        self.write_receipt(ask_id, {**receipt, "recorded_at": datetime.now(timezone.utc).isoformat()})
        shutil.rmtree(answer_path)
        client.remove_route(ask_id)
        return receipt

    def reconcile_stale_gate_answers(self, client: FileProxyClient) -> list[dict]:
        """Record completed local gates whose run destinations have been removed."""
        results = []
        if not client.answer_root.is_dir():
            return results
        for answer_path in sorted(client.answer_root.iterdir()):
            if not answer_path.is_dir() or answer_path.name.startswith("."):
                continue
            try:
                ask = self._json(answer_path / "ask_manifest.json")
                if ask.get("task_type") not in {"local_head_image_gate", "local_body_reference_gate"}:
                    continue
                results.append(self.fail_stale_gate_answer(answer_path, client))
            except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
                # Incomplete, active, foreign, or ambiguous answers remain retryable.
                results.append({"ask_id": answer_path.name, "status": "RETAINED", "message": str(exc)})
        return results

    def lock_path(self, job_id: str) -> Path:
        """Use a bounded lock pool so completed jobs do not leave one lock each."""
        number = int(hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:8], 16) % 64
        return self.root / "Locks" / f"workflow-{number:02d}.lock"

    def file_proxy_client(self) -> FileProxyClient:
        return FileProxyClient(self.queue_root, route_root=self.route_root)

    def inbox_answers(self) -> list[Path]:
        if not self.inbox_root.is_dir():
            return []
        return sorted(path for path in self.inbox_root.iterdir() if path.is_dir() and not path.name.startswith("."))

    def recent_receipts(self, limit: int = 20) -> list[dict]:
        if not self.receipt_root.is_dir() or limit <= 0:
            return []
        receipts = []
        for path in self.receipt_root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                receipts.append(payload)
        receipts.sort(key=lambda row: str(row.get("harvested_at") or row.get("recorded_at") or ""), reverse=True)
        return receipts[:limit]

    def iter_receipts(self):
        if not self.receipt_root.is_dir():
            return
        for path in self.receipt_root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                yield path, payload

    def cleanup_report(self) -> dict:
        """Describe legacy shared payloads without deleting anything."""
        candidates = []
        archive = Path(self.config.ai_harvest_archive_path)
        if not str(self.config.ai_harvest_archive_path or "").strip():
            archive = self.queue_root / "Zet_File_Proxy_State" / "Archive" / "Harvested"
        elif not archive.is_absolute():
            archive = self.queue_root / archive
        roots = (
            (self.queue_root / "Zet_File_Proxy_State" / "Superseded_Asks", "superseded ask payload"),
            (archive, "legacy harvested payload"),
            (self.queue_root / "Manual_Render_Queue" / "Answer", "manual answer payload"),
        )
        for root, reason in roots:
            if not root.is_dir() or root.is_symlink():
                continue
            if root.name == "Superseded_Asks":
                folders = root.iterdir()
            elif reason == "legacy harvested payload":
                folders = (folder for parent in root.iterdir()
                           if parent.is_dir() and not parent.is_symlink()
                           and parent.resolve().is_relative_to(root.resolve())
                           for folder in parent.iterdir())
            else:
                folders = root.iterdir()
            for folder in folders:
                if (not folder.is_dir() or folder.is_symlink()
                        or not folder.resolve().is_relative_to(root.resolve())):
                    continue
                if root.name != "Superseded_Asks" and not (folder / "harvest_manifest.json").is_file():
                    continue
                files = [path for path in folder.rglob("*") if path.is_file() and not path.is_symlink()]
                candidates.append({"path": str(folder), "reason": reason, "files": len(files),
                                  "bytes": sum(path.stat().st_size for path in files)})
        old_locks = self.queue_root / "Zet_File_Proxy_State" / "Locks"
        if old_locks.is_dir():
            for path in old_locks.iterdir():
                if path.is_file() and not path.is_symlink():
                    candidates.append({"path": str(path), "reason": "legacy persistent lock; retire only after stopping queue workers",
                                       "files": 1, "bytes": path.stat().st_size})
        return {"dry_run": True, "candidate_count": len(candidates),
                "files": sum(item["files"] for item in candidates),
                "bytes": sum(item["bytes"] for item in candidates), "candidates": candidates,
                "unresolved": "Review the report and reconcile gate destinations before legacy cleanup."}

    def _prune_debug(self) -> None:
        now = datetime.now(timezone.utc)
        folders = sorted(
            (path for path in self.debug_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
        )
        for path in folders:
            retention = timedelta(days=max(1, int(getattr(self.config, "ai_queue_debug_retention_days", 7))))
            if now - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > retention:
                shutil.rmtree(path)
        total = sum(p.stat().st_size for folder in self.debug_root.iterdir() if folder.is_dir()
                    for p in folder.rglob("*") if p.is_file())
        for folder in (path for path in sorted(self.debug_root.iterdir(), key=lambda p: p.stat().st_mtime)
                       if path.is_dir()):
            maximum = max(1, int(getattr(self.config, "ai_queue_debug_max_bytes", 1024 * 1024 * 1024)))
            if total <= maximum:
                break
            size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
            shutil.rmtree(folder)
            total -= size

    @staticmethod
    def _json(path: Path) -> dict:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object: {path}")
        return value

    @staticmethod
    def _verify_equal(source: Path, copy: Path) -> None:
        source_files = {p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()}
        copy_files = {p.relative_to(copy).as_posix(): p for p in copy.rglob("*") if p.is_file()}
        if source_files.keys() != copy_files.keys():
            raise IOError("Answer transfer file inventory differs from its source.")
        for relative, original in source_files.items():
            duplicate = copy_files[relative]
            if original.stat().st_size != duplicate.stat().st_size:
                raise IOError(f"Answer transfer size mismatch: {relative}")
            if AIQueueLifecycleService._sha256(original) != AIQueueLifecycleService._sha256(duplicate):
                raise IOError(f"Answer transfer checksum mismatch: {relative}")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


