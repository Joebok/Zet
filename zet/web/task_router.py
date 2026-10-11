import json

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request, Response

from zet.app import ZetApp
from starlette.concurrency import run_in_threadpool

from zet.services.task_service import MAX_SCREENSHOT_REQUEST_BYTES, TaskServiceError


def render_task_capture_page(path: Path) -> str:
    """Render the shared capture dialog into a known dashboard template."""
    return path.read_text(encoding="utf-8").replace(
        "<!-- TASK_CAPTURE_FORM -->", path.with_name("task_capture.html").read_text(encoding="utf-8")
    )


def create_task_router(provider: Callable[[], ZetApp]) -> APIRouter:
    router = APIRouter(prefix="/api/tasks", tags=["tasks"])

    @router.get("/config")
    def configuration():
        return provider().task_service.metadata()

    @router.post("", status_code=201)
    def create(response: Response, payload: dict = Body(...)):
        try:
            result = provider().create_task(payload)
        except TaskServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        response.status_code = 201 if result["created"] else 200
        return result

    @router.post("/attachments", status_code=201)
    async def upload(request: Request, response: Response):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "Screenshots require application/json.")
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_SCREENSHOT_REQUEST_BYTES:
                raise HTTPException(413, "Screenshot request exceeds 7 MiB.")
            raw.extend(chunk)
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(422, "Invalid screenshot JSON.") from exc
        try:
            result = await run_in_threadpool(provider().upload_task_attachment, payload)
        except TaskServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        response.status_code = 201 if result["created"] else 200
        return result

    return router
