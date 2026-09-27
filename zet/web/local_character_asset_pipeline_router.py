from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from starlette.background import BackgroundTask

from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
from zet.services.local_character_overview_service import submit_local_pipeline_task
from zet.services.local_batch_status_service import LocalBatchStatusService
from zet.services.local_run_all_remaining_service import LocalRunAllRemainingService


def create_local_character_asset_pipeline_router(
    app_factory: Callable[[str | Path], Any], project_root: str | Path,
) -> APIRouter:
    router = APIRouter()
    root = Path(project_root)

    def service(pipeline: str) -> LocalImagePipelineWorkflowService:
        return LocalImagePipelineWorkflowService(app_factory(), root, pipeline)

    def call(function, *, missing: int = 400):
        try:
            return function()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=missing, detail=str(exc)) from exc

    def run_all_service() -> LocalRunAllRemainingService:
        return LocalRunAllRemainingService(app_factory(), root)

    def batch_status_service() -> LocalBatchStatusService:
        return LocalBatchStatusService(app_factory(), root)

    @router.get("/api/local/batch-status")
    def local_batch_status():
        return call(batch_status_service().list_actionable_batches)

    @router.post("/api/local/run-all-remaining")
    def start_run_all_remaining():
        return call(run_all_service().start)

    @router.get("/api/local/run-all-remaining/{campaign_id}")
    def run_all_remaining_status(campaign_id: str):
        return call(lambda: run_all_service().status(campaign_id), missing=404)

    @router.post("/api/local/head-image/sources")
    async def upload_head_image_source(request: Request, filename: str = Query(...),
                                       character: str = Query(...), phase: str = Query(...)):
        request_body = await request.body()
        return call(lambda: service("head-image").adapter.upload_source(
            character, phase, filename, request_body
        ))

    for pipeline in ("body-reference", "head-image", "character-assembly", "costume-dressing"):
        prefix = f"/api/local/{pipeline}"
        shared_sources = pipeline in {"character-assembly", "costume-dressing"}

        def action(_pipeline: str, name: str, **args: Any):
            return service(_pipeline).action(name, **args)

        @router.post(f"{prefix}/preview")
        def preview(payload: dict[str, Any] = Body(...), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "preview", payload=payload))

        @router.post(f"{prefix}/runs")
        def create_run(payload: dict[str, Any] = Body(...), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "create", payload=payload))

        @router.get(f"{prefix}/runs")
        def list_runs(character: str = Query(""), phase: str = Query(""), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: {"runs": action(_pipeline, "list", character=character, phase=phase, costume=costume if _pipeline == "costume-dressing" else "")})

        @router.put(f"{prefix}/runs/{{run_id}}/name")
        def rename_run(run_id: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "rename_batch", run_id=run_id, payload=payload, costume=costume if _pipeline == "costume-dressing" else ""), missing=404)

        @router.get(f"{prefix}/runs/{{run_id}}")
        def detail(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "detail", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else ""), missing=404)

        @router.post(f"{prefix}/runs/{{run_id}}/start")
        def start(run_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            current = call(lambda: action(_pipeline, "detail", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else ""), missing=404)
            if current.get("status") != "QUEUED":
                raise HTTPException(status_code=409, detail="Only a queued local image batch can be started.")
            instance = service(_pipeline)
            submit_local_pipeline_task(instance.execute, run_id, costume=costume if _pipeline == "costume-dressing" else "")
            return {"started": True, "run_id": run_id}

        @router.post(f"{prefix}/runs/{{run_id}}/rerun")
        def rerun(run_id: str, background_tasks: BackgroundTasks, payload: dict[str, Any] = Body(default={}), costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("rerun_batch", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else "", refresh_sources=payload.get("refresh_sources", True)))
            submit_local_pipeline_task(instance.execute, run_id, costume=costume if _pipeline == "costume-dressing" else "")
            return result

        @router.get(f"{prefix}/runs/{{run_id}}/images/{{candidate_id}}")
        def image(run_id: str, candidate_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            path = call(lambda: service(_pipeline).adapter.image_path(run_id, candidate_id, **({"costume": costume} if _pipeline == "costume-dressing" else {})), missing=404)
            return FileResponse(path)

        @router.get(f"{prefix}/runs/{{run_id}}/reference-images/{{view}}/{{index}}")
        def reference_image(run_id: str, view: str, index: int, costume: str = Query(""), _pipeline: str = pipeline):
            def resolve_reference():
                adapter = service(_pipeline).adapter
                run = adapter.detail(run_id, **({"costume": costume} if _pipeline == "costume-dressing" else {}))
                references = []
                seen = set()
                for candidate in run.get("candidates", []):
                    if str(candidate.get("view") or "").upper() != view.upper():
                        continue
                    for reference in candidate.get("reference_images", []):
                        path = str(reference.get("path") or "")
                        key = (str(reference.get("role") or ""), path)
                        if path and key not in seen:
                            seen.add(key)
                            references.append(reference)
                if index < 0 or index >= len(references):
                    raise FileNotFoundError("Reference image is unavailable.")
                path = Path(str(references[index].get("path") or "")).resolve()
                if not path.is_file():
                    raise FileNotFoundError("Reference image is unavailable.")
                return path
            path = call(resolve_reference, missing=404)
            return FileResponse(path)

        if shared_sources:
            @router.get(f"{prefix}/runs/{{run_id}}/sources/{{view}}/{{role}}")
            def source(run_id: str, view: str, role: str, costume: str = Query(""), _pipeline: str = pipeline):
                path = call(lambda: service(_pipeline).adapter.source_path(run_id, view, role, costume), missing=404)
                return FileResponse(path)
        elif pipeline == "head-image":
            @router.get(f"{prefix}/runs/{{run_id}}/source")
            def front_source(run_id: str, _pipeline: str = pipeline):
                path = call(lambda: service(_pipeline).adapter.front_source_path(run_id), missing=404)
                return FileResponse(path)

            @router.put(f"{prefix}/runs/{{run_id}}/source")
            def update_front_source(run_id: str, payload: dict[str, Any] = Body(...), _pipeline: str = pipeline):
                call(lambda: service(_pipeline).adapter.update_front_source(
                    run_id, str(payload.get("source_path") or "")))
                return call(lambda: service(_pipeline).prompt_improvement.detail(run_id))

        @router.get(f"{prefix}/runs/{{run_id}}/image-prompt/{{view}}", response_class=PlainTextResponse)
        def image_prompt(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return PlainTextResponse(call(lambda: service(_pipeline).adapter.image_prompt(run_id, view, **({"costume": costume} if _pipeline == "costume-dressing" else {})), missing=404), media_type="text/markdown")

        @router.get(f"{prefix}/runs/{{run_id}}/review-spec/{{view}}", response_class=PlainTextResponse)
        def review_specification(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            method = "review_prompt" if _pipeline in {"body-reference", "head-image"} else "review_specification"
            return PlainTextResponse(call(lambda: getattr(service(_pipeline).adapter, method)(run_id, view, **({"costume": costume} if _pipeline == "costume-dressing" else {})), missing=404), media_type="text/markdown")

        @router.get(f"{prefix}/runs/{{run_id}}/views/{{view}}/gates/{{gate}}/prompt", response_class=PlainTextResponse)
        def gate_prompt(run_id: str, view: str, gate: str, costume: str = Query(""), _pipeline: str = pipeline):
            return PlainTextResponse(call(lambda: service(_pipeline).adapter.gate_prompt(run_id, view, gate, **({"costume": costume} if _pipeline == "costume-dressing" else {})), missing=404), media_type="text/markdown")

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/select")
        def select(run_id: str, view: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "select_view", run_id=run_id, view=view, candidate_id=str(payload.get("candidate_id") or ""), costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/rank")
        def rank(run_id: str, view: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            submit_local_pipeline_task(instance.action, "rank", run_id=run_id, view=view, costume=costume if _pipeline == "costume-dressing" else "")
            return {"queued": True, "run_id": run_id, "view": view.upper()}

        @router.put(f"{prefix}/runs/{{run_id}}/views/{{view}}/observations")
        def save_observations(run_id: str, view: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "save_observations", run_id=run_id, view=view, payload=payload,
                                       costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/reanalyze")
        def reanalyze(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "reanalyze", run_id=run_id, view=view,
                                       costume=costume if _pipeline == "costume-dressing" else ""))

        @router.get(f"{prefix}/runs/{{run_id}}/prompt-improvement-package")
        def prompt_improvement_package(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            path = call(lambda: service(_pipeline).prompt_improvement.create_package(
                run_id, costume if _pipeline == "costume-dressing" else ""), missing=404)
            return FileResponse(path, media_type="application/zip", filename=f"{_pipeline}_{run_id}_prompt_improvement.zip",
                                background=BackgroundTask(path.unlink, missing_ok=True))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/ranking/move")
        def move_rank(run_id: str, view: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "move_rank", run_id=run_id, view=view, candidate_id=str(payload.get("candidate_id") or ""), direction=str(payload.get("direction") or ""), costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/rerun-failed")
        def rerun_failed(run_id: str, background_tasks: BackgroundTasks, view: str = Query(""), costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("rerun_failed", run_id=run_id, view=view, costume=costume if _pipeline == "costume-dressing" else ""))
            submit_local_pipeline_task(instance.execute, run_id, views={view.upper()}, costume=costume if _pipeline == "costume-dressing" else "")
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/reevaluate")
        def reevaluate(run_id: str, background_tasks: BackgroundTasks, view: str = Query(""), costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("reevaluate", run_id=run_id, view=view.strip() or None, costume=costume if _pipeline == "costume-dressing" else ""))
            submit_local_pipeline_task(instance.execute, run_id, views={view.upper()} if view else None, costume=costume if _pipeline == "costume-dressing" else "")
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/lock")
        def lock(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "lock_view", run_id=run_id, view=view, costume=costume if _pipeline == "costume-dressing" else ""))

        @router.get(f"{prefix}/runs/{{run_id}}/views/{{view}}/lock-preview")
        def lock_preview(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "lock_preview", run_id=run_id, view=view, costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/unlock")
        def unlock(run_id: str, view: str, character: str = Query(...), phase: str = Query(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "unlock_view", character=character, phase=phase, view=view, costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/proceed")
        def proceed(run_id: str, view: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("run_unstarted_views", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else ""))
            target_views = set(result.get("target_views") or [])
            if target_views:
                submit_local_pipeline_task(instance.execute, run_id, views=target_views, costume=costume if _pipeline == "costume-dressing" else "")
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/candidates/{{candidate_id}}/review")
        def review(run_id: str, candidate_id: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "review_candidate", run_id=run_id, candidate_id=candidate_id, payload=payload, costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/candidates/{{candidate_id}}/retry")
        def retry(run_id: str, candidate_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("retry_candidate", run_id=run_id, candidate_id=candidate_id, costume=costume if _pipeline == "costume-dressing" else ""))
            submit_local_pipeline_task(instance.execute, run_id, views={next(item["view"] for item in result["candidates"] if item["candidate_id"] == candidate_id)}, costume=costume if _pipeline == "costume-dressing" else "")
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/stop")
        def stop(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "stop", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/rerun")
        def rerun_view(run_id: str, view: str, background_tasks: BackgroundTasks, payload: dict[str, Any] = Body(default={}), costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("rerun_view", run_id=run_id, view=view, costume=costume if _pipeline == "costume-dressing" else "", refresh_sources=payload.get("refresh_sources", True)))
            submit_local_pipeline_task(instance.execute, run_id, views={view.upper()}, costume=costume if _pipeline == "costume-dressing" else "")
            return result

        @router.delete(f"{prefix}/runs/{{run_id}}")
        def delete_run(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: action(_pipeline, "delete_batch", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else ""))

        @router.post(f"{prefix}/runs/{{run_id}}/resume")
        def resume(run_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.action("resume", run_id=run_id, costume=costume if _pipeline == "costume-dressing" else ""))
            if result.get("status") == "QUEUED":
                submit_local_pipeline_task(instance.execute, run_id, costume=costume if _pipeline == "costume-dressing" else "")
            return result

    return router
