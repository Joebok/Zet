from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from zet.services.ad_hoc_image_generation_service import (
    AdHocImageGenerationError,
    AdHocImageGenerationService,
)
from zet.services.render_slot_service import RenderSlotConflict


def create_ad_hoc_image_generation_router(
    service_provider: Callable[[], AdHocImageGenerationService],
) -> APIRouter:
    router = APIRouter(prefix="/api/image-generation", tags=["image-generation"])

    @router.get("/assets")
    def assets():
        return {"assets": service_provider().slot_workspace.list_assets()}

    @router.post("/assets")
    def create_asset(payload: dict[str, Any] = Body(...)):
        try:
            return service_provider().slot_workspace.create_asset(
                payload.get("name"), payload.get("inputs"), payload.get("recovery_id"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/assets/{asset_id}")
    def asset_detail(asset_id: str):
        try:
            return service_provider().slot_workspace.asset(asset_id).detail()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/assets/{asset_id}/progress")
    def asset_progress(asset_id: str):
        try:
            return service_provider().slot_workspace.asset(asset_id).progress()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/assets/{asset_id}/{operation}")
    def asset_action(asset_id: str, operation: str, payload: dict[str, Any] = Body(default={})):
        service = service_provider()
        try:
            workspace = service.slot_workspace.asset(asset_id)
            if operation == "save":
                return workspace.update_asset(payload)
            bulk = operation.removesuffix("-preview")
            if bulk in {"delete-asset", "delete-drafts", "delete-non-selected"}:
                return workspace.bulk(bulk, payload, preview=operation.endswith("-preview"))
            if operation in {"inventory-add", "inventory-update"}:
                return workspace.publish(operation, payload)
            if operation == "analyze":
                return service.reconstruction.start_asset_analysis(workspace, payload)
            if operation == "compare":
                return service.reconstruction.start_comparison({**payload, "generation_asset_id": asset_id})
            if operation == "correct":
                return service.reconstruction.correct_selected({**payload, "generation_asset_id": asset_id})
            if operation in {"generate", "regenerate", "retry", "upscale", "select", "unselect", "clear", "cancel"}:
                if (operation != "generate" or "slot" in payload) and (
                        "slot" not in payload or "expected_assignment" not in payload):
                    raise ValueError("Provide the current slot and occupant.")
                return workspace.action(operation, payload)
            raise ValueError("Unknown asset action.")
        except RenderSlotConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/options")
    def options() -> dict[str, Any]:
        return service_provider().options()

    @router.get("/sizing")
    def sizing(render_mode: str = Query("draft"), aspect_ratio: str = Query("1:1")):
        try:
            return service_provider().sizing(render_mode, aspect_ratio)
        except AdHocImageGenerationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/reconstructions/options")
    def reconstruction_options():
        return service_provider().reconstruction.options()

    @router.post("/reconstructions")
    def reconstruct(payload: dict[str, Any] = Body(...)):
        try:
            return service_provider().reconstruction.start(payload)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/reconstructions/{job_id}")
    def reconstruction_status(job_id: str):
        try:
            return service_provider().reconstruction.status(job_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/reconstructions/{job_id}/sources/{index}")
    def reconstruction_source(job_id: str, index: int):
        try:
            core = service_provider().reconstruction
            contents, mime = core.source_image(job_id, index)
            return Response(content=contents, media_type=mime, headers={"Cache-Control": "no-store"})
        except (KeyError, ValueError, IndexError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/comparisons")
    def compare_selected(payload: dict[str, Any] = Body(...)):
        try:
            return service_provider().reconstruction.start_comparison(payload)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/reconstructions/{job_id}/reports/{report_id}")
    def comparison_status(job_id: str, report_id: str):
        try:
            return service_provider().reconstruction.report(job_id, report_id)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/corrections")
    def correct_selected(payload: dict[str, Any] = Body(...)):
        try:
            return service_provider().reconstruction.correct_selected(payload)
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/jobs")
    def submit(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return service_provider().submit(payload)
        except AdHocImageGenerationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Unable to stage image generation through AI_Proxy: {exc}") from exc

    @router.get("/jobs/{request_id}")
    def status(request_id: str) -> dict[str, Any]:
        try:
            return service_provider().status(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc

    @router.get("/jobs/{request_id}/references/{index}")
    def captured_reference(request_id: str, index: int):
        try:
            contents, mime = service_provider().captured_reference(request_id, index)
            return Response(content=contents, media_type=mime, headers={"Cache-Control": "no-store"})
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Captured reference not found.") from exc

    @router.get("/jobs/{request_id}/images/{index}")
    def image(request_id: str, index: int, download: bool = Query(False)) -> Response:
        try:
            contents, media_type = service_provider().image(request_id, index)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        headers = {"Cache-Control": "no-store"}
        if download:
            extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(media_type, "img")
            headers["Content-Disposition"] = f'attachment; filename="zet-image-{index + 1}.{extension}"'
        return Response(content=contents, media_type=media_type, headers=headers)

    @router.delete("/jobs/{request_id}/images/{index}")
    def clear_image(request_id: str, index: int) -> dict[str, Any]:
        try:
            service = service_provider()
            with service.slot_workspace.standalone_request(request_id):
                return service.clear_image(request_id, index)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        except (AdHocImageGenerationError, RenderSlotConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/jobs/{request_id}/images/{index}/import")
    def import_image(request_id: str, index: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            service = service_provider()
            with service.slot_workspace.standalone_request(request_id):
                result = service.import_into_library(request_id, index, payload)
            return {"asset": result.get("asset", result),
                    "duplicate": bool(result.get("duplicate", False))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/jobs/{request_id}/images/{index}/apply")
    def apply_image(request_id: str, index: int) -> dict[str, Any]:
        try:
            service = service_provider()
            with service.slot_workspace.standalone_request(request_id):
                return {"asset": service.apply_to_source(request_id, index)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.delete("/jobs/{request_id}")
    def clear(request_id: str) -> dict[str, str]:
        try:
            service = service_provider()
            with service.slot_workspace.standalone_request(request_id):
                service.clear(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        except (AdHocImageGenerationError, RenderSlotConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Image generation results cleared."}

    return router
