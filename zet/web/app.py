from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from zet.app import ZetApp
from zet.render_console.queue import RenderConsoleQueue
from zet.services.config_service import ConfigService
from zet.services.pipeline_control_service import AutomationSettings
from zet.services.prompt_review_service import LocalRenderUnavailable

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]


def _app(config_path: str | Path) -> ZetApp:
    return ZetApp.from_config(config_path)


def _render_console_queue(config_path: str | Path) -> RenderConsoleQueue:
    return RenderConsoleQueue(ConfigService.load(config_path))


def _format_value(value: Any) -> str:
    return "None" if value is None else str(value)


def _format_timestamp_with_age(value: Any) -> str:
    return _format_value(value)


def _discover_characters(base_character_path: str) -> list[str]:
    root = Path(base_character_path)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _discover_phases(base_character_path: str, character: str) -> list[str]:
    root = Path(base_character_path) / character
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _review_image_ready(zet_app: ZetApp, asset) -> bool:
    if asset.pipeline_stage == "PROMPT_REVIEW":
        if asset.pipeline != "Body-Reference":
            return False
        try:
            context = zet_app.prompt_review_service.get_context(asset.character, asset.phase, asset.asset_id)
            return context.latest_local_test_render is not None
        except Exception:
            return False
    if asset.pipeline_stage == "RENDER_REVIEW":
        try:
            return zet_app.path_service.candidate_image_path(asset).exists()
        except Exception:
            return False
    return False


def _is_prompt_review_asset(asset) -> bool:
    return asset.pipeline_stage == "PROMPT_REVIEW" and asset.actor == "HUMAN_AGENT"


def _is_render_review_asset(asset) -> bool:
    return asset.pipeline_stage == "RENDER_REVIEW" and asset.actor == "HUMAN_AGENT"


def _is_head_fitment_manifest_asset(asset) -> bool:
    return asset.pipeline == "Head-Fitment" and asset.pipeline_stage in {"MANIFEST", "ADD_REF"} and asset.actor == "PYTHON"


def _asset_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    data = asdict(asset)
    data["head_view"] = _format_value(asset.head_view)
    data["costume"] = _format_value(asset.costume)
    data["expression"] = _format_value(asset.expression)
    data["ai_state"] = _format_value(asset.ai_state)
    data["final_image_output"] = _format_value(asset.final_image_output)
    data["updated_at_display"] = _format_timestamp_with_age(asset.updated_at)
    data["review_image_ready"] = _review_image_ready(zet_app, asset)
    if asset.pipeline_stage == "ADD_REF" and asset.error_code:
        data["pipeline_stage_display"] = f"ADD_REF ({asset.error_code})"
    elif data["review_image_ready"]:
        data["pipeline_stage_display"] = f"CAMERA {asset.pipeline_stage}"
    else:
        data["pipeline_stage_display"] = asset.pipeline_stage
    return data


def _prompt_review_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    try:
        context = zet_app.prompt_review_service.get_context(asset.character, asset.phase, asset.asset_id)
        payload["prompt_path"] = str(context.prompt_path) if context.prompt_path else None
        payload["condense_state"] = context.condense_status.get("state")
        payload["latest_local_test_render"] = str(context.latest_local_test_render) if context.latest_local_test_render else None
    except Exception:
        payload["prompt_path"] = None
        payload["condense_state"] = None
        payload["latest_local_test_render"] = None
    return payload


def _prompt_review_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    context = zet_app.prompt_review_service.get_context(character, phase, asset_id)
    asset = context.asset
    return {
        "asset": _asset_payload(zet_app, asset),
        "is_reviewable": _is_prompt_review_asset(asset),
        "prompt_path": str(context.prompt_path) if context.prompt_path else None,
        "prompt_text": context.prompt_text or "",
        "condensed_prompt_path": str(context.condensed_prompt_path) if context.condensed_prompt_path else None,
        "condensed_prompt_text": context.condensed_prompt_text or "",
        "render_prompt_path": str(context.render_prompt_path) if context.render_prompt_path else None,
        "prompt_review_path": str(context.prompt_review_path) if context.prompt_review_path else None,
        "latest_local_test_render": str(context.latest_local_test_render) if context.latest_local_test_render else None,
        "prompt_candidates": [str(path) for path in context.prompt_candidates],
        "condense_status": _jsonable(context.condense_status),
    }


def _render_review_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    try:
        candidate_image_path = zet_app.path_service.candidate_image_path(asset)
        locked_image_path = zet_app.path_service.locked_image_path(asset)
        payload["candidate_image_path"] = str(candidate_image_path)
        payload["candidate_image_exists"] = candidate_image_path.exists()
        payload["locked_image_path"] = str(locked_image_path)
        payload["locked_image_exists"] = locked_image_path.exists()
    except Exception:
        payload["candidate_image_path"] = None
        payload["candidate_image_exists"] = False
        payload["locked_image_path"] = None
        payload["locked_image_exists"] = False
    return payload


def _render_review_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    detail = _asset_detail_payload(zet_app, character, phase, asset_id)
    asset = detail["asset"]
    return {
        "asset": asset,
        "is_reviewable": _is_render_review_asset(zet_app.asset(character, phase, asset_id).get()),
        "paths": detail["paths"],
        "exists": detail["exists"],
        "stage_text": detail["stage_text"],
        "history_text": detail["history_text"],
        "candidate_image_path": detail["paths"]["candidate_image_path"],
        "locked_image_path": detail["paths"]["locked_image_path"],
    }


def _head_fitment_manifest_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    payload["reference_count"] = len(asset.reference_files or [])
    payload["has_body_reference"] = any(ref.get("role") == "body_reference" for ref in asset.reference_files or [])
    payload["has_headshot"] = any(ref.get("role") == "headshot" for ref in asset.reference_files or [])
    return payload


def _head_fitment_manifest_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    context = zet_app.head_fitment_reference_context(character, phase, asset_id)
    return {
        "asset": _asset_payload(zet_app, context["asset"]),
        "is_manifest_editable": context["is_manifest_editable"],
        "body_reference_options": _jsonable(context["body_reference_options"]),
        "headshot_options": _jsonable(context["headshot_options"]),
        "selected_body_reference": _jsonable(context["selected_body_reference"]),
        "selected_headshot": _jsonable(context["selected_headshot"]),
        "reference_files": _jsonable(context["reference_files"]),
    }


def _monitor_request_payloads(zet_app: ZetApp) -> list[dict[str, Any]]:
    root = zet_app.ai_proxy_service.ai_proxy_path_service.monitor_requests_root()
    if not root.exists():
        return []
    rows = []
    for request_path in sorted((path for path in root.iterdir() if path.is_dir()), reverse=True):
        manifest_path = request_path / "request.json"
        payload: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                import json

                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        rows.append(
            {
                "test_id": payload.get("test_id") or request_path.name,
                "instruction": payload.get("instruction") or "",
                "created_at": payload.get("created_at") or "",
                "path": str(request_path),
            }
        )
    return rows


def _ai_controls_payload(zet_app: ZetApp) -> dict[str, Any]:
    queue_snapshot = zet_app.queue_snapshot()
    manual_render_asks = [
        item for item in queue_snapshot["ask"]
        if item.get("worker_type") == "manual_chatgpt_render"
    ]
    return {
        "stop_state": _jsonable(zet_app.proxy_stop_state()),
        "queue": _jsonable(queue_snapshot),
        "queue_counts": {key: len(value) for key, value in queue_snapshot.items()},
        "manual_render_asks": _jsonable(manual_render_asks),
        "monitor_requests": _monitor_request_payloads(zet_app),
        "monitor_responses": _jsonable(zet_app.list_monitor_responses()),
        "processes": [status.to_dict() for status in zet_app.process_statuses()],
        "render_console_url": f"http://{zet_app.config.render_console_host}:{zet_app.config.render_console_port}",
    }


def _automation_settings_from_payload(payload: dict[str, Any]) -> AutomationSettings:
    return AutomationSettings(
        prompt_condense_enabled=bool(payload.get("prompt_condense_enabled", False)),
        prompt_condense_model=str(payload.get("prompt_condense_model", "")),
        prompt_condense_file=str(payload.get("prompt_condense_file", "")),
        local_render_auto_queue_after_condense=bool(payload.get("local_render_auto_queue_after_condense", False)),
        local_render_preset=str(payload.get("local_render_preset", "")),
        ai_harvest_auto_enabled=bool(payload.get("ai_harvest_auto_enabled", False)),
        ai_harvest_interval_seconds=int(payload.get("ai_harvest_interval_seconds", 0)),
        render_backend=str(payload.get("render_backend", "")),
    )


def _pipeline_controls_payload(zet_app: ZetApp, character: str, phase: str) -> dict[str, Any]:
    snapshot = zet_app.pipeline_control_snapshot(character, phase)
    pipeline_names = sorted({row.pipeline for row in snapshot.pipeline_rows})
    return {
        "config_path": str(snapshot.config_path),
        "pipelines_path": str(snapshot.pipelines_path),
        "automation": _jsonable(snapshot.automation),
        "pipeline_rows": _jsonable(snapshot.pipeline_rows),
        "project_config_rows": _jsonable(snapshot.project_config_rows),
        "pipeline_names": pipeline_names,
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _asset_detail_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    asset_ref = zet_app.asset(character, phase, asset_id)
    asset = asset_ref.get()
    pipeline_path = asset_ref.pipeline_path()
    candidate_image_path = asset_ref.candidate_image_path()
    locked_image_path = asset_ref.locked_image_path()
    stage_path = pipeline_path / "_stage.txt"
    history_path = pipeline_path / "_history.log"
    return {
        "asset": _asset_payload(zet_app, asset),
        "paths": {
            "character_path": str(zet_app.path_service.character_path(character, phase)),
            "character_asset_path": str(zet_app.path_service.character_asset_path(character, phase)),
            "pipeline_path": str(pipeline_path),
            "candidate_image_path": str(candidate_image_path),
            "locked_image_path": str(locked_image_path),
        },
        "exists": {
            "candidate_image": candidate_image_path.exists(),
            "locked_image": locked_image_path.exists(),
            "stage": stage_path.exists(),
            "history": history_path.exists(),
        },
        "stage_text": stage_path.read_text(encoding="utf-8") if stage_path.exists() else "",
        "history_text": history_path.read_text(encoding="utf-8") if history_path.exists() else "",
    }


def _action_response(zet_app: ZetApp, character: str, phase: str, asset_id: int, message: str) -> dict[str, Any]:
    return {
        "message": message,
        "detail": _asset_detail_payload(zet_app, character, phase, asset_id),
        "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
    }


def create_app(config_path: str | Path = "config.toml") -> FastAPI:
    config_path = Path(config_path)
    config = ConfigService.load(config_path)
    app = FastAPI(title="Zet Web")
    app.state.config_path = str(config_path)

    app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="zet_web_static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (PACKAGE_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    @app.get("/api/context")
    def context() -> dict[str, Any]:
        current_config = ConfigService.load(app.state.config_path)
        characters = _discover_characters(current_config.base_character_path)
        phases_by_character = {
            character: _discover_phases(current_config.base_character_path, character)
            for character in characters
        }
        return {
            "characters": characters,
            "phases_by_character": phases_by_character,
            "default_character": characters[0] if characters else None,
            "default_phase": phases_by_character.get(characters[0], [None])[0] if characters else None,
        }

    @app.get("/api/assets")
    def assets(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            items = zet_app.list_assets(character, phase)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"assets": [_asset_payload(zet_app, asset) for asset in items]}

    @app.get("/api/assets/{asset_id}")
    def asset_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _asset_detail_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/file")
    def local_file(path: str = Query(...)):
        requested = Path(path)
        if not requested.exists() or not requested.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        return FileResponse(requested)

    @app.get("/api/prompt-review/tasks")
    def prompt_review_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [asset for asset in zet_app.list_assets(character, phase) if _is_prompt_review_asset(asset)]
            return {"tasks": [_prompt_review_task_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompt-review/{asset_id}")
    def prompt_review_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _prompt_review_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/local-test-render")
    def prompt_review_local_test_render(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.generate_local_test_render(character, phase, asset_id)
            payload = _prompt_review_context_payload(zet_app, character, phase, asset_id)
            payload["message"] = f"Local test image generated: {result.image_path}"
            return payload
        except LocalRenderUnavailable as exc:
            raise HTTPException(status_code=503, detail="Local render backend unavailable.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/approve")
    def prompt_review_approve(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.approve_prompt_review(character, phase, asset_id)
            return {
                "message": f"Prompt approved. Asset {updated.asset_id} moved to {updated.pipeline_stage}.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _prompt_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_prompt_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/fail")
    def prompt_review_fail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.fail_prompt_review(character, phase, asset_id)
            return {
                "message": f"Prompt failed. Asset {updated.asset_id} moved to {updated.pipeline_stage}.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _prompt_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_prompt_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/tasks")
    def render_review_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [asset for asset in zet_app.list_assets(character, phase) if _is_render_review_asset(asset)]
            return {"tasks": [_render_review_task_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/{asset_id}")
    def render_review_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _render_review_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/promote-to-locked")
    def render_review_promote_to_locked(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).promote_to_locked()
            return {
                "message": f"Render approved. Asset {updated.asset_id} moved to LOCKED.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/fail-to-render")
    def render_review_fail_to_render(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.fail_render_review_to_render(character, phase, asset_id)
            return {
                "message": f"Render rejected. Asset {updated.asset_id} moved back to RENDER.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/fail-to-regenerate")
    def render_review_fail_to_regenerate(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).regenerate()
            return {
                "message": f"Render rejected. Asset {updated.asset_id} reset to {updated.pipeline_stage}.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/head-fitment-manifest/tasks")
    def head_fitment_manifest_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [
                asset for asset in zet_app.list_assets(character, phase)
                if _is_head_fitment_manifest_asset(asset)
            ]
            return {"tasks": [_head_fitment_manifest_task_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/head-fitment-manifest/{asset_id}")
    def head_fitment_manifest_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _head_fitment_manifest_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/head-fitment-manifest/{asset_id}/references")
    def head_fitment_manifest_save_references(
        asset_id: int,
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.save_head_fitment_references(
                character,
                phase,
                asset_id,
                str(payload.get("body_reference_path") or ""),
                str(payload.get("headshot_path") or ""),
            )
            response = _head_fitment_manifest_context_payload(zet_app, character, phase, updated.asset_id)
            response["message"] = "Head-fitment reference slots saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/head-fitment-manifest/headshots")
    async def head_fitment_manifest_upload_headshot(
        request: Request,
        filename: str = Query(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            path = zet_app.upload_headshot_reference(character, phase, filename, await request.body())
            return {"path": str(path), "name": path.name}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/ai-controls")
    def ai_controls() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _ai_controls_payload(zet_app)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/harvest")
    def ai_controls_harvest() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            results = zet_app.harvest_ai_answers()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = f"Harvested {len(results)} AI answer folder(s)." if results else "No AI answer folders found."
            payload["harvest_results"] = _jsonable(results)
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/monitor-test")
    def ai_controls_monitor_test(instruction: str = Query("", max_length=1000)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            request_path = zet_app.issue_monitor_test(instruction)
            payload = _ai_controls_payload(zet_app)
            payload["message"] = f"Monitor test sent: {request_path.name}"
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/stop")
    def ai_controls_stop() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            stop_state = zet_app.activate_proxy_stop()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = f"Proxy stop activated. Cleared {stop_state['cleared_asks']} ask folder(s)."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/resume")
    def ai_controls_resume() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.resume_proxy_stop()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = "Proxy stop cleared. New asks may be processed."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/processes/{process_id}/{action}")
    def ai_controls_process_action(process_id: str, action: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            if action == "start":
                zet_app.start_process(process_id)
                message = f"Started {process_id}."
            elif action == "stop":
                count = zet_app.stop_process(process_id)
                message = f"Stopped {count} process(es) for {process_id}."
            elif action == "restart":
                count = zet_app.restart_process(process_id)
                message = f"Restarted {process_id}; stopped {count} old process(es)."
            else:
                raise ValueError(f"Unsupported process action: {action}")
            payload = _ai_controls_payload(zet_app)
            payload["message"] = message
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/pipeline-controls")
    def pipeline_controls(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _pipeline_controls_payload(zet_app, character, phase)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pipeline-controls/automation")
    def pipeline_controls_save_automation(
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.save_automation_settings(_automation_settings_from_payload(payload))
            refreshed = _app(app.state.config_path)
            response = _pipeline_controls_payload(refreshed, character, phase)
            response["message"] = "Project automation settings saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pipeline-controls/batch-render-reset")
    def pipeline_controls_batch_render_reset(
        pipeline_name: str = Query(...),
        include_locked: bool = Query(False),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            results = zet_app.reset_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)
            response = _pipeline_controls_payload(zet_app, character, phase)
            reset_count = sum(1 for result in results if result.status == "RESET")
            skipped_count = sum(1 for result in results if result.status == "SKIPPED")
            error_count = sum(1 for result in results if result.status == "ERROR")
            response["message"] = (
                f"Batch render reset complete for {pipeline_name}: "
                f"{reset_count} reset, {skipped_count} skipped, {error_count} error."
            )
            response["batch_results"] = _jsonable(results)
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-console/tasks")
    def render_console_tasks() -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        try:
            return {"tasks": [task.to_dict() for task in queue.list_tasks()]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-console/tasks/{ask_id}")
    def render_console_task_detail(ask_id: str) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        return {
            "task": task.to_dict(),
            "manifest": _jsonable(task.manifest),
            "prompt": queue.read_prompt(task),
        }

    @app.post("/api/render-console/tasks/{ask_id}/answer-image")
    async def render_console_answer_image(ask_id: str, request: Request) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        image_bytes = await request.body()
        content_type = request.headers.get("content-type", "")
        try:
            answer_path = queue.write_answer_image(task, image_bytes, content_type)
            tasks = queue.list_tasks()
            return {
                "status": "SUCCESS",
                "answer_path": str(answer_path),
                "remaining_tasks": [item.to_dict() for item in tasks],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-console/tasks/{ask_id}/fail")
    async def render_console_fail_task(ask_id: str, request: Request) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        payload = await request.json()
        reason = str(payload.get("reason") or "")
        try:
            answer_path = queue.write_failed_answer(task, reason)
            tasks = queue.list_tasks()
            return {
                "status": "ERROR",
                "answer_path": str(answer_path),
                "remaining_tasks": [item.to_dict() for item in tasks],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/stage-ai-ask")
    def stage_ai_ask(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            ask_path = zet_app.asset(character, phase, asset_id).stage_ai_ask()
            return _action_response(zet_app, character, phase, asset_id, f"AI ask staged at {ask_path}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/run-current-worker")
    def run_current_worker(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).run_current_worker()
            return _action_response(zet_app, character, phase, updated.asset_id, f"Worker finished at {updated.pipeline_stage}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/run-housekeeping")
    def run_housekeeping(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            path = zet_app.asset(character, phase, asset_id).run_housekeeping()
            return _action_response(zet_app, character, phase, asset_id, f"Housekeeping complete at {path}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/retry-ai")
    def retry_ai(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).retry_ai()
            return _action_response(zet_app, character, phase, updated.asset_id, "AI retry requested.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/regenerate")
    def regenerate(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).regenerate()
            return _action_response(zet_app, character, phase, updated.asset_id, f"Asset reset to {updated.pipeline_stage}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/promote-to-locked")
    def promote_to_locked(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).promote_to_locked()
            return _action_response(zet_app, character, phase, updated.asset_id, "Asset promoted to LOCKED.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Zet FastAPI web dashboard.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    import uvicorn

    uvicorn.run(create_app(args.config), host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
