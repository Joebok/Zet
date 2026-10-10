from collections.abc import Callable

from fastapi import APIRouter, Body, HTTPException, Response

from zet.app import ZetApp
from zet.services.task_service import TaskServiceError


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
