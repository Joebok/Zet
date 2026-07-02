from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from zet.render_console.queue import RenderConsoleQueue
from zet.services.config_service import ConfigService

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]


def create_app(config_path: str | Path = "config.toml") -> FastAPI:
    config = ConfigService.load(config_path)
    queue = RenderConsoleQueue(config)
    app = FastAPI(title="Zet Render Console")
    app.state.config_path = str(config_path)
    app.state.queue = queue

    app.mount(
        "/static",
        StaticFiles(directory=PACKAGE_ROOT / "static"),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (PACKAGE_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    @app.get("/api/tasks")
    def list_tasks() -> dict:
        tasks = app.state.queue.list_tasks()
        return {"tasks": [task.to_dict() for task in tasks]}

    @app.get("/api/tasks/{ask_id}")
    def get_task(ask_id: str) -> dict:
        task = app.state.queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        return {
            "task": task.to_dict(),
            "manifest": task.manifest,
            "prompt": app.state.queue.read_prompt(task),
        }

    @app.post("/api/tasks/{ask_id}/answer-image")
    async def answer_image(ask_id: str, request: Request) -> dict:
        task = app.state.queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")

        image_bytes = await request.body()
        content_type = request.headers.get("content-type", "")
        try:
            answer_path = app.state.queue.write_answer_image(task, image_bytes, content_type)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        tasks = app.state.queue.list_tasks()
        return {
            "status": "SUCCESS",
            "answer_path": str(answer_path),
            "remaining_tasks": [item.to_dict() for item in tasks],
        }

    return app


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Zet manual render console.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = ConfigService.load(args.config)
    host = args.host or config.render_console_host
    port = args.port or config.render_console_port

    import uvicorn

    uvicorn.run(create_app(args.config), host=host, port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
