"""Producer-local request records; transport state remains AI_Proxy-owned."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from zet.services.atomic_file_service import write_json_atomic


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class AIJobRepository:
    def __init__(self, root: Path):
        self.root = root / "Jobs"

    def path(self, job_id):
        return self.root / (hashlib.sha256(str(job_id).encode()).hexdigest() + ".json")

    def get(self, job_id):
        try:
            value = json.loads(self.path(job_id).read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def put(self, job_id, record):
        write_json_atomic(self.path(job_id), {**record, "ask_id": job_id, "updated_at": timestamp()})

    def update(self, job_id, **changes):
        self.put(job_id, {**self.get(job_id), **changes})

    def all(self):
        if self.root.is_dir():
            for path in self.root.glob("*.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(value, dict):
                        yield value
                except (OSError, ValueError):
                    continue

    def register(self, job_id, manifest, envelope, request=None):
        current = self.get(job_id)
        if current:
            return
        model = str(manifest.get("model") or manifest.get("ollama_model") or manifest.get("checkpoint") or "")
        provider = str(manifest.get("provider") or ("manual" if manifest.get("worker_type") == "manual_chatgpt_render" else "codex" if model.startswith("codex:") else
                       "comfyui" if manifest.get("worker_type") == "local_image_render" else "ollama"))
        self.put(job_id, {"version": 1, "created_at": envelope["created_at"], "producer_id": envelope["producer_id"],
                         "universe_id": manifest.get("universe_id", ""), "task_type": manifest.get("task_type", ""),
                         "consumer": manifest.get("consumer", "zet"), "model": model, "provider": provider,
                         "workflow": manifest.get("workflow") or manifest.get("pipeline") or manifest.get("task_type", ""),
                         "worker_type": manifest.get("worker_type", ""), "asset_id": manifest.get("asset_id"),
                         "owner": {key: manifest[key] for key in manifest if key.endswith("_id") or key in {"story_slug", "scene_slug", "character", "phase", "view", "costume"}},
                         "manifest": manifest, "request": request or {}, "input_inventory": envelope.get("files", []),
                         "harvest_state": "PUBLISHED"})
