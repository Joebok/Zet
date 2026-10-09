"""Durable, schema-constrained Codex text attempts owned by narrative jobs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

from zet.models.narrative import new_id
from zet.services.atomic_file_service import write_json_atomic


CODEX_MODELS = ("gpt-6-luna", "gpt-6-sol", "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra")


class NarrativeCodexService:
    def __init__(self, repository):
        self.repository = repository
        self.runner = subprocess.run
        self._attempts = {}
        self._guard = threading.Lock()
        self._closed = threading.Event()

    def close(self):
        self._closed.set()

    @staticmethod
    def executable():
        executable = shutil.which("codex")
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
            if installs:
                executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
        if not executable:
            raise RuntimeError("Codex CLI is unavailable. Select an Ollama model or configure Codex.")
        return executable

    def poll(self, story, scene, target, job):
        attempt = job.get("codex_attempt")
        root = self.repository.folder(story, scene, target) / "text-jobs" / job["id"]
        output = root / f"{attempt}.json"
        if attempt and output.is_file():
            value = json.loads(output.read_text(encoding="utf-8"))
            if value.get("attempt") == attempt:
                if value.get("error"):
                    return "FAILED", value["error"]
                return "COMPLETE", json.dumps(value["result"]).encode("utf-8")
        with self._guard:
            thread = self._attempts.get(attempt)
            if thread and thread.is_alive():
                return "RUNNING", None
            if self._closed.is_set():
                return "QUEUED", None
            # A new executor after restart owns a fresh attempt. Old results cannot apply.
            attempt = new_id()
            job["codex_attempt"] = attempt
            record = self.repository.read(story, scene, target)
            record["jobs"][job["id"]] = job
            self.repository.write(record, story, scene, target)
            thread = threading.Thread(target=self._run, args=(story, scene, target, dict(job), root, attempt),
                                      name="zet-narrative-codex", daemon=True)
            self._attempts[attempt] = thread
            thread.start()
        return "RUNNING", None

    def _run(self, story, scene, target, job, root, attempt):
        try:
            root.mkdir(parents=True, exist_ok=True)
            schema = root / f"{attempt}-schema.json"
            output = root / f"{attempt}-output.json"
            write_json_atomic(schema, job["schema"])
            command = [self.executable(), "-a", "never", "-s", "read-only", "-m", job["model"].removeprefix("codex:"),
                       "-c", 'model_reasoning_effort="high"', "-C", str(root.resolve()), "exec", "--ignore-user-config",
                       "--skip-git-repo-check", "--ephemeral", "--output-schema", str(schema.resolve()),
                       "--output-last-message", str(output.resolve())]
            result = self.runner(command, input=job["request"], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=900, check=False)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or "Codex generation failed")[-2000:])
            value = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Codex returned invalid JSON.")
            for key in job["schema"]["required"]:
                expected = job["schema"]["properties"][key]["type"]
                if key not in value or not isinstance(value[key], str if expected == "string" else list):
                    raise ValueError(f"Codex returned an invalid {key} field.")
            response = {"attempt": attempt, "result": value}
        except Exception as exc:
            response = {"attempt": attempt, "error": str(exc)}
        if self._closed.is_set():
            return
        with self.repository.lock():
            try:
                current = self.repository.read(story, scene, target)["jobs"].get(job["id"], {})
            except KeyError:
                return
            if current.get("codex_attempt") == attempt:
                write_json_atomic(root / f"{attempt}.json", response)
