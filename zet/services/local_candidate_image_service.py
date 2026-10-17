"""Resolve a current local pipeline candidate image without building run detail."""
from __future__ import annotations

from pathlib import Path

from zet.services.library_reference_service import read_library_json
from zet.services.render_slot_service import merge_candidates
from zet.services.workflow_storage import file_lock


class CandidateImageUnavailable(ValueError):
    """The requested candidate has no safe, current image file."""


def candidate_image_path(run_root: str | Path, candidate_id: str,
                         library_root: str | Path) -> Path:
    """Return a candidate's image after checking current membership and run ownership."""
    root = Path(run_root).resolve()
    owner = Path(library_root).resolve()
    if not root.is_relative_to(owner):
        raise CandidateImageUnavailable("Candidate image is unavailable.")
    spec_path, state_path = root / "spec.json", root / "state.json"
    if not spec_path.is_file() or not state_path.is_file():
        raise CandidateImageUnavailable("Candidate image is unavailable.")
    try:
        spec = read_library_json(spec_path, owner)
        with file_lock(root / "state.lock"):
            state = read_library_json(state_path, owner)
        candidate = merge_candidates(spec, state).get(str(candidate_id))
        path = Path(str((candidate or {}).get("image_path") or "")).resolve()
    except (OSError, ValueError, KeyError, TypeError):
        raise CandidateImageUnavailable("Candidate image is unavailable.") from None
    if (not candidate or not path.is_file() or not path.is_relative_to(root)):
        raise CandidateImageUnavailable("Candidate image is unavailable.")
    return path
