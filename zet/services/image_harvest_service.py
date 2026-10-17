"""File availability and current ownership for local pipeline advice."""
from pathlib import Path
from contextlib import contextmanager
import hashlib
from zet.services.workflow_storage import file_lock


def _current_candidate(run, candidate):
    if run.get("stop_requested") or run.get("status") == "CANCELLED":
        raise ValueError("Image workflow has been stopped")
    current = next((item for item in run.get("candidates", [])
                    if item["candidate_id"] == candidate["candidate_id"]), None)
    if (not current or current.get("ask_id") != candidate.get("ask_id")
            or current.get("image_path") != candidate.get("image_path")):
        raise ValueError("Image candidate was replaced before analysis")
    return current


def require_candidate_harvest(app, run, candidate):
    """Retain the shared entry point; a current image file admits local review."""
    current = _current_candidate(run, candidate)
    image = Path(str(current.get("image_path") or ""))
    if not image.is_file():
        raise ValueError("Candidate image is unavailable")
    return {"ask_id": str(current.get("ask_id") or ""), "path": str(image),
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}


def reconcile_candidate_harvest(app, read_run, run, candidates):
    """Refresh file bookkeeping on explicit re-evaluation, before starting advice."""
    from zet.services.local_image_pipeline_policy import mutate_local_run_state

    root = Path(run["root"]).resolve()
    with file_lock(root / "state.lock"):
        current = read_run()
        recovered = {}
        for candidate in candidates:
            saved = _current_candidate(current, candidate)
            image = Path(str(saved.get("image_path") or "")).resolve()
            if not image.is_relative_to(root):
                raise ValueError("Harvested image is outside its candidate batch")
            evidence = require_candidate_harvest(app, current, saved)
            if (saved.get("image_sha256") != evidence["sha256"]
                    or saved.get("status") in {"PENDING", "QUEUED", "RUNNING", "FAILED"}):
                recovered[saved["candidate_id"]] = evidence["sha256"]
        if recovered:
            def commit(state):
                for candidate_id, digest in recovered.items():
                    saved = state.setdefault("candidates", {}).setdefault(candidate_id, {})
                    saved["image_sha256"] = digest
                    if saved.get("status") in {"PENDING", "QUEUED", "RUNNING", "FAILED"}:
                        saved.update(status="WAITING_FOR_HUMAN_REVIEW", render_error="")
            mutate_local_run_state(root, commit)
        return read_run()


@contextmanager
def candidate_admission(app, read_run, run, candidates):
    """Recheck under the run lock while the immutable analysis request is published."""
    with file_lock(Path(run["root"]) / "state.lock"):
        current = read_run()
        if current.get("front_anchor") != run.get("front_anchor"):
            raise ValueError("Image analysis anchor changed before publication")
        for candidate in candidates:
            require_candidate_harvest(app, current, candidate)
            view = candidate["view"]
            previous = (run.get("evaluations") or {}).get(view, {})
            active = (current.get("evaluations") or {}).get(view, {})
            if previous.get("evaluation_id") != active.get("evaluation_id") or active.get("status") == "SUPERSEDED":
                raise ValueError("Image evaluation changed before publication")
        yield
