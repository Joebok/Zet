"""AI_Proxy transport owned only by narrative scenes."""
from zet.services.narrative_backdrop_policy import backdrop_reference
import json
from pathlib import Path
import shutil

from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.ai_job_service import AIExecutionError
from zet.services.image_production_service import ImageProductionService


CONSUMER = "zet-narrative-scenes"
RENDER_PRESET = "comfyui-qwen-narrative"


class NarrativeProxyService:
    def __init__(self, app):
        self.app = app
        self.config = app.config
        self.image_production = ImageProductionService(app)

    @property
    def client(self):
        return self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client

    def publish(self, story: str, scene: str, target: str, job: dict, prompt: str,
                *, schema: dict | None = None, references: list[dict] | None = None, width=1216, height=832, seed=0):
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        if paths.jobs.repository.get(job["id"]) or paths.lifecycle.read_receipt(job["id"]):
            return
        worker = ("codex_generate" if str(job.get("model", "")).startswith("codex:") else "ollama_generate") if schema else "local_image_render"
        bundle_files = {"prompt.md": prompt.encode("utf-8")}
        manifest = {
            "version": 1, "ask_id": job["id"], "consumer": CONSUMER, "worker_type": worker,
            "universe_id": self.config.universe_id,
            "narrative_story_id": story, "narrative_scene_id": scene, "narrative_target_id": target,
            "ollama_attempt_id": job["id"], "prompt_file": "prompt.md",
            "expected_output": "answer.json" if schema else "image.png", "auxiliary": True,
            "task_type": "narrative_" + job["kind"], "queue_priority": 100,
            "workflow": "Narrative",
        }
        titles = job.get("queue_titles") or {}
        if any(titles.get(key) for key in ("story", "scene", "target")):
            manifest["queue_titles"] = {key: titles.get(key, "") for key in ("story", "scene", "target")}
        if job.get("candidate_id"):
            manifest["narrative_candidate_id"] = job["candidate_id"]
        if "slot" in job:
            manifest["candidate_slot"] = job["slot"]
        if schema:
            detail = job["detail"]
            role = "narrative_interview" if job["kind"] == "interview" else "narrative_prompt"
            operation = ("composite" if detail["kind"] == "assembly" and detail.get("assembly_mode") == "assemble_references"
                         else "edit" if detail["kind"] == "assembly" or backdrop_reference(detail)
                         else "composite" if job.get("references") else "generate")
            manifest.update(llm_role=role, llm_context={"operation": operation,
                "render_references": [{key: ref.get(key) for key in ("label", "role", "image_index")} for ref in job.get("references", [])],
                "bindings_owned_by_zet": True, "canvas": {"width": detail["width"], "height": detail["height"]},
                "style": detail["context"].get("style", ""), "direction": job.get("message", ""),
                "transparent_background": (detail.get("use_transparent_background", False)
                                            if detail["kind"] == "subscene" else False)})
            manifest.update(ollama_model=job.get("model") or self.config.ai_narrative_scene_model, ollama_chat=True, json_output=True,
                            ollama_allow_unmanaged_model=True,
                            response_schema=schema, ollama_temperature=0.2, ollama_think=False,
                            ollama_request_options={"system": "You are an illustration assistant. Keep reasoning minimal. "
                                                    "Return only the requested JSON, without explaining your process."})
        else:
            request = job.get("render_request") or {}
            settings = request.get("settings", {})
            if request:
                if request.get("universe_id") != self.config.universe_id or request.get("target_id") != target:
                    raise ValueError("Frozen render request belongs to another Narrative target.")
                prompt = request["prompt"]
                references = request.get("inputs", [])
                seed = request["seed"]
                width = settings.get("width", width)
                height = settings.get("height", height)
                manifest["render_request"] = request
                if settings.get("profile_snapshot"):
                    manifest["profile_snapshot"] = settings["profile_snapshot"]
                manifest["checkpoint"] = settings.get("checkpoint", "")
                manifest["render_sizing"] = {key: settings[key] for key in
                    ("render_mode", "aspect_ratio", "target_pixels", "width", "height") if key in settings}
            manifest.update(ollama_model="", image_generation="comfyui",
                            render_preset=settings.get("profile", RENDER_PRESET),
                            workflow_kind=settings.get("profile_snapshot", {}).get("workflow_kind", "qwen_narrative_prompt"),
                            checkpoint=manifest.get("checkpoint", self.config.comfyui_checkpoint),
                            seed=seed, reference_files=references or [],
                            render_overrides={key: settings[key] for key in
                                ("width", "height", "steps", "cfg", "sampler_name", "scheduler", "denoise", "text_encoder", "vae", "disable_prompt_globals") if key in settings}
                                if request else {"width": width, "height": height, "disable_prompt_globals": True})
        if schema and job.get("interview_evidence"):
            folder = self.app.narrative_scene_service.repository.folder(story, scene, target).resolve()
            source = (folder / job["interview_evidence"]["file"]).resolve()
            if not source.is_relative_to(folder):
                raise ValueError("Invalid interview image snapshot.")
            name = "interview-image" + source.suffix
            bundle_files[name] = source.read_bytes()
            manifest["image_files"] = [name]
        if worker == "local_image_render":
            self.image_production.publish_bundle(job["id"], manifest, worker, bundle_files)
        else:
            staging = self.client.staging_path(job["id"])
            self.client.ensure_layout()
            staging.mkdir(exist_ok=True)
            try:
                for name, contents in bundle_files.items():
                    write_bytes_atomic(staging / name, contents)
                write_json_atomic(staging / "ask_manifest.json", manifest)
                self.client.publish(staging, job["id"], worker)
            except Exception:
                if staging.is_dir():
                    shutil.rmtree(staging)
                raise

    def poll(self, story: str, scene: str, target: str, job: dict) -> tuple[str, bytes | str | None]:
        if job.get("kind") == "image":
            expected = {"consumer": CONSUMER, "universe_id": self.config.universe_id,
                        "narrative_story_id": story, "narrative_scene_id": scene,
                        "narrative_target_id": target}
            if job.get("candidate_id"):
                expected["narrative_candidate_id"] = job["candidate_id"]
                expected["image_production"] = {"consumer": CONSUMER,
                    "universe_id": self.config.universe_id, "target_id": target,
                    "candidate_id": job["candidate_id"], "attempt_id": job["id"]}
            if "slot" in job:
                expected["image_production"]["slot"] = job["slot"]
            state, result = self.image_production.collect_bytes(
                job["id"], expected, allow_legacy_owner="slot" not in job)
            if state == "COMPLETE":
                job["proxy_duration_seconds"] = self.image_production.render_duration_seconds(job["id"])
            return state, result
        if job.get("codex_attempt"):
            legacy = self.app.narrative_scene_service.repository.folder(story, scene, target) / "text-jobs" / job["id"] / (job["codex_attempt"] + ".json")
            imported = json.loads(legacy.read_text(encoding="utf-8")) if legacy.is_file() else {}
            if imported.get("attempt") == job["codex_attempt"] or not imported:
                self.app.ai_proxy_service.ai_proxy_path_service.jobs.adopt_legacy_text(job["id"], {
                    "version": 1, "ask_id": job["id"], "consumer": CONSUMER, "universe_id": self.config.universe_id,
                    "narrative_story_id": story, "narrative_scene_id": scene, "narrative_target_id": target,
                    "worker_type": "codex_generate", "ollama_model": job["model"], "expected_output": "answer.json",
                    "task_type": "narrative_" + job["kind"]}, imported.get("result"), str(imported.get("error") or ""),
                    created_at=job.get("created_at", ""))
        answer = self.app.ai_proxy_service.ai_proxy_path_service.answer_path(job["id"])
        if answer.is_dir():
            blocked = self.client.answer_blocked_reason(answer)
            if blocked:
                return "RUNNING", None
            try:
                ask = json.loads((answer / "ask_manifest.json").read_text(encoding="utf-8"))
                expected = {"ask_id": job["id"], "consumer": CONSUMER, "narrative_story_id": story,
                            "narrative_scene_id": scene, "narrative_target_id": target, "universe_id": self.config.universe_id}
                if job.get("candidate_id"):
                    expected["narrative_candidate_id"] = job["candidate_id"]
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
                        provenance.update(model=job["model"], provider="codex" if job["model"].startswith("codex:") else "ollama")
                    if result.get("ollama_runtime"):
                        provenance["runtime"] = result["ollama_runtime"]
                        provenance["effective_model"] = result["ollama_runtime"].get("effective_alias", "")
                filename = str(result["expected_output"])
                if Path(filename).name != filename:
                    return "FAILED", "Invalid AI_Proxy output filename."
                verified = self.app.ai_proxy_service.ai_proxy_path_service.jobs.result(job["id"])
                return ("COMPLETE", verified[0]) if verified is not None else ("RUNNING", None)
            except AIExecutionError as exc:
                return "FAILED", f"Unable to read AI_Proxy answer: {exc}"
            except (OSError, ValueError, KeyError) as exc:
                self.app.ai_proxy_service.ai_proxy_path_service.jobs.repository.collection_failed(
                    job["id"], exc, stage="narrative_collection", path=answer)
                return "RUNNING", None
        if (self.client.running_root / job["id"]).is_dir():
            return "RUNNING", None
        if (self.client.ask_root / job["id"]).is_dir():
            return "QUEUED", None
        return "QUEUED", None

    def release(self, story: str, scene: str, target: str, job: dict) -> None:
        answer = self.app.ai_proxy_service.ai_proxy_path_service.answer_path(job["id"])
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
