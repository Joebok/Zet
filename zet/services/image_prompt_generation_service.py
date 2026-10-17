from __future__ import annotations

import json
import hashlib
from pathlib import Path
import threading
from uuid import uuid4

from zet.services.ollama_model_service import OllamaModelService
from zet.services.atomic_file_service import write_json_atomic
from zet.services.ai_workflow_service import AIWorkflowService
from zet.services.workflow_storage import file_lock


class ImagePromptGenerationService:
    """Analyze an inventory image and return a structured prompt draft."""

    SCHEMA = {
        "type": "object",
        "properties": {"prompt": {"type": "string"}, "negative_prompt": {"type": "string"}},
        "required": ["prompt", "negative_prompt"],
        "additionalProperties": False,
    }
    INSTRUCTIONS = (
        "Analyze the supplied image for image generation. Write a concise positive prompt describing "
        "the visible subject, composition, art style, lighting, and background. Write conservative "
        "negative guidance for artifacts or unwanted additions without negating visible required content. "
        "Do not infer hidden details. Return only the requested JSON object."
    )
    IDENTITY_SCHEMA = {
        "type": "object",
        "properties": {"identity": {"type": "string"}},
        "required": ["identity"],
        "additionalProperties": False,
    }
    IDENTITY_INSTRUCTIONS = (
        "Look at the supplied image and write a short, concise identity description for the pictured "
        "person, creature, place, or object. Include only distinctive visible, stable facts that a "
        "scene builder needs to recognize and depict the same entity when this image is referenced. "
        "Do not write an image generation prompt. Omit composition, camera, lighting, art style, "
        "background, actions, and generic quality terms. Do not guess names, history, personality, "
        "or details that are not visible. Use one compact sentence or phrase. Return only the requested JSON object."
    )

    def __init__(self, zet_app, project_root: str | Path, model_service=None):
        self.zet_app = zet_app
        self.project_root = Path(project_root)
        self.model_service = model_service or OllamaModelService(
            timeout_seconds=600,
            proxy_path_service=zet_app.ai_proxy_service.ai_proxy_path_service,
        )
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self.records_root = Path(zet_app.config.base_library_path) / "_state/ImagePromptJobs"
        if self.records_root.is_dir():
            for path in self.records_root.glob("*.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    self._jobs[value["job_id"]] = value
                except (OSError, ValueError, KeyError):
                    continue

    def start(self, asset_id: str) -> dict:
        return self._start(asset_id, "prompt")

    def start_identity(self, asset_id: str) -> dict:
        return self._start(asset_id, "identity")

    def _start(self, asset_id: str, kind: str) -> dict:
        asset = self.zet_app.entity_library_asset(asset_id)
        if asset.get("status") == "archived":
            raise ValueError("Archived images cannot be analyzed.")
        if not Path(asset["image_path"]).is_file():
            raise ValueError("The image is unavailable.")
        job_id = uuid4().hex
        job = {"job_id": job_id, "asset_id": asset_id, "checksum": asset["checksum"], "kind": kind,
               "status": "RUNNING", "draft": None, "error": "", "existing_prompt": asset.get("prompt", ""),
               "existing_negative_prompt": asset.get("negative_prompt", "")}
        with self._lock:
            self._jobs[job_id] = job
        write_json_atomic(self.records_root / f"{job_id}.json", job)
        AIWorkflowService(self.zet_app).submit(self._run, [job_id, asset], service="image_prompt",
                                             owner={"asset_id": asset_id})
        return self.status(job_id)

    def status(self, job_id: str) -> dict:
        self.zet_app.ai_proxy_service.ai_proxy_path_service.jobs.validate_id(job_id)
        with self._lock, file_lock(self.records_root / f"{job_id}.lock"):
            path = self.records_root / f"{job_id}.json"
            if path.is_file():
                self._jobs[job_id] = json.loads(path.read_text(encoding="utf-8"))
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError("Image prompt analysis job not found.")
            result = dict(job)
        if result["status"] == "COMPLETE":
            try:
                current = self.zet_app.entity_library_asset(result["asset_id"])
                if current.get("checksum") != result["checksum"]:
                    action = "Generate Identity" if result["kind"] == "identity" else "Generate Prompt"
                    result.update(status="FAILED", error=f"The image changed during analysis. Run {action} again.")
            except Exception:
                result.update(status="FAILED", error="The image was removed during analysis.")
        result.pop("checksum", None)
        return result

    def _run(self, job_id: str, asset: dict) -> None:
        with self._lock, file_lock(self.records_root / f"{job_id}.lock"):
            self._execute_analysis(job_id, asset)

    def _execute_analysis(self, job_id: str, asset: dict) -> None:
        if job_id not in self._jobs:
            self._jobs[job_id] = json.loads((self.records_root / f"{job_id}.json").read_text(encoding="utf-8"))
        try:
            with self._lock:
                kind = self._jobs[job_id]["kind"]
            if kind == "identity":
                draft = self._codex(self.zet_app.config.codex_default_model, asset["image_path"],
                                    instructions=self.IDENTITY_INSTRUCTIONS, schema=self.IDENTITY_SCHEMA)
                identity = draft.get("identity")
                if not isinstance(identity, str) or not identity.strip():
                    raise ValueError("Luna returned an empty identity description.")
                with self._lock:
                    self._jobs[job_id].update(status="COMPLETE", draft={"identity": identity.strip()})
                return
            model = str(self.zet_app.config.ai_image_prompt_generation_model or "image-analysis:latest").strip()
            draft = self.model_service.generate_json(model, "You describe image content for image generation.",
                                                     self.INSTRUCTIONS, self.SCHEMA, images=[asset["image_path"]])
            prompt = draft.get("prompt")
            negative = draft.get("negative_prompt")
            if not isinstance(prompt, str) or not isinstance(negative, str):
                raise ValueError("The model returned a malformed prompt draft.")
            with self._lock:
                current = self._jobs[job_id]
                final_prompt = prompt.strip() or current["existing_prompt"]
                if not final_prompt:
                    raise ValueError("The model returned an empty image prompt.")
                current.update(status="COMPLETE", draft={
                    "prompt": final_prompt,
                    "negative_prompt": negative.strip() or current["existing_negative_prompt"],
                })
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].update(status="FAILED", error=str(exc))
        finally:
            write_json_atomic(self.records_root / f"{job_id}.json", self._jobs[job_id])

    def _codex(self, model: str, image_path: str, *, instructions: str | None = None,
               schema: dict | None = None) -> dict:
        return self.zet_app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            "codex:" + model.removeprefix("codex:"), "", instructions or self.INSTRUCTIONS,
            schema or self.SCHEMA, [image_path], task_type="image_prompt_analysis")[0]
