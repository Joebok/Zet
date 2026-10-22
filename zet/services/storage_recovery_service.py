"""Recurring backend recovery shared by dashboard and standalone harvesting."""
from __future__ import annotations
import logging
from pathlib import Path
import time

from zet.services.storage_health_service import storage_health
from zet.services.workflow_storage import file_lock


def submit_recovered_run(adapter, run_id, root, **options):
    """Recheck intent when the executor actually starts, including competing hosts."""
    from zet.services.local_character_overview_service import submit_local_pipeline_task
    def resume():
        try:
            with file_lock(Path(root) / "runner.lock", timeout=0):
                kwargs = {"costume": options["costume"]} if "costume" in options else {}
                latest = adapter.detail(run_id, **kwargs)
                if latest.get("stop_requested") or latest.get("status") not in {"QUEUED", "INTERRUPTED", "PAUSED_STORAGE", "RECOVERING"}:
                    return
                adapter.execute_run(run_id, **options)
        except TimeoutError:
            return
    return submit_local_pipeline_task(resume)


class StorageRecoveryService:
    def __init__(self, app):
        self.app = app
        self.health = storage_health(app.config)
        self._last = 0.0

    def recover(self):
        try:
            with file_lock(self.health.journal.parent / "workflow-recovery.lock", timeout=0):
                self._recover_locked()
        except TimeoutError:
            return

    def _recover_locked(self):
        if time.monotonic() - self._last < 10:
            return
        self.health.require()
        self._last = time.monotonic()
        from zet.services.local_character_overview_service import LocalCharacterOverviewService
        from zet.services.local_run_all_remaining_service import LocalRunAllRemainingService
        project = Path(__file__).resolve().parents[2]
        LocalCharacterOverviewService(self.app, project).recover()
        LocalRunAllRemainingService(self.app, project).recover()
        # Normal batches do not need an active Run All Remaining campaign.
        from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
        for pipeline in ("body-reference", "head-image", "head-image-edit", "character-assembly", "costume-dressing"):
            workflow = LocalImagePipelineWorkflowService(self.app, project, pipeline)
            adapter = workflow.adapter
            for summary in adapter.list_runs():
                run_id = summary.get("run_id")
                kwargs = {"costume": summary.get("costume") or ""} if pipeline in {"character-assembly", "costume-dressing"} else {}
                try:
                    run = adapter.detail(run_id, **kwargs)
                    if run.get("stop_requested") or run.get("status") in {"CANCELLED", "STOPPED", "COMPLETE"}:
                        continue
                    if run.get("slot_render_ids") or run.get("slot_review_views"):
                        workflow.slots.start(run_id, kwargs.get("costume", ""))
                    if run.get("status") not in {"INTERRUPTED", "PAUSED_STORAGE", "RECOVERING"}:
                        continue
                    root = Path(run["root"])
                    # Probe the actual cross-process lease, not another process's active set.
                    with file_lock(root / "runner.lock", timeout=0):
                        run = adapter.detail(run_id, **kwargs)
                        if run.get("stop_requested"):
                            continue
                        targets = set(run.get("target_candidate_ids") or [])
                        views = set(run.get("target_views") or [])
                        state = adapter._read_json(root / "state.json") if pipeline == "body-reference" else (
                            adapter._read_json(root / "state.json") if pipeline in {"head-image", "head-image-edit"} else adapter._read(root / "state.json"))
                        # Preserve a review-only operation; do not turn it into generation.
                        state.update(status="QUEUED", error="")
                        if pipeline == "body-reference":
                            adapter._save_state(run_id, state)
                        else:
                            adapter._write(root / "state.json", state)
                    submit_recovered_run(adapter, run_id, root,
                        views=views or None, candidate_ids=targets or None, render_only=bool(state.get("recovery_render_only")), **kwargs)
                except TimeoutError:
                    continue
                except Exception as exc:
                    if self.health.check_error(exc):
                        return
                    logging.getLogger(__name__).exception("Unable to recover %s batch %s", pipeline, run_id)
