"""Local Luna-first review server for a layer-integration follow-up run."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from zet.services.scene_layer_integration_followup import SceneLayerIntegrationFollowup

PAGE = Path(__file__).with_name("scene_layer_integration_review.html")


def serve(run_id: str, host: str = "127.0.0.1", port: int = 18548) -> None:
    service = SceneLayerIntegrationFollowup(run_id)

    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, value: object) -> None:
            data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            try:
                if route == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(PAGE.read_bytes())
                elif route == "/api/catalog":
                    self.send_json(200, service.review_catalog())
                elif route.startswith("/artifact/"):
                    parts = route.split("/")
                    if len(parts) != 4:
                        self.send_error(404)
                        return
                    path = service.artifact_path(parts[2], parts[3])
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(path.read_bytes())
                else:
                    self.send_error(404)
            except Exception as exc:
                self.send_json(400, {"error": str(exc)})

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 2_000_000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(size))
                if route == "/api/draft":
                    service.save_draft(str(payload["item_id"]), payload["values"])
                    self.send_json(200, {"saved": True, "effective": False})
                elif route == "/api/confirm":
                    item_id = str(payload["item_id"])
                    if ":" not in item_id:
                        service.confirm_prep(item_id, payload["values"], amended=bool(payload.get("amended")))
                    else:
                        service.confirm_review(item_id, payload["values"], amended=bool(payload.get("amended")))
                    self.send_json(200, {"confirmed": True})
                elif route == "/api/luna":
                    self.send_json(200, {"response": service.luna_review(str(payload["item_id"]))})
                elif route == "/api/status":
                    self.send_json(200, service.status())
                else:
                    self.send_error(404)
            except Exception as exc:
                self.send_json(400, {"error": str(exc)})

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Luna-first preparation review for {run_id}: http://{host}:{port}/", flush=True)
    print("Keep this terminal open during review. Use Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

