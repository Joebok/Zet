"""Common action boundary for local candidate-based image workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zet.services.local_body_reference_service import LocalBodyReferenceService
from zet.services.local_character_asset_pipeline_service import LocalCharacterAssetPipelineService
from zet.services.local_head_image_service import LocalHeadImageService
from zet.services.local_image_pipeline_policy import local_image_pipeline_config, pipeline_page_config
from zet.services.local_prompt_improvement_service import LocalPromptImprovementService
from zet.services.render_slot_service import CharacterRenderSlots, RenderSlotConflict


class LocalImageWorkflowError(ValueError):
    pass


class LocalImagePipelineWorkflowService:
    """Route shared workflow actions to a pipeline's rendering/reference adapter."""

    def __init__(self, app: Any, project_root: str | Path, pipeline: str):
        self.app = app
        self.project_root = Path(project_root)
        self.pipeline = str(pipeline).lower()
        self.pipeline_config = local_image_pipeline_config(self.pipeline)
        self.config = pipeline_page_config(self.pipeline)
        if self.pipeline_config.generation_adapter == "head-image":
            self.adapter = LocalHeadImageService(app, self.project_root)
        elif self.pipeline_config.generation_adapter == "body-reference":
            self.adapter = LocalBodyReferenceService(app, self.project_root)
        else:
            self.adapter = LocalCharacterAssetPipelineService(app, self.project_root, self.pipeline)
        self.prompt_improvement = LocalPromptImprovementService(self.adapter, self.pipeline, self.project_root)
        self.slots = CharacterRenderSlots(self)

    def action(self, name: str, **args: Any) -> dict[str, Any] | list[dict[str, Any]]:
        """Call a stable action name while preserving adapter-specific render details."""
        run_id = str(args.get("run_id") or "")
        view = str(args.get("view") or "")
        candidate_id = str(args.get("candidate_id") or "")
        costume = str(args.get("costume") or "")
        payload = args.get("payload") or {}
        direction = str(args.get("direction") or "")
        if name in {"rerun_batch", "rerun_view", "rerun_failed", "reevaluate", "run_unstarted_views", "delete_batch"}:
            current = self.prompt_improvement.detail(run_id, costume)
            if current.get("slot_work_pending") or current.get("slot_render_ids"):
                raise RenderSlotConflict("Wait for submitted slot renders to start and finish.")
        if name == "preview":
            return self.adapter.preview(payload)
        if name == "create":
            created = self.adapter.create_run(payload)
            return self.prompt_improvement.detail(str(created.get("run_id") or ""), costume)
        if name == "detail":
            return self.slots.detail(self.prompt_improvement.detail(run_id, costume))
        if name in {"generate_slots", "clear_slot", "regenerate_slot", "retry_render_slot"}:
            operation = {"generate_slots": "generate", "clear_slot": "clear", "regenerate_slot": "regenerate", "retry_render_slot": "retry"}[name]
            return self.slots.change(run_id, view, operation, payload, costume)
        if name == "list":
            return self.adapter.list_run_summaries(str(args.get("character") or ""), str(args.get("phase") or ""), costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.list_run_summaries(str(args.get("character") or ""), str(args.get("phase") or ""))
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
            recompile = bool(args.get("recompile", False))
            if self.pipeline == "costume-dressing":
                result = self.adapter.rerun(run_id, costume,
                                            refresh_sources=bool(args.get("refresh_sources", True)) or recompile,
                                            recompile=recompile)
            elif self.pipeline == "character-assembly":
                result = self.adapter.rerun(run_id, costume,
                                            refresh_sources=bool(args.get("refresh_sources", True)) or recompile)
            elif self.pipeline == "body-reference":
                result = self.adapter.rerun(run_id, recompile=recompile)
            else:
                result = self.adapter.rerun(run_id)
            self.prompt_improvement.reset_after_rerender(run_id, set(result.get("views") or []), costume)
            return self.prompt_improvement.detail(run_id, costume)
        if name == "rerun_view":
            recompile = bool(args.get("recompile", False))
            if self.pipeline == "costume-dressing":
                result = self.adapter.rerun_view(run_id, view, costume,
                                                 refresh_sources=bool(args.get("refresh_sources", True)) or recompile,
                                                 recompile=recompile)
            elif self.pipeline == "character-assembly":
                result = self.adapter.rerun_view(run_id, view, costume,
                                                 refresh_sources=bool(args.get("refresh_sources", True)) or recompile)
            elif self.pipeline == "body-reference":
                result = self.adapter.rerun_view(run_id, view, recompile=recompile)
            else:
                result = self.adapter.rerun_view(run_id, view)
            self.prompt_improvement.reset_after_rerender(run_id, {view.upper()}, costume)
            return self.prompt_improvement.detail(run_id, costume)
        if name == "rerun_failed":
            method = self.adapter.rerun_failed_view if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.rerun_failed_view
            result = method(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, view)
            affected = {view.upper()} if view else set(result.get("views") or [])
            self.prompt_improvement.reset_after_rerender(run_id, affected, costume)
            return self.prompt_improvement.detail(run_id, costume)
        if name == "reevaluate":
            return self.reevaluate(run_id, view, costume=costume)
        if name == "rank":
            return self.adapter.stage_view_evaluation(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.stage_view_evaluation(run_id, view)
        if name == "move_rank":
            if self.pipeline in {"head-image", "body-reference"}:
                return self.adapter.move_candidate_rank(run_id, view, candidate_id, direction)
            return self.adapter.move_rank(run_id, view, candidate_id, direction, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.move_rank(run_id, view, candidate_id, direction)
        if name == "review_candidate":
            method = self.adapter.update_candidate
            return method(run_id, candidate_id, payload, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, candidate_id, payload)
        if name == "save_observations":
            return self.prompt_improvement.save_observations(run_id, view, payload.get("observations"), costume)
        if name == "reanalyze":
            return self.prompt_improvement.start(run_id, view, costume)
        if name in {"select_view", "unselect_view"}:
            selected_id = candidate_id if name == "select_view" else ""
            method = self.adapter.select_view
            result = method(run_id, view, selected_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else method(run_id, view, selected_id)
            if view.upper() == "FRONT" and selected_id:
                from zet.services.local_run_all_remaining_service import LocalRunAllRemainingService
                LocalRunAllRemainingService(self.app, self.project_root).front_selection_changed(
                    self.pipeline, run_id, costume if self.pipeline == "costume-dressing" else "")
            return result
        if name == "select_front_anchor":
            if self.pipeline == "body-reference":
                return self.adapter.select_front_anchor(run_id, candidate_id)
            return self.action("select_view", run_id=run_id, view="FRONT", candidate_id=candidate_id, costume=costume)
        if name == "run_unstarted_views":
            return self.adapter.proceed(run_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.proceed(run_id)
        if name == "lock_view":
            return self.adapter.lock_selected_view(run_id, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.lock_selected_view(run_id, view)
        if name == "lock_preview":
            return self.adapter.lock_preview(run_id, view, costume)
        if name == "unlock_view":
            character, phase = str(args.get("character") or ""), str(args.get("phase") or "")
            return self.adapter.unlock_view(character, phase, view, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.unlock_view(character, phase, view)
        if name == "retry_candidate":
            result = self.adapter.retry_candidate(run_id, candidate_id, costume) if self.pipeline in {"character-assembly", "costume-dressing"} else self.adapter.retry_candidate(run_id, candidate_id)
            candidate = next((item for item in result.get("candidates") or []
                              if item.get("candidate_id") == candidate_id), {})
            self.prompt_improvement.reset_after_rerender(run_id, {str(candidate.get("view") or "")}, costume)
            return self.prompt_improvement.detail(run_id, costume)
        raise LocalImageWorkflowError(f"Unsupported local image workflow action: {name}")

    def execute(self, run_id: str, *, views: set[str] | None = None, costume: str = "",
                candidate_ids: set[str] | None = None, render_only: bool = False) -> None:
        if self.pipeline in {"character-assembly", "costume-dressing"}:
            self.adapter.execute_run(run_id, views=views, costume=costume,
                                     candidate_ids=candidate_ids, render_only=render_only)
        else:
            self.adapter.execute_run(run_id, views=views, candidate_ids=candidate_ids,
                                     render_only=render_only)

    def reevaluate(self, run_id: str, view: str = "", *, costume: str = "") -> dict[str, Any]:
        """Refresh ranking and prompt observations using existing harvested images."""
        from zet.services.image_harvest_service import require_candidate_harvest
        from zet.services.local_image_pipeline_policy import ACTIVE_RUN_STATUSES

        run = self.prompt_improvement.detail(run_id, costume)
        if run.get("status") in ACTIVE_RUN_STATUSES or run.get("slot_work_pending") or run.get("slot_render_ids"):
            raise LocalImageWorkflowError("Wait for current renders to finish before re-evaluating.")
        if run.get("stop_requested") or run.get("status") in {"CANCELLED", "STOPPED"}:
            raise LocalImageWorkflowError("Resume the stopped batch before re-evaluating.")
        view = str(view or "").strip().upper()
        if view and view not in run.get("views", []):
            raise LocalImageWorkflowError(f"Unknown local batch view: {view}")
        images = [item for item in run.get("candidates", [])
                  if (not view or item["view"] == view)
                  and Path(str(item.get("image_path") or "")).is_file()]
        targets = [target for target in run.get("views", []) if any(item["view"] == target for item in images)]
        if not targets:
            raise LocalImageWorkflowError("No rendered images are available to re-evaluate.")
        requires_anchor = self.pipeline in {"body-reference", "head-image"} or bool(run.get("use_front_anchor"))
        if requires_anchor and any(target != "FRONT" for target in targets):
            anchor = next((item for item in run["candidates"] if item["candidate_id"] == run.get("front_anchor")), {})
            if not Path(str(anchor.get("image_path") or "")).is_file():
                raise LocalImageWorkflowError("Select a completed FRONT anchor before re-evaluating other views.")
        qualifier = self.adapter._qualifier(costume) if self.pipeline == "costume-dressing" else ""
        for target in targets:
            self.adapter.asset_store.assert_batch_change_allowed(
                run["character"], run["phase"], self.pipeline_config.label, target, qualifier)
        for candidate in images:
            require_candidate_harvest(self.app, run, candidate)
        for target in targets:
            self.prompt_improvement.start(run_id, target, costume)
            self.stage_view_evaluation(run_id, target, costume=costume)
        return self.action("detail", run_id=run_id, costume=costume)

    def stage_view_evaluation(self, run_id: str, view: str, *, costume: str = "",
                              candidate_ids: set[str] | None = None) -> dict[str, Any]:
        """Start advisory evaluation without taking the batch runner lock."""
        if self.pipeline in {"character-assembly", "costume-dressing"}:
            return self.adapter.stage_view_evaluation(run_id, view, costume, candidate_ids=candidate_ids)
        return self.adapter.stage_view_evaluation(run_id, view, candidate_ids=candidate_ids)

    def reconcile_review_jobs(self, run_id: str, *, costume: str = "") -> dict[str, Any]:
        """Resume persisted advisory jobs after a server restart."""
        if self.pipeline in {"character-assembly", "costume-dressing"}:
            return self.adapter.reconcile_review_jobs(run_id, costume)
        return self.adapter.reconcile_review_jobs(run_id)
