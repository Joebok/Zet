from __future__ import annotations

import json
import re
from urllib import request
from pathlib import Path
import threading


class OllamaModelService:
    """Compatibility facade for proxy-owned metadata and structured inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 5.0,
        cache_path: str | Path | None = None,
        proxy_path_service=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cache_path = Path(cache_path) if cache_path is not None else None
        self.proxy_path_service = proxy_path_service
        self._catalog_lock = threading.Lock()

    def cached_models(self) -> dict | None:
        """Return the last saved local model catalog, if one is available."""
        if self.proxy_path_service is not None:
            from zet.services.ai_model_catalog_service import AIModelCatalogService
            return AIModelCatalogService(self.proxy_path_service.config.base_ai_queue_path).legacy_options()
        if self.cache_path is None:
            return None
        try:
            value = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or not isinstance(value.get("models"), list):
            return None
        vision_models = value.get("vision_models", [])
        if not isinstance(vision_models, list):
            vision_models = []
        return {
            "models": [str(model) for model in value["models"] if isinstance(model, str)],
            "vision_models": [str(model) for model in vision_models if isinstance(model, str)],
            "capability_metadata_available": bool(value.get("capability_metadata_available", False)),
        }

    def refresh_model_catalog(self) -> dict:
        if self.proxy_path_service is None:
            raise RuntimeError("Model discovery requires the AI_Proxy capability catalog.")
        from zet.services.ai_model_catalog_service import AIModelCatalogService
        catalog = AIModelCatalogService(self.proxy_path_service.config.base_ai_queue_path)
        catalog.catalog(refresh=True)
        return catalog.legacy_options()

    def list_models(self) -> dict:
        """Read the shared proxy catalog; model discovery belongs to AI_Proxy."""
        if self.proxy_path_service is None:
            raise RuntimeError("Model listing requires the AI_Proxy capability catalog.")
        from zet.services.ai_model_catalog_service import AIModelCatalogService
        return AIModelCatalogService(self.proxy_path_service.config.base_ai_queue_path).legacy_options()

    def generate_json(
        self,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        *,
        images: list[str | Path] | None = None,
    ) -> dict:
        value, _ = self.generate_json_with_evidence(model, system, prompt, schema, images=images)
        return value

    def generate_json_with_evidence(
        self,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        *,
        images: list[str | Path] | None = None,
    ) -> tuple[dict, dict]:
        from zet.services.ai_job_service import AIJobService
        if self.proxy_path_service is None:
            raise RuntimeError("AI inference requires the configured AI_Proxy queue.")
        return AIJobService(self.proxy_path_service).generate_json(
            model, system, prompt, schema, images, timeout=self.timeout_seconds)


    # Compatibility only: immutable legacy envelopes use AI_Manager/ollama_proxy_worker.py.
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

    def runtime_evidence(self, requested_alias: str, response: dict | None = None) -> dict:
        """Resolve managed alias evidence for the AI_Proxy worker."""
        tags = self._request_json("/api/tags").get("models", [])
        show = self._request_json("/api/show", {"model": requested_alias})
        effective_alias = str((response or {}).get("model") or requested_alias)
        digest = ""
        requested_names = {requested_alias, effective_alias}
        requested_names.update(f"{name}:latest" for name in tuple(requested_names) if ":" not in name)
        for item in tags if isinstance(tags, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "")
            if name in requested_names:
                digest = str(item.get("digest") or "")
                break
        parameters = str(show.get("parameters") or "")
        if not parameters:
            parameters = str(show.get("modelfile") or "")
        runtime_settings = {}
        for key in ("num_ctx", "num_predict"):
            match = re.search(rf"(?m)^(?:PARAMETER\s+)?{key}\s+([^\s#]+)", parameters)
            if match:
                raw = match.group(1)
                runtime_settings[key] = int(raw) if raw.isdigit() else raw
        missing = [key for key in ("num_ctx", "num_predict") if key not in runtime_settings]
        if not digest or missing:
            details = []
            if not digest:
                details.append("alias digest")
            if missing:
                details.append("managed " + "/".join(missing))
            raise RuntimeError(
                f"Ollama runtime evidence for {requested_alias} is incomplete: missing {', '.join(details)}."
            )
        return {
            "requested_alias": requested_alias,
            "effective_alias": effective_alias,
            "digest": digest,
            "runtime_settings": runtime_settings,
        }
