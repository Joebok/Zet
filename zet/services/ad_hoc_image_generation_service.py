from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random
import shutil
import tempfile
import threading
import time
from typing import Any
from uuid import uuid4

from PIL import Image

from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.local_render_policy import require_qwen_profile
from zet.services.workflow_storage import validate_image


IMAGE_GENERATION_CONSUMER = "zet-image-generation"
IMAGE_GENERATION_DEFAULT_COUNT = 4
IMAGE_GENERATION_MAX_COUNT = 16
IMAGE_GENERATION_MAX_REFERENCE_BYTES = 20 * 1024 * 1024
IMAGE_GENERATION_MAX_REFERENCES = 10
IMAGE_GENERATION_DEFAULT_WIDTH = 1024
IMAGE_GENERATION_DEFAULT_HEIGHT = 1024
IMAGE_GENERATION_MIN_DIMENSION = 256
IMAGE_GENERATION_MAX_DIMENSION = 4096


class AdHocImageGenerationError(ValueError):
    pass


class AdHocImageGenerationService:
    """Stage ComfyUI candidates through AI_Proxy without harvesting library work."""

    def __init__(self, zet_app, project_root: str | Path):
        self.zet_app = zet_app
        self.project_root = Path(project_root)
        self.presets_path = self.project_root / "Config" / "Local_Render_Presets.json"
        self.proxy_paths = zet_app.ai_proxy_service.ai_proxy_path_service
        self.proxy_client = self.proxy_paths.file_proxy_client
        self.workspace_root = Path(tempfile.gettempdir()) / "zet-ad-hoc-image-generation"
        self.results_root = Path(zet_app.config.base_library_path) / "_state" / "ImageGeneration"
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self.results_root.mkdir(parents=True, exist_ok=True)
        self._load_jobs()
        self.cleanup_abandoned()

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def options(self) -> dict[str, Any]:
        presets = json.loads(self.presets_path.read_text(encoding="utf-8"))
        configured = str(self.zet_app.config.comfyui_checkpoint or "").strip()
        return {
            "model": "Qwen Image 2.1",
            "checkpoint": configured or presets["comfyui-qwen-head-image-text"]["diffusion_model"],
            "default_count": IMAGE_GENERATION_DEFAULT_COUNT,
            "max_count": IMAGE_GENERATION_MAX_COUNT,
            "default_width": IMAGE_GENERATION_DEFAULT_WIDTH,
            "default_height": IMAGE_GENERATION_DEFAULT_HEIGHT,
            "max_references": IMAGE_GENERATION_MAX_REFERENCES,
        }

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "txt2img").strip().lower()
        if mode not in {"txt2img", "img2img"}:
            raise AdHocImageGenerationError("Choose txt2img or img2img.")
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise AdHocImageGenerationError("Enter a prompt before generating.")
        source_asset_id = str(payload.get("source_asset_id") or "").strip()
        source_checksum = str(payload.get("source_checksum") or "").strip()
        if source_asset_id:
            try:
                source = self.zet_app.entity_library_asset(source_asset_id)
            except Exception as exc:
                raise AdHocImageGenerationError(f"Source image is unavailable: {exc}") from exc
            if source.get("origin") == "pipeline" or source.get("status") == "archived":
                raise AdHocImageGenerationError("Only available, non-pipeline images can be modified.")
            if not source_checksum or source.get("checksum") != source_checksum:
                raise AdHocImageGenerationError("The source image changed. Reopen Image Generation from the current image.")
        elif source_checksum:
            raise AdHocImageGenerationError("A source checksum requires a source image.")
        count_value = payload.get("count", IMAGE_GENERATION_DEFAULT_COUNT)
        if isinstance(count_value, bool):
            raise AdHocImageGenerationError("Image count must be between 1 and 16.")
        if isinstance(count_value, float) and not count_value.is_integer():
            raise AdHocImageGenerationError("Image count must be between 1 and 16.")
        try:
            count = int(count_value)
        except (TypeError, ValueError) as exc:
            raise AdHocImageGenerationError("Image count must be between 1 and 16.") from exc
        if not 1 <= count <= IMAGE_GENERATION_MAX_COUNT:
            raise AdHocImageGenerationError("Image count must be between 1 and 16.")
        width = self._dimension(payload.get("width", IMAGE_GENERATION_DEFAULT_WIDTH), "Width")
        height = self._dimension(payload.get("height", IMAGE_GENERATION_DEFAULT_HEIGHT), "Height")

        reference_images: list[dict[str, Any]] = []
        if mode == "img2img":
            supplied_references = payload.get("reference_images")
            if supplied_references is None and payload.get("reference_image"):
                supplied_references = [{"label": "source image", "image": payload["reference_image"]}]
            if not isinstance(supplied_references, list) or not supplied_references:
                raise AdHocImageGenerationError("Choose at least one reference image for img2img.")
            if len(supplied_references) > IMAGE_GENERATION_MAX_REFERENCES:
                raise AdHocImageGenerationError("Choose no more than 10 reference images for img2img.")
            for index, item in enumerate(supplied_references, start=1):
                if not isinstance(item, dict):
                    raise AdHocImageGenerationError(f"Reference image {index} is invalid.")
                label = str(item.get("label") or "").strip()
                if not label:
                    raise AdHocImageGenerationError(f"Enter a prompt label for reference image {index}.")
                encoded = str(item.get("image") or "")
                if not encoded:
                    raise AdHocImageGenerationError(f"Reference image {index} has no image data.")
                if "," in encoded and encoded.lstrip().startswith("data:"):
                    encoded = encoded.split(",", 1)[1]
                if len(encoded) > (IMAGE_GENERATION_MAX_REFERENCE_BYTES * 4 // 3 + 8):
                    raise AdHocImageGenerationError("Reference images must be 20 MiB or smaller.")
                try:
                    reference_bytes = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise AdHocImageGenerationError(f"Reference image {index} data is invalid.") from exc
                if len(reference_bytes) > IMAGE_GENERATION_MAX_REFERENCE_BYTES:
                    raise AdHocImageGenerationError("Reference images must be 20 MiB or smaller.")
                try:
                    validate_image(reference_bytes)
                    with Image.open(BytesIO(reference_bytes)) as image:
                        extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image.format]
                except (ValueError, KeyError) as exc:
                    raise AdHocImageGenerationError(str(exc)) from exc
                reference_images.append({"label": label, "bytes": reference_bytes, "extension": extension})
            if source_asset_id:
                source_path = Path(str(source.get("image_path") or ""))
                if (not source_path.is_file()
                        or hashlib.sha256(source_path.read_bytes()).hexdigest() != source_checksum
                        or hashlib.sha256(reference_images[0]["bytes"]).hexdigest() != source_checksum):
                    raise AdHocImageGenerationError("The reference image does not match the selected inventory image.")
        preset_name = (
            ("comfyui-qwen-local-character-edit" if payload.get("reference_images") is not None
             else "comfyui-qwen-head-image-edit")
            if mode == "img2img" else "comfyui-qwen-head-image-text"
        )
        if payload.get("model_family") and payload["model_family"] != "qwen-image-2.1":
            raise AdHocImageGenerationError("Local rendering supports only Qwen Image 2.1.")
        require_qwen_profile(self.project_root, str(payload.get("render_preset") or payload.get("profile") or preset_name),
                             str(payload.get("backend") or payload.get("image_generation") or "comfyui"),
                             str(payload.get("checkpoint") or ""))
        checkpoint = str(self.zet_app.config.comfyui_checkpoint or "").strip()
        if not checkpoint:
            checkpoint = str(self._preset(preset_name).get("diffusion_model") or "")

        request_id = uuid4().hex
        workspace = self.workspace_root / request_id
        workspace.mkdir(parents=True, exist_ok=False)
        prompt_path = workspace / "Final_Image_Prompt.md"
        try:
            prompt_path.write_text(
                f"Prompt: {prompt}\nNegative: {str(payload.get('negative_prompt') or '').strip()}\n",
                encoding="utf-8",
            )
            references = []
            if reference_images:
                label_lines = ["Reference image labels (images are supplied in this order):"]
                for index, reference in enumerate(reference_images, start=1):
                    reference_path = workspace / f"reference_{index:02d}.{reference['extension']}"
                    reference_path.write_bytes(reference["bytes"])
                    label_lines.append(f"Image {index}: {reference['label']}")
                    references.append({
                        "version": 1, "type": "reference_file", "role": reference["label"],
                        "label": reference["label"], "path": str(reference_path), "image_index": index,
                    })
                prompt = prompt + "\n\n" + "\n".join(label_lines)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise

        children = []
        seeds: set[int] = set()
        try:
            for index in range(count):
                seed = random.SystemRandom().randrange(0, 2**63 - 1)
                while seed in seeds:
                    seed = random.SystemRandom().randrange(0, 2**63 - 1)
                seeds.add(seed)
                staged = self.zet_app.ai_proxy_service.stage_render_task_local_render_ask(
                    {"ask_id": f"adhoc_{request_id}", "ad_hoc_request_id": request_id},
                    prompt_path,
                    workspace,
                    allow_parallel=True,
                    seed=seed,
                    checkpoint=checkpoint,
                    render_overrides={
                        "width": width,
                        "height": height,
                        "disable_prompt_globals": True,
                    },
                    render_preset=preset_name,
                    image_generation="comfyui",
                    reference_files=references,
                    consumer=IMAGE_GENERATION_CONSUMER,
                )
                children.append({"ask_id": staged.name, "index": index})
        except Exception as exc:
            with self._lock:
                job = self._new_job(
                    request_id, mode, count, workspace, children, prompt_path,
                    "QUEUED" if children else "ERROR", f"Only {len(children)} of {count} images could be queued: {exc}",
                )
                job["failures"] = count - len(children)
                job.update(self._request_details(payload, width, height, prompt))
                self._jobs[request_id] = job
                self._save_job(job)
            if not children:
                shutil.rmtree(workspace, ignore_errors=True)
            return self.status(request_id)

        with self._lock:
            self._jobs[request_id] = self._new_job(
                request_id, mode, count, workspace, children, prompt_path, "QUEUED", "",
            )
            self._jobs[request_id].update(self._request_details(payload, width, height, prompt))
            self._save_job(self._jobs[request_id])
        return self.status(request_id)

    def _new_job(self, request_id, mode, count, workspace, children, prompt_path, status, error):
        return {
            "request_id": request_id,
            "mode": mode,
            "prompt": "",
            "negative_prompt": "",
            "width": IMAGE_GENERATION_DEFAULT_WIDTH,
            "height": IMAGE_GENERATION_DEFAULT_HEIGHT,
            "count": count,
            "workspace": workspace,
            "children": children,
            "prompt_path": prompt_path,
            "status": status,
            "error": error,
            "images": [],
            "failures": 0,
            "created_at": time.time(),
            "finished_at": time.time() if status == "ERROR" else None,
        }

    @staticmethod
    def _request_details(payload, width, height, prompt):
        return {
            "prompt": prompt,
            "negative_prompt": str(payload.get("negative_prompt") or "").strip(),
            "width": width,
            "height": height,
            "source_asset_id": str(payload.get("source_asset_id") or "").strip(),
            "source_checksum": str(payload.get("source_checksum") or "").strip(),
        }

    def _preset(self, name: str) -> dict[str, Any]:
        return LocalRenderBackendService(self.presets_path).preset(name)

    @staticmethod
    def _dimension(value: Any, label: str) -> int:
        if isinstance(value, bool):
            raise AdHocImageGenerationError(f"{label} must be between 256 and 4096 and divisible by 32.")
        if isinstance(value, float) and not value.is_integer():
            raise AdHocImageGenerationError(f"{label} must be between 256 and 4096 and divisible by 32.")
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise AdHocImageGenerationError(f"{label} must be between 256 and 4096 and divisible by 32.") from exc
        if (result < IMAGE_GENERATION_MIN_DIMENSION or result > IMAGE_GENERATION_MAX_DIMENSION
                or result % 32 != 0):
            raise AdHocImageGenerationError(f"{label} must be between 256 and 4096 and divisible by 32.")
        return result

    def status(self, request_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None:
                raise KeyError("Image generation request not found.")
            self._refresh(job)
            self._save_job(job)
            return {
                "request_id": request_id,
                "mode": job["mode"],
                "status": job["status"],
                "requested": job["count"],
                "completed": sum(image is not None for image in job["images"]),
                "failed": job["failures"],
                "error": job["error"],
                "prompt": job.get("prompt", ""),
                "negative_prompt": job.get("negative_prompt", ""),
                "source_asset_id": job.get("source_asset_id", ""),
                "source_checksum": job.get("source_checksum", ""),
                "images": [
                    {"index": index, "url": f"/api/image-generation/jobs/{request_id}/images/{index}"}
                    for index, image in enumerate(job["images"]) if image is not None
                ],
            }

    def image(self, request_id: str, index: int) -> tuple[bytes, str]:
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None or index < 0 or index >= len(job["images"]) or job["images"][index] is None:
                raise KeyError("Image not found.")
            return job["images"][index]

    def library_result(self, request_id: str, index: int):
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None or index < 0 or index >= len(job["images"]) or job["images"][index] is None:
                raise KeyError("Generated image not found.")
            image_bytes, mime_type = job["images"][index]
            return image_bytes, mime_type, {
                "prompt": job.get("prompt", ""), "negative_prompt": job.get("negative_prompt", ""),
                "source_asset_id": job.get("source_asset_id", ""),
                "source_checksum": job.get("source_checksum", ""),
            }

    def import_into_library(self, request_id: str, index: int, data: dict[str, Any]) -> dict[str, Any]:
        label = str(data.get("label") or "").strip()
        if not label:
            raise AdHocImageGenerationError("Image name is required.")
        provenance = str(data.get("provenance") or f"Image Generation job {request_id}, result {index + 1}")
        result = self.zet_app.entity_library_import_generation_result(
            self, request_id, index, label=label, entity_id=str(data.get("entity_id") or "").strip(),
            reference_role=str(data.get("reference_role") or "primary_subject"), provenance=provenance,
        )
        return result if isinstance(result, dict) and "asset" in result else {"asset": result, "duplicate": False}

    def apply_to_source(self, request_id: str, index: int) -> dict[str, Any]:
        image_bytes, mime_type, generation = self.library_result(request_id, index)
        asset_id = str(generation.get("source_asset_id") or "")
        if not asset_id:
            raise AdHocImageGenerationError("This generation job was not opened from an inventory image.")
        try:
            return self.zet_app.entity_library_apply_generated_image(
                asset_id, generation["source_checksum"], mime_type, image_bytes,
                generation["prompt"], generation["negative_prompt"], request_id, index,
            )
        except Exception as exc:
            raise AdHocImageGenerationError(str(exc)) from exc

    def clear(self, request_id: str) -> None:
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None:
                raise KeyError("Image generation request not found or expired.")
            if job["status"] in {"QUEUED", "RUNNING"}:
                raise AdHocImageGenerationError("Wait for queued images to finish before clearing results.")
            self._release(job)
            del self._jobs[request_id]
            shutil.rmtree(self.results_root / request_id, ignore_errors=True)

    def clear_image(self, request_id: str, index: int) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(request_id)
            if job is None or index < 0 or index >= len(job["images"]) or job["images"][index] is None:
                raise KeyError("Generated image not found.")
            if job["status"] in {"QUEUED", "RUNNING"}:
                raise AdHocImageGenerationError("Wait for queued images to finish before clearing a slot.")
            job["images"][index] = None
            (self.results_root / request_id / f"image-{index}.bin").unlink(missing_ok=True)
            self._save_job(job)
            return self.status(request_id)

    def _refresh(self, job: dict[str, Any]) -> None:
        if job["status"] in {"COMPLETE", "PARTIAL", "FAILED", "ERROR"}:
            return
        running = 0
        transfer_message = ""
        for child in job["children"]:
            if child.get("done"):
                continue
            ask_id = child["ask_id"]
            answer_path = self.proxy_paths.answer_root() / ask_id
            running_path = self.proxy_paths.running_root() / ask_id
            ask_path = self.proxy_paths.ask_root() / ask_id
            if answer_path.is_dir():
                blocked = self.proxy_client.answer_blocked_reason(answer_path)
                if blocked:
                    running += 1
                    transfer_message = f"Waiting for AI_Proxy to finish transferring an image: {blocked}"
                    continue
                owned_answer = False
                try:
                    ask = self.proxy_paths.read_ask_manifest(answer_path).to_dict()
                    if (ask.get("ask_id") != ask_id
                            or ask.get("consumer") != IMAGE_GENERATION_CONSUMER
                            or ask.get("ad_hoc_request_id") != job["request_id"]):
                        raise AdHocImageGenerationError("Proxy answer ownership could not be verified.")
                    owned_answer = True
                    answer = self.proxy_paths.read_answer_manifest(answer_path).to_dict()
                    if (answer.get("ask_id") != ask_id
                            or answer.get("expected_output") != ask.get("expected_output")):
                        raise AdHocImageGenerationError("AI_Proxy returned an answer for another job.")
                    if answer.get("status") != "SUCCESS":
                        raise AdHocImageGenerationError(str(answer.get("error_message") or "AI_Proxy render failed."))
                    filename = str(answer.get("expected_output") or "")
                    if not filename or Path(filename).name != filename:
                        raise AdHocImageGenerationError("AI_Proxy returned an invalid image filename.")
                    image_path = answer_path / filename
                    image_bytes = image_path.read_bytes()
                    validate_image(image_bytes)
                    with Image.open(BytesIO(image_bytes)) as image:
                        content_type = Image.MIME.get(image.format or "", "application/octet-stream")
                    job["images"].append((image_bytes, content_type))
                except Exception as exc:
                    job["failures"] += 1
                    if not job["error"]:
                        job["error"] = str(exc)
                finally:
                    if owned_answer:
                        self.proxy_client.remove_answer(ask_id)
                        self.proxy_client.remove_route(ask_id)
                    child["done"] = True
                    self._save_job(job)
            elif running_path.is_dir():
                running += 1
            elif ask_path.is_dir():
                pass
            else:
                job["failures"] += 1
                job["error"] = job["error"] or "AI_Proxy no longer has this queued image job."
                child["done"] = True

        if running or any(not child.get("done") for child in job["children"]):
            job["status"] = "RUNNING" if running else "QUEUED"
            if transfer_message:
                job["error"] = transfer_message
            return
        completed = sum(image is not None for image in job["images"])
        if job["failures"] and completed:
            job["status"] = "PARTIAL"
        elif job["failures"]:
            job["status"] = "FAILED"
        else:
            job["status"] = "COMPLETE"
        job["finished_at"] = time.time()
        shutil.rmtree(job["workspace"], ignore_errors=True)
        self._save_job(job)

    def _release(self, job: dict[str, Any]) -> None:
        shutil.rmtree(job["workspace"], ignore_errors=True)
        job["images"].clear()

    def _save_job(self, job: dict[str, Any]) -> None:
        directory = self.results_root / job["request_id"]
        directory.mkdir(parents=True, exist_ok=True)
        image_records = []
        for index, image in enumerate(job["images"]):
            if image is None:
                image_records.append(None)
                continue
            image_bytes, content_type = image
            filename = f"image-{index}.bin"
            image_path = directory / filename
            if not image_path.exists() or image_path.stat().st_size != len(image_bytes):
                image_path.write_bytes(image_bytes)
            image_records.append({"filename": filename, "content_type": content_type})
        record = {key: job[key] for key in (
            "request_id", "mode", "prompt", "negative_prompt", "width", "height", "count",
            "children", "status", "error", "failures", "created_at", "finished_at",
        )}
        record["source_asset_id"] = job.get("source_asset_id", "")
        record["source_checksum"] = job.get("source_checksum", "")
        record.update({"workspace": str(job["workspace"]), "prompt_path": str(job["prompt_path"]),
                       "images": image_records})
        temporary = directory / "job.json.tmp"
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        temporary.replace(directory / "job.json")

    def _load_jobs(self) -> None:
        for directory in self.results_root.iterdir():
            record_path = directory / "job.json"
            if not directory.is_dir() or not record_path.is_file():
                continue
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
                images = [((directory / item["filename"]).read_bytes(), str(item["content_type"])) if item else None
                          for item in record.get("images", [])]
                job = {**record, "workspace": Path(record["workspace"]),
                       "prompt_path": Path(record["prompt_path"]), "images": images}
                self._jobs[str(job["request_id"])] = job
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue

    def cleanup_abandoned(self) -> None:
        known_children = {child["ask_id"] for job in self._jobs.values() for child in job.get("children", [])}
        for answer_path in self.proxy_paths.task_paths("answer"):
            try:
                ask = self.proxy_paths.read_ask_manifest(answer_path).to_dict()
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if ask.get("consumer") == IMAGE_GENERATION_CONSUMER and answer_path.name not in known_children:
                self.proxy_client.remove_answer(answer_path.name)
                self.proxy_client.remove_route(answer_path.name)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        for workspace in self.workspace_root.iterdir():
            try:
                stale = time.time() - workspace.stat().st_mtime >= 24 * 3600
            except OSError:
                continue
            if workspace.is_dir() and len(workspace.name) == 32 and stale:
                shutil.rmtree(workspace, ignore_errors=True)
