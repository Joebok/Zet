from __future__ import annotations

import base64
import json
from pathlib import Path
import re
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
        return {
            "models": names,
            "vision_models": vision_models,
            "capability_metadata_available": capability_metadata_available,
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
                "options": {"temperature": 0.2},
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
        return value, self.runtime_evidence(model, response)

    def runtime_evidence(self, requested_alias: str, response: dict | None = None) -> dict:
        """Resolve the active managed alias artifact and its Modelfile-owned runtime limits."""
        tags = self._request_json("/api/tags").get("models", [])
        show = self._request_json("/api/show", {"model": requested_alias})
        effective_alias = str((response or {}).get("model") or requested_alias)
        digest = ""
        requested_names = {requested_alias, effective_alias}
        requested_names.update(
            f"{name}:latest" for name in tuple(requested_names) if ":" not in name
        )
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
