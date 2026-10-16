"""Common producer-side submission, verified collection and durable AI results."""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
import socket
import time
from uuid import uuid4
from contextlib import nullcontext

from zet.repositories.ai_job_repository import AIJobRepository, timestamp
from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class AIExecutionError(RuntimeError):
    """A terminal provider/transport failure, distinct from collection failure."""


class AIJobService:
    @staticmethod
    def validate_id(job_id):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,239}", str(job_id)):
            raise ValueError("Invalid AI job identifier")
    def __init__(self, paths):
        self.paths = paths
        self.client = paths.file_proxy_client
        self.lifecycle = paths.lifecycle
        self.repository = AIJobRepository(self.lifecycle.root)

    def inspect(self, job_id):
        """Inspect durable state without collecting, registering, or modifying a job."""
        self.validate_id(job_id)
        record = self.repository.get(job_id)
        receipt = self.lifecycle.read_receipt(job_id)
        info = {"ask_id": job_id, "status": "RECONCILING", "location": "", "path": "",
                "harvest_state": record.get("harvest_state", ""), "blocking_reason": record.get("error", ""),
                **{key: record.get(key, "") for key in ("failure_stage", "exception_type", "affected_path", "failed_at")}}
        if receipt:
            return {**info, "status": str(receipt.get("status") or "APPLIED"), "location": "receipt",
                    "execution_status": receipt.get("execution_status", ""), "answer_status": receipt.get("answer_status", ""),
                    "blocking_reason": receipt.get("error_message") or receipt.get("message", "")}
        for root, location, state in ((self.lifecycle.inbox_root, "inbox", "ANSWERED"),
                                     (self.client.answer_root, "answer", "ANSWERED"),
                                     (self.client.running_root, "running", "RUNNING"),
                                     (self.client.ask_root, "ask", "QUEUED")):
            path = root / job_id
            if not path.is_dir():
                continue
            info.update(status=state, location=location, path=str(path))
            if location in {"answer", "inbox"}:
                info.update(self.client.answer_block(path))
                for name, field in (("proxy_result.json", "execution_status"), ("answer_manifest.json", "answer_status")):
                    try:
                        info[field] = json.loads((path / name).read_text(encoding="utf-8")).get("status", "")
                    except (OSError, ValueError):
                        pass
            break
        if record.get("harvest_state") == "HARVEST_FAILED":
            info.update(status="HARVEST_FAILED", blocking_reason=record.get("error", ""))
        return info

    def is_pending(self, job_id):
        """Known unfinished requests do not expire while queued or being collected."""
        return self.inspect(job_id)["status"] in {
            "QUEUED", "RUNNING", "ANSWERED", "HARVESTING", "HARVEST_FAILED", "TRANSFERRING", "RECOVERY_REQUIRED"}

    def assert_image_harvest(self, job_id, image_path, expected_hash=""):
        """The durable receipt and exact image, never file existence alone, admit analysis."""
        from zet.services.workflow_storage import validate_image
        self.validate_id(job_id)
        receipt = self.lifecycle.read_receipt(job_id)
        status = str(receipt.get("status", ""))
        if (not receipt or receipt.get("answer_status") != "SUCCESS"
                or receipt.get("execution_status") not in {None, "", "SUCCEEDED"}
                or not (status == "APPLIED" or status.endswith("_APPLIED"))):
            raise ValueError("A successful image harvest receipt is required before analysis")
        if receipt.get("universe_id") != self.paths.config.universe_id:
            raise ValueError("Image harvest belongs to another universe")
        contents = Path(image_path).read_bytes()
        validate_image(contents)
        digest = hashlib.sha256(contents).hexdigest()
        evidence = receipt.get("applied_artifact") or {}
        required = evidence.get("sha256") or expected_hash
        if not required or digest != required or (expected_hash and digest != expected_hash):
            raise ValueError("Harvested image does not match the current render attempt")
        return {"ask_id": job_id, "sha256": digest, "path": str(image_path)}

    def followup_stamp(self, parent_id, kind, inputs):
        """Reserve one publication identity before creating an analysis envelope."""
        from datetime import datetime, timezone
        key = hashlib.sha256(json.dumps([parent_id, kind, inputs], sort_keys=True).encode()).hexdigest()
        path = self.lifecycle.root / "Followups" / (key + ".json")
        with file_lock(self.lifecycle.lock_path(key)):
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))["stamp"]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            write_json_atomic(path, {"parent_id": parent_id, "kind": kind, "stamp": stamp})
            return stamp

    def image_harvest_ready(self, job_id, image_path):
        try:
            digest = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
            self.assert_image_harvest(job_id, image_path, digest)
            return True
        except (OSError, ValueError):
            return False

    def reuse_followup(self, job_id, output, hashes, prompt_hash):
        if self.inspect(job_id)["location"]:
            return {"status": "QUEUED", "ask_id": job_id, "output_path": str(output),
                    "input_hashes": hashes, "prompt_sha256": prompt_hash}
        return None

    def submit_text(self, model, system, prompt, schema=None, images=None, *, job_id=None,
                    consumer="zet-structured", owner=None, task_type="structured_inference", options=None, workflow=None, admission=None):
        model = str(model).strip()
        provider = "codex" if model.startswith("codex:") else "ollama"
        job_id = job_id or "AI_" + uuid4().hex
        self.validate_id(job_id)
        with (admission() if admission else nullcontext()), file_lock(self.lifecycle.lock_path(job_id)):
            if self.repository.get(job_id) or (self.client.ask_root / job_id).exists() or (self.client.running_root / job_id).exists():
                return job_id
            from zet.services.ai_model_catalog_service import AIModelCatalogService
            AIModelCatalogService(self.paths.config.base_ai_queue_path).validate(model, required=["vision"] if images else ["text"])
            staging = self.client.create_staging(job_id)
            files = []
            for index, image in enumerate(images or []):
                source = Path(image)
                name = f"image-{index:03d}{source.suffix or '.png'}"
                (staging / name).write_bytes(source.read_bytes())
                files.append(name)
            worker = "codex_generate" if provider == "codex" else "ollama_generate"
            ask = {"version": 1, "ask_id": job_id, "consumer": consumer, "worker_type": worker,
                   "universe_id": self.paths.config.universe_id, "model": model, "provider": provider,
                   "ollama_model": model, "ollama_attempt_id": job_id, "prompt_file": "prompt.md",
                   "image_files": files, "response_schema": schema, "expected_output": "answer.json",
                   "task_type": task_type, **(owner or {})}
            ask["workflow"] = workflow or (owner or {}).get("pipeline") or task_type
            request = {"version": 1, "provider": provider, "model": model, "system": system,
                       "prompt": prompt, "images": files, "schema": schema, "output": "answer.json",
                       "options": options or {}, "owner": {"universe_id": self.paths.config.universe_id, **(owner or {})}}
            (staging / "prompt.md").write_text(prompt, encoding="utf-8")
            write_json_atomic(staging / "ai_request.json", request)
            write_json_atomic(staging / "ask_manifest.json", ask)
            self.client.publish(staging, job_id, worker)
        return job_id

    def ready_answer(self, job_id):
        """Only verified, matching, durably copied answers reach a workflow handler."""
        self.validate_id(job_id)
        with file_lock(self.lifecycle.lock_path(job_id)):
            inbox = self.lifecycle.inbox_root / job_id
            source = self.client.answer_root / job_id
            if self.lifecycle.read_receipt(job_id):
                return None
            candidate = inbox if inbox.is_dir() else source
            if not candidate.is_dir() or self.client.answer_blocked_reason(candidate):
                return None
            ask = json.loads((candidate / "ask_manifest.json").read_text(encoding="utf-8"))
            envelope = json.loads((candidate / "job.json").read_text(encoding="utf-8"))
            if (ask.get("ask_id") != job_id or envelope.get("job_id") != job_id
                    or str(envelope.get("producer_id", "")).casefold() != socket.gethostname().casefold()
                    or ask.get("universe_id") != self.paths.config.universe_id):
                return None
            record = self.repository.get(job_id)
            if record.get("harvest_state") == "HARVEST_FAILED":
                return None
            if not record:
                self.repository.register(job_id, ask, envelope)
                record = self.repository.get(job_id)
            expected = record.get("manifest", {})
            if any(ask.get(key) != value for key, value in expected.items()):
                self.repository.collection_failed(job_id, ValueError("Answer request identity changed"),
                                                  stage="identity", path=candidate)
                return None
            if candidate == source:
                try:
                    candidate = self.lifecycle.drain_answer(source, self.client)
                except Exception as exc:
                    self.repository.collection_failed(job_id, exc, stage="answer_transfer", path=source)
                    raise
            if not (candidate / "answer_manifest.json").is_file():
                outcome = json.loads((candidate / "proxy_result.json").read_text(encoding="utf-8"))
                if outcome.get("status") in {"FAILED", "INVALID"}:
                    write_json_atomic(candidate / "answer_manifest.json", {"version": 1, "ask_id": job_id,
                        "asset_id": ask.get("asset_id"), "status": "FAILED", "expected_output": ask.get("expected_output"),
                        "error_type": outcome.get("error_type", "PROXY_EXECUTION_FAILED"),
                        "error_message": outcome.get("error_message") or "AI_Proxy execution failed before producing an answer",
                        "worker_id": outcome.get("worker", ""), "completed_at": outcome.get("completed_at", "")})
            if record.get("harvest_state") not in {"HARVESTING", "HARVEST_FAILED"}:
                self.repository.update(job_id, harvest_state="AWAITING_HARVEST")
            return candidate

    def state(self, job_id):
        return self.inspect(job_id)["status"]

    def execution_status(self, job_id):
        receipt = self.lifecycle.read_receipt(job_id)
        if receipt:
            return "HARVESTED", {**receipt, "ask_id": job_id, "status": receipt.get("answer_status", "SUCCESS")}
        path = self.ready_answer(job_id)
        if path:
            answer = json.loads((path / "answer_manifest.json").read_text(encoding="utf-8"))
            outcome = json.loads((path / "proxy_result.json").read_text(encoding="utf-8"))
            if outcome.get("status") != "SUCCEEDED":
                answer = {**answer, "status": "FAILED", "error_message": outcome.get("error_message") or "AI_Proxy execution failed"}
            return "ANSWERED", answer
        return self.state(job_id), {}

    def copy_result(self, job_id, target, *, image=False):
        from zet.services.atomic_file_service import write_bytes_atomic
        from zet.services.workflow_storage import validate_image
        with file_lock(self.lifecycle.lock_path(job_id)):
            result = self.result(job_id)
            if result is None:
                return False
            contents, _ = result
            if image:
                validate_image(contents)
            write_bytes_atomic(Path(target), contents)
            self.finish(job_id, applied_artifact={"path": str(Path(target).resolve()),
                        "sha256": hashlib.sha256(contents).hexdigest(), "image": image})
            return True

    def adopt_legacy_text(self, job_id, ask, result=None, error="", created_at=""):
        """Import a fenced old Codex outcome locally, without dispatching it again."""
        envelope = {"protocol_version": 1, "job_id": job_id, "subscriber_id": "zet", "worker": "legacy-codex",
                    "producer_id": socket.gethostname(), "created_at": created_at, "files": [], "route_required": False}
        with file_lock(self.lifecycle.lock_path(job_id)):
            self.repository.register(job_id, ask, envelope)
            if result is None and not error:
                return
            folder = self.lifecycle.inbox_root / job_id
            if folder.exists() or self.lifecycle.read_receipt(job_id):
                return
            temporary = self.lifecycle.inbox_root / ("." + job_id + ".legacy")
            temporary.mkdir(parents=True, exist_ok=True)
            write_json_atomic(temporary / "ask_manifest.json", ask)
            write_json_atomic(temporary / "job.json", envelope)
            write_json_atomic(temporary / "answer.json", result or {})
            write_json_atomic(temporary / "answer_manifest.json", {"version": 1, "ask_id": job_id,
                "status": "FAILED" if error else "SUCCESS", "expected_output": "answer.json",
                "error_message": error, "imported_at": timestamp(), "worker_id": "legacy-codex"})
            inventory = self.client._file_inventory(temporary)
            write_json_atomic(temporary / "proxy_result.json", {"status": "SUCCEEDED", "output_files": inventory})
            self.client._replace_with_retry(temporary, folder)

    def finish(self, job_id, *, status="APPLIED", message="", **evidence):
        with file_lock(self.lifecycle.lock_path(job_id)):
            path = self.lifecycle.inbox_root / job_id
            if not path.is_dir():
                path = self.client.answer_root / job_id
            if path.is_dir():
                self.lifecycle.finish_answer(path, {"status": status, "message": message, **evidence})

    def result(self, job_id):
        with file_lock(self.lifecycle.lock_path(job_id)):
            return self._result(job_id)

    def _result(self, job_id):
        path = self.ready_answer(job_id)
        if path is None:
            return None
        answer = json.loads((path / "answer_manifest.json").read_text(encoding="utf-8"))
        ask = json.loads((path / "ask_manifest.json").read_text(encoding="utf-8"))
        outcome = json.loads((path / "proxy_result.json").read_text(encoding="utf-8"))
        if answer.get("ask_id") != job_id or answer.get("expected_output") != ask.get("expected_output"):
            raise ValueError("AI answer does not match the requested output")
        if outcome.get("status") != "SUCCEEDED" or answer.get("status") != "SUCCESS":
            raise AIExecutionError(str(answer.get("error_message") or outcome.get("error_message") or "AI execution failed"))
        filename = str(answer["expected_output"])
        if Path(filename).name != filename:
            raise ValueError("AI output filename must be a direct child")
        return (path / filename).read_bytes(), answer

    def generate_json(self, model, system, prompt, schema, images=None, *, timeout=1800, **metadata):
        """Compatibility callers share transport/collection; durable continuations use submit_text/result."""
        from zet.services.ai_workflow_service import current_workflow, work_id, AIPending
        context = current_workflow.get()
        if context is not None:
            signature = json.dumps([system, prompt, schema,
                                   [hashlib.sha256(Path(image).read_bytes()).hexdigest() for image in images or []]], sort_keys=True)
            metadata.setdefault("job_id", "AI_" + hashlib.sha256((context["id"] + signature).encode()).hexdigest()[:32])
            metadata.setdefault("owner", context["owner"])
            metadata.setdefault("workflow", context["service"])
            metadata.setdefault("admission", context.get("admission"))
        elif (metadata.get("owner") or {}).get("evaluation_id"):
            signature = json.dumps([metadata["owner"], system, prompt, schema,
                [hashlib.sha256(Path(image).read_bytes()).hexdigest() for image in images or []]], sort_keys=True)
            metadata.setdefault("job_id", "AI_" + hashlib.sha256((self.paths.config.universe_id + signature).encode()).hexdigest()[:32])
        job_id = self.submit_text(model, system, prompt, schema, images, **metadata)
        cache = self.lifecycle.root / "StructuredResults" / f"{job_id}.json"
        if cache.is_file():
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("error"):
                raise RuntimeError(saved["error"])
            return saved["result"], saved.get("runtime", {})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline or self.is_pending(job_id):
            if cache.is_file():
                saved = json.loads(cache.read_text(encoding="utf-8"))
                if saved.get("error"):
                    raise RuntimeError(saved["error"])
                return saved["result"], saved.get("runtime", {})
            try:
                result = self.result(job_id)
            except AIExecutionError as exc:
                self.finish(job_id, status="FAILED", message=str(exc))
                raise
            except Exception as exc:
                self.repository.collection_failed(job_id, exc, stage="structured_result")
                if context is not None:
                    raise AIPending()
                raise
            if result is not None:
                contents, answer = result
                value = json.loads(contents)
                if not isinstance(value, dict):
                    raise ValueError("Structured AI output must be an object")
                # Keep a compact durable response for resumable domain continuation.
                write_json_atomic(self.lifecycle.root / "StructuredResults" / f"{job_id}.json", {"result": value, "runtime": answer.get("runtime", answer.get("ollama_runtime", {}))})
                self.finish(job_id)
                return value, answer.get("runtime", answer.get("ollama_runtime", {}))
            if context is not None:
                raise AIPending()
            time.sleep(0.2)
        self.repository.update(job_id, error="Caller stopped waiting; background collection remains active")
        raise TimeoutError(f"AI job {job_id} is still pending")
