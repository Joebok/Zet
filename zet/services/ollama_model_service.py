from __future__ import annotations

import json
from pathlib import Path
import re
import threading
import time
from urllib import request


class OllamaModelService:
    """Discover model metadata and submit structured inference through AI_Proxy."""

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
        """Fetch the current Ollama catalog and persist it for later Config page loads."""
        with self._catalog_lock:
            catalog = self.list_models()
            if self.cache_path is not None:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
                temporary_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
                temporary_path.replace(self.cache_path)
            return catalog

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
        """Stage one structured JSON request through AI_Proxy and return its result."""
        if self.proxy_path_service is None:
            raise RuntimeError("Ollama inference requires the configured AI_Proxy queue.")

        from uuid import uuid4

        paths = self.proxy_path_service
        proxy = paths.file_proxy_client
        ask_id = f"Ask_ZetOllama_{uuid4().hex}"
        staging = proxy.create_staging(ask_id)
        prompt_file = "OLLAMA_PROMPT.md"
        output_file = "OLLAMA_RESPONSE.json"
        image_files: list[str] = []
        for index, image in enumerate(images or []):
            source = Path(image)
            suffix = source.suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                suffix = ".img"
            filename = f"image_{index + 1}{suffix}"
            (staging / filename).write_bytes(source.read_bytes())
            image_files.append(filename)
        (staging / prompt_file).write_text(prompt, encoding="utf-8")
        config = paths.config
        manifest = {
            "version": 1,
            "ask_id": ask_id,
            "ollama_attempt_id": ask_id,
            "worker_type": "ollama_generate",
            "ollama_model": model,
            "ollama_chat": True,
            "ollama_think": False,
            "ollama_temperature": 0.2,
            "ollama_request_options": {"system": system},
            "prompt_file": prompt_file,
            "image_files": image_files,
            "json_output": True,
            "response_schema": schema,
            "expected_output": output_file,
            "task_type": "structured_ollama_inference",
            "consumer": "zet_ollama_model_service",
            "universe_id": str(getattr(config, "universe_id", "Moonsea")),
        }
        (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        proxy.publish(staging, ask_id, "ollama_generate")

        answer_path = proxy.answer_root / ask_id
        deadline = time.monotonic() + self.timeout_seconds
        while not proxy.answer_is_ready(answer_path):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for AI_Proxy Ollama job {ask_id}.")
            time.sleep(min(1.0, max(0.1, deadline - time.monotonic())))
        try:
            answer = json.loads((answer_path / "answer_manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AI_Proxy returned an invalid answer manifest for {ask_id}.") from exc
        if answer.get("ask_id") != ask_id or answer.get("expected_output") != output_file:
            raise RuntimeError(f"AI_Proxy returned a mismatched answer for {ask_id}.")
        status = str(answer.get("status") or "").upper()
        if status != "SUCCESS":
            raise RuntimeError(str(answer.get("error_message") or f"AI_Proxy Ollama job {status or 'failed'}."))
        try:
            content = (answer_path / output_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("AI_Proxy returned no structured response.") from exc
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Ollama JSON response must be an object.")
        runtime = answer.get("ollama_runtime")
        runtime = runtime if isinstance(runtime, dict) else {}
        paths.lifecycle.finish_answer(answer_path, {
            "status": "APPLIED",
            "answer_status": status,
            "task_type": manifest["task_type"],
            "worker_type": manifest["worker_type"],
            "completed_at": answer.get("completed_at", ""),
        })
        return value, runtime

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
