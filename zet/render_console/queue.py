from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION, AIProxyAskManifest
from zet.services.ai_proxy_path_service import AIProxyPathService
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
        story_slug = str(self.manifest.get("story_slug") or "")
        scene_slug = str(self.manifest.get("scene_slug") or "")
        if story_slug or scene_slug:
            display_label = " / ".join(value for value in [story_slug, scene_slug] if value)
        elif self.asset_id is not None:
            display_label = f"Asset {self.asset_id}"
        else:
            display_label = self.ask_id
        return {
            "ask_id": self.ask_id,
            "display_label": display_label,
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
        self.path_service = AIProxyPathService(config)

    @property
    def proxy_root(self) -> Path:
        return self.path_service.manual_root()

    @property
    def ask_root(self) -> Path:
        return self.path_service.manual_ask_root()

    @property
    def answer_root(self) -> Path:
        return self.path_service.manual_answer_root()

    def _timestamp(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _read_json_if_exists(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _task_from_ask_path(self, ask_path: Path) -> ManualRenderTask | None:
        manifest = AIProxyAskManifest.from_dict(self._read_json_if_exists(ask_path / "ask_manifest.json")).to_dict()
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

    def write_answer_image(self, task: ManualRenderTask, image_bytes: bytes, content_type: str = "", render_comment: str = "") -> Path:
        """Write a successful manual render answer and optional review comment."""
        if not image_bytes:
            raise ValueError("No image data was provided.")
        if not task.expected_output:
            raise ValueError(f"Task {task.ask_id} has no expected_output.")

        self.answer_root.mkdir(parents=True, exist_ok=True)
        answer_path = self.answer_root / task.ask_path.name
        if answer_path.exists():
            raise FileExistsError(f"Answer folder already exists: {answer_path}")

        shutil.copytree(task.ask_path, answer_path)
        output_path = answer_path / task.expected_output
        output_path.write_bytes(image_bytes)
        target_output = str(task.manifest.get("target_output_file") or "").strip()
        if target_output:
            target_path = Path(target_output)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(image_bytes)
        comment = str(render_comment or "").strip()
        if comment:
            (answer_path / "Render_Review_Comment.md").write_text(comment + "\n", encoding="utf-8")

        completed_at = self._timestamp()
        answer_manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION,
            "ask_id": task.ask_id,
            "asset_id": task.asset_id,
            "ollama_attempt_id": str(task.manifest.get("ollama_attempt_id") or ""),
            "worker_id": "manual-chatgpt-render-console",
            "status": "SUCCESS",
            "expected_output": task.expected_output,
            "started_at": completed_at,
            "completed_at": completed_at,
            "elapsed_seconds": 0,
            "error_type": "",
            "error_message": "",
            "content_type": content_type,
            "render_comment": comment,
            "target_output_file": target_output,
        }
        (answer_path / "answer_manifest.json").write_text(
            json.dumps(answer_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.rmtree(task.ask_path)
        return answer_path

    def write_failed_answer(self, task: ManualRenderTask, reason: str = "") -> Path:
        self.answer_root.mkdir(parents=True, exist_ok=True)
        answer_path = self.answer_root / task.ask_path.name
        if answer_path.exists():
            raise FileExistsError(f"Answer folder already exists: {answer_path}")

        shutil.copytree(task.ask_path, answer_path)
        completed_at = self._timestamp()
        message = reason.strip() or "Manual ChatGPT render failed from Render Console."
        answer_manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION,
            "ask_id": task.ask_id,
            "asset_id": task.asset_id,
            "ollama_attempt_id": str(task.manifest.get("ollama_attempt_id") or ""),
            "worker_id": "manual-chatgpt-render-console",
            "status": "ERROR",
            "expected_output": task.expected_output,
            "started_at": completed_at,
            "completed_at": completed_at,
            "elapsed_seconds": 0,
            "error_type": "MANUAL_RENDER_FAILED",
            "error_message": message,
        }
        (answer_path / "answer_manifest.json").write_text(
            json.dumps(answer_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.rmtree(task.ask_path)
        return answer_path
