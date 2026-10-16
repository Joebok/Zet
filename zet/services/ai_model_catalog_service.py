"""One cached capability catalog for every Zet model control and submission."""
from __future__ import annotations

import json
from pathlib import Path

from zet.services.ai_queue_paths import queue_local_state_root
from zet.services.atomic_file_service import write_json_atomic


class AIModelCatalogService:
    def __init__(self, queue_root):
        self.queue_root = Path(queue_root)
        self.cache_path = queue_local_state_root(queue_root) / "model_catalog.json"
        self.shared_path = self.queue_root / "File_Proxy/Control/model_catalog.json"

    @staticmethod
    def _read(path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or value.get("version") != 1
                or not isinstance(value.get("models"), list)
                or any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
                       or not isinstance(item.get("capabilities"), list) for item in value["models"])):
            raise ValueError("Unsupported AI_Proxy model catalog")
        return value

    def catalog(self, refresh=False):
        error = ""
        try:
            shared = self._read(self.shared_path)
            write_json_atomic(self.cache_path, shared)
            value = shared
        except (OSError, ValueError) as exc:
            error = str(exc)
            try:
                value = self._read(self.cache_path)
            except (OSError, ValueError):
                value = {"version": 1, "models": [], "refreshed_at": "", "errors": {}}
        if refresh:
            # Metadata refresh is a request to the proxy, never a direct backend lookup.
            request = self.queue_root / "File_Proxy/Control/refresh-models.json"
            write_json_atomic(request, {"version": 1})
        return {**value, "stale": bool(error or value.get("errors")), "cache_error": error}

    def models(self, *, required=(), providers=("codex", "ollama")):
        return [item for item in self.catalog()["models"] if item.get("provider") in providers
                and set(required).issubset(item.get("capabilities", []))]

    def validate(self, model, *, required=(), providers=("codex", "ollama")):
        normalized = model.removeprefix("ollama:") if model.startswith("ollama:") else model
        matches = [item for item in self.models(required=required, providers=providers) if item["id"] == normalized]
        if not matches:
            raise ValueError(f"Model {model!r} is unavailable or lacks the required capabilities: {', '.join(required) or 'text'}")
        return matches[0]

    def legacy_options(self):
        catalog = self.catalog()
        ollama = [item for item in catalog["models"] if item["provider"] == "ollama"]
        return {"models": [item["id"] for item in ollama],
                "vision_models": [item["id"] for item in ollama if "vision" in item.get("capabilities", [])],
                "codex_models": [item["id"] for item in catalog["models"] if item["provider"] == "codex"],
                "capability_metadata_available": True, "refreshed_at": catalog.get("refreshed_at", ""),
                "stale": catalog["stale"], "errors": catalog.get("errors", {})}
