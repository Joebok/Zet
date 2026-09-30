from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from zet.services.ad_hoc_image_generation_service import (
    AdHocImageGenerationError,
    AdHocImageGenerationService,
)


def create_ad_hoc_image_generation_router(
    service_provider: Callable[[], AdHocImageGenerationService],
) -> APIRouter:
    router = APIRouter(prefix="/api/image-generation", tags=["image-generation"])

    @router.get("/options")
    def options() -> dict[str, Any]:
        return service_provider().options()

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

    @router.delete("/jobs/{request_id}")
    def clear(request_id: str) -> dict[str, str]:
        try:
            service_provider().clear(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
        except AdHocImageGenerationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"message": "Image generation results cleared."}

    return router
