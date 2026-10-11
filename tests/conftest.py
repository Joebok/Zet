"""Isolate import-time application construction from the developer checkout."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import tempfile


_bootstrap = tempfile.TemporaryDirectory(prefix="zet-pytest-app-")
_bootstrap_root = Path(_bootstrap.name)
for directory in ("Characters", "Assets", "Pipelines", "Queue", "Config"):
    (_bootstrap_root / directory).mkdir()
(_bootstrap_root / "Config" / "AI_Prompt_Analysis_Instructions.md").write_text(
    "Analyze the compiled prompt.\n", encoding="utf-8"
)
(_bootstrap_root / "config.toml").write_text(
    "[BaseFolders]\n"
    f'BaseLibraryPath = "{_bootstrap_root.as_posix()}"\n'
    f'BaseCharacterPath = "{(_bootstrap_root / "Characters").as_posix()}"\n'
    f'BaseAssetPath = "{(_bootstrap_root / "Assets").as_posix()}"\n'
    f'BasePipelinePath = "{(_bootstrap_root / "Pipelines").as_posix()}"\n'
    f'BaseAIQueuePath = "{(_bootstrap_root / "Queue").as_posix()}"\n',
    encoding="utf-8",
)

_original_cwd = Path.cwd()
try:
    os.chdir(_bootstrap_root)
    _web_app_module = importlib.import_module("zet.web.app")
    _web_app_module.app.state.config_path = str(_bootstrap_root / "config.toml")
finally:
    os.chdir(_original_cwd)
