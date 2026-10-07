"""Local, blinded browser interface for the scene assembly experiment."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from zet.services.scene_assembly_experiment_service import SceneAssemblyExperimentService


PAGE = Path(__file__).with_name("scene_assembly_review.html")


def serve_review(run_id: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    service = SceneAssemblyExperimentService(run_id)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                elif parsed.path == "/api/review":
                    body = json.dumps(service.review_catalog()).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                elif parsed.path.startswith("/image/"):
                    parts = [unquote(part) for part in parsed.path.split("/")]
                    if len(parts) != 4:
                        self._send(404, b"Not found", "text/plain; charset=utf-8")
                        return
                    image_path = service.review_image_path(parts[2], parts[3])
                    self._send(200, image_path.read_bytes(), "image/png")
                elif parsed.path.startswith("/sheet/"):
                    parts = [unquote(part) for part in parsed.path.split("/")]
                    manifest = service._manifest()
                    slug = parts[2]
                    seed = int(parts[3])
                    if slug not in manifest["scenes"] or seed not in manifest["seeds"]:
                        raise ValueError("Unknown scene or seed")
                    image_path = service._scene_dir(slug) / "blind-sheets" / f"seed-{seed}.jpg"
                    self._send(200, image_path.read_bytes(), "image/jpeg")
                else:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
            except FileNotFoundError as exc:
                self._send(404, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
            except Exception as exc:
                self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            if urlparse(self.path).path == "/api/letter":
                try:
                    result = service.generate_lettered_stage()
                    self._send(200, json.dumps(result).encode("utf-8"), "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json; charset=utf-8")
                return
            if urlparse(self.path).path != "/api/review":
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 100_000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length))
                service.save_candidate_review(str(payload["token"]), str(payload["variant"]), payload)
                self._send(200, b'{"saved":true}', "application/json; charset=utf-8")
            except Exception as exc:
                self._send(400, json.dumps({"error": str(exc)}).encode("utf-8"), "application/json; charset=utf-8")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Blinded review for run {run_id}: http://{host}:{port}/", flush=True)
    print("Keep this terminal running while you review. Press Ctrl+C to stop; saved ratings remain in the run.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
