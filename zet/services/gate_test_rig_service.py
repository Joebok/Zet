from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from typing import Any
from uuid import uuid4

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_body_reference_service import (
    LocalBodyReferenceService,
    _parse_orientation_gate_verdict,
    _parse_passing_gate_verdict,
)
from zet.services.local_head_image_service import LocalHeadImageService


class GateTestRigError(ValueError):
    """Raised when a Gate Test Rig selection or request is invalid."""


class GateTestRigService:
    """Run isolated gate experiments against saved local pipeline images."""

    PIPELINES = {
        "body-reference": "Local Body-Reference",
        "head-image": "Local Head-Image",
    }

    PROMPT_FILE = "OLLAMA_PROMPT.md"
    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
        self.root = self.library_root / "Experiments" / "Gate-Test-Rig"
        self.config_root = self.root / "configs"
        self.test_root = self.root / "tests"

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _body(self) -> LocalBodyReferenceService:
        return LocalBodyReferenceService(self.app, self.project_root)

    def _head(self) -> LocalHeadImageService:
        return LocalHeadImageService(self.app, self.project_root)

    @classmethod
    def _pipeline(cls, pipeline: str) -> str:
        value = str(pipeline or "body-reference").strip()
        if value not in cls.PIPELINES:
            raise GateTestRigError(f"Unknown local pipeline: {value}")
        return value

    def _service(self, pipeline: str) -> Any:
        return self._head() if self._pipeline(pipeline) == "head-image" else self._body()

    def catalog(self, pipeline: str = "") -> dict[str, Any]:
        if pipeline:
            key = self._pipeline(pipeline)
            return {"runs": self._service(key).list_runs()}
        return {"pipelines": [{"key": key, "label": label} for key, label in self.PIPELINES.items()]}

    def run_summary(self, run_id: str, pipeline: str = "body-reference") -> dict[str, Any]:
        key = self._pipeline(pipeline)
        run = self._service(key).detail(run_id)
        return {"run_id": run_id, "character": run.get("character", ""),
                "phase": run.get("phase", ""), "views": run.get("views", []), "pipeline": key}

    def selection(self, run_id: str, view: str, pipeline: str = "body-reference") -> dict[str, Any]:
        key = self._pipeline(pipeline)
        service = self._service(key)
        run = service.detail(run_id)
        view = str(view or "").strip().upper()
        if view not in run.get("views", []):
            raise GateTestRigError(f"Unknown {self.PIPELINES[key]} view: {view}")
        gates = (service.review_gates(view, has_front_source=bool(run.get("front_source")))
                 if key == "head-image" else service.review_gates(view))
        candidates = []
        for item in run.get("candidates") or []:
            if item.get("view") != view:
                continue
            image_path = Path(str(item.get("image_path") or ""))
            if not image_path.is_file():
                continue
            candidates.append({"candidate_id": item["candidate_id"], "status": item.get("status", "")})
        anchor = next((item for item in run.get("candidates") or []
                       if item.get("candidate_id") == run.get("front_anchor")), None)
        anchor_path = Path(str(anchor.get("image_path") or "")) if anchor else None
        source_path = Path(str(run.get("front_source") or "")) if key == "head-image" else None
        return {
            "pipeline": key,
            "run_id": run_id,
            "character": run.get("character", ""),
            "phase": run.get("phase", ""),
            "view": view,
            "gates": [{"key": gate.key, "prompt": gate.prompt, "uses_anchor": gate.uses_anchor,
                       "crop_head": gate.crop_head} for gate in gates],
            "candidates": candidates,
            "front_anchor": run.get("front_anchor") if anchor_path and anchor_path.is_file() else None,
            "front_anchor_available": bool(anchor_path and anchor_path.is_file()),
            "front_source_available": bool(source_path and source_path.is_file()),
        }

    def configs(self) -> list[dict[str, Any]]:
        if not self.config_root.is_dir():
            return []
        values = []
        for path in sorted(self.config_root.glob("*.json")):
            value = self._read_json(path)
            if value:
                values.append(value)
        return sorted(values, key=lambda item: str(item.get("name") or "").casefold())

    def save_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise GateTestRigError("A configuration name is required.")
        config = self._validate_config(payload.get("config"))
        config_id = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-").lower()
        if not config_id:
            raise GateTestRigError("Configuration name must contain a letter or number.")
        value = {"config_id": config_id, "name": name, "config": config,
                 "updated_at": datetime.now().isoformat(timespec="seconds")}
        self.config_root.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.config_root / f"{config_id}.json", value)
        return value

    @staticmethod
    def _validate_config(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise GateTestRigError("Configuration must be an object.")
        gate = str(value.get("gate") or "").strip()
        if gate not in {"face", "proportion", "framing", "orientation", "body_identity",
                        "background", "identity", "source_identity", "gaze"}:
            raise GateTestRigError("Choose a known review gate.")
        model = str(value.get("model") or "").strip()
        if not model or model == "codex:":
            raise GateTestRigError("Choose an Ollama model or GPT-6 Luna.")
        if model.startswith("codex:") and model != "codex:gpt-6-luna":
            raise GateTestRigError("GPT-6 Luna is the only supported Codex model in the Gate Test Rig.")
        api = str(value.get("api") or "generate").lower()
        if api not in {"generate", "chat"}:
            raise GateTestRigError("API mode must be generate or chat.")
        think = value.get("think", "high" if model == "codex:gpt-6-luna" else False)
        if model == "codex:gpt-6-luna":
            if not isinstance(think, str) or think not in {"none", "low", "medium", "high", "xhigh", "max"}:
                raise GateTestRigError("GPT-6 Luna reasoning must be none, low, medium, high, xhigh, or max.")
        elif think is not None and not isinstance(think, bool):
            raise GateTestRigError("Ollama thinking must be true, false, or use the model default.")
        try:
            temperature = float(value.get("temperature", 0.1))
        except (TypeError, ValueError) as exc:
            raise GateTestRigError("Temperature must be a number from 0 to 2.") from exc
        if isinstance(value.get("temperature"), bool) or not 0 <= temperature <= 2:
            raise GateTestRigError("Temperature must be a number from 0 to 2.")
        keep_alive = value.get("keep_alive", "5m")
        if isinstance(keep_alive, bool) or not isinstance(keep_alive, (str, int)):
            raise GateTestRigError("Keep-alive must be a string duration or integer.")
        options = value.get("options", {})
        request_options = value.get("request_options", {})
        if not isinstance(options, dict) or not isinstance(request_options, dict):
            raise GateTestRigError("Advanced Ollama options must be JSON objects.")
        reserved_fields = {"model", "prompt", "images", "messages", "stream", "think", "keep_alive", "options"}
        if reserved_fields.intersection(request_options):
            raise GateTestRigError("Request fields cannot override model, prompt, images, thinking, streaming, or options.")
        if "system" in request_options and not isinstance(request_options["system"], str):
            raise GateTestRigError("The optional system field must be text.")
        try:
            json.dumps(options)
            json.dumps(request_options)
        except (TypeError, ValueError) as exc:
            raise GateTestRigError("Advanced options must contain JSON-compatible values.") from exc
        return {
            "gate": gate,
            "prompt": str(value.get("prompt") or ""),
            "api": api,
            "model": model,
            "think": think,
            "temperature": temperature,
            "keep_alive": keep_alive,
            "options": options,
            "request_options": request_options,
        }

    def _codex_executable(self) -> str:
        executable = shutil.which("codex")
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
            if installs:
                executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
        if not executable:
            raise GateTestRigError("Codex CLI is unavailable for GPT-6 Luna.")
        return executable

    def _run_codex_attempt(self, *, config: dict[str, Any], prompt: str,
                           images: list[tuple[str, Path]], output: Path) -> None:
        model = config["model"].removeprefix("codex:")
        command = [self._codex_executable(), "-a", "never", "-s", "read-only", "-m", model,
                   "-c", f'model_reasoning_effort="{config["think"]}"', "-C", str(self.project_root), "exec",
                   "--ignore-user-config", "--skip-git-repo-check", "--ephemeral",
                   "--output-last-message", str(output)]
        for _, image in images:
            command.extend(["--image", str(image)])
        completed = subprocess.run(
            command, input=prompt, capture_output=True, text=True, timeout=1800, check=False,
            env=LocalBodyReferenceService._luna_environment(),
        )
        if completed.returncode != 0:
            raise GateTestRigError((completed.stderr or completed.stdout or "GPT-6 Luna request failed")[-2000:])

    def _run_codex_attempt_background(self, *, config: dict[str, Any], prompt: str,
                                      images: list[tuple[str, Path]], output: Path,
                                      error_path: Path) -> None:
        try:
            self._run_codex_attempt(config=config, prompt=prompt, images=images, output=output)
        except Exception as exc:
            write_json_atomic(error_path, {"error": str(exc)})

    def start_test(self, payload: dict[str, Any]) -> dict[str, Any]:
        pipeline = self._pipeline(str(payload.get("pipeline") or "body-reference"))
        run_id = str(payload.get("run_id") or "").strip()
        view = str(payload.get("view") or "").strip().upper()
        config = self._validate_config(payload.get("config"))
        selected = self.selection(run_id, view, pipeline)
        gate = next((item for item in selected["gates"] if item["key"] == config["gate"]), None)
        if gate is None:
            raise GateTestRigError(f"Gate {config['gate']} does not apply to {view}.")
        prompt = config["prompt"] or gate["prompt"]
        if not prompt.strip():
            raise GateTestRigError("The gate prompt cannot be blank.")
        if gate["uses_anchor"] and not selected["front_anchor_available"]:
            raise GateTestRigError("This gate requires an available FRONT anchor image.")
        if config["gate"] == "source_identity" and not selected["front_source_available"]:
            raise GateTestRigError("This gate requires an available front source image.")
        if not selected["candidates"]:
            raise GateTestRigError(f"No completed candidate images are available for {view}.")

        service = self._service(pipeline)
        run = service.detail(run_id)
        by_id = {item["candidate_id"]: item for item in run.get("candidates") or []}
        anchor = next((item for item in run.get("candidates") or []
                       if item.get("candidate_id") == selected["front_anchor"]), None)
        test_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid4().hex[:8]
        root = self.test_root / test_id
        root.mkdir(parents=True, exist_ok=False)
        result_dir = root / "results"
        result_dir.mkdir()
        record = {
            "test_id": test_id,
            "pipeline": pipeline,
            "run_id": run_id,
            "view": view,
            "gate": config["gate"],
            "prompt": prompt,
            "config": config,
            "status": "RUNNING",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "attempts": [],
        }
        record_path = root / "test.json"
        write_json_atomic(record_path, record)
        for candidate in selected["candidates"]:
            candidate_id = candidate["candidate_id"]
            image = Path(str(by_id[candidate_id].get("image_path") or ""))
            candidate_dir = root / candidate_id
            candidate_dir.mkdir()
            images: list[tuple[str, Path]] = []
            if gate["uses_anchor"]:
                anchor_image = Path(str(anchor.get("image_path") or ""))
                images.append(("front_anchor.png", anchor_image))
            if gate["crop_head"]:
                if pipeline != "body-reference":
                    raise GateTestRigError("Head crops are only supported for Body-Reference gates.")
                crop = candidate_dir / "candidate_head.png"
                service._crop_head(image, crop)
                images.append(("candidate_head.png", crop))
            else:
                images.append(("candidate.png", image))
            if config["gate"] == "source_identity" and pipeline == "head-image":
                images.insert(0, ("front_source.png", Path(str(run["front_source"]))))

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            ask_id = f"Ask_GateTestRig_{test_id}_{candidate_id}_{stamp}"
            output_name = "response.txt"
            if config["model"].startswith("codex:"):
                output = result_dir / f"{candidate_id}.txt"
                image_mapping = "\n".join(
                    f"Image {index}: {name}" for index, (name, _) in enumerate(images, start=1)
                )
                codex_prompt = (
                    f"{prompt}\n\nEvaluate the supplied image(s) for the {config['gate']} gate. "
                    "Return the gate verdict in the exact format requested by the prompt.\n\n"
                    f"Image mapping:\n{image_mapping}"
                )
                attempt = {"candidate_id": candidate_id, "ask_id": ask_id, "status": "RUNNING",
                           "output_path": str(output),
                           "codex_error_path": str(root / f"{candidate_id}.codex-error.json"),
                           "input_hashes": {name: self._hash(source) for name, source in images},
                           "source_image_hashes": {
                               "candidate": self._hash(image),
                               "front_anchor": self._hash(Path(str(anchor.get("image_path") or "")))
                               if gate["uses_anchor"] and anchor else "",
                               **({"front_source": self._hash(Path(str(run.get("front_source") or "")))}
                                  if config["gate"] == "source_identity" and pipeline == "head-image" else {}),
                           },
                           "prompt_sha256": hashlib.sha256(codex_prompt.encode("utf-8")).hexdigest()}
                record["attempts"].append(attempt)
                write_json_atomic(record_path, record)
                threading.Thread(
                    target=self._run_codex_attempt_background,
                    kwargs={"config": config, "prompt": codex_prompt, "images": images,
                            "output": output, "error_path": Path(attempt["codex_error_path"])},
                    name=f"gate-test-codex-{test_id}-{candidate_id}", daemon=True,
                ).start()
                continue
            staging = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.create_staging(ask_id)
            for filename, source in images:
                shutil.copy2(source, staging / filename)
            (staging / self.PROMPT_FILE).write_text(prompt, encoding="utf-8")
            manifest = {
                "version": AI_PROXY_PROTOCOL_VERSION,
                "ask_id": ask_id,
                "asset_id": None,
                "character": run.get("character", ""),
                "phase": run.get("phase", ""),
                "pipeline": "Gate-Test-Rig",
                "pipeline_stage": f"GATE_TEST_{config['gate'].upper()}",
                "ollama_attempt_id": test_id,
                "worker_type": "ollama_generate",
                "ollama_model": config["model"],
                "ollama_chat": config["api"] == "chat",
                "ollama_force_generate": config["api"] == "generate",
                "ollama_think": config["think"],
                "ollama_temperature": config["temperature"],
                "ollama_keep_alive": config["keep_alive"],
                "ollama_options": {**config["options"], "temperature": config["temperature"]},
                "ollama_request_options": config["request_options"],
                "ollama_allow_unmanaged_model": True,
                "prompt_file": self.PROMPT_FILE,
                "image_files": [name for name, _ in images],
                "json_output": False,
                "expected_output": output_name,
                "task_type": "gate_test_rig",
                "auxiliary": True,
                "target_output_dir": str(result_dir.resolve()),
                "target_output_file": f"{candidate_id}.txt",
                "gate_test_rig_id": test_id,
                "source_run_id": run_id,
                "source_pipeline": pipeline,
                "candidate_id": candidate_id,
                "gate": config["gate"],
                "view": view,
                "input_hashes": {name: self._hash(source) for name, source in images},
                "source_image_hashes": {
                    "candidate": self._hash(image),
                    "front_anchor": self._hash(Path(str(anchor.get("image_path") or "")))
                    if gate["uses_anchor"] and anchor else "",
                    **({"front_source": self._hash(Path(str(run.get("front_source") or "")))}
                       if config["gate"] == "source_identity" and pipeline == "head-image" else {}),
                },
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "request_config": config,
            }
            (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            attempt = {"candidate_id": candidate_id, "ask_id": ask_id, "status": "QUEUED",
                       "output_path": str(result_dir / f"{candidate_id}.txt"),
                       "input_hashes": manifest["input_hashes"],
                       "source_image_hashes": manifest["source_image_hashes"],
                       "prompt_sha256": manifest["prompt_sha256"]}
            record["attempts"].append(attempt)
            write_json_atomic(record_path, record)
            try:
                self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.publish(
                    staging, ask_id, "ollama_generate"
                )
            except Exception as exc:
                shutil.rmtree(staging, ignore_errors=True)
                attempt.update(status="FAILED", error=f"Could not queue AI Proxy request: {exc}")
                write_json_atomic(record_path, record)
        return self.status(test_id)

    def _proxy_answer(self, ask_id: str) -> dict[str, Any]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        roots = (paths.ask_root(), paths.running_root(), paths.answer_root())
        for root in roots:
            folder = root / ask_id
            if folder.is_dir():
                answer = self._read_json(folder / "answer_manifest.json")
                return self._attach_thinking(answer, folder)
        for folder in paths.harvested_archive_root().glob(f"*/{ask_id}"):
            answer = self._read_json(folder / "answer_manifest.json")
            if answer:
                return self._attach_thinking(answer, folder)
        return {}

    @staticmethod
    def _attach_thinking(answer: dict[str, Any], folder: Path) -> dict[str, Any]:
        generation = answer.get("ollama_generation") or {}
        filename = str(generation.get("thinking_file") or "")
        if filename and Path(filename).name == filename:
            thinking_path = folder / filename
            if thinking_path.is_file():
                answer["thinking_text"] = thinking_path.read_text(encoding="utf-8")
        return answer

    @staticmethod
    def _interpret(gate: str, response: str, pipeline: str = "body-reference") -> dict[str, str]:
        if pipeline == "head-image":
            answer = str(response or "").strip().upper()
            if answer not in {"TRUE", "FALSE"}:
                raise ValueError(f"Expected TRUE or FALSE, received {answer[:80]!r}.")
            return {"result": "REJECT" if answer == "TRUE" else "PASS", "reason": ""}
        if gate == "orientation":
            rejection, reason = _parse_orientation_gate_verdict(response)
        elif gate in {"proportion", "framing", "body_identity"}:
            rejection, reason = _parse_passing_gate_verdict(response)
        else:
            answer = str(response or "").strip().upper()
            if answer not in {"TRUE", "FALSE"}:
                raise ValueError(f"Expected TRUE or FALSE, received {answer[:80]!r}.")
            rejection, reason = answer, ""
        return {"result": "REJECT" if rejection == "TRUE" else "PASS", "reason": reason}

    def status(self, test_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"\d{8}_\d{6}_\d{6}_[a-f0-9]{8}", str(test_id or "")):
            raise GateTestRigError("Invalid Gate Test Rig test id.")
        root = self.test_root / test_id
        record_path = root / "test.json"
        record = self._read_json(record_path)
        if not record:
            raise GateTestRigError(f"Gate Test Rig test not found: {test_id}")
        terminal = {"COMPLETE", "FAILED", "INVALID"}
        for attempt in record.get("attempts") or []:
            if attempt.get("status") in terminal:
                continue
            output = Path(str(attempt.get("output_path") or ""))
            codex_error = Path(str(attempt.get("codex_error_path") or "")) if attempt.get("codex_error_path") else None
            if codex_error and codex_error.is_file():
                attempt.update(status="FAILED", error=self._read_json(codex_error).get("error", "GPT-6 Luna failed."))
                continue
            if output.is_file():
                response = output.read_text(encoding="utf-8")
                attempt["response"] = response
                if not codex_error:
                    attempt["answer_manifest"] = self._proxy_answer(str(attempt.get("ask_id") or ""))
                try:
                    attempt.update(self._interpret(record["gate"], response, record.get("pipeline", "body-reference")))
                    attempt["status"] = "COMPLETE"
                except ValueError as exc:
                    attempt["status"] = "INVALID"
                    attempt["error"] = str(exc)
            elif not codex_error:
                answer = self._proxy_answer(str(attempt.get("ask_id") or ""))
                if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER"}:
                    attempt["status"] = "FAILED"
                    attempt["error"] = answer.get("error_message") or "AI Proxy request failed."
                    attempt["answer_manifest"] = answer
                elif answer:
                    attempt["status"] = "RUNNING"
                    attempt["answer_manifest"] = answer
        states = {attempt.get("status") for attempt in record.get("attempts") or []}
        record["status"] = "COMPLETE" if states.issubset(terminal) else "RUNNING"
        write_json_atomic(record_path, record)
        return record

    def list_tests(self) -> list[dict[str, Any]]:
        """Return persisted test summaries, newest first, without polling proxy jobs."""
        tests: list[dict[str, Any]] = []
        if not self.test_root.is_dir():
            return tests
        for record_path in self.test_root.glob("*/test.json"):
            record = self._read_json(record_path)
            if not record or record.get("test_id") != record_path.parent.name:
                continue
            attempts = record.get("attempts") or []
            tests.append({
                "test_id": record["test_id"],
                "pipeline": record.get("pipeline", "body-reference"),
                "run_id": record.get("run_id", ""),
                "view": record.get("view", ""),
                "gate": record.get("gate", ""),
                "model": (record.get("config") or {}).get("model", ""),
                "status": record.get("status", "RUNNING"),
                "created_at": record.get("created_at", ""),
                "attempt_count": len(attempts),
                "complete_count": sum(item.get("status") == "COMPLETE" for item in attempts),
                "finished_count": sum(item.get("status") in {"COMPLETE", "FAILED", "INVALID"} for item in attempts),
            })
        return sorted(tests, key=lambda item: (item["created_at"], item["test_id"]), reverse=True)
