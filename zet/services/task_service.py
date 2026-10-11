"""Forward frozen dashboard reports to Kanban without owning its board files."""

from __future__ import annotations

import base64
import hashlib
import json
from http.client import HTTPException as HTTPTransportError
import math
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
MAX_SCREENSHOT_REQUEST_BYTES = 7 * 1024 * 1024
ATTACHMENT_ID = r"attachment-[0-9a-f]{32}"


class TaskServiceError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def validate_kanban_settings(base_url, project_id, timeout_seconds) -> tuple[str, str, float]:
    if not isinstance(base_url, str) or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in base_url) or "\\" in base_url:
        raise TaskServiceError("Kanban BaseURL must be an HTTP(S) origin without credentials or a path.")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise TaskServiceError("Kanban BaseURL is invalid.") from exc
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or port == 0 or
            parsed.username is not None or parsed.password is not None or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise TaskServiceError("Kanban BaseURL must be an HTTP(S) origin without credentials or a path.")
    if not isinstance(project_id, str) or (project_id and re.fullmatch(r"project-[0-9a-f]{8}", project_id) is None):
        raise TaskServiceError("Kanban ProjectID must be empty or a registered project identifier.")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
        raise TaskServiceError("Kanban TimeoutSeconds must be a finite number greater than zero and at most 60.")
    return base_url.rstrip("/"), project_id, float(timeout_seconds)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TaskService:
    def __init__(self, base_url: str, project_id: str, timeout_seconds: float = 5.0, *, project_root: Path):
        self.base_url, self.project_id, self.timeout_seconds = validate_kanban_settings(base_url, project_id, timeout_seconds)
        # Keep local reports off ambient HTTP proxies and do not follow redirects.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.zet_revision = self._revision(project_root)

    @staticmethod
    def _revision(project_root: Path) -> str | None:
        try:
            result = subprocess.run(["git", "-C", str(project_root), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, timeout=2, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        revision = result.stdout.strip()
        return revision if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", revision) else None

    def metadata(self) -> dict:
        return {"configured": bool(self.project_id), "board_url": self.base_url + "/",
                "project_id": self.project_id or None, "report_context_version": 1, "zet_revision": self.zet_revision}

    @staticmethod
    def _error_detail(error: HTTPError) -> str:
        try:
            value = json.loads(error.read(65536).decode("utf-8"))
        except (ValueError, OSError, HTTPTransportError):
            return "Kanban rejected the report."
        detail = value.get("detail") if isinstance(value, dict) else None
        if isinstance(detail, str):
            return detail[:1000] or "Kanban rejected the report."
        if isinstance(detail, list):
            messages = [item["msg"] for item in detail if isinstance(item, dict) and isinstance(item.get("msg"), str)]
            return "; ".join(messages)[:1000] or "Kanban rejected the report."
        return "Kanban rejected the report."

    def create_task(self, payload: dict) -> dict:
        allowed = {"request_id", "project_id", "type", "title", "description", "expected_behavior",
                   "actual_behavior", "reproduction_steps", "context", "attachment_ids"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise TaskServiceError("Expected a report with supported intake fields.", 422)
        request_id = payload.get("request_id")
        if (not isinstance(request_id, str) or not request_id.strip() or request_id != request_id.strip() or len(request_id) > 128 or
                any(ord(c) < 32 or ord(c) == 127 for c in request_id)):
            raise TaskServiceError("A stable request_id is required for task creation and retries.", 422)
        if not isinstance(payload.get("type"), str) or payload["type"] not in {"bug", "improvement", "feature"} or not isinstance(payload.get("title"), str) or not payload["title"].strip():
            raise TaskServiceError("A task type and non-empty title are required.", 422)
        context = payload.get("context")
        if not isinstance(context, dict) or type(context.get("version")) is not int or context["version"] != 1:
            raise TaskServiceError("A frozen context-v1 snapshot is required.", 422)
        if not self.project_id:
            raise TaskServiceError("Register Zet on the Kanban board and set Kanban.ProjectID in config.toml.")
        if "project_id" in payload and payload["project_id"] != self.project_id:
            raise TaskServiceError("The report project does not match Kanban.ProjectID. Preserve the original mapping when retrying.", 409)
        attachment_ids = payload.get("attachment_ids", [])
        if (not isinstance(attachment_ids, list) or len(attachment_ids) > 4 or
                any(not isinstance(item, str) or re.fullmatch(ATTACHMENT_ID, item) is None for item in attachment_ids) or
                len(set(attachment_ids)) != len(attachment_ids)):
            raise TaskServiceError("Use up to four unique screenshot attachment IDs.", 422)
        report = {**payload, "project_id": self.project_id}
        status, receipt = self._post_json("/api/v1/intake", report)
        if (not isinstance(receipt, dict) or not isinstance(receipt.get("task_id"), str) or
                re.fullmatch(r"task-[0-9a-f]{8}", receipt["task_id"]) is None or
                type(receipt.get("created")) is not bool or receipt["created"] != (status == 201) or
                receipt.get("board_url") != f"/?task_id={receipt['task_id']}"):
            raise TaskServiceError("Kanban returned an invalid intake receipt; keep the draft and retry.", 502)
        return {"task_id": receipt["task_id"], "board_url": self.base_url + receipt["board_url"], "created": receipt["created"]}

    def upload_task_attachment(self, payload: dict) -> dict:
        allowed = {"request_id", "project_id", "filename", "content_type", "content_base64"}
        if not isinstance(payload, dict) or set(payload) != allowed:
            raise TaskServiceError("Expected a screenshot with project, request, filename, type, and content.", 422)
        if not self.project_id:
            raise TaskServiceError("Register Zet on Kanban and configure Kanban.ProjectID.")
        if payload["project_id"] != self.project_id:
            raise TaskServiceError("The screenshot project does not match Kanban.ProjectID. Preserve the original mapping when retrying.", 409)
        request_id, name, mime, encoded = (payload[key] for key in ("request_id", "filename", "content_type", "content_base64"))
        if (not isinstance(request_id, str) or not request_id.strip() or request_id != request_id.strip() or len(request_id) > 128 or
                any(ord(c) < 32 or ord(c) == 127 for c in request_id)):
            raise TaskServiceError("A stable request_id is required for screenshot retries.", 422)
        extensions = {"image/png": {".png"}, "image/jpeg": {".jpg", ".jpeg"}, "image/webp": {".webp"}}
        if (not isinstance(name, str) or not name.strip() or len(name) > 240 or "/" in name or "\\" in name or
                any(ord(c) < 32 or ord(c) == 127 for c in name) or not isinstance(mime, str) or
                mime not in extensions or Path(name).suffix.lower() not in extensions[mime]):
            raise TaskServiceError("Choose a PNG, JPEG, or WebP screenshot with a matching plain filename.", 422)
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_SCREENSHOT_BYTES + 2) // 3):
            raise TaskServiceError("Screenshots must be at most 5 MiB.", 413)
        try:
            content = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise TaskServiceError("The screenshot encoding is invalid.", 422) from exc
        if not content or len(content) > MAX_SCREENSHOT_BYTES:
            raise TaskServiceError("Screenshots must contain an image of at most 5 MiB.", 422 if not content else 413)
        status, receipt = self._post_json("/api/v1/attachments", payload)
        if (not isinstance(receipt, dict) or not isinstance(receipt.get("attachment_id"), str) or
                re.fullmatch(ATTACHMENT_ID, receipt["attachment_id"]) is None or
                type(receipt.get("created")) is not bool or receipt["created"] != (status == 201) or
                receipt.get("filename") != name or receipt.get("content_type") != mime or
                type(receipt.get("size_bytes")) is not int or receipt["size_bytes"] != len(content) or
                receipt.get("sha256") != hashlib.sha256(content).hexdigest()):
            raise TaskServiceError("Kanban returned an invalid screenshot receipt; keep the draft and retry.", 502)
        return receipt

    def _post_json(self, path: str, report: dict) -> tuple[int, dict]:
        try:
            body = json.dumps(report, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TaskServiceError("The report must contain JSON values.", 422) from exc
        request = Request(self.base_url + path, data=body,
                          headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                status = response.status
                raw = response.read(65537)
        except HTTPError as exc:
            try:
                if exc.code in {400, 404, 409, 413, 415, 422}:
                    raise TaskServiceError(self._error_detail(exc), exc.code) from exc
                raise TaskServiceError("Kanban returned an unexpected HTTP response; keep the draft and retry.", 502) from exc
            finally:
                exc.close()
        except TimeoutError as exc:
            raise TaskServiceError("Kanban timed out; keep the draft and retry with the same request_id.", 504) from exc
        except (URLError, OSError, HTTPTransportError) as exc:
            timed_out = isinstance(getattr(exc, "reason", None), TimeoutError)
            raise TaskServiceError("Kanban is unavailable; keep the draft and retry with the same request_id.", 504 if timed_out else 503) from exc
        if len(raw) > 65536 or status not in {200, 201}:
            raise TaskServiceError("Kanban returned an invalid delivery response; keep the draft and retry.", 502)
        try:
            receipt = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise TaskServiceError("Kanban returned an invalid delivery response; keep the draft and retry.", 502) from exc
        return status, receipt
