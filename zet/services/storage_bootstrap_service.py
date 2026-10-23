"""Construct storage-dependent services only after their roots are accessible."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from zet.services.storage_health_service import StorageUnavailable, storage_health


RETRY_AFTER_SECONDS = "10"


def storage_paused_response(message="Storage unavailable; retry automatically"):
    return JSONResponse({"status": "PAUSED_STORAGE", "detail": message},
                        status_code=503, headers={"Retry-After": RETRY_AFTER_SECONDS})


WAITING_PAGE = """<!doctype html><html><head><title>Zet — Storage paused</title></head>
<body><h1>Zet is waiting for storage</h1><p>The library or queue is unavailable.
Work will resume automatically when storage returns. Reconnect the drive if needed.</p>
<pre id="status"></pre><script>setInterval(async()=>{try{const r=await fetch('/api/storage/status');
const s=await r.json();document.getElementById('status').textContent=JSON.stringify(s,null,2);
if(s.available&&s.initialized)location.reload();}catch(e){}},10000);</script></body></html>"""


def install_storage_status(app, health, config):
    @app.exception_handler(StorageUnavailable)
    async def storage_unavailable(_request: Request, _exc: StorageUnavailable):
        return storage_paused_response()

    def for_request(request):
        universe = request.query_params.get("universe_id")
        if universe and universe != app.state.zet_app.universe_id:
            known = app.state.universe_apps.get(universe)
            if known is not None:
                return storage_health(known.config)
            try:
                return storage_health(app.state.zet_app.universe_service.bind_config(config, universe))
            except ValueError:
                pass
        return health

    @app.get("/api/storage/status")
    async def storage_status(request: Request):
        selected = await asyncio.to_thread(for_request, request)
        return {**await asyncio.to_thread(selected.poll), "initialized": True}

    @app.middleware("http")
    async def storage_gate(request: Request, call_next):
        path = request.url.path
        if path == "/api/storage/status" or path.startswith("/static/"):
            return await call_next(request)
        request_health = await asyncio.to_thread(for_request, request)
        status = await asyncio.to_thread(request_health.poll)
        unavailable = not status["available"]
        if path == "/api/ai/jobs":
            unavailable = any(status["resources"][name]["status"] != "AVAILABLE" for name in ("queue", "application"))
        if unavailable:
            if not path.startswith("/api/"):
                return HTMLResponse(WAITING_PAGE)
            if path == "/api/ai/jobs":
                from zet.services.ai_queue_query_service import AIQueueQueryService
                return JSONResponse({**AIQueueQueryService.cached(config), "storage": status})
            return JSONResponse({"status": "PAUSED_STORAGE", "detail": "Storage unavailable; retry automatically", "storage": status},
                                status_code=503, headers={"Retry-After": RETRY_AFTER_SECONDS})
        response = await call_next(request)
        if response.status_code >= 400 and not (await asyncio.to_thread(request_health.poll, force=True))["available"]:
            return storage_paused_response("Storage unavailable; recovery is automatic")
        return response


def waiting_app(config, factory):
    health = storage_health(config)
    state = {"inner": None, "error": ""}

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()
        context = None

        async def initialize():
            nonlocal context
            while not stop.is_set():
                if state["inner"] is None and (await asyncio.to_thread(health.poll))["available"]:
                    try:
                        inner = await asyncio.to_thread(factory)
                        candidate_context = inner.router.lifespan_context(inner)
                        await candidate_context.__aenter__()
                        context = candidate_context
                        state.update(inner=inner, error="")
                    except Exception as exc:
                        if context:
                            await context.__aexit__(type(exc), exc, exc.__traceback__)
                            context = None
                        if state["error"] != str(exc):
                            logging.getLogger(__name__).exception("Zet initialization deferred")
                        state["error"] = str(exc)
                        health.check_error(exc)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2)
                except TimeoutError:
                    pass

        task = asyncio.create_task(initialize())
        try:
            yield
        finally:
            stop.set()
            await task
            if context:
                await context.__aexit__(None, None, None)

    outer = FastAPI(title="Zet — waiting for storage", lifespan=lifespan)

    @outer.get("/api/storage/status")
    async def status():
        return {**await asyncio.to_thread(health.poll), "initialized": state["inner"] is not None, "initialization_error": state["error"]}

    async def dispatch(scope, receive, send):
        if state["inner"] is not None:
            await state["inner"](scope, receive, send)
        else:
            if scope.get("path") == "/api/ai/jobs":
                from zet.services.ai_queue_query_service import AIQueueQueryService
                await JSONResponse({**AIQueueQueryService.cached(config), "storage": health.status()})(scope, receive, send)
                return
            response = JSONResponse({"status": "PAUSED_STORAGE", "detail": "Waiting for configured storage", "storage": health.status()},
                                    status_code=503, headers={"Retry-After": RETRY_AFTER_SECONDS}) if scope.get("path", "").startswith("/api/") else HTMLResponse(WAITING_PAGE)
            await response(scope, receive, send)

    outer.mount("/", dispatch)
    return outer
