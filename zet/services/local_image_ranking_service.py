"""Shared Luna invocation for comparative local image ranking."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable

from zet.services.candidate_review_contract import validate_ranking


def rank_images_with_luna(
    *,
    project_root: str | Path,
    model: str,
    prompt: str,
    candidate_ids: list[str],
    image_paths: list[str | Path],
    executable: str,
    reference_image_paths: list[str | Path] | None = None,
    runner: Callable[..., Any] = subprocess.run,
    environment: dict[str, str] | None = None,
    timeout: int = 1800,
) -> tuple[list[dict[str, str]], str]:
    """Run the common structured ranking contract over the supplied image set."""
    if len(candidate_ids) != len(image_paths):
        raise ValueError("Every ranked candidate must have exactly one image.")
    if not candidate_ids:
        return [], ""
    schema = {
        "type": "object",
        "properties": {"ranking": {"type": "array", "items": {
            "type": "object",
            "properties": {"candidate_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["candidate_id", "reason"],
            "additionalProperties": False,
        }}},
        "required": ["ranking"],
        "additionalProperties": False,
    }
    with tempfile.TemporaryDirectory(prefix="zet_local_image_rank_") as temporary:
        schema_path = Path(temporary) / "schema.json"
        output_path = Path(temporary) / "ranking.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        command = [executable, "-a", "never", "-s", "read-only", "-m", model,
                   "-c", 'model_reasoning_effort="high"', "-C", str(Path(project_root)), "exec",
                   "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--output-schema",
                   str(schema_path), "--output-last-message", str(output_path)]
        for image in [*(reference_image_paths or []), *image_paths]:
            command.extend(["--image", str(image)])
        result = runner(command, input=prompt, capture_output=True, text=True, encoding="utf-8",
                        timeout=timeout, check=False, **({"env": environment} if environment is not None else {}))
        if result.returncode:
            raise ValueError((result.stderr or result.stdout or "Luna ranking failed")[-2000:])
        value = json.loads(output_path.read_text(encoding="utf-8"))
        return validate_ranking(value, candidate_ids), model
