from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService


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

    for pipeline in ("character-assembly", "costume-dressing"):
        prefix = f"/api/local/{pipeline}"

        @router.post(f"{prefix}/preview")
        def preview(payload: dict[str, Any] = Body(...), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).preview(payload))

        @router.post(f"{prefix}/runs")
        def create_run(payload: dict[str, Any] = Body(...), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).create_run(payload))

        @router.get(f"{prefix}/runs")
        def list_runs(character: str = Query(""), phase: str = Query(""), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: {"runs": service(_pipeline).list_runs(character, phase, costume)})

        @router.put(f"{prefix}/runs/{{run_id}}/name")
        def rename_run(run_id: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).rename_run(run_id, str(payload.get("batch_name") or ""), costume), missing=404)

        @router.get(f"{prefix}/runs/{{run_id}}")
        def detail(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).detail(run_id, costume, upgrade_legacy=True), missing=404)

        @router.post(f"{prefix}/runs/{{run_id}}/start")
        def start(run_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            current = call(lambda: service(_pipeline).detail(run_id, costume), missing=404)
            if current.get("status") != "QUEUED":
                raise HTTPException(status_code=409, detail="Only a queued local image batch can be started.")
            background_tasks.add_task(service(_pipeline).execute_run, run_id, costume=costume)
            return {"started": True, "run_id": run_id}

        @router.post(f"{prefix}/runs/{{run_id}}/rerun")
        def rerun(run_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.rerun(run_id, costume))
            background_tasks.add_task(instance.execute_run, run_id, costume=costume)
            return result

        @router.get(f"{prefix}/runs/{{run_id}}/images/{{candidate_id}}")
        def image(run_id: str, candidate_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            path = call(lambda: service(_pipeline).image_path(run_id, candidate_id, costume), missing=404)
            return FileResponse(path)

        @router.get(f"{prefix}/runs/{{run_id}}/sources/{{view}}/{{role}}")
        def source(run_id: str, view: str, role: str, costume: str = Query(""), _pipeline: str = pipeline):
            path = call(lambda: service(_pipeline).source_path(run_id, view, role, costume), missing=404)
            return FileResponse(path)

        @router.get(f"{prefix}/runs/{{run_id}}/image-prompt/{{view}}", response_class=PlainTextResponse)
        def image_prompt(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return PlainTextResponse(call(lambda: service(_pipeline).image_prompt(run_id, view, costume), missing=404), media_type="text/markdown")

        @router.get(f"{prefix}/runs/{{run_id}}/review-spec/{{view}}", response_class=PlainTextResponse)
        def review_specification(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return PlainTextResponse(call(lambda: service(_pipeline).review_specification(run_id, view, costume), missing=404), media_type="text/markdown")

        @router.get(f"{prefix}/runs/{{run_id}}/views/{{view}}/gates/{{gate}}/prompt", response_class=PlainTextResponse)
        def gate_prompt(run_id: str, view: str, gate: str, costume: str = Query(""), _pipeline: str = pipeline):
            return PlainTextResponse(call(lambda: service(_pipeline).gate_prompt(run_id, view, gate, costume), missing=404), media_type="text/markdown")

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/select")
        def select(run_id: str, view: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).select_view(run_id, view, str(payload.get("candidate_id") or ""), costume))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/rank")
        def rank(run_id: str, view: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            background_tasks.add_task(instance.rank_view, run_id, view, costume)
            return {"queued": True, "run_id": run_id, "view": view.upper()}

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/ranking/move")
        def move_rank(run_id: str, view: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).move_rank(run_id, view, str(payload.get("candidate_id") or ""), str(payload.get("direction") or ""), costume))

        @router.post(f"{prefix}/runs/{{run_id}}/rerun-failed")
        def rerun_failed(run_id: str, background_tasks: BackgroundTasks, view: str = Query(""), costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.rerun_failed_view(run_id, view, costume))
            background_tasks.add_task(instance.execute_run, run_id, views={view.upper()}, costume=costume)
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/reevaluate")
        def reevaluate(run_id: str, background_tasks: BackgroundTasks, view: str = Query(""), costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.reevaluate(run_id, view.strip() or None, costume))
            background_tasks.add_task(instance.execute_run, run_id, views={view.upper()} if view else None, costume=costume)
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/lock")
        def lock(run_id: str, view: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).lock_selected_view(run_id, view, costume))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/unlock")
        def unlock(run_id: str, view: str, character: str = Query(...), phase: str = Query(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).unlock_view(character, phase, view, costume))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/proceed")
        def proceed(run_id: str, view: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.proceed(run_id, costume))
            target_views = set(result.get("target_views") or [])
            if target_views:
                background_tasks.add_task(instance.execute_run, run_id, views=target_views, costume=costume)
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/candidates/{{candidate_id}}/review")
        def review(run_id: str, candidate_id: str, payload: dict[str, Any] = Body(...), costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).update_candidate(run_id, candidate_id, payload, costume))

        @router.post(f"{prefix}/runs/{{run_id}}/candidates/{{candidate_id}}/retry")
        def retry(run_id: str, candidate_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.retry_candidate(run_id, candidate_id, costume))
            background_tasks.add_task(instance.execute_run, run_id, views={next(item["view"] for item in result["candidates"] if item["candidate_id"] == candidate_id)}, costume=costume)
            return result

        @router.post(f"{prefix}/runs/{{run_id}}/stop")
        def stop(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).request_stop(run_id, costume))

        @router.post(f"{prefix}/runs/{{run_id}}/views/{{view}}/rerun")
        def rerun_view(run_id: str, view: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.rerun_view(run_id, view, costume))
            background_tasks.add_task(instance.execute_run, run_id, views={view.upper()}, costume=costume)
            return result

        @router.delete(f"{prefix}/runs/{{run_id}}")
        def delete_run(run_id: str, costume: str = Query(""), _pipeline: str = pipeline):
            return call(lambda: service(_pipeline).delete_run(run_id, costume))

        @router.post(f"{prefix}/runs/{{run_id}}/resume")
        def resume(run_id: str, background_tasks: BackgroundTasks, costume: str = Query(""), _pipeline: str = pipeline):
            instance = service(_pipeline)
            result = call(lambda: instance.resume(run_id, costume))
            background_tasks.add_task(instance.execute_run, run_id, costume=costume)
            return result

    return router
