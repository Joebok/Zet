"""Common action boundary for local candidate-based image workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zet.services.local_body_reference_service import LocalBodyReferenceService
from zet.services.local_character_asset_pipeline_service import LocalCharacterAssetPipelineService
from zet.services.local_head_image_service import LocalHeadImageService
from zet.services.local_image_pipeline_policy import pipeline_page_config


class LocalImageWorkflowError(ValueError):
    pass


class LocalImagePipelineWorkflowService:
    """Route shared workflow actions to a pipeline's rendering/reference adapter."""

    def __init__(self, app: Any, project_root: str | Path, pipeline: str):
        self.app = app
        self.project_root = Path(project_root)
        self.pipeline = str(pipeline).lower()
        self.config = pipeline_page_config(self.pipeline)
        if self.pipeline == "head-image":
            self.adapter = LocalHeadImageService(app, self.project_root)
        elif self.pipeline == "body-reference":
            self.adapter = LocalBodyReferenceService(app, self.project_root)
        else:
            self.adapter = LocalCharacterAssetPipelineService(app, self.project_root, self.pipeline)

    def action(self, name: str, **args: Any) -> dict[str, Any] | list[dict[str, Any]]:
        """Call a stable action name while preserving adapter-specific render details."""
        run_id = str(args.get("run_id") or "")
        view = str(args.get("view") or "")
        candidate_id = str(args.get("candidate_id") or "")
        costume = str(args.get("costume") or "")
        payload = args.get("payload") or {}
        direction = str(args.get("direction") or "")
        if name == "preview":
            return self.adapter.preview(payload)
        if name == "create":
            return self.adapter.create_run(payload)
        if name == "detail":
            if self.pipeline in {"body-reference", "character-assembly", "costume-dressing"}:
                return self.adapter.detail(run_id, upgrade_legacy=True, **({"costume": costume} if self.pipeline in {"character-assembly", "costume-dressing"} else {}))
            return self.adapter.detail(run_id)
        if name == "list":
            return self.adapter.list_runs(str(args.get("character") or ""), str(args.get("phase") or ""), costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.list_runs(str(args.get("character") or ""), str(args.get("phase") or ""))
        if name == "rename_batch":
            return self.adapter.rename_run(run_id, str(payload.get("batch_name") or ""), costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.rename_run(run_id, str(payload.get("batch_name") or ""))
        if name == "delete_batch":
            return self.adapter.delete_run(run_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.delete_run(run_id)
        if name == "start":
            current = self.action("detail", run_id=run_id, costume=costume)
            if current.get("status") != "QUEUED":
                raise LocalImageWorkflowError("Only a queued local image batch can be started.")
            return {"started": True, "run_id": run_id}
        if name == "stop":
            return self.adapter.request_stop(run_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.request_stop(run_id)
        if name == "resume":
            return self.adapter.resume(run_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.resume(run_id)
        if name == "rerun_batch":
            return self.adapter.rerun(run_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.rerun(run_id)
        if name == "rerun_view":
            return self.adapter.rerun_view(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.rerun_view(run_id, view)
        if name == "rerun_failed":
            method = self.adapter.rerun_failed_view if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.rerun_failed_view
            return method(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, view)
        if name == "reevaluate":
            return self.adapter.reevaluate(run_id, view or None, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.reevaluate(run_id, view or None)
        if name == "rank":
            method = self.adapter.rank_view if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.rank_view
            return method(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, view)
        if name == "move_rank":
            if self.pipeline in {"head-image", "body-reference"}:
                return self.adapter.move_candidate_rank(run_id, view, candidate_id, direction)
            return self.adapter.move_rank(run_id, view, candidate_id, direction, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.move_rank(run_id, view, candidate_id, direction)
        if name == "review_candidate":
            method = self.adapter.update_candidate
            return method(run_id, candidate_id, payload, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, candidate_id, payload)
        if name in {"select_view", "unselect_view"}:
            selected_id = candidate_id if name == "select_view" else ""
            method = self.adapter.select_view
            return method(run_id, view, selected_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, view, selected_id)
        if name == "select_front_anchor":
            if self.pipeline == "body-reference":
                return self.adapter.select_front_anchor(run_id, candidate_id)
            return self.action("select_view", run_id=run_id, view="FRONT", candidate_id=candidate_id, costume=costume)
        if name == "run_unstarted_views":
            return self.adapter.proceed(run_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.proceed(run_id)
        if name == "lock_view":
            return self.adapter.lock_selected_view(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.lock_selected_view(run_id, view)
        if name == "unlock_view":
            character, phase = str(args.get("character") or ""), str(args.get("phase") or "")
            return self.adapter.unlock_view(character, phase, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.unlock_view(character, phase, view)
        if name == "retry_candidate":
            return self.adapter.retry_candidate(run_id, candidate_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.retry_candidate(run_id, candidate_id)
        raise LocalImageWorkflowError(f"Unsupported local image workflow action: {name}")

    def execute(self, run_id: str, *, views: set[str] | None = None, costume: str = "") -> None:
        if self.pipeline in {"character-assembly", "costume-dressing"}:
            self.adapter.execute_run(run_id, views=views, costume=costume)
        else:
            self.adapter.execute_run(run_id, views=views)
