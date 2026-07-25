from __future__ import annotations

from datetime import datetime
from pathlib import Path
import random
from typing import Any

from zet.render_console.queue import ManualRenderTask


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
        return [
            {
                "name": path.name,
                "path": str(path),
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "size_bytes": path.stat().st_size,
            }
            for path in images
        ]

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

    def queue_images(self, task: ManualRenderTask, count: int) -> list[dict[str, Any]]:
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
            )
            queued.append({"ask_path": str(ask_path), "seed": seed})
        return queued
