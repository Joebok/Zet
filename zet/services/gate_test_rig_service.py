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
import zipfile

from zet.models.ai_proxy import AI_PROXY_PROTOCOL_VERSION
from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_body_reference_service import LocalBodyReferenceService
from zet.services.local_gate_registry_service import LocalGateRegistryService


class GateTestRigError(ValueError):
    """Raised when a Gate Test Rig selection or request is invalid."""


class GateTestRigService:
    """Run and save curated local pipeline gate regression tests."""

    PROMPT_FILE = "OLLAMA_PROMPT.md"
    TERMINAL_ATTEMPT_STATES = {"COMPLETE", "FAILED", "INVALID"}

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.registry = LocalGateRegistryService(app, project_root)
        self.root = self.registry.root
        self.run_root = self.root / "runs"
        self.saved_test_root = self.registry.saved_test_root
        cleanup_marker = self.root / ".legacy-rig-data-discarded"
        if not cleanup_marker.exists():
            for legacy in (self.root / "configs", self.root / "tests"):
                if legacy.is_dir():
                    shutil.rmtree(legacy)
            cleanup_marker.parent.mkdir(parents=True, exist_ok=True)
            cleanup_marker.write_text("discarded by curated Gate Test Rig", encoding="utf-8")

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

    @staticmethod
    def _safe_id(value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", str(value or "")):
            raise GateTestRigError("Invalid saved test id.")
        return value

    def catalog(self, pipeline: str = "") -> dict[str, Any]:
        if pipeline:
            value = self.registry.catalog(pipeline)
            value["cases"] = self.registry.list_cases(pipeline)
            return value
        value = self.registry.catalog()
        for item in value["pipelines"]:
            item["gates"] = self.registry.catalog(item["key"])["gates"]
        return value

    @staticmethod
    def _validate_config(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise GateTestRigError("Model request must be an object.")
        model = str(value.get("model") or "").strip()
        if not model or model == "codex:":
            raise GateTestRigError("Choose an Ollama model or GPT-6 Luna.")
        if model.startswith("codex:") and model != "codex:gpt-6-luna":
            raise GateTestRigError("GPT-6 Luna is the only supported Codex model in the Gate Test Rig.")
        api = str(value.get("api") or "generate").lower()
        if api not in {"generate", "chat"}:
            raise GateTestRigError("API endpoint must be generate or chat.")
        think = value.get("think", "high" if model.startswith("codex:") else False)
        if model.startswith("codex:"):
            if not isinstance(think, str) or think not in {"none", "low", "medium", "high", "xhigh", "max"}:
                raise GateTestRigError("GPT-6 Luna reasoning must be none, low, medium, high, xhigh, or max.")
        elif think is not None and not isinstance(think, bool):
            raise GateTestRigError("Ollama thinking must be true, false, or model default.")
        return {"model": model, "api": api, "think": think}

    def _codex_executable(self) -> str:
        import shutil as shutil_module
        executable = shutil_module.which("codex")
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
        completed = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                   timeout=1800, check=False,
                                   env=LocalBodyReferenceService._luna_environment())
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
        pipeline = self.registry.pipeline(str(payload.get("pipeline") or ""))
        gate = str(payload.get("gate") or "").strip()
        catalog = self.registry.catalog(pipeline.key)
        if gate not in catalog["gates"]:
            raise GateTestRigError(f"Unknown {pipeline.label} gate: {gate}")
        config = self._validate_config(payload.get("config"))
        overrides = payload.get("prompt_overrides") or {}
        if not isinstance(overrides, dict):
            raise GateTestRigError("Prompt overrides must be an object keyed by view.")
        prompt_overrides: dict[str, str] = {}
        for view, prompt in overrides.items():
            view = str(view).strip().upper()
            if view not in pipeline.views or not isinstance(prompt, str):
                raise GateTestRigError(f"Invalid prompt override for view {view}.")
            if prompt.strip():
                prompt_overrides[view] = prompt
        cases = self.registry.list_cases(pipeline.key, gate)
        if not cases:
            raise GateTestRigError("Add at least one curated test case for this gate before running it.")

        definitions = {}
        for view in pipeline.views:
            for definition in pipeline.gates_for_view(None, view):
                if definition.key == gate:
                    definitions[view] = definition
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid4().hex[:8]
        root = self.run_root / run_id
        snapshot_root = root / "cases"
        results_root = root / "results"
        snapshot_root.mkdir(parents=True, exist_ok=False)
        results_root.mkdir()
        record = {"run_id": run_id, "pipeline": pipeline.key, "gate": gate, "config": config,
                  "prompt_overrides": prompt_overrides, "status": "RUNNING",
                  "created_at": datetime.now().isoformat(timespec="seconds"), "attempts": []}
        record_path = root / "run.json"
        for case in cases:
            view = case["view"]
            definition = definitions.get(view)
            if definition is None:
                raise GateTestRigError(f"Gate {gate} no longer applies to case view {view}.")
            prompt = prompt_overrides.get(view, definition.prompt)
            if not prompt.strip():
                raise GateTestRigError(f"Prompt for {view} cannot be blank.")
            case_id = case["case_id"]
            case_dir = snapshot_root / case_id
            case_dir.mkdir()
            source_image = self.registry.case_image_path(pipeline.key, gate, case_id, "candidate")
            candidate_copy = case_dir / "candidate.png"
            shutil.copy2(source_image, candidate_copy)
            case_image_roles = list(definition.input_roles)
            if definition.crop_head and "candidate_head" not in case_image_roles:
                case_image_roles.append("candidate_head")
            elif "candidate" not in case_image_roles:
                case_image_roles.append("candidate")
            if definition.uses_anchor and "front_anchor" not in case_image_roles:
                case_image_roles.append("front_anchor")
            if definition.uses_source and "front_source" not in case_image_roles:
                case_image_roles.append("front_source")
            image_roles = [("candidate", candidate_copy)]
            if definition.crop_head:
                from PIL import Image
                with Image.open(candidate_copy) as source:
                    rgb = source.convert("RGB")
                    width, height = rgb.size
                    crop = case_dir / "candidate_head.png"
                    rgb.crop((int(width * .25), 0, int(width * .75), int(height * .32))).save(crop, format="PNG")
                image_roles = [("candidate_head", crop)]
            for role in case_image_roles:
                if role in {"candidate", "candidate_head"}:
                    continue
                image_roles.append((role, self.registry.case_image_path(pipeline.key, gate, case_id, role)))
            images = []
            hashes = {}
            for role, source in image_roles:
                copied = source if source.parent == case_dir else case_dir / f"{role}.png"
                if copied != source:
                    shutil.copy2(source, copied)
                images.append((f"{role}.png", copied))
                hashes[role] = self._hash(copied)
            prompt_path = case_dir / "prompt.md"
            prompt_path.write_text(prompt, encoding="utf-8")
            attempt_id = uuid4().hex
            output = results_root / f"{attempt_id}.txt"
            ask_id = f"Ask_GateTestRig_{run_id}_{attempt_id}"
            attempt = {"attempt_id": attempt_id, "case_id": case_id, "view": view,
                       "expected": case["expected"], "status": "QUEUED", "ask_id": ask_id,
                       "output_path": str(output), "image_files": [name for name, _ in images],
                       "input_hashes": hashes, "prompt": prompt,
                       "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                       "case_snapshot": str(case_dir)}
            record["attempts"].append(attempt)
            write_json_atomic(record_path, record)
            if config["model"].startswith("codex:"):
                error_path = root / f"{attempt_id}.codex-error.json"
                attempt.update(status="RUNNING", codex_error_path=str(error_path))
                write_json_atomic(record_path, record)
                image_mapping = "\n".join(f"Image {index}: {name}" for index, (name, _) in enumerate(images, 1))
                codex_prompt = (f"{prompt}\n\nEvaluate this {pipeline.key} {gate} gate case. Return PASS or FAIL "
                                f"as a single verdict.\n\nImage mapping:\n{image_mapping}")
                threading.Thread(target=self._run_codex_attempt_background,
                                 kwargs={"config": config, "prompt": codex_prompt, "images": images,
                                         "output": output, "error_path": error_path},
                                 name=f"gate-case-{attempt_id}", daemon=True).start()
                continue
            staging = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.create_staging(ask_id)
            for filename, source in images:
                shutil.copy2(source, staging / filename)
            (staging / self.PROMPT_FILE).write_text(prompt, encoding="utf-8")
            manifest = {
                "version": AI_PROXY_PROTOCOL_VERSION, "ask_id": ask_id, "asset_id": None,
                "pipeline": "Gate-Test-Rig", "pipeline_stage": f"GATE_TEST_{gate.upper()}",
                "worker_type": "ollama_generate", "ollama_model": config["model"],
                "ollama_chat": config["api"] == "chat", "ollama_force_generate": config["api"] == "generate",
                "ollama_think": config["think"], "ollama_allow_unmanaged_model": True,
                "prompt_file": self.PROMPT_FILE, "image_files": [name for name, _ in images],
                "json_output": False, "expected_output": "response.txt", "task_type": "gate_test_rig",
                "auxiliary": True, "target_output_dir": str(results_root.resolve()),
                "target_output_file": output.name, "gate_test_rig_id": run_id,
                "source_pipeline": pipeline.key, "case_id": case_id, "gate": gate, "view": view,
                "input_hashes": {name: self._hash(source) for name, source in images},
                "source_image_hashes": hashes, "prompt_sha256": attempt["prompt_sha256"],
                "request_config": config,
            }
            (staging / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            attempt.update(status="QUEUED", answer_manifest_path="")
            write_json_atomic(record_path, record)
            try:
                self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.publish(staging, ask_id, "ollama_generate")
            except Exception as exc:
                shutil.rmtree(staging, ignore_errors=True)
                attempt.update(status="FAILED", error=f"Could not queue AI Proxy request: {exc}")
                write_json_atomic(record_path, record)
        return self.status(run_id)

    def _proxy_answer(self, ask_id: str) -> dict[str, Any]:
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        roots = (paths.ask_root(), paths.running_root(), paths.answer_root())
        for base in roots:
            folder = base / ask_id
            if folder.is_dir():
                answer = self._read_json(folder / "answer_manifest.json")
                generation = answer.get("ollama_generation") or {}
                filename = str(generation.get("thinking_file") or "")
                if filename and Path(filename).name == filename and (folder / filename).is_file():
                    answer["thinking_text"] = (folder / filename).read_text(encoding="utf-8")
                return answer
        for folder in paths.harvested_archive_root().glob(f"*/{ask_id}"):
            answer = self._read_json(folder / "answer_manifest.json")
            if answer:
                return answer
        return {}

    def _saved_run_record(self, test_id: str) -> tuple[Path, dict[str, Any]]:
        run_path = self.run_root / test_id / "run.json"
        if run_path.is_file():
            return run_path, self._read_json(run_path)
        saved_id = self._safe_id(test_id)
        saved_path = self.saved_test_root / saved_id / "saved.json"
        metadata = self._read_json(saved_path)
        snapshot = self.saved_test_root / saved_id / str(metadata.get("snapshot") or "") / "run.json"
        if metadata and snapshot.is_file():
            return snapshot, self._read_json(snapshot)
        raise GateTestRigError(f"Gate test not found: {test_id}")

    def status(self, test_id: str) -> dict[str, Any]:
        record_path, record = self._saved_run_record(test_id)
        terminal = self.TERMINAL_ATTEMPT_STATES
        for attempt in record.get("attempts") or []:
            if attempt.get("status") in terminal:
                continue
            output = Path(str(attempt.get("output_path") or ""))
            codex_error = Path(str(attempt.get("codex_error_path") or "")) if attempt.get("codex_error_path") else None
            if codex_error and codex_error.is_file():
                attempt.update(status="FAILED", error=self._read_json(codex_error).get("error", "GPT-6 Luna failed."))
            elif output.is_file():
                response = output.read_text(encoding="utf-8")
                attempt["response"] = response
                if not codex_error:
                    attempt["answer_manifest"] = self._proxy_answer(str(attempt.get("ask_id") or ""))
                try:
                    pipeline = self.registry.pipeline(record["pipeline"])
                    actual = pipeline.interpret(record["gate"], response)["result"]
                    attempt["actual"] = actual
                    attempt["result"] = "PASS" if actual == attempt["expected"] else "FAIL"
                    attempt["status"] = "COMPLETE"
                except (ValueError, KeyError) as exc:
                    attempt.update(status="INVALID", error=str(exc))
            else:
                answer = self._proxy_answer(str(attempt.get("ask_id") or ""))
                if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER"}:
                    attempt.update(status="FAILED", error=answer.get("error_message") or "AI Proxy request failed.",
                                   answer_manifest=answer)
                elif answer:
                    attempt.update(status="RUNNING", answer_manifest=answer)
        states = {attempt.get("status") for attempt in record.get("attempts") or []}
        record["status"] = "COMPLETE" if states.issubset(terminal) else "RUNNING"
        write_json_atomic(record_path, record)
        return record

    def list_tests(self) -> list[dict[str, Any]]:
        tests = []
        if not self.saved_test_root.is_dir():
            return tests
        for saved_path in self.saved_test_root.glob("*/saved.json"):
            metadata = self._read_json(saved_path)
            if not metadata or metadata.get("test_id") != saved_path.parent.name:
                continue
            snapshot = saved_path.parent / str(metadata.get("snapshot") or "") / "run.json"
            record = self._read_json(snapshot)
            tests.append({"test_id": metadata["test_id"], "name": metadata.get("name", ""),
                          "pipeline": record.get("pipeline", ""), "gate": record.get("gate", ""),
                          "status": record.get("status", ""), "created_at": metadata.get("created_at", ""),
                          "attempt_count": len(record.get("attempts") or []),
                          "complete_count": sum(a.get("status") == "COMPLETE" for a in record.get("attempts") or [])})
        return sorted(tests, key=lambda item: (item["created_at"], item["test_id"]), reverse=True)

    def save_test(self, run_id: str, name: str, test_id: str = "") -> dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            raise GateTestRigError("A saved test name is required.")
        run = self.status(run_id)
        if run["status"] != "COMPLETE":
            raise GateTestRigError("Wait for every case result before saving the test.")
        test_id = self._safe_id(test_id) if test_id else uuid4().hex
        folder = self.saved_test_root / test_id
        folder.mkdir(parents=True, exist_ok=True)
        snapshot_id = uuid4().hex
        snapshot = folder / snapshot_id
        source = self.run_root / run["run_id"]
        shutil.copytree(source, snapshot)
        metadata = self._read_json(folder / "saved.json")
        saved = {"test_id": test_id, "name": name,
                 "created_at": metadata.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                 "updated_at": datetime.now().isoformat(timespec="seconds"), "snapshot": snapshot_id}
        write_json_atomic(folder / "saved.json", saved)
        old_snapshot = str(metadata.get("snapshot") or "")
        if old_snapshot and old_snapshot != snapshot_id:
            shutil.rmtree(folder / old_snapshot, ignore_errors=True)
        (folder / f"{test_id}-review-packet.zip").unlink(missing_ok=True)
        return {**saved, **run}

    def rename_test(self, test_id: str, name: str) -> dict[str, Any]:
        test_id = self._safe_id(test_id)
        name = str(name or "").strip()
        if not name:
            raise GateTestRigError("A saved test name is required.")
        folder = self.saved_test_root / test_id
        path = folder / "saved.json"
        saved = self._read_json(path)
        if not saved:
            raise GateTestRigError(f"Saved test not found: {test_id}")
        saved.update(name=name, updated_at=datetime.now().isoformat(timespec="seconds"))
        write_json_atomic(path, saved)
        return saved

    def delete_test(self, test_id: str) -> None:
        folder = self.saved_test_root / self._safe_id(test_id)
        if not (folder / "saved.json").is_file():
            raise GateTestRigError(f"Saved test not found: {test_id}")
        shutil.rmtree(folder)

    def review_packet(self, test_id: str) -> Path:
        test_id = self._safe_id(test_id)
        folder = self.saved_test_root / test_id
        metadata = self._read_json(folder / "saved.json")
        if not metadata:
            raise GateTestRigError(f"Saved test not found: {test_id}")
        snapshot = folder / str(metadata["snapshot"])
        packet = folder / f"{test_id}-review-packet.zip"
        with zipfile.ZipFile(packet, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(folder / "saved.json", "saved.json")
            for path in snapshot.rglob("*"):
                if path.is_file():
                    archive.write(path, Path("snapshot") / path.relative_to(snapshot))
            archive.writestr("README.txt", "Gate Test Rig review packet. run.json includes prompts, model settings, per-case verdicts, image hashes, and available diagnostics.\n")
        return packet

    def run_case_image_path(self, run_id: str, case_id: str, role: str = "candidate") -> Path:
        run_id = self._safe_id(run_id)
        case_id = self._safe_id(case_id)
        if role not in {"candidate", "front_anchor", "front_source"}:
            raise GateTestRigError("Unknown case image role.")
        path = self.run_root / run_id / "cases" / case_id / f"{role}.png"
        if not path.is_file():
            raise GateTestRigError(f"Run image not found: {case_id} {role}")
        return path

    def saved_case_image_path(self, test_id: str, case_id: str, role: str = "candidate") -> Path:
        test_id = self._safe_id(test_id)
        case_id = self._safe_id(case_id)
        if role not in {"candidate", "front_anchor", "front_source"}:
            raise GateTestRigError("Unknown case image role.")
        metadata = self._read_json(self.saved_test_root / test_id / "saved.json")
        path = self.saved_test_root / test_id / str(metadata.get("snapshot") or "") / "cases" / case_id / f"{role}.png"
        if not metadata or not path.is_file():
            raise GateTestRigError(f"Saved image not found: {case_id} {role}")
        return path
