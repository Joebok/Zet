"""Validate storage health for the retired character batch workflow boundary."""
from __future__ import annotations

import time

from zet.services.storage_health_service import storage_health
from zet.services.workflow_storage import file_lock


def submit_recovered_run(adapter, run_id, root, **options):
    """Legacy operation-handler handoff retained for rollback; never scheduled at startup."""
    from pathlib import Path
    from zet.services.local_task_executor_service import submit_local_pipeline_task

    def resume():
        try:
            with file_lock(Path(root) / "runner.lock", timeout=0):
                kwargs = {"costume": options["costume"]} if "costume" in options else {}
                latest = adapter.detail(run_id, **kwargs)
                if (latest.get("stop_requested") or latest.get("slot_paused")
                        or latest.get("status") not in {"QUEUED", "INTERRUPTED", "PAUSED_STORAGE", "RECOVERING"}):
                    return
                adapter.execute_run(run_id, **options)
        except TimeoutError:
            return

    return submit_local_pipeline_task(resume)


class StorageRecoveryService:
    """Keep the shared recovery hook without resuming legacy character batches."""

    def __init__(self, app):
        self.app = app
        self.health = storage_health(app.config)
        self._last = 0.0

    def recover(self):
        try:
            with file_lock(self.health.journal.parent / "workflow-recovery.lock", timeout=0):
                if time.monotonic() - self._last < 10:
                    return
                self.health.require()
                self._last = time.monotonic()
        except TimeoutError:
            return
