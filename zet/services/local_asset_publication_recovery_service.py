"""Recover interrupted local-asset publications across JSON and catalog storage."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Callable

from zet.services.library_reference_service import write_library_json


class LocalAssetPublicationRecoveryService:
    def __init__(self, library_root: str | Path, ensure_catalog: Callable):
        self.library_root = Path(library_root).resolve()
        self.ensure_catalog = ensure_catalog

    def recover_locked(self, character: str, phase: str) -> None:
        workspace = (self.library_root / "_state" / "LocalAssets" / character / phase
                     / "local_assets.json")
        journal_root = workspace.parent / "publications"
        if not journal_root.is_dir():
            return
        for journal_path in sorted(journal_root.glob("*.json")):
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            operation_id = str(journal.get("operation_id") or journal_path.stem)
            if not re.fullmatch(r"[a-f0-9]{32}", operation_id):
                raise ValueError(f"Invalid publication journal: {journal_path}")
            receipt = self.ensure_catalog().publication_receipt(operation_id)
            if receipt:
                next_state = journal.get("next")
                if not isinstance(next_state, dict):
                    raise ValueError(f"Committed publication has no recovery state: {journal_path}")
                write_library_json(workspace, next_state, self.library_root)
            else:
                previous = journal.get("previous")
                if isinstance(previous, dict):
                    write_library_json(workspace, previous, self.library_root)
                staging = self.library_root / "images" / ".publication-staging" / operation_id
                plan_path = staging / "plan.json"
                if plan_path.is_file():
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    image_root = (self.library_root / "images").resolve()
                    for item in plan.get("assets", []):
                        target = Path(str(item.get("target_path") or "")).resolve()
                        if (not item.get("file_was_present") and target.is_relative_to(image_root)
                                and target != image_root):
                            target.unlink(missing_ok=True)
            shutil.rmtree(self.library_root / "images" / ".publication-staging" / operation_id,
                          ignore_errors=True)
            journal_path.unlink(missing_ok=True)

    def recover_pending(self) -> None:
        state_root = self.library_root / "_state" / "LocalAssets"
        if not state_root.is_dir():
            return
        for journal in sorted(state_root.glob("*/*/publications/*.json")):
            relative = journal.relative_to(state_root)
            if len(relative.parts) != 4:
                continue
            character, phase = relative.parts[:2]
            from zet.services.workflow_storage import file_lock
            workspace = state_root / character / phase / "local_assets.json"
            with file_lock(workspace.with_suffix(".lock")):
                self.recover_locked(character, phase)
