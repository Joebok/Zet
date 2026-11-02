"""Recoverable isolation of generated artifacts for a candidate retry."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
from uuid import UUID


class RetryArtifactConflict(ValueError):
    """The candidate artifacts no longer match the retry's ownership."""


class LocalPipelineRetryArtifactService:
    """Move one candidate's old generated output aside without copying it.

    Callers must hold the appropriate operation and worker fences, validate the
    candidate under the batch-state lock, and persist a reservation before using
    this helper. A detached directory belongs exclusively to the operation ID.
    """

    def __init__(self, run_root: Path, candidate_id: str, operation_id: str):
        if not re.fullmatch(r"(?:F|FL|FR|PL|PR|B|BR|BL)-\d{3,}", str(candidate_id or "")):
            raise ValueError("Invalid local image candidate ID.")
        operation_id = UUID(str(operation_id)).hex
        root = Path(run_root).resolve()
        candidate = root / "renders" / candidate_id
        if candidate.resolve() != candidate or not candidate.is_relative_to(root):
            raise ValueError("Candidate artifact path is not directly owned by this run.")
        self.root = root
        self.source = candidate / "Local_Test_Renders"
        self.detached = candidate / (".zet-retry-" + operation_id)

    def inspect(self) -> tuple[bool, bool]:
        """Return current/detached directory presence after containment checks."""
        for path in (self.source, self.detached):
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise RetryArtifactConflict("Candidate artifact path is not safe.")
            if path.exists() and not path.is_dir():
                raise RetryArtifactConflict("Candidate artifact path is not a directory.")
        source, detached = self.source.is_dir(), self.detached.is_dir()
        if source and detached:
            raise RetryArtifactConflict("Both current and detached artifacts exist; review the candidate.")
        return source, detached

    def detach(self) -> bool:
        """Atomically detach existing output, or recognize an earlier detach."""
        source, detached = self.inspect()
        if source:
            os.replace(self.source, self.detached)
            return True
        return detached

    def restore(self) -> bool:
        """Restore detached output after cancellation, without overwriting output."""
        source, detached = self.inspect()
        if detached:
            os.replace(self.detached, self.source)
            return True
        return source

    def discard(self) -> bool:
        """Delete only this operation's detached output after state commit."""
        _, detached = self.inspect()
        if detached:
            shutil.rmtree(self.detached)
        return detached
