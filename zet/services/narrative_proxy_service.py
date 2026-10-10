"""AI_Proxy transport owned only by narrative scenes."""
import json
from pathlib import Path
import shutil

from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic


CONSUMER = "zet-narrative-scenes"
RENDER_PRESET = "comfyui-qwen-narrative"


class NarrativeProxyService:
    def __init__(self, app):
        self.app = app
        self.config = app.config

    @property
    def client(self):
        return self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client

    def publish(self, story: str, scene: str, target: str, job: dict, prompt: str,
                *, schema: dict | None = None, references: list[dict] | None = None, width=1216, height=832, seed=0):
        worker = "ollama_generate" if schema else "local_image_render"
        staging = self.client.create_staging(job["id"])
        manifest = {
            "version": 1, "ask_id": job["id"], "consumer": CONSUMER, "worker_type": worker,
            "universe_id": self.config.universe_id,
            "narrative_story_id": story, "narrative_scene_id": scene, "narrative_target_id": target,
            "ollama_attempt_id": job["id"], "prompt_file": "prompt.md",
            "expected_output": "answer.json" if schema else "image.png", "auxiliary": True,
            "task_type": "narrative_" + job["kind"], "queue_priority": 100,
        }
        if schema:
            manifest.update(ollama_model=job.get("model") or self.config.ai_narrative_scene_model, ollama_chat=True, json_output=True,
                            ollama_allow_unmanaged_model=True,
                            response_schema=schema, ollama_temperature=0.2, ollama_think=False,
                            ollama_request_options={"system": "You are a concise illustration assistant. Keep reasoning minimal. "
                                                    "Return only the requested JSON, without explaining your process."})
        else:
            manifest.update(ollama_model="", image_generation="comfyui", render_preset=RENDER_PRESET,
                            workflow_kind="qwen_narrative_prompt", checkpoint=self.config.comfyui_checkpoint,
                            seed=seed, reference_files=references or [],
                            render_overrides={"width": width, "height": height, "disable_prompt_globals": True})
        try:
            write_bytes_atomic(staging / "prompt.md", prompt.encode("utf-8"))
            write_json_atomic(staging / "ask_manifest.json", manifest)
            self.client.publish(staging, job["id"], worker)
        except Exception:
            if staging.is_dir():
                shutil.rmtree(staging)
            raise

    def poll(self, story: str, scene: str, target: str, job: dict) -> tuple[str, bytes | str | None]:
        answer = self.client.answer_root / job["id"]
        if answer.is_dir():
            blocked = self.client.answer_blocked_reason(answer)
            if blocked:
                return "RUNNING", None
            try:
                ask = json.loads((answer / "ask_manifest.json").read_text(encoding="utf-8"))
                expected = {"ask_id": job["id"], "consumer": CONSUMER, "narrative_story_id": story,
                            "narrative_scene_id": scene, "narrative_target_id": target, "universe_id": self.config.universe_id}
                if job.get("model") and job["kind"] != "image":
                    expected["ollama_model"] = job["model"]
                if any(ask.get(key) != value for key, value in expected.items()):
                    return "FAILED", "Answer ownership did not match this narrative target."
                result = json.loads((answer / "answer_manifest.json").read_text(encoding="utf-8"))
                if result.get("ask_id") != job["id"] or result.get("expected_output") != ask["expected_output"]:
                    return "FAILED", "Answer did not match the requested output."
                if result.get("status") != "SUCCESS":
                    return "FAILED", str(result.get("error_message") or "AI_Proxy job failed.")
                if job.get("kind") != "image":
                    provenance = job.setdefault("provenance", {})
                    if ask.get("ollama_model"):
                        job.setdefault("model", ask["ollama_model"])
                        provenance.update(model=job["model"], provider="ollama")
                    if result.get("ollama_runtime"):
                        provenance["runtime"] = result["ollama_runtime"]
                        provenance["effective_model"] = result["ollama_runtime"].get("effective_alias", "")
                filename = str(result["expected_output"])
                if Path(filename).name != filename:
                    return "FAILED", "Invalid AI_Proxy output filename."
                return "COMPLETE", (answer / filename).read_bytes()
            except (OSError, ValueError, KeyError) as exc:
                return "FAILED", f"Unable to read AI_Proxy answer: {exc}"
        if (self.client.running_root / job["id"]).is_dir():
            return "RUNNING", None
        if (self.client.ask_root / job["id"]).is_dir():
            return "QUEUED", None
        return "FAILED", "AI_Proxy no longer has this job; retry it."

    def release(self, story: str, scene: str, target: str, job: dict) -> None:
        answer = self.client.answer_root / job["id"]
        if not answer.is_dir() or self.client.answer_blocked_reason(answer):
            return
        try:
            ask = json.loads((answer / "ask_manifest.json").read_text(encoding="utf-8"))
            if (ask.get("ask_id"), ask.get("consumer"), ask.get("universe_id"), ask.get("narrative_story_id"), ask.get("narrative_scene_id"), ask.get("narrative_target_id")) != (job["id"], CONSUMER, self.config.universe_id, story, scene, target):
                return
        except (OSError, ValueError):
            return
        self.client.remove_answer(job["id"])
        self.client.remove_route(job["id"])
