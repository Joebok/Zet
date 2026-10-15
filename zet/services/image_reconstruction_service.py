"""Durable image-to-text-to-image work; source pixels never enter rendering."""
from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
import re
import threading
from uuid import uuid4
from PIL import Image

from zet.services.atomic_file_service import write_json_atomic
from zet.services.image_prompt_generation_service import ImagePromptGenerationService
from zet.services.narrative_codex_service import CODEX_MODELS
from zet.services.ollama_model_service import OllamaModelService
from zet.services.render_slot_service import render_count
from zet.services.universe_style_service import compose_style, universe_style
from zet.services.workflow_storage import validate_image


class ImageReconstructionService:
    SCHEMA = {"type": "object", "properties": {
        "content_prompt": {"type": "string"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    }, "required": ["content_prompt", "uncertainties"], "additionalProperties": False}
    INSTRUCTIONS = (
        "Deconstruct the supplied image into a self-contained image generation description of visible content. "
        "Describe distinctive subjects, adult/child presentation where clear, species, facial and body structure, "
        "hair, garment layers and construction, objects, materials, colors, pose, composition and background. "
        "Retain defining visible facts and exclusions with enough detail to reconstruct the content. "
        "Exclude the source's art style, medium, artist names, brushwork, linework, cel shading, photographic or "
        "anime labels, generic quality slogans, texture noise and rendering conventions. Destination rendering "
        "style will be supplied separately. Material construction is content; the way strokes depict it is not. "
        "Do not infer hidden features, biography, names or extra objects. Put uncertain/occluded details in "
        "uncertainties rather than inventing them. Return only JSON with content_prompt and uncertainties."
    )

    def __init__(self, generator, analyzer=None, catalog=None):
        self.generator = generator
        self.app = generator.zet_app
        self.root = Path(self.app.config.base_library_path) / "_state" / "ImageReconstruction"
        self.analyzer = analyzer or ImagePromptGenerationService(self.app, generator.project_root)
        self.catalog = catalog or OllamaModelService(cache_path=self.app.config.state_file(
            generator.project_root, "ollama-models-cache.json"))
        self._active = set()
        self._guard = threading.RLock()

    def _path(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError("Invalid reconstruction ID.")
        return self.root / job_id / "job.json"

    def _read(self, job_id):
        try:
            return json.loads(self._path(job_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError("Reconstruction not found.") from exc

    def _save(self, job):
        write_json_atomic(self._path(job["id"]), job)

    def options(self):
        catalog = self.catalog.cached_models()
        if catalog is None:
            try:
                catalog = self.catalog.refresh_model_catalog()
            except Exception:
                catalog = {"vision_models": []}
        models = ["codex:" + value for value in CODEX_MODELS] + catalog.get("vision_models", [])
        default = self.app.config.ai_image_prompt_generation_model
        return {"models": list(dict.fromkeys(models)), "default_model": default,
                "style": universe_style(self.app.config.base_library_path)}

    def start(self, payload):
        model = str(payload.get("model") or self.app.config.ai_image_prompt_generation_model).strip()
        if model not in self.options()["models"]:
            raise ValueError("Choose an available Codex or vision-capable Ollama analysis model.")
        style = universe_style(self.app.config.base_library_path)
        if not style["text"]:
            raise ValueError("Set the destination universe's Canonical Art Style before reconstructing.")
        count = render_count(payload.get("count"), 4)
        width = self.generator._dimension(payload.get("width", 1024), "Width")
        height = self.generator._dimension(payload.get("height", 1024), "Height")
        source = {"asset_id": "", "label": str(payload.get("label") or "Uploaded source")}
        asset_id = str(payload.get("asset_id") or "").strip()
        if asset_id:
            asset = self.app.entity_library_asset(asset_id)
            if asset.get("status") == "archived":
                raise ValueError("Choose an available source image.")
            contents = Path(asset["image_path"]).read_bytes()
            if hashlib.sha256(contents).hexdigest() != asset["checksum"]:
                raise ValueError("The source changed outside the library. Refresh it before reconstructing.")
            source.update(asset_id=asset_id, label=asset.get("label", asset_id))
        else:
            encoded = str(payload.get("image") or "")
            if len(encoded) > 28 * 1024 * 1024:
                raise ValueError("Source images must be 20 MiB or smaller.")
            if encoded.startswith("data:"):
                encoded = encoded.split(",", 1)[-1]
            try:
                contents = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise ValueError("Invalid source image data.") from exc
        if not contents or len(contents) > 20 * 1024 * 1024:
            raise ValueError("Choose a nonempty source image of 20 MiB or smaller.")
        validate_image(contents)
        with Image.open(BytesIO(contents)) as image:
            extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image.format]
        source["sha256"] = hashlib.sha256(contents).hexdigest()
        job_id = uuid4().hex
        path = self._path(job_id)
        path.parent.mkdir(parents=True, exist_ok=False)
        source_file = "source." + extension
        (path.parent / source_file).write_bytes(contents)
        job = {"id": job_id, "version": 1, "status": "RUNNING", "error": "", "model": model,
               "source": source, "style": style, "instruction_version": 1,
               "source_file": source_file, "notes": str(payload.get("notes") or "").strip(), "count": count,
               "width": width, "height": height, "content_prompt": "", "uncertainties": [],
               "prompt": "", "render_request_id": job_id}
        self._save(job)
        with self._guard:
            self._active.add(job_id)
        try:
            self.generator.slot_workspace.reserve_reconstruction(job_id, count)
        except Exception as exc:
            job.update(status="FAILED", error=str(exc)); self._save(job)
            with self._guard:
                self._active.discard(job_id)
            raise
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        thread.start()
        return job

    def _run(self, job_id):
        job = self._read(job_id)
        try:
            image = str(self._path(job_id).parent / job["source_file"])
            if job["model"].startswith("codex:"):
                draft = self.analyzer._codex(job["model"][6:], image,
                                            instructions=self.INSTRUCTIONS, schema=self.SCHEMA)
            else:
                draft = self.analyzer.model_service.generate_json(job["model"],
                    "Describe visible content independently of rendering style.", self.INSTRUCTIONS,
                    self.SCHEMA, images=[image])
            content = draft.get("content_prompt")
            uncertainties = draft.get("uncertainties")
            if (not isinstance(content, str) or not content.strip() or not isinstance(uncertainties, list)
                    or any(not isinstance(item, str) for item in uncertainties)):
                raise ValueError("The analysis model returned an invalid reconstruction description.")
            job.update(content_prompt=content.strip(), uncertainties=uncertainties,
                       prompt=compose_style(content, job["style"]["text"], job["notes"]), status="DISPATCHING")
            self._save(job)
            if job["source"]["asset_id"]:
                current = self.app.entity_library_asset(job["source"]["asset_id"])
                if (current.get("status") == "archived" or current["checksum"] != job["source"]["sha256"]
                        or hashlib.sha256(Path(current["image_path"]).read_bytes()).hexdigest() != current["checksum"]):
                    raise ValueError("The library source changed during analysis. Start a new reconstruction.")
            self.generator.slot_workspace.submit_reconstruction(job_id, {
                "mode": "txt2img", "prompt": job["prompt"], "negative_prompt": "",
                "count": job["count"], "width": job["width"], "height": job["height"],
                "reconstruction": {key: job[key] for key in ("id", "model", "source", "style",
                    "instruction_version", "content_prompt", "uncertainties", "notes", "prompt")},
            })
            job["status"] = "SUBMITTED"
        except Exception as exc:
            job.update(status="FAILED", error=str(exc))
        finally:
            self._save(job)
            with self._guard:
                self._active.discard(job_id)

    def pending(self, job_id):
        try:
            job = self.status(job_id)
            return {**job, "status": "RUNNING" if job["status"] in {"RUNNING", "DISPATCHING"} else "FAILED"}
        except (KeyError, ValueError):
            return {}

    def status(self, job_id):
        with self._guard:
            job = self._read(job_id)
            active = job_id in self._active
        if not active and job["status"] in {"RUNNING", "DISPATCHING"}:
            # A persisted render job is authoritative after a crash at the handoff.
            if job_id in self.generator._jobs:
                job["status"] = "SUBMITTED"
            else:
                job.update(status="FAILED", error="Analysis was interrupted. Start a new reconstruction.")
            self._save(job)
        return job
