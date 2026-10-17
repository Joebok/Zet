from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zet.services.local_render_policy import require_qwen_profile


class LocalRenderBackendService:
    def __init__(self, presets_path: str | Path, queue_root=None, *, config=None):
        self.presets_path = Path(presets_path)
        self.queue_root = queue_root
        self.config = config

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
        preset = require_qwen_profile(self.presets_path.parent.parent, preset_name, backend or "comfyui", presets_path=self.presets_path)
        names = self._catalog().get("comfyui_options", {}).get("diffusion_models", [])
        supported = set()
        for name in names:
            try:
                require_qwen_profile(self.presets_path.parent.parent, preset_name, checkpoint=str(name), presets_path=self.presets_path)
                supported.add(str(name))
            except ValueError:
                continue
        return [{"title": name, "model_name": name, "filename": name, "hash": ""} for name in names if name in supported]

    def _catalog(self):
        if self.queue_root is None:
            raise RuntimeError("Backend metadata requires the configured AI_Proxy catalog.")
        from zet.services.ai_model_catalog_service import AIModelCatalogService
        return AIModelCatalogService(self.queue_root, config=self.config).catalog()

    def comfyui_options(self, server_url: str = "") -> dict[str, Any]:
        value = self._catalog().get("comfyui_options", {})
        if not value:
            raise RuntimeError("ComfyUI metadata is not cached yet. Refresh the AI_Proxy catalog after backend startup.")
        return value
