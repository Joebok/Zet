"""Admission barrier for image-based local pipeline advice."""
from pathlib import Path
from contextlib import contextmanager
from zet.services.workflow_storage import file_lock


def require_candidate_harvest(app, run, candidate):
    if run.get("stop_requested") or run.get("status") == "CANCELLED":
        raise ValueError("Image workflow has been stopped")
    current = next((item for item in run.get("candidates", [])
                    if item["candidate_id"] == candidate["candidate_id"]), None)
    if (not current or current.get("ask_id") != candidate.get("ask_id")
            or current.get("image_sha256") != candidate.get("image_sha256")
            or current.get("image_path") != candidate.get("image_path")):
        raise ValueError("Image candidate was replaced before analysis")
    image = Path(str(current.get("image_path") or ""))
    if not current.get("image_sha256"):
        raise ValueError("Image candidate has not committed its harvested image state")
    return app.ai_proxy_service.ai_proxy_path_service.jobs.assert_image_harvest(
        str(current.get("ask_id") or ""), image, current["image_sha256"])


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
