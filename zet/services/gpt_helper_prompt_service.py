from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class GptHelperPromptRepository:
    def read_object(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}

    def read(self, path: Path) -> dict[str, Any]:
        data = self.read_object(path)
        data.setdefault("schema_version", 1)
        data.setdefault("pipelines", {})
        return data

    def write(self, path: Path, data: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp_path.replace(path)
        return path


class GptHelperPromptService:
    def __init__(self, zet_app: Any, project_root: str | Path, repository: GptHelperPromptRepository | None = None):
        self.zet_app = zet_app
        self.project_root = Path(project_root)
        self.repository = repository or GptHelperPromptRepository()

    @staticmethod
    def view_key(value: Any) -> str:
        return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")

    def _asset(self, task: Any) -> Any | None:
        if task.asset_id is None:
            return None
        try:
            return self.zet_app.asset(task.character, task.phase, int(task.asset_id)).get()
        except Exception:
            return None

    def _legacy_path(self) -> Path:
        local_path = Path(self.zet_app.config_path).resolve().parent / "Config" / "GPT_Helper_Prompts.json"
        return local_path if local_path.exists() else self.project_root / "Config" / "GPT_Helper_Prompts.json"

    def _view_keys(self) -> list[str]:
        data = self.repository.read_object(self.project_root / "Config" / "Prompt_View_Text.json")
        views = data.get("views", {})
        return [str(key) for key in views] if isinstance(views, dict) else []

    def path_for_task(self, task: Any) -> Path | None:
        asset = self._asset(task)
        if asset is None:
            return None
        return self.zet_app.path_service.gpt_helper_prompt_path(asset.character, asset.phase)

    def ensure(self, task: Any) -> Path:
        path = self.path_for_task(task)
        if path is None:
            raise ValueError("Cannot load helper prompts because the render task is not tied to an asset.")
        if not path.exists():
            self.seed(path, task)
        return path

    def seed(self, path: Path, task: Any) -> Path:
        asset = self._asset(task)
        if asset is None:
            raise ValueError("Cannot seed helper prompts because the render task is not tied to an asset.")
        legacy = self.repository.read_object(self._legacy_path())
        defaults = legacy.get("defaults", {}) if isinstance(legacy.get("defaults"), dict) else {}
        legacy_pipelines = legacy.get("pipelines", {}) if isinstance(legacy.get("pipelines"), dict) else {}
        phase_pipelines: dict[str, dict[str, str]] = {}
        for pipeline in self.zet_app.pipeline_repository.list_pipelines(asset.character, asset.phase):
            configured = legacy_pipelines.get(pipeline.name, {})
            configured = configured if isinstance(configured, dict) else {}
            phase_pipelines[pipeline.name] = {
                view: str(configured.get(view) or configured.get("__default") or defaults.get(view) or "").strip()
                for view in self._view_keys()
            }
        return self.repository.write(path, {"schema_version": 1, "pipelines": phase_pipelines})

    def get(self, task: Any) -> dict[str, str]:
        asset = self._asset(task)
        if asset is None:
            return {"text": "", "view": "", "source": ""}
        view = self.view_key(asset.body_view)
        path = self.ensure(task)
        data = self.repository.read(path)
        pipelines = data.get("pipelines", {})
        pipeline_prompts = pipelines.get(asset.pipeline, {}) if isinstance(pipelines, dict) else {}
        text = str(pipeline_prompts.get(view) or "").strip() if isinstance(pipeline_prompts, dict) else ""
        return {
            "text": text,
            "view": view,
            "source": f"pipeline:{asset.pipeline}" if text else "",
            "pipeline": asset.pipeline,
            "config_path": str(path),
        }

    def save(self, task: Any, text: str) -> dict[str, str]:
        asset = self._asset(task)
        if asset is None:
            raise ValueError("Cannot save helper prompt because the render task is not tied to an asset.")
        view = self.view_key(asset.body_view)
        if not view:
            raise ValueError("Cannot save helper prompt because the asset has no view.")
        path = self.ensure(task)
        data = self.repository.read(path)
        pipelines = data.setdefault("pipelines", {})
        if not isinstance(pipelines, dict):
            pipelines = {}
            data["pipelines"] = pipelines
        pipeline_prompts = pipelines.setdefault(asset.pipeline, {})
        if not isinstance(pipeline_prompts, dict):
            pipeline_prompts = {}
            pipelines[asset.pipeline] = pipeline_prompts
        pipeline_prompts[view] = str(text or "").strip()
        self.repository.write(path, data)
        return self.get(task)
