from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zet.services.config_service import Config


MANUAL_CHATGPT_WORKER_TYPE = "manual_chatgpt_render"


@dataclass(frozen=True)
class ManualRenderTask:
    ask_id: str
    ask_path: Path
    asset_id: int | None
    character: str
    phase: str
    pipeline: str
    pipeline_stage: str
    prompt_file: str
    expected_output: str
    render_preset: str
    updated_at: float
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ask_id": self.ask_id,
            "ask_path": str(self.ask_path),
            "asset_id": self.asset_id,
            "character": self.character,
            "phase": self.phase,
            "pipeline": self.pipeline,
            "pipeline_stage": self.pipeline_stage,
            "prompt_file": self.prompt_file,
            "expected_output": self.expected_output,
            "render_preset": self.render_preset,
            "updated_at": self.updated_at,
        }


class RenderConsoleQueue:
    def __init__(self, config: Config):
        self.config = config

    @property
    def proxy_root(self) -> Path:
        return Path(self.config.base_ai_queue_path) / "Ollama_Proxy"

    @property
    def ask_root(self) -> Path:
        return self.proxy_root / "Ask"

    def _read_json_if_exists(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _task_from_ask_path(self, ask_path: Path) -> ManualRenderTask | None:
        manifest = self._read_json_if_exists(ask_path / "ask_manifest.json")
        if manifest.get("worker_type") != MANUAL_CHATGPT_WORKER_TYPE:
            return None

        asset_id = manifest.get("asset_id")
        try:
            asset_id = int(asset_id) if asset_id is not None else None
        except Exception:
            asset_id = None

        return ManualRenderTask(
            ask_id=str(manifest.get("ask_id") or ask_path.name),
            ask_path=ask_path,
            asset_id=asset_id,
            character=str(manifest.get("character") or ""),
            phase=str(manifest.get("phase") or ""),
            pipeline=str(manifest.get("pipeline") or ""),
            pipeline_stage=str(manifest.get("pipeline_stage") or ""),
            prompt_file=str(manifest.get("prompt_file") or ""),
            expected_output=str(manifest.get("expected_output") or ""),
            render_preset=str(manifest.get("render_preset") or ""),
            updated_at=ask_path.stat().st_mtime,
            manifest=manifest,
        )

    def list_tasks(self) -> list[ManualRenderTask]:
        if not self.ask_root.exists():
            return []
        tasks: list[ManualRenderTask] = []
        for ask_path in sorted(path for path in self.ask_root.iterdir() if path.is_dir()):
            task = self._task_from_ask_path(ask_path)
            if task is not None:
                tasks.append(task)
        tasks.sort(key=lambda task: (task.updated_at, task.ask_id))
        return tasks

    def get_task(self, ask_id: str) -> ManualRenderTask | None:
        for task in self.list_tasks():
            if task.ask_id == ask_id or task.ask_path.name == ask_id:
                return task
        return None

    def read_prompt(self, task: ManualRenderTask) -> str:
        prompt_path = task.ask_path / task.prompt_file
        if not prompt_path.exists() or not prompt_path.is_file():
            return ""
        return prompt_path.read_text(encoding="utf-8")
