from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class LocalRenderBackendService:
    def __init__(self, presets_path: str | Path):
        self.presets_path = Path(presets_path)

    def preset(self, preset_name: str) -> dict[str, Any]:
        presets = json.loads(self.presets_path.read_text(encoding="utf-8")) if self.presets_path.exists() else {}
        preset = presets.get(preset_name)
        return preset if isinstance(preset, dict) else {}

    def list_checkpoints(
        self,
        preset_name: str,
        *,
        backend: str = "",
        server_url: str = "",
    ) -> list[dict[str, str]]:
        preset = self.preset(preset_name)
        selected_backend = str(backend or preset.get("backend") or "stable_matrix").strip().lower()
        selected_url = str(
            server_url
            or preset.get("server_url")
            or ("http://127.0.0.1:8188" if selected_backend == "comfyui" else "http://127.0.0.1:7860")
        ).rstrip("/")
        api_path = "/object_info/CheckpointLoaderSimple" if selected_backend == "comfyui" else "/sdapi/v1/sd-models"
        request = Request(selected_url + api_path, method="GET")
        try:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError("Local image backend unavailable.") from exc
        if selected_backend == "comfyui":
            loader = data.get("CheckpointLoaderSimple", {}) if isinstance(data, dict) else {}
            required = loader.get("input", {}).get("required", {}) if isinstance(loader, dict) else {}
            choices = required.get("ckpt_name", [])
            names = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], list) else []
            return [
                {"title": str(name), "model_name": str(name), "filename": str(name), "hash": ""}
                for name in names
                if str(name).strip()
            ]
        if not isinstance(data, list):
            return []
        checkpoints = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("model_name") or "").strip()
            if title:
                checkpoints.append({
                    "title": title,
                    "model_name": str(item.get("model_name") or ""),
                    "filename": str(item.get("filename") or ""),
                    "hash": str(item.get("hash") or ""),
                })
        return checkpoints

    def comfyui_options(self, server_url: str) -> dict[str, Any]:
        request = Request(str(server_url).rstrip("/") + "/object_info", method="GET")
        try:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError("ComfyUI unavailable.") from exc
        if not isinstance(data, dict):
            raise RuntimeError("ComfyUI returned invalid object_info.")

        def choices(node_type: str, input_name: str) -> list[str]:
            node = data.get(node_type, {})
            required = node.get("input", {}).get("required", {}) if isinstance(node, dict) else {}
            value = required.get(input_name, []) if isinstance(required, dict) else []
            values = value[0] if isinstance(value, list) and value and isinstance(value[0], list) else []
            return [str(item) for item in values if str(item).strip()]

        return {
            "checkpoints": choices("CheckpointLoaderSimple", "ckpt_name"),
            "controlnet_models": choices("ControlNetLoader", "control_net_name"),
            "samplers": choices("KSampler", "sampler_name"),
            "schedulers": choices("KSampler", "scheduler"),
            "node_types": sorted(str(name) for name in data),
        }
