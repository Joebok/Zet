"""Compatibility entry point; all structured generation uses the common job service."""
from pathlib import Path


def codex_json(project_root: Path, model: str, system: str, prompt: str, schema: dict,
               images: list[str], *, label: str, error_type=ValueError, paths=None) -> dict:
    if paths is None:
        raise error_type("Structured generation requires an explicit universe-bound AI_Proxy service.")
    try:
        return paths.jobs.generate_json("codex:" + model.removeprefix("codex:"), system, prompt,
                                        schema, images, task_type=label)[0]
    except Exception as exc:
        raise error_type(str(exc)) from exc
