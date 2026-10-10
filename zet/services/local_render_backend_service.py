from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zet.services.local_render_policy import require_qwen_profile
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
        preset = require_qwen_profile(self.presets_path.parent.parent, preset_name, backend or "comfyui", presets_path=self.presets_path)
        selected_url = str(server_url or preset.get("server_url") or "http://127.0.0.1:8188").rstrip("/")
        request = Request(selected_url + "/object_info/UNETLoader", method="GET")
        try:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise RuntimeError("Local image backend unavailable.") from exc
        loader = data.get("UNETLoader", {}) if isinstance(data, dict) else {}
        required = loader.get("input", {}).get("required", {}) if isinstance(loader, dict) else {}
        choices = required.get("unet_name", [])
        names = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], list) else []
        supported = set()
        for name in names:
            try:
                require_qwen_profile(self.presets_path.parent.parent, preset_name, checkpoint=str(name), presets_path=self.presets_path)
                supported.add(str(name))
            except ValueError:
                continue
        return [{"title": name, "model_name": name, "filename": name, "hash": ""} for name in names if name in supported]

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
            "diffusion_models": choices("UNETLoader", "unet_name"),
            "text_encoders": sorted(set(
                choices("CLIPLoader", "clip_name")
                + choices("DualCLIPLoader", "clip_name1")
                + choices("DualCLIPLoader", "clip_name2")
            )),
            "vaes": choices("VAELoader", "vae_name"),
            "node_types": sorted(str(name) for name in data),
        }
