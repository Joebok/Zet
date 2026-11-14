"""Aggregate actionable local image batches for the dashboard status page."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
from zet.services.local_image_pipeline_policy import LOCAL_IMAGE_PIPELINES


PIPELINES = tuple(LOCAL_IMAGE_PIPELINES)
PIPELINE_LABELS = {key: LOCAL_IMAGE_PIPELINES[key].label for key in PIPELINES}

STATUS_GROUPS = (
    ("PAUSED_STORAGE", "Paused — storage unavailable"),
    ("RECOVERING", "Recovering"),
    ("READY_TO_PUBLISH", "Ready to publish"),
    ("INTERRUPTED", "Interrupted"),
    ("FAILED", "Failed / Error"),
    ("STOPPED", "Stopped / Cancelled"),
    ("AWAITING_FRONT_ANCHOR", "Awaiting FRONT anchor"),
    ("AWAITING_HUMAN_SELECTION", "Awaiting selection"),
    ("REVIEW_REQUIRED", "Review required"),
    ("READY_FOR_VIEWS", "Ready for other views"),
    ("RUNNING", "Running"),
    ("REEVALUATING", "Re-evaluating"),
    ("STOPPING", "Stopping"),
    ("PREFLIGHT", "Checking inputs"),
    ("QUEUED", "Queued"),
)
STATUS_GROUP_ORDER = {status: index for index, (status, _label) in enumerate(STATUS_GROUPS)}
ACTIONABLE_STATUSES = set(STATUS_GROUP_ORDER)


class LocalBatchStatusService:
    """Read current local pipeline summaries and project actionable batches."""

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root)

    def _adapter(self, pipeline: str) -> Any:
        return LocalImagePipelineWorkflowService(self.app, self.project_root, pipeline).adapter

    @staticmethod
    def _current_view(run: dict[str, Any]) -> str:
        summary_views = run.get("current_views") or []
        if summary_views:
            return ", ".join(str(view) for view in summary_views)
        active_views = sorted({
            str(candidate.get("view") or "")
            for candidate in run.get("candidates") or []
            if candidate.get("status") == "RUNNING" and candidate.get("view")
        })
        if active_views:
            return ", ".join(active_views)
        target_views = list(dict.fromkeys(
            str(view) for view in run.get("target_views") or [] if view
        ))
        return ", ".join(target_views)

    def list_actionable_batches(self) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = {status: [] for status in STATUS_GROUP_ORDER}
        for pipeline in PIPELINES:
            adapter = self._adapter(pipeline)
            costume_pipeline = pipeline in {"character-assembly", "costume-dressing"}
            summaries = adapter.list_run_summaries()
            mode_summaries = []
            for summary in summaries:
                modes = summary.get("progress_by_mode") or {}
                if not modes:
                    mode_summaries.append({**summary, "render_mode": "draft"})
                    continue
                for mode, progress in modes.items():
                    status = progress.get("status") or "NOT_STARTED"
                    if mode == "draft" and summary.get("status") in {"PAUSED_STORAGE", "RECOVERING", "INTERRUPTED", "STOPPED", "CANCELLED", "REVIEW_REQUIRED"}:
                        status = summary["status"]
                    mode_summaries.append({**summary, "render_mode": mode, "status": status,
                                           "current_views": progress.get("current_views") or []})
            for summary in mode_summaries:
                status = str(summary.get("status") or "UNKNOWN").upper()
                if status in {"ERROR", "FAILED"}:
                    group_status = "FAILED"
                elif status in {"STOPPED", "CANCELLED"}:
                    group_status = "STOPPED"
                else:
                    group_status = status
                if group_status not in ACTIONABLE_STATUSES:
                    continue

                costume = str(summary.get("costume") or "") if costume_pipeline else ""
                current_view = self._current_view(summary) if group_status in {
                    "RUNNING", "REEVALUATING", "STOPPING", "PREFLIGHT"
                } else ""

                groups[group_status].append({
                    "pipeline": pipeline,
                    "render_mode": summary.get("render_mode", "draft"),
                    "pipeline_label": PIPELINE_LABELS[pipeline],
                    "run_id": str(summary.get("run_id") or ""),
                    "batch_name": str(summary.get("batch_name") or "").strip(),
                    "character": str(summary.get("character") or ""),
                    "phase": str(summary.get("phase") or ""),
                    "costume": costume,
                    "created_at": str(summary.get("created_at") or ""),
                    "status": group_status,
                    "status_label": next(label for key, label in STATUS_GROUPS if key == group_status),
                    "current_view": current_view,
                })

        scenes = getattr(self.app, "local_scene_batch_service", None)
        if scenes is not None:
            from urllib.parse import urlencode
            for batch in scenes.summaries():
                status = batch["status"]
                if status not in groups:
                    continue
                groups[status].append({"pipeline": "scene", "pipeline_label": "Scene", "run_id": batch["run_id"],
                    "batch_name": str(batch.get("batch_name") or "").strip(), "character": "", "phase": "", "costume": "",
                    "story_slug": batch["story_slug"], "scene_slug": batch["scene_slug"],
                    "render_target_id": batch["render_target_id"], "current_view": batch["target_label"],
                    "created_at": batch["created_at"], "status": status,
                    "status_label": dict(STATUS_GROUPS)[status], "href": "/?" + urlencode({"page": "scene-batches",
                        "story_slug": batch["story_slug"], "scene_slug": batch["scene_slug"],
                        "render_target_id": batch["render_target_id"], "batch": batch["run_id"]})})
        result = []
        for status, label in STATUS_GROUPS:
            batches = groups[status]
            if not batches:
                continue
            batches.sort(key=lambda item: (item["created_at"], item["run_id"]), reverse=True)
            result.append({"status": status, "label": label, "batches": batches})
        return {"groups": result, "batch_count": sum(len(group["batches"]) for group in result)}
