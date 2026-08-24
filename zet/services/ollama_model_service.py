from __future__ import annotations

import base64
import json
from pathlib import Path
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

    def generate_json(
        self,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        *,
        images: list[str | Path] | None = None,
    ) -> dict:
        """Generate one structured JSON response with a local Ollama model."""
        user_message: dict = {"role": "user", "content": prompt}
        if images:
            user_message["images"] = [
                base64.b64encode(Path(path).read_bytes()).decode("ascii")
                for path in images
            ]
        response = self._request_json(
            "/api/chat",
            {
                "model": model,
                "stream": False,
                "think": False,
                "format": schema,
                "messages": [
                    {"role": "system", "content": system},
                    user_message,
                ],
                "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 4096},
            },
        )
        content = response.get("message", {}).get("content")
        if not isinstance(content, str):
            raise RuntimeError("Ollama returned no structured response.")
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Ollama JSON response must be an object.")
        return value
