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
        if task.manifest.get("render_bundle_hash") or (task.ask_path / "submission.json").exists():
            raise ValueError("This prompt belongs to a staged render bundle. Recompile to create a new render attempt.")
        path = task.ask_path / task.prompt_file
        path.write_text(prompt, encoding="utf-8")
        return path

    def submit_image(
        self,
        task: ManualRenderTask,
        image_bytes: bytes,
        content_type: str = "",
        render_comment: str = "",
        refinement_required: bool = False,
        additional_image_generations: int = 0,
        refinement_note: str = "",
    ) -> Path:
        note = str(refinement_note or "").strip()
        if not isinstance(refinement_required, bool):
            raise ValueError("Refinement required must be a boolean.")
        if isinstance(additional_image_generations, bool) or not isinstance(additional_image_generations, int):
            raise ValueError("Additional image generations must be an integer.")
        if additional_image_generations < 0 or additional_image_generations > 10000:
            raise ValueError("Additional image generations must be between 0 and 10000.")
        if len(note) > 2000:
            raise ValueError("Refinement note must be 2000 characters or fewer.")
        if refinement_required:
            if additional_image_generations < 1:
                raise ValueError("Additional image generations must be at least 1 when refinement was required.")
        elif additional_image_generations or note:
            raise ValueError("Refinement count and note require the refinement checkbox.")
        refinement = {
            "schema_version": 1,
            "required": bool(refinement_required),
            "additional_image_generations": int(additional_image_generations),
            "note": note,
        }
        return self.queue.write_answer_image(
            task,
            image_bytes,
            content_type,
            render_comment,
            chatgpt_refinement=refinement,
        )

    def submit_failure(self, task: ManualRenderTask, reason: str = "") -> Path:
        return self.queue.write_failed_answer(task, reason)
