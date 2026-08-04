from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from zet.app import ZetApp


def create_pipeline_inspection_router(get_app: Callable[[], ZetApp]) -> APIRouter:
    router = APIRouter(prefix="/api/pipeline-inspection")

    @router.get("")
    def pipelines() -> dict:
        return {"pipelines": get_app().list_pipeline_inspections()}

    @router.get("/files")
    def files(pipeline_id: str = Query(...)) -> dict:
        try:
            return {"files": get_app().list_pipeline_files(pipeline_id)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/text")
    def text(pipeline_id: str = Query(...), file_id: str = Query(...)) -> dict:
        try:
            return {"content": get_app().read_pipeline_file(pipeline_id, file_id)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/file")
    def file(pipeline_id: str = Query(...), file_id: str = Query(...)) -> FileResponse:
        try:
            return FileResponse(get_app().pipeline_file_path(pipeline_id, file_id))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/open-folder")
    def open_folder(pipeline_id: str = Query(...), file_id: str = Query(...)) -> dict[str, str]:
        try:
            folder = get_app().open_pipeline_folder(pipeline_id, file_id)
            return {"path": str(folder)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
