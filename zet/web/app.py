from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from zet.app import ZetApp
from zet.services.config_service import ConfigService

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]


def _app(config_path: str | Path) -> ZetApp:
    return ZetApp.from_config(config_path)


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


def _asset_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    data = asdict(asset)
    data["head_view"] = _format_value(asset.head_view)
    data["costume"] = _format_value(asset.costume)
    data["expression"] = _format_value(asset.expression)
    data["ai_state"] = _format_value(asset.ai_state)
    data["final_image_output"] = _format_value(asset.final_image_output)
    data["updated_at_display"] = _format_timestamp_with_age(asset.updated_at)
    data["review_image_ready"] = _review_image_ready(zet_app, asset)
    data["pipeline_stage_display"] = f"CAMERA {asset.pipeline_stage}" if data["review_image_ready"] else asset.pipeline_stage
    return data


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
