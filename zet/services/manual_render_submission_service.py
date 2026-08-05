from __future__ import annotations

from pathlib import Path

from zet.render_console.queue import ManualRenderTask, RenderConsoleQueue


class ManualRenderSubmissionService:
    def __init__(self, queue: RenderConsoleQueue):
        self.queue = queue

    @staticmethod
    def _matches_story(task: ManualRenderTask, story_slug: str, scene_slug: str) -> bool:
        manifest = task.manifest
        return (not story_slug or manifest.get("story_slug") == story_slug) and (
            not scene_slug or manifest.get("scene_slug") == scene_slug
        )

    def list_tasks(
        self,
        character: str = "",
        phase: str = "",
        story_slug: str = "",
        scene_slug: str = "",
    ) -> list[ManualRenderTask]:
        tasks = self.queue.list_tasks()
        if character:
            tasks = [task for task in tasks if not task.character or task.character == character]
        if phase:
            tasks = [task for task in tasks if not task.phase or task.phase == phase]
        if story_slug or scene_slug:
            tasks = [task for task in tasks if self._matches_story(task, story_slug, scene_slug)]
        return tasks

    def get_task(
        self,
        ask_id: str,
        character: str = "",
        phase: str = "",
        story_slug: str = "",
        scene_slug: str = "",
    ) -> ManualRenderTask | None:
        task = self.queue.get_task(ask_id)
        if task is None:
            return None
        if character and task.character and task.character != character:
            return None
        if phase and task.phase and task.phase != phase:
            return None
        if (story_slug or scene_slug) and not self._matches_story(task, story_slug, scene_slug):
            return None
        return task

    def replace_prompt(self, task: ManualRenderTask, prompt: str) -> Path:
        path = task.ask_path / task.prompt_file
        path.write_text(prompt, encoding="utf-8")
        return path

    def submit_image(
        self,
        task: ManualRenderTask,
        image_bytes: bytes,
        content_type: str = "",
        render_comment: str = "",
    ) -> Path:
        return self.queue.write_answer_image(task, image_bytes, content_type, render_comment)

    def submit_failure(self, task: ManualRenderTask, reason: str = "") -> Path:
        return self.queue.write_failed_answer(task, reason)
