"""Shared structured Codex calls for reference authoring wizards."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


CODEX_MODELS = {"gpt-6-luna", "gpt-6-sol", "gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra"}


def codex_json(project_root: Path, model: str, system: str, prompt: str, schema: dict,
               images: list[str], *, label: str, error_type=ValueError) -> dict:
    if model not in CODEX_MODELS:
        raise error_type(f"Unsupported {label} Codex model: {model}")
    executable = shutil.which("codex")
    if not executable and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        installs = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
        if installs:
            executable = str(max(installs, key=lambda path: path.stat().st_mtime_ns))
    if not executable:
        raise error_type(f"Codex CLI is unavailable for {label}.")
    with tempfile.TemporaryDirectory(prefix="zet_wizard_") as temp:
        schema_path, output = Path(temp) / "schema.json", Path(temp) / "answer.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        command = [executable, "-a", "never", "-s", "read-only", "-m", model,
                   "-c", 'model_reasoning_effort="high"', "-C", str(project_root), "exec",
                   "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--output-schema",
                   str(schema_path), "--output-last-message", str(output)]
        for image in images:
            command.extend(["--image", image])
        completed = subprocess.run(command, input=f"{system}\n\n{prompt}", capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=1800, check=False)
        if completed.returncode:
            raise error_type((completed.stderr or completed.stdout or f"Codex {label} task failed")[-2000:])
        try:
            value = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise error_type(f"Codex returned an invalid {label} response.") from exc
        if not isinstance(value, dict):
            raise error_type(f"Codex returned an invalid {label} response.")
        return value
