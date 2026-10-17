"""Admission barrier for image-based local pipeline advice."""
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
            or current.get("image_sha256") != candidate.get("image_sha256")
            or current.get("image_path") != candidate.get("image_path")):
        raise ValueError("Image candidate was replaced before analysis")
    return current


def require_candidate_harvest(app, run, candidate):
    current = _current_candidate(run, candidate)
    image = Path(str(current.get("image_path") or ""))
    if not current.get("image_sha256"):
        raise ValueError("Image candidate has not committed its harvested image state")
    return app.ai_proxy_service.ai_proxy_path_service.jobs.assert_image_harvest(
        str(current.get("ask_id") or ""), image, current["image_sha256"])


def reconcile_candidate_harvest(app, read_run, run, candidates, *, source_prefix):
    """Finish interrupted domain commits on explicit re-evaluation, before admission."""
    from zet.services.local_image_pipeline_policy import mutate_local_run_state

    root = Path(run["root"]).resolve()
    jobs = app.ai_proxy_service.ai_proxy_path_service.jobs
    with file_lock(root / "state.lock"):
        current = read_run()
        recovered = {}
        for candidate in candidates:
            saved = _current_candidate(current, candidate)
            if saved.get("image_sha256"):
                require_candidate_harvest(app, current, saved)
                continue
            image = Path(str(saved.get("image_path") or "")).resolve()
            if not image.is_relative_to(root):
                raise ValueError("Harvested image is outside its candidate batch")
            job_id = str(saved.get("ask_id") or "")
            jobs.validate_id(job_id)
            receipt = jobs.lifecycle.read_receipt(job_id)
            artifact = receipt.get("applied_artifact") or {}
            if not artifact.get("sha256"):
                # Older generic-harvester receipts lack artifact checksums. Bind
                # their successful application to the exact saved render attempt.
                record = jobs.repository.get(job_id)
                manifest = record.get("manifest") or {}
                source_id = (f"{source_prefix}_{current['run_id']}_{saved['candidate_id']}_"
                             f"{int(saved.get('retry_count') or 0)}")
                if (record.get("ask_id") != job_id or manifest.get("ask_id") != job_id
                        or manifest.get("source_ask_id") != source_id
                        or any(manifest.get(key) != current.get(key)
                               for key in ("universe_id", "character", "phase"))
                        or Path(str(manifest.get("target_output_file") or "")).name != image.name):
                    raise ValueError("Saved render request does not match the current image candidate")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            jobs.assert_image_harvest(job_id, image, digest)
            recovered[saved["candidate_id"]] = digest
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
