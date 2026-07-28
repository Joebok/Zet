from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from zet.app import ZetApp
from zet.services.pipeline_control_service import AutomationSettings


def create_pipeline_controls_router(
    get_app: Callable[[], ZetApp],
    reload_app: Callable[[], ZetApp],
    payload_for: Callable[[ZetApp, str, str], dict[str, Any]],
    settings_from_payload: Callable[[dict[str, Any], AutomationSettings | None], AutomationSettings],
    jsonable: Callable[[Any], Any],
) -> APIRouter:
    router = APIRouter(prefix="/api/pipeline-controls")

    @router.get("")
    def pipeline_controls(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        try:
            return payload_for(get_app(), character, phase)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/automation")
    def save_automation(
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = get_app()
        try:
            defaults = zet_app.pipeline_control_service.automation_settings()
            zet_app.save_automation_settings(settings_from_payload(payload, defaults))
            response = payload_for(reload_app(), character, phase)
            response["message"] = "Project automation settings saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/batch-render-reset")
    def batch_render_reset(
        pipeline_name: str = Query(...),
        include_locked: bool = Query(False),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = get_app()
        try:
            results = zet_app.reset_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)
            response = payload_for(zet_app, character, phase)
            reset_count = sum(1 for result in results if result.status == "RESET")
            skipped_count = sum(1 for result in results if result.status == "SKIPPED")
            error_count = sum(1 for result in results if result.status == "ERROR")
            response["message"] = (
                f"Batch render reset complete for {pipeline_name}: "
                f"{reset_count} reset, {skipped_count} skipped, {error_count} error."
            )
            response["batch_results"] = jsonable(results)
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/batch-render-reset/preview")
    def batch_render_reset_preview(
        pipeline_name: str = Query(...),
        include_locked: bool = Query(False),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = get_app()
        try:
            results = zet_app.preview_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)
            affected_count = sum(1 for result in results if result.preview_status == "WOULD_RESET")
            skipped_count = sum(1 for result in results if result.preview_status == "SKIPPED")
            locked_count = sum(1 for result in results if result.previous_state == "LOCKED")
            return {
                "pipeline_name": pipeline_name,
                "include_locked": include_locked,
                "counts": {
                    "affected": affected_count,
                    "skipped": skipped_count,
                    "locked": locked_count,
                },
                "items": jsonable(results),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
