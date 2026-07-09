#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.services.config_service import ConfigService


def load_project_config(project_root: Path = PROJECT_ROOT):
    """Load the Zet project config for script path resolution."""
    return ConfigService.load(project_root / "config.toml")


def library_root(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the configured external library root."""
    return Path(load_project_config(project_root).base_library_path)


def character_root(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the configured character library root."""
    return Path(load_project_config(project_root).base_character_path)


def asset_root(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the configured asset library root."""
    return Path(load_project_config(project_root).base_asset_path)


def pipeline_root(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the configured pipeline library root."""
    return Path(load_project_config(project_root).base_pipeline_path)


def resolve_library_path(project_root: Path, raw_path: str | Path) -> Path:
    """Resolve absolute, project-relative, and legacy _Lib paths."""
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "_Lib":
        return library_root(project_root).joinpath(*parts[1:])
    if parts and parts[0] in {"Characters", "Assets", "Pipelines", "AuxiliaryResources", "Stories"}:
        return library_root(project_root).joinpath(*parts)
    return project_root / path
