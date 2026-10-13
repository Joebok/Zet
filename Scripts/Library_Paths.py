#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from zet.services.config_service import ConfigService
from zet.services.path_service import PathService
from zet.services.universe_service import UniverseService


def load_project_config(project_root: Path = PROJECT_ROOT):
    """Load the Zet project config for script path resolution."""
    path = Path(os.environ.get("ZET_CONFIG_PATH", "")) if os.environ.get("ZET_CONFIG_PATH") else project_root / "config.toml"
    return ConfigService.load(path)


def library_root(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the currently selected universe root."""
    config = load_project_config(project_root)
    active_root = Path(os.environ["ZET_CONFIG_PATH"]).resolve().parent if os.environ.get("ZET_CONFIG_PATH") else project_root
    service = UniverseService(config.base_library_path, config.state_file(active_root, "universe-selection.json"))
    return Path(service.get_universe(service.selection())["root"])


def shared_library_root(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the source-controlled shared library root."""
    return project_root / "Shared_Library"


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
    return PathService(load_project_config(project_root), project_root).resolve_path(path)
