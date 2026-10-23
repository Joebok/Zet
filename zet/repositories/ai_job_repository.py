"""Producer-local request records; transport state remains AI_Proxy-owned."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from zet.services.atomic_file_service import write_json_atomic, read_json


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class AIJobRepository:
    def __init__(self, root: Path):
        self.root = root / "Jobs"

    def path(self, job_id):
        return self.root / (hashlib.sha256(str(job_id).encode()).hexdigest() + ".json")

    def deletion_path(self, job_id):
        return self.root.parent / "DeletedJobs" / self.path(job_id).name

    def is_deleted(self, job_id):
        return self.deletion_path(job_id).exists()

    def get(self, job_id):
        from zet.services.storage_health_service import guard_path
        guard_path(self.root)
        try:
            value = read_json(self.path(job_id))
            return value if isinstance(value, dict) else {}
        except FileNotFoundError:
            # A not-yet-recorded job is common during polling; require() still
            # checks the root even when the full probe is on its normal cadence.
            guard_path(self.root)
            return {}
        except ValueError:
            return {}

    def put(self, job_id, record):
        if self.is_deleted(job_id):
            return
        write_json_atomic(self.path(job_id), {**record, "ask_id": job_id, "updated_at": timestamp()})

    def update(self, job_id, **changes):
        self.put(job_id, {**self.get(job_id), **changes})

    def collection_failed(self, job_id, exc, *, stage="application", path=""):
        attempts = int(self.get(job_id).get("collection_failures") or 0) + 1
        retry_at = (datetime.now(timezone.utc) + timedelta(seconds=min(30, 2 ** min(attempts, 5)))).isoformat() if isinstance(exc, OSError) else ""
        self.update(job_id, harvest_state="HARVEST_FAILED", error=str(exc),
                    failure_stage=stage, exception_type=type(exc).__name__,
                    affected_path=str(path or getattr(exc, "filename", "") or ""), failed_at=timestamp(),
                    collection_failures=attempts, collection_retry_at=retry_at)

    def all(self):
        from zet.services.storage_health_service import guard_path
        guard_path(self.root)
        if self.root.is_dir():
            for path in self.root.glob("*.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(value, dict) and not self.is_deleted(value.get("ask_id", "")):
                        yield value
                except FileNotFoundError:
                    guard_path(self.root, force=True)
                    continue
                except ValueError:
                    continue

    def register(self, job_id, manifest, envelope, request=None):
        current = self.get(job_id)
        if current:
            return
        model = str(manifest.get("model") or manifest.get("ollama_model") or manifest.get("checkpoint") or "")
        provider = str(manifest.get("provider") or ("manual" if manifest.get("worker_type") == "manual_chatgpt_render" else "codex" if model.startswith("codex:") else
                       "comfyui" if manifest.get("worker_type") == "local_image_render" else "ollama"))
        self.put(job_id, {"version": 1, "created_at": envelope["created_at"], "producer_id": envelope["producer_id"],
                         "logical_job_id": manifest.get("logical_job_id", ""),
                         "universe_id": manifest.get("universe_id", ""), "task_type": manifest.get("task_type", ""),
                         "consumer": manifest.get("consumer", "zet"), "model": model, "provider": provider,
                         "workflow": manifest.get("workflow") or manifest.get("pipeline") or manifest.get("task_type", ""),
                         "worker_type": manifest.get("worker_type", ""), "asset_id": manifest.get("asset_id"),
                         "owner": {key: manifest[key] for key in manifest if key.endswith("_id") or key in {"story_slug", "scene_slug", "character", "phase", "view", "costume"}},
                         "manifest": manifest, "request": request or {}, "input_inventory": envelope.get("files", []),
                         "envelope": envelope,
                         "harvest_state": "PUBLISHED"})
