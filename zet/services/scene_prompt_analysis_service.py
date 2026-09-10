from __future__ import annotations

from datetime import datetime
import json
import hashlib
from pathlib import Path

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock, supersede_task, task_state_path
from zet.services.summary_cache import invalidate_summary_cache


class ScenePromptAnalysisService:
    """Queue and track AI analyses of compiled Scene Builder prompts."""

    RESULT_FILE = "AI_Prompt_Analysis.md"
    PROMPT_FILE = "OLLAMA_PROMPT.md"
    TASK_TYPE = "scene_prompt_analysis"

    def __init__(self, config, story_service):
        self.config = config
        self.story_service = story_service
        self.path_service = AIProxyPathService(config)

    def queue(self, story_slug: str, scene_slug: str, render_target_id: str = "main", prompt_path: Path | None = None) -> dict:
        pipeline = self.story_service.scene_pipeline_path(story_slug, scene_slug, render_target_id)
        with file_lock(pipeline / "Prompt_Analysis.lock"):
            return self._queue(story_slug, scene_slug, render_target_id, prompt_path)

    def _queue(self, story_slug, scene_slug, render_target_id, prompt_path):
        target_id = str(render_target_id or "main").strip()
        prompt_path = prompt_path or self.story_service.compile_scene_prompt(story_slug, scene_slug, target_id)
        prompt_text = prompt_path.read_text(encoding="utf-8")
        prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        status = self.status(story_slug, scene_slug, target_id, current_prompt_text=prompt_text)
        if status["pending"] and status.get("prompt_sha256") == prompt_hash:
            return status
        result_path = Path(status["result_path"])
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        ask_id = f"Ask_Story_{story_slug}_{scene_slug}_PROMPT_ANALYSIS_{stamp}"
        ask_path = self.path_service.file_proxy_client.create_staging(ask_id)
        instructions_path = Path(__file__).resolve().parents[2] / self.config.ai_prompt_analysis_instructions_file
        manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION,
            "ask_id": ask_id,
            "asset_id": None,
            "character": "",
            "phase": "",
            "pipeline": "Story",
            "pipeline_stage": "PROMPT_ANALYSIS",
            "ollama_attempt_id": f"{stamp}_PROMPT_ANALYSIS",
            "worker_type": "ollama_generate",
            "ollama_model": self.config.ai_prompt_analysis_model,
            "prompt_file": self.PROMPT_FILE,
            "expected_output": self.RESULT_FILE,
            "task_type": self.TASK_TYPE,
            "auxiliary": True,
            "manual": False,
            "target_output_file": self.RESULT_FILE,
            "target_output_dir": str(result_path.parent.resolve()),
            "story_slug": story_slug,
            "scene_slug": scene_slug,
            "render_target_id": target_id,
            "source_prompt_sha256": prompt_hash,
            "ai_prompt_analysis_instructions_file": self.config.ai_prompt_analysis_instructions_file,
        }
        (ask_path / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        instructions = instructions_path.read_text(encoding="utf-8")
        (ask_path / self.PROMPT_FILE).write_text(
            instructions.replace("{{FINAL_IMAGE_PROMPT}}", prompt_text), encoding="utf-8"
        )
        request_path = result_path.with_suffix(".request.json")
        previous = json.loads(request_path.read_text(encoding="utf-8")) if request_path.is_file() else None
        write_json_atomic(request_path, {"ask_id": ask_id, "prompt_sha256": prompt_hash})
        try:
            self.path_service.file_proxy_client.publish(ask_path, ask_id, "ollama_generate")
        except Exception:
            if not self.path_service.file_proxy_client.ready_path(ask_id).exists():
                if previous is None:
                    request_path.unlink(missing_ok=True)
                else:
                    write_json_atomic(request_path, previous)
            raise
        for path in self.path_service.task_paths("ask", "answer", "running"):
            previous = self.path_service.read_ask_manifest(path)
            if previous.get("task_type") == self.TASK_TYPE and previous.get("story_slug") == story_slug and previous.get("scene_slug") == scene_slug and str(previous.get("render_target_id") or "main") == target_id and previous.get("ask_id") != ask_id:
                supersede_task(Path(self.config.base_ai_queue_path), path, "New prompt analysis requested")
        invalidate_summary_cache()
        return self.status(story_slug, scene_slug, target_id, current_prompt_text=prompt_text)

    def status(
        self,
        story_slug: str,
        scene_slug: str,
        render_target_id: str = "main",
        *,
        current_prompt_text: str | None = None,
        pending: bool | None = None,
        verify_current: bool = True,
    ) -> dict:
        target_id = str(render_target_id or "main").strip()
        pipeline_path = self.story_service.scene_pipeline_path(story_slug, scene_slug, target_id)
        result_path = pipeline_path / self.RESULT_FILE
        pending = self._has_pending(story_slug, scene_slug, target_id) if pending is None else pending
        def metadata(path):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}
        request = metadata(result_path.with_suffix(".request.json"))
        result = metadata(result_path.with_suffix(".result.json"))
        prompt = pipeline_path / "Final_Image_Prompt.md"
        if current_prompt_text is not None:
            current_hash = hashlib.sha256(current_prompt_text.encode("utf-8")).hexdigest()
        else:
            current_hash = hashlib.sha256(prompt.read_text(encoding="utf-8").encode("utf-8")).hexdigest() if prompt.is_file() else ""
        renderer = getattr(self.story_service, "story_render_service", None)
        if verify_current and current_prompt_text is None and renderer is not None:
            try:
                current_prompt = renderer._compile(story_slug, scene_slug, target_id, allow_stale_dependencies=True,
                                                   allow_incomplete_reference_descriptions=True)[-2]
                current_hash = hashlib.sha256(current_prompt.replace("\r\n", "\n").encode("utf-8")).hexdigest()
            except Exception:
                current_hash = ""  # Uncompilable current inputs cannot have a current analysis.
        complete = bool(result_path.is_file() and result_path.stat().st_size > 0 and not pending and
                        result.get("ask_id") == request.get("ask_id") and current_hash and
                        result.get("prompt_sha256") == current_hash and result.get("status") == "SUCCESS")
        return {"pending": pending, "complete": complete, "result_path": str(result_path), "render_target_id": target_id,
                "prompt_sha256": request.get("prompt_sha256", ""), "error": result.get("error", ""),
                "stale": bool(result_path.is_file() and not complete and not pending)}

    def pending_count(self, story_slug: str = "", scene_slug: str = "") -> int:
        return sum(
            1
            for story, scene, _target in self._pending_records()
            if (not story_slug or story == story_slug)
            and (not scene_slug or scene == scene_slug)
        )

    def pending_keys(self) -> set[tuple[str, str, str]]:
        return set(self._pending_records())

    def pending_records(self) -> list[tuple[str, str, str]]:
        """Return the current pending task snapshot, preserving duplicate tasks."""
        return self._pending_records()

    def _pending_records(self) -> list[tuple[str, str, str]]:
        records: list[tuple[str, str, str]] = []
        for path in self.path_service.task_paths("ask", "answer", "running"):
            if task_state_path(Path(self.config.base_ai_queue_path), "Superseded", path.name).exists():
                continue
            if (path / "harvest_manifest.json").exists() or not (path / "ask_manifest.json").exists():
                continue
            manifest = self.path_service.read_ask_manifest(path)
            if manifest.get("task_type") != self.TASK_TYPE:
                continue
            records.append((
                str(manifest.get("story_slug") or ""),
                str(manifest.get("scene_slug") or ""),
                str(manifest.get("render_target_id") or "main"),
            ))
        return records

    def list_statuses(self, story_slug: str = "", scene_slug: str = "") -> list[dict]:
        rows = []
        pending_keys = self._pending_keys()
        for story in self.story_service.list_stories():
            if story_slug and story.slug != story_slug:
                continue
            for scene in self.story_service.list_scenes(story.slug):
                if scene_slug and scene.slug != scene_slug:
                    continue
                status = self.status(
                    story.slug,
                    scene.slug,
                    pending=(story.slug, scene.slug, "main") in pending_keys,
                    verify_current=False,
                )
                if status["pending"] or status["complete"]:
                    rows.append({
                        "story_slug": story.slug,
                        "scene_slug": scene.slug,
                        "title": scene.title,
                        **status,
                    })
        return rows

    def _has_pending(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> bool:
        return (story_slug, scene_slug, render_target_id) in self._pending_keys()

    def _pending_keys(self) -> set[tuple[str, str, str]]:
        keys: set[tuple[str, str, str]] = set()
        for path in self.path_service.task_paths("ask", "answer", "running"):
            if task_state_path(Path(self.config.base_ai_queue_path), "Superseded", path.name).exists():
                continue
            if (path / "harvest_manifest.json").exists() or not (path / "ask_manifest.json").exists():
                continue
            manifest = self.path_service.read_ask_manifest(path)
            if manifest.get("task_type") == self.TASK_TYPE:
                keys.add((
                    str(manifest.get("story_slug") or ""),
                    str(manifest.get("scene_slug") or ""),
                    str(manifest.get("render_target_id") or "main"),
                ))
        return keys
