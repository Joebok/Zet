from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


class ScenePromptAnalysisService:
    """Queue and track AI analyses of compiled Scene Builder prompts."""

    RESULT_FILE = "AI_Prompt_Analysis.md"
    PROMPT_FILE = "OLLAMA_PROMPT.md"
    TASK_TYPE = "scene_prompt_analysis"

    def __init__(self, config, story_service):
        self.config = config
        self.story_service = story_service

    def queue(self, story_slug: str, scene_slug: str) -> dict:
        prompt_path = self.story_service.compile_scene_prompt(story_slug, scene_slug)
        status = self.status(story_slug, scene_slug)
        if status["pending"]:
            return status
        result_path = Path(status["result_path"])
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        ask_id = f"Ask_Story_{story_slug}_{scene_slug}_PROMPT_ANALYSIS_{stamp}"
        ask_path = Path(self.config.base_ai_queue_path) / "Ollama_Proxy" / "Ask" / ask_id
        ask_path.mkdir(parents=True, exist_ok=False)
        instructions_path = Path(__file__).resolve().parents[2] / self.config.ai_prompt_analysis_instructions_file
        manifest = {
            "version": 1,
            "ask_id": ask_id,
            "asset_id": None,
            "character": "",
            "phase": "",
            "pipeline": "Story",
            "pipeline_stage": "PROMPT_ANALYSIS",
            "ollama_attempt_id": f"{stamp}_PROMPT_ANALYSIS",
            "worker_type": "ollama_generate",
            "ollama_model": self.config.ai_prompt_review_model,
            "prompt_file": self.PROMPT_FILE,
            "expected_output": self.RESULT_FILE,
            "task_type": self.TASK_TYPE,
            "auxiliary": True,
            "manual": False,
            "target_output_file": self.RESULT_FILE,
            "target_output_dir": str(result_path.parent.resolve()),
            "story_slug": story_slug,
            "scene_slug": scene_slug,
            "ai_prompt_analysis_instructions_file": self.config.ai_prompt_analysis_instructions_file,
        }
        (ask_path / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        instructions = instructions_path.read_text(encoding="utf-8")
        (ask_path / self.PROMPT_FILE).write_text(
            instructions.replace("{{FINAL_IMAGE_PROMPT}}", prompt_path.read_text(encoding="utf-8")), encoding="utf-8"
        )
        return self.status(story_slug, scene_slug)

    def status(self, story_slug: str, scene_slug: str) -> dict:
        pipeline_path = self.story_service.scene_pipeline_path(story_slug, scene_slug)
        result_path = pipeline_path / self.RESULT_FILE
        pending = self._has_pending(story_slug, scene_slug)
        return {"pending": pending, "complete": result_path.exists() and not pending, "result_path": str(result_path)}

    def _has_pending(self, story_slug: str, scene_slug: str) -> bool:
        proxy_root = Path(self.config.base_ai_queue_path) / "Ollama_Proxy"
        roots = [proxy_root / "Ask", proxy_root / "Answer"]
        claimed = proxy_root / "Claimed"
        if claimed.exists():
            roots.extend(path for path in claimed.iterdir() if path.is_dir())
        for root in roots:
            if not root.exists():
                continue
            for path in root.iterdir():
                manifest_path = path / "ask_manifest.json"
                if not path.is_dir() or (path / "harvest_manifest.json").exists() or not manifest_path.exists():
                    continue
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if manifest.get("task_type") == self.TASK_TYPE and manifest.get("story_slug") == story_slug and manifest.get("scene_slug") == scene_slug:
                    return True
        return False
