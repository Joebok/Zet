from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from uuid import uuid4

from zet.services.ollama_model_service import OllamaModelService


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

    def __init__(self, zet_app, project_root: str | Path, model_service=None, runner=subprocess.run):
        self.zet_app = zet_app
        self.project_root = Path(project_root)
        self.model_service = model_service or OllamaModelService(timeout_seconds=600)
        self.runner = runner
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}

    def start(self, asset_id: str) -> dict:
        return self._start(asset_id, "prompt")

    def start_identity(self, asset_id: str) -> dict:
        return self._start(asset_id, "identity")

    def _start(self, asset_id: str, kind: str) -> dict:
        asset = self.zet_app.entity_library_asset(asset_id)
        if asset.get("status") == "archived":
            raise ValueError("Archived images cannot be analyzed.")
        if hashlib.sha256(Path(asset["image_path"]).read_bytes()).hexdigest() != asset["checksum"]:
            raise ValueError("The image changed outside the library. Refresh the inventory before analysis.")
        job_id = uuid4().hex
        job = {"job_id": job_id, "asset_id": asset_id, "checksum": asset["checksum"], "kind": kind,
               "status": "RUNNING", "draft": None, "error": "", "existing_prompt": asset.get("prompt", ""),
               "existing_negative_prompt": asset.get("negative_prompt", "")}
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run, args=(job_id, asset), daemon=True)
        thread.start()
        return self.status(job_id)

    def status(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError("Image prompt analysis job not found.")
            result = dict(job)
        if result["status"] == "COMPLETE":
            try:
                current = self.zet_app.entity_library_asset(result["asset_id"])
                if (current.get("checksum") != result["checksum"]
                        or hashlib.sha256(Path(current["image_path"]).read_bytes()).hexdigest() != result["checksum"]):
                    action = "Generate Identity" if result["kind"] == "identity" else "Generate Prompt"
                    result.update(status="FAILED", error=f"The image changed during analysis. Run {action} again.")
            except Exception:
                result.update(status="FAILED", error="The image was removed during analysis.")
        result.pop("checksum", None)
        return result

    def _run(self, job_id: str, asset: dict) -> None:
        try:
            with self._lock:
                kind = self._jobs[job_id]["kind"]
            if kind == "identity":
                draft = self._codex("gpt-6-luna", asset["image_path"],
                                    instructions=self.IDENTITY_INSTRUCTIONS, schema=self.IDENTITY_SCHEMA)
                identity = draft.get("identity")
                if not isinstance(identity, str) or not identity.strip():
                    raise ValueError("Luna returned an empty identity description.")
                with self._lock:
                    self._jobs[job_id].update(status="COMPLETE", draft={"identity": identity.strip()})
                return
            model = str(self.zet_app.config.ai_image_prompt_generation_model or "image-analysis:latest").strip()
            if model.startswith("codex:"):
                draft = self._codex(model.removeprefix("codex:"), asset["image_path"])
            else:
                draft = self.model_service.generate_json(
                    model, "You describe image content for image generation.",
                    self.INSTRUCTIONS, self.SCHEMA, images=[asset["image_path"]],
                )
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

    @staticmethod
    def _codex_executable() -> str:
        executable = shutil.which("codex")
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
            if installs:
                executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
        if not executable:
            raise RuntimeError("Codex CLI is unavailable for image analysis.")
        return executable

    def _codex(self, model: str, image_path: str, *, instructions: str | None = None,
               schema: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory(prefix="zet_image_prompt_") as temporary:
            root = Path(temporary)
            schema_path = root / "schema.json"
            output = root / "draft.json"
            schema_path.write_text(json.dumps(schema or self.SCHEMA), encoding="utf-8")
            command = [self._codex_executable(), "-a", "never", "-s", "read-only",
                       "-m", model, "-c", 'model_reasoning_effort="high"',
                       "-C", str(self.project_root), "exec", "--ignore-user-config",
                       "--skip-git-repo-check", "--ephemeral", "--output-schema", str(schema_path),
                       "--output-last-message", str(output), "--image", str(image_path)]
            result = self.runner(command, input=instructions or self.INSTRUCTIONS, capture_output=True,
                                 text=True, timeout=900, check=False)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or "Codex image analysis failed")[-2000:])
            value = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise RuntimeError("Codex returned an invalid image analysis draft.")
            return value
