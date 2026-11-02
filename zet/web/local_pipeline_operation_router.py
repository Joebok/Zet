"""HTTP boundary for character pipeline operation admission and status."""
from __future__ import annotations

import asyncio
from concurrent.futures import Executor
from functools import partial

from fastapi import APIRouter, Body, HTTPException, Query

from zet.repositories.local_pipeline_operation_repository import OperationConflict
from zet.services.local_pipeline_operation_service import LocalPipelineOperationService


def create_local_pipeline_operation_router(service: LocalPipelineOperationService, control_executor: Executor, universe_provider=None) -> APIRouter:
    router = APIRouter(prefix="/api/local/operations")

    async def call(function, *args, **kwargs):
        try:
            return await asyncio.get_running_loop().run_in_executor(control_executor, partial(function, *args, **kwargs))
        except OperationConflict as exc:
            raise HTTPException(status_code=409, detail={"message": str(exc), "operation_id": exc.operation_id}) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Operation not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("", status_code=202)
    async def submit(payload: dict = Body(...)):
        if universe_provider is not None and payload.get("universe_id") != universe_provider():
            raise HTTPException(status_code=400, detail="The operation universe does not match the selected universe.")
        record = await call(service.admit, payload)
        return {**record, "status_url": f"/api/local/operations/{record['id']}"}

    @router.get("")
    async def list_operations(universe_id: str = "", run_id: str = "", offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        return await call(service.list, universe_id=universe_id, run_id=run_id, offset=offset, limit=limit)

    @router.get("/{operation_id}")
    async def operation(operation_id: str):
        return await call(service.repository.get, operation_id)

    return router
