from __future__ import annotations

import json
from collections.abc import Callable

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from zet.services.quick_character_wizard_service import (
    QuickCharacterWizardConflict, QuickCharacterWizardError, QuickCharacterWizardService,
)


def create_quick_character_wizard_router(provider: Callable[[], QuickCharacterWizardService]) -> APIRouter:
    router = APIRouter(prefix="/api/quick-character-wizard", tags=["quick-character-wizard"])

    def call(operation):
        try:
            return operation(provider())
        except QuickCharacterWizardConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (QuickCharacterWizardError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("")
    def sessions():
        return {"sessions": call(lambda service: service.list_sessions())}

    @router.post("")
    async def create(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 85 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Wizard references exceed the request limit.")
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Expected an object.")
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Expected a JSON wizard form.") from exc
        return {"session": await run_in_threadpool(call, lambda service: service.create_session(payload))}

    @router.get("/{sid}")
    def status(sid: str):
        return {"session": call(lambda service: service.get_session(sid))}

    @router.get("/{sid}/references/{index}")
    def reference(sid: str, index: int):
        return FileResponse(call(lambda service: service.image_path(sid, reference_index=index)))

    @router.get("/{sid}/images/{candidate_id}")
    def image(sid: str, candidate_id: str):
        return FileResponse(call(lambda service: service.image_path(sid, candidate_id=candidate_id)))

    @router.post("/{sid}/generate")
    def generate(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.generate_draft(sid, str(payload.get("revision_id") or "")))}

    @router.post("/{sid}/answers")
    def answers(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.generate_draft(sid, str(payload.get("revision_id") or ""), payload.get("answers", [])))}

    @router.patch("/{sid}/draft")
    def draft(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.update_draft(sid, str(payload.get("revision_id") or ""), payload))}

    @router.post("/{sid}/render")
    def render(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.render(sid, str(payload.get("revision_id") or ""), str(payload.get("view") or "")))}

    @router.post("/{sid}/refine")
    def refine(sid: str, payload: dict = Body(...)):
        instructions = str(payload.get("instructions") or "").strip()
        if not instructions:
            raise HTTPException(status_code=400, detail="Enter refinement instructions.")
        return {"session": call(lambda s: s.render(sid, str(payload.get("revision_id") or ""),
                                                  str(payload.get("view") or ""), instructions, str(payload.get("candidate_id") or "")))}

    @router.post("/{sid}/select")
    def select(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.select(sid, str(payload.get("revision_id") or ""), str(payload.get("candidate_id") or "")))}

    @router.post("/{sid}/review")
    def review(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.retry_review(sid, str(payload.get("revision_id") or ""), str(payload.get("candidate_id") or "")))}

    @router.post("/{sid}/accept")
    def accept(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.accept(sid, str(payload.get("revision_id") or "")))}

    @router.post("/{sid}/abandon")
    def abandon(sid: str, payload: dict = Body(...)):
        return {"session": call(lambda s: s.abandon(sid, str(payload.get("revision_id") or "")))}

    return router
