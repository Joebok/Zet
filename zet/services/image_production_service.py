"""Shared AI_Proxy transport for frozen image render requests."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.image_render_request import ImageRenderRequest


class ImageProductionService:
    """Queue and collect image requests while callers retain candidate state."""

    def __init__(self, app):
        self.app = app

    @staticmethod
    def _manifest(ask_path: Path) -> dict:
        try:
            value = json.loads((ask_path / "ask_manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def submit(self, request: dict, *, manifest: dict, prompt_path: Path,
               output_directory: Path, consumer: str) -> dict:
        render = ImageRenderRequest.from_dict(request)
        owner = manifest.get("image_production")
        if not isinstance(owner, dict):
            raise ValueError("Image render ownership is required.")
        if (owner.get("universe_id") != render.universe_id
                or owner.get("target_id") != render.target_id
                or owner.get("candidate_id") != render.candidate_id
                or render.universe_id != self.app.universe_id):
            raise ValueError("Frozen image request does not match its render owner.")
        settings = render.settings
        sizing = {key: settings[key] for key in
                  ("render_mode", "aspect_ratio", "target_pixels", "width", "height") if key in settings}
        ask = self.app.ai_proxy_service.render_task_local_render_api_params(
            manifest, prompt_path, output_directory, seed=render.seed, checkpoint=settings.get("checkpoint", ""),
            render_overrides={key: value for key, value in settings.items()
                if key not in {"profile", "checkpoint", "render_mode", "aspect_ratio", "target_pixels", "width", "height",
                               "profile_snapshot"}},
            render_preset=settings["profile"], image_generation="comfyui",
            reference_files=list(render.inputs), consumer=consumer, profile_snapshot=settings.get("profile_snapshot"))
        ask_id = manifest["transport_job_id"]
        ask.update(ask_id=ask_id, universe_id=render.universe_id, ollama_attempt_id=ask_id,
                   image_production=owner, workflow=manifest["pipeline"])
        if settings.get("profile_snapshot"):
            ask["profile_snapshot"] = settings["profile_snapshot"]
        self.publish_bundle(ask_id, ask, "local_image_render", {prompt_path.name: render.prompt.encode("utf-8")})
        return {"ask_id": ask_id, "expected_output": ask["expected_output"],
                "output_path": str(output_directory / "Local_Test_Renders" / ask["expected_output"]),
                "render_sizing": sizing}

    @staticmethod
    def place(output: Path, contents: bytes, finish=None) -> None:
        from zet.services.workflow_storage import validate_image
        validate_image(contents)
        write_bytes_atomic(output, finish(contents) if finish else contents)

    def publish_bundle(self, ask_id: str, manifest: dict, worker_type: str,
                       files: dict[str, bytes]) -> None:
        if worker_type == "local_image_render" and "image_production" not in manifest:
            prompt_file = str(manifest.get("prompt_file") or "prompt.md")
            frozen = manifest.get("render_request")
            if frozen:
                request = ImageRenderRequest.from_dict(frozen)
                if (request.universe_id != self.app.config.universe_id
                        or request.candidate_id != manifest.get("narrative_candidate_id")
                        or files.get(prompt_file) != request.prompt.encode("utf-8")):
                    raise ValueError("Narrative image bundle does not match its frozen render request.")
                universe_id, target_id, candidate_id = request.universe_id, request.target_id, request.candidate_id
            else:
                # Older persisted Narrative jobs may be recovered from a parent
                # request before they have a frozen candidate-level request.
                universe_id = self.app.config.universe_id
                target_id = str(manifest.get("narrative_target_id") or "")
                candidate_id = str(manifest.get("narrative_candidate_id") or "")
            if not target_id or not candidate_id:
                raise ValueError("Narrative image target and candidate identities are required.")
            owner = {"consumer": manifest.get("consumer"), "universe_id": universe_id,
                     "target_id": target_id, "candidate_id": candidate_id, "attempt_id": ask_id}
            if "candidate_slot" in manifest:
                owner["slot"] = manifest["candidate_slot"]
            manifest["image_production"] = owner
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        if paths.jobs.repository.get(ask_id) or paths.lifecycle.read_receipt(ask_id):
            return
        client = paths.file_proxy_client
        staging = client.staging_path(ask_id)
        client.ensure_layout()
        staging.mkdir(exist_ok=True)
        try:
            for name, contents in files.items():
                if Path(name).name != name or not isinstance(contents, bytes):
                    raise ValueError("Image production bundle members must be named byte files.")
                write_bytes_atomic(staging / name, contents)
            write_json_atomic(staging / "ask_manifest.json", manifest)
            client.publish(staging, ask_id, worker_type)
        except Exception:
            if staging.is_dir():
                shutil.rmtree(staging)
            raise

    def collect_bytes(self, ask_id: str, expected: dict[str, Any], *, allow_legacy_owner: bool = True) -> tuple[str, bytes | str | None]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        answer = paths.answer_path(ask_id)
        if answer.is_dir():
            blocked = paths.file_proxy_client.answer_blocked_reason(answer)
            if blocked:
                return "RUNNING", None
            ask = self._manifest(answer)
            if not ask:
                return "RUNNING", None
            expected_owner = expected.get("image_production")
            fields = {key: value for key, value in expected.items() if key != "image_production"}
            if (any(ask.get(key) != value for key, value in {"ask_id": ask_id, **fields}.items())
                    or (expected_owner and ask.get("image_production") != expected_owner
                        and not (allow_legacy_owner and ask.get("image_production") is None))):
                return "FAILED", "Answer ownership did not match this image production target."
            try:
                result = json.loads((answer / "answer_manifest.json").read_text(encoding="utf-8"))
                if result.get("ask_id") != ask_id or result.get("expected_output") != ask.get("expected_output"):
                    return "FAILED", "AI_Proxy answer did not match the requested image output."
                if result.get("status") != "SUCCESS":
                    return "FAILED", str(result.get("error_message") or "AI_Proxy image render failed.")
                filename = str(result.get("expected_output") or "")
                if not filename or Path(filename).name != filename:
                    return "FAILED", "AI_Proxy returned an invalid output filename."
                verified = paths.jobs.result(ask_id)
                return ("COMPLETE", verified[0]) if verified is not None else ("RUNNING", None)
            except Exception as exc:
                from zet.services.ai_job_service import AIExecutionError
                if isinstance(exc, AIExecutionError):
                    return "FAILED", f"Unable to collect AI_Proxy image result: {exc}"
                if isinstance(exc, (OSError, ValueError, KeyError)):
                    paths.jobs.repository.collection_failed(
                        ask_id, exc, stage="image_production_collection", path=answer)
                    return "RUNNING", None
                raise
        if (paths.file_proxy_client.running_root / ask_id).is_dir():
            return "RUNNING", None
        return "QUEUED", None

    def find_attempt(self, source_ask_id: str, owner: dict[str, Any], reserved_id: str = "") -> dict | None:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        if reserved_id:
            record = paths.jobs.repository.get(reserved_id)
            ask = (record or {}).get("manifest", {})
            if ask.get("source_ask_id") == source_ask_id and ask.get("image_production") == owner:
                return ask
            return None
        for ask_path in paths.task_paths("ask", "running", "answer"):
            ask = self._manifest(ask_path)
            if (ask.get("source_ask_id") == source_ask_id
                    and ask.get("consumer") == owner.get("consumer")
                    and ask.get("image_production") == owner):
                return ask
        return None

    def reconcile(self, candidate, owner, root: Path, source_id: str) -> dict:
        ask_id = candidate.get("ask_id")
        output = candidate.get("output_path")
        if not ask_id:
            ask = self.find_attempt(source_id, owner, candidate.get("reserved_ask_id", ""))
            if not ask:
                return {"status": "FAILED", "error": "Submission was interrupted. Retry this render."}
            ask_id = ask["ask_id"]
            paths = self.app.ai_proxy_service.ai_proxy_path_service
            if (candidate.get("reserved_ask_id") and paths.file_proxy_client.staging_path(ask_id).is_dir()
                    and not paths.jobs.inspect(ask_id).get("location")):
                return {"status": "FAILED", "error": "Submission stopped before publication. Retry this render."}
            filename = ask.get("target_output_file") or ask.get("expected_output")
            if not filename or Path(filename).name != filename:
                return {"status": "FAILED", "error": "The recovered render has an invalid output file."}
            output = str(root / "Local_Test_Renders" / filename)
        state, error = self.collect(ask_id, owner, Path(output))
        updates = {"ask_id": ask_id, "output_path": output, "status": state, "error": error}
        if state == "COMPLETE":
            updates["image_path"] = output
        return updates

    def collect(self, ask_id: str, owner: dict[str, Any], output: Path) -> tuple[str, str]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        state, evidence = paths.jobs.execution_status(ask_id)
        if state == "HARVESTED":
            import hashlib
            record = paths.jobs.repository.get(ask_id) or {}
            artifact = evidence.get("applied_artifact") or {}
            if (record.get("manifest", {}).get("image_production") == owner
                    and artifact.get("path") == str(output.resolve()) and output.is_file()
                    and hashlib.sha256(output.read_bytes()).hexdigest() == artifact.get("sha256")):
                return "COMPLETE", ""
            return "FAILED", "The harvested image could not be recovered. Retry this render."
        if state in {"FAILED", "INVALID", "CANCELLED", "DELETED", "HARVEST_FAILED", "SUPERSEDED", "RECOVERY_REQUIRED"}:
            return "FAILED", f"AI_Proxy render ended with {state}."
        state, result = self.collect_bytes(ask_id, {"consumer": owner["consumer"], "image_production": owner},
                                          allow_legacy_owner=False)
        if state == "COMPLETE":
            import hashlib
            try:
                self.place(output, result)
                paths.jobs.finish(ask_id, applied_artifact={"path": str(output.resolve()),
                    "sha256": hashlib.sha256(result).hexdigest(), "image": True})
            except (OSError, ValueError) as exc:
                return "FAILED", str(exc)
        elif state == "FAILED":
            return state, str(result)
        return state, ""
