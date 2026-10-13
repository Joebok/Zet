"""Explicit code-relative defaults and persistent production state locations."""
import os
from pathlib import Path


def state_file(config, project_root, filename: str) -> Path:
    root = getattr(config, "runtime_state_path", "")
    return Path(root) / filename if root else Path(project_root) / "Config" / filename


def workflow_root(config) -> Path:
    configured = getattr(config, "task_state_path", "") or getattr(config, "runtime_state_path", "")
    return Path(configured) if configured else Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local"))) / "Zet" / "TaskWorkflow"
