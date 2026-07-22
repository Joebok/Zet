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

    def list_checkpoints(self, preset_name: str) -> list[dict[str, str]]:
        server_url = str(self.preset(preset_name).get("server_url") or "http://127.0.0.1:7860").rstrip("/")
        request = Request(server_url + "/sdapi/v1/sd-models", method="GET")
        try:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError("Local image backend unavailable.") from exc
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
