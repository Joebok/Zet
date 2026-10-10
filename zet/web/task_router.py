from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Response

from zet.app import ZetApp
from zet.services.task_service import TaskServiceError


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

    return router
