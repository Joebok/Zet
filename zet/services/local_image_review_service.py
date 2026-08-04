from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import random
from typing import Any

from zet.render_console.queue import ManualRenderTask
from zet.services.local_render_backend_service import LocalRenderBackendService


LOCAL_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class LocalImageReviewService:
    def __init__(self, zet_app: Any):
        self.zet_app = zet_app

    def workspace(self, task: ManualRenderTask) -> Path:
        if task.asset_id is not None:
            context = self.zet_app.prompt_review_service.get_context(
                task.character,
                task.phase,
                task.asset_id,
            )
            if context.prompt_path is not None:
                return context.prompt_path.parent
            return self.zet_app.path_service.pipeline_path(context.asset)
        pipeline_path = str(task.manifest.get("pipeline_path") or "").strip()
        return Path(pipeline_path) if pipeline_path else task.ask_path

    def list_images(self, task: ManualRenderTask) -> list[dict[str, Any]]:
        render_dir = self.workspace(task) / "Local_Test_Renders"
        if not render_dir.exists():
            return []
        images = [
            path
            for path in render_dir.iterdir()
            if path.is_file() and path.suffix.lower() in LOCAL_IMAGE_SUFFIXES
        ]
        images.sort(key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
        result = []
        for path in images:
            metadata = self._metadata(path)
            result.append({
                "name": path.name,
                "path": str(path),
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "size_bytes": path.stat().st_size,
                "image_generation": str(metadata.get("image_generation") or metadata.get("backend") or ""),
                "render_profile": str(metadata.get("render_profile") or metadata.get("preset") or metadata.get("profile") or ""),
                "checkpoint": str(metadata.get("checkpoint") or ""),
            })
        return result

    def _metadata(self, image_path: Path) -> dict[str, Any]:
        try:
            data = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def clear_images(self, task: ManualRenderTask) -> int:
        render_dir = self.workspace(task) / "Local_Test_Renders"
        if not render_dir.exists():
            return 0
        removed = 0
        for path in render_dir.iterdir():
            if path.is_file() and path.suffix.lower() in LOCAL_IMAGE_SUFFIXES:
                path.unlink()
                removed += 1
        return removed

    def queue_images(
        self,
        task: ManualRenderTask,
        count: int,
        *,
        checkpoint: str | None = None,
    ) -> list[dict[str, Any]]:
        if count < 1 or count > 10:
            raise ValueError("Local image count must be between 1 and 10.")
        seeds: list[int] = []
        generator = random.SystemRandom()
        while len(seeds) < count:
            seed = generator.randrange(0, 2**63 - 1)
            if seed not in seeds:
                seeds.append(seed)

        queued = []
        if task.asset_id is not None:
            context = self.zet_app.prompt_review_service.get_context(
                task.character,
                task.phase,
                task.asset_id,
            )
            if context.condensed_prompt_path is None:
                raise FileNotFoundError(f"No condensed prompt was found for task {task.ask_id}.")
            for seed in seeds:
                ask_path = self.zet_app.stage_render_task_local_render_ask(
                    task.manifest,
                    context.condensed_prompt_path,
                    context.condensed_prompt_path.parent,
                    allow_parallel=True,
                    seed=seed,
                    checkpoint=checkpoint,
                )
                queued.append({"ask_path": str(ask_path), "seed": seed})
            return queued

        workspace = self.workspace(task)
        for seed in seeds:
            ask_path = self.zet_app.stage_scene_local_render_ask(
                task.manifest,
                workspace,
                allow_parallel=True,
                seed=seed,
                checkpoint=checkpoint,
            )
            queued.append({"ask_path": str(ask_path), "seed": seed})
        return queued

    def queue_images_for_all_checkpoints(
        self,
        task: ManualRenderTask,
        count: int,
    ) -> tuple[list[dict[str, Any]], int]:
        config = self.zet_app.config
        backend = str(config.local_render_backend).strip().lower()
        preset = config.comfyui_profile if backend == "comfyui" else config.local_render_preset
        server_url = config.comfyui_server_url if backend == "comfyui" else ""
        profiles_path = self.zet_app.config_path.resolve().parent / "Config" / "Local_Render_Presets.json"
        checkpoints = LocalRenderBackendService(profiles_path).list_checkpoints(
            preset,
            backend=backend,
            server_url=server_url,
        )
        queued = []
        for item in checkpoints:
            checkpoint = str(item.get("title") or "").strip()
            if checkpoint:
                for render in self.queue_images(task, count, checkpoint=checkpoint):
                    queued.append({**render, "checkpoint": checkpoint})
        return queued, len(checkpoints)
