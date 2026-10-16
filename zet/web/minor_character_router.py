"""HTTP presentation for persistent Minor Character workspaces."""
import json

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from zet.services.quick_character_wizard_service import QuickCharacterWizardConflict
from zet.services.minor_character_service import MinorCharacterNotFound


def create_minor_character_router(provider):
    router = APIRouter(prefix="/api/minor-characters", tags=["minor-characters"])

    def call(operation):
        try:
            return operation(provider())
        except MinorCharacterNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except QuickCharacterWizardConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    async def payload(request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 85 * 1024 * 1024:
                raise HTTPException(413, "References exceed the request limit.")
        try:
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, "Expected a Minor Character form.") from exc

    @router.get("")
    def characters():
        return {"characters": call(lambda s: s.list_characters())}

    @router.get("/options")
    def options():
        return call(lambda s: s.reconstruction_options())

    @router.get("/owner/{asset_id}")
    def owner(asset_id: str):
        return {"character_id": call(lambda s: s.owner(asset_id))}

    @router.post("")
    async def create(request: Request):
        data = await payload(request)
        return {"character": await run_in_threadpool(call, lambda s: s.create_character(data))}

    @router.get("/{sid}")
    def character(sid: str):
        return {"character": call(lambda s: s.get_character(sid))}

    @router.patch("/{sid}")
    async def update(sid: str, request: Request):
        data = await payload(request)
        return {"character": await run_in_threadpool(call, lambda s: s.update_character(sid, data))}

    @router.delete("/{sid}")
    def delete(sid: str):
        return call(lambda s: s.delete_character(sid))

    @router.delete("/{sid}/iterations/{iteration_id}")
    def delete_iteration(sid: str, iteration_id: str):
        return {"character": call(lambda s: s.delete_iteration(sid, iteration_id))}

    @router.post("/{sid}/generate")
    def generate(sid: str, data: dict = Body(...)):
        return {"character": call(lambda s: s.render(sid, "", str(data.get("view", "FRONT")),
            str(data.get("instructions", "")), str(data.get("candidate_id", "")), data.get("item_ids", [])))}

    @router.post("/{sid}/analyze")
    def analyze(sid: str, data: dict = Body(default={})):
        return {"character": call(lambda s: s.analyze(sid, answers=data.get("answers")))}

    @router.post("/{sid}/iterations/{iteration_id}/slots")
    def slots(sid: str, iteration_id: str, data: dict = Body(...)):
        return {"character": call(lambda s: s.iteration_slots(sid, iteration_id,
            data.get("action"), data.get("slot"), data.get("count", 1)))}

    @router.post("/{sid}/select")
    def select(sid: str, data: dict = Body(...)):
        return {"character": call(lambda s: s.select(sid, "", str(data.get("candidate_id", ""))))}

    @router.post("/{sid}/lock")
    def lock(sid: str, data: dict = Body(...)):
        return {"character": call(lambda s: s.lock_view(sid, str(data.get("view", "FRONT")), str(data.get("candidate_id", ""))))}

    @router.get("/{sid}/references/{reference_id}")
    def reference(sid: str, reference_id: str):
        return FileResponse(call(lambda s: s.reference_image_path(sid, reference_id)))

    @router.get("/{sid}/images/{candidate_id}")
    def image(sid: str, candidate_id: str):
        return FileResponse(call(lambda s: s.image_path(sid, candidate_id=candidate_id)))

    @router.get("/{sid}/locked/{view}")
    def locked(sid: str, view: str):
        return FileResponse(call(lambda s: s.locked_image_path(sid, view)))

    return router
