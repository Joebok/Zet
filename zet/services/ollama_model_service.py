from __future__ import annotations

import json
from urllib import request


class OllamaModelService:
    """Discover locally available Ollama models and their capabilities."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request_json(self, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method="POST" if data is not None else "GET",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            value = json.loads(response.read().decode("utf-8"))
        return value if isinstance(value, dict) else {}

    def list_models(self) -> dict:
        tagged_models = self._request_json("/api/tags").get("models", [])
        names = sorted(
            {
                str(model.get("name") or model.get("model") or "").strip()
                for model in tagged_models
                if isinstance(model, dict)
            }
            - {""},
            key=str.casefold,
        )
        vision_models: list[str] = []
        capability_metadata_available = False
        for name in names:
            try:
                capabilities = self._request_json("/api/show", {"model": name}).get("capabilities")
            except Exception:
                continue
            if isinstance(capabilities, list):
                capability_metadata_available = True
                if "vision" in {str(item).strip().lower() for item in capabilities}:
                    vision_models.append(name)
        filtered = capability_metadata_available and bool(vision_models)
        return {
            "models": vision_models if filtered else names,
            "vision_filtered": filtered,
        }
