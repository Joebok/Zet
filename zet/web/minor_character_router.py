"""HTTP presentation for Minor Character collections."""
import json

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from zet.services.minor_character_service import MinorCharacterNotFound
from zet.services.protected_effect_preview import ProtectedEffectsChanged
from zet.services.quick_character_wizard_service import QuickCharacterWizardConflict


def create_minor_character_router(provider):
    router = APIRouter(prefix="/api/minor-characters", tags=["minor-characters"])

    def call(method, *args):
        try:
            return getattr(provider(), method)(*args)
        except MinorCharacterNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except ProtectedEffectsChanged as exc:
            raise HTTPException(409, {"message": str(exc), "preview": exc.preview}) from exc
        except QuickCharacterWizardConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("")
    def characters():
        return {"characters": call("list_characters")}

    @router.get("/owner/{asset_id}")
    def owner(asset_id: str):
        return {"character_id": call("owner", asset_id)}

    @router.post("")
    def create(data: dict = Body(...)):
        return {"character": call("create_character", data)}

    @router.get("/{sid}")
    def character(sid: str):
        return {"character": call("get_character", sid)}

    @router.patch("/{sid}")
    async def update(sid: str, request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 28 * 1024 * 1024:
                raise HTTPException(413, "The source image is too large.")
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, "Expected a Minor Character form.") from exc
        return {"character": await run_in_threadpool(call, "update_character", sid, data)}

    @router.get("/{sid}/source")
    def source(sid: str):
        return FileResponse(call("source_image", sid))

    @router.get("/{sid}/assets/{view}/progress")
    def progress(sid: str, view: str):
        return call("progress", sid, view)

    @router.post("/{sid}/assets/{view}/generate")
    def generate(sid: str, view: str, data: dict = Body(...)):
        return {"character": call("generate", sid, view, data)}

    @router.post("/{sid}/assets/{view}/authoring/{action}")
    def author(sid: str, view: str, action: str, data: dict = Body(...)):
        return {"character": call("text_action", sid, view, action, data)}

    @router.post("/{sid}/assets/{view}/bulk/{kind}/preview")
    def preview(sid: str, view: str, kind: str):
        return call("bulk", sid, view, kind)

    @router.post("/{sid}/assets/{view}/bulk/{kind}")
    def bulk(sid: str, view: str, kind: str, data: dict = Body(...)):
        return {"character": call("bulk", sid, view, kind, data)}

    @router.get("/{sid}/assets/{view}/candidates/{cid}/image")
    def image(sid: str, view: str, cid: str):
        return FileResponse(call("candidate_file", sid, view, cid))

    @router.get("/{sid}/assets/{view}/candidates/{cid}/inputs/{index}")
    def input_image(sid: str, view: str, cid: str, index: int):
        return FileResponse(call("candidate_file", sid, view, cid, index))

    @router.post("/{sid}/assets/{view}/candidates/{cid}/{action}")
    def action(sid: str, view: str, cid: str, action: str, data: dict = Body(...)):
        return {"character": call("action", sid, view, cid, action, data)}

    return router
