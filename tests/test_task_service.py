from copy import deepcopy
from http.client import IncompleteRead
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from zet.app import ZetApp
from zet.services.config_service import ConfigService, ConfigServiceError
from zet.services.task_service import TaskService, TaskServiceError
from zet.web.app import create_app
from zet.web.task_router import create_task_router
from support.project_fixture import write_project_fixture


PROJECT_ID = "project-aaaaaaaa"
RECEIPT = {"task_id": "task-aaaaaaaa", "board_url": "/?task_id=task-aaaaaaaa", "created": True}


def payload():
    return {"request_id": "capture-1", "type": "bug", "title": "Wrong costume",
            "description": "The preview did not update.",
            "context": {"version": 1, "page_id": "costumes", "page_name": "Costumes",
                        "source_url": "http://127.0.0.1:8600/?page=costumes", "universe_id": "Moonsea",
                        "captured_at": "2026-10-10T12:00:00Z", "zet_revision": None,
                        "selections": {"costume": {"state": "selected", "id": "cloak"}}}}


class Reply:
    def __init__(self, body=RECEIPT, status=201):
        self.body = json.dumps(body).encode() if isinstance(body, dict) else body
        self.status = status

    def read(self, size):
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def service(project_id=PROJECT_ID):
    with patch("zet.services.task_service.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="a" * 40)):
        value = TaskService("http://127.0.0.1:8000/", project_id, 2, project_root=Path("."))
    value._opener = Mock()
    value._opener.open.return_value = Reply()
    return value


def test_configuration_defaults_and_explicit_mapping(tmp_path):
    path = write_project_fixture(tmp_path)
    default = ConfigService.load(path)
    assert default.kanban_base_url == "http://127.0.0.1:8000" and default.kanban_project_id == ""
    assert default.kanban_timeout_seconds == 5
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f'\n[Kanban]\nBaseURL = "http://localhost:8123/"\nProjectID = "{PROJECT_ID}"\nTimeoutSeconds = 2.5\n')
    configured = ConfigService.load(path)
    assert configured.kanban_base_url == "http://localhost:8123"
    assert configured.kanban_project_id == PROJECT_ID and configured.kanban_timeout_seconds == 2.5


@pytest.mark.parametrize("setting", ['BaseURL = "file:///tmp/board"', 'BaseURL = "http://user:secret@localhost/"',
                                    'BaseURL = "http://localhost/api"', 'BaseURL = "http://localhost:99999"',
                                    'ProjectID = "Zet"', 'TimeoutSeconds = true', 'TimeoutSeconds = 0',
                                    'TimeoutSeconds = inf', 'TimeoutSeconds = 61', 'ProjectId = "typo"'])
def test_invalid_configuration_is_reported_as_kanban_error(tmp_path, setting):
    path = write_project_fixture(tmp_path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n[Kanban]\n" + setting + "\n")
    with pytest.raises(ConfigServiceError, match="Kanban"):
        ConfigService.load(path)


def test_frozen_payload_is_forwarded_once_with_configured_project_and_timeout():
    sender = service()
    report = payload()
    original = deepcopy(report)
    result = sender.create_task(report)
    assert report == original
    assert result == {**RECEIPT, "board_url": "http://127.0.0.1:8000/?task_id=task-aaaaaaaa"}
    sender._opener.open.assert_called_once()
    request = sender._opener.open.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:8000/api/v1/intake" and request.method == "POST"
    assert json.loads(request.data) == {**report, "project_id": PROJECT_ID}
    assert sender._opener.open.call_args.kwargs == {"timeout": 2.0}


def test_uncertain_delivery_retry_preserves_request_id_context_and_body():
    sender = service()
    sender._opener.open.side_effect = [URLError("offline"), Reply({**RECEIPT, "created": False}, status=200)]
    report = payload()
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(report)
    assert failure.value.status_code == 503
    assert sender._opener.open.call_count == 1
    result = sender.create_task(report)
    assert result["created"] is False and result["task_id"] == RECEIPT["task_id"]
    first, second = [call.args[0] for call in sender._opener.open.call_args_list]
    assert first.data == second.data and json.loads(second.data)["request_id"] == report["request_id"]


@pytest.mark.parametrize("error,status", [(TimeoutError(), 504), (URLError(TimeoutError()), 504),
                                        (URLError("offline"), 503), (IncompleteRead(b"partial"), 503)])
def test_transport_failures_are_bounded_and_do_not_retry_automatically(error, status):
    sender = service()
    sender._opener.open.side_effect = error
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(payload())
    assert failure.value.status_code == status and "same request_id" in str(failure.value)
    assert sender._opener.open.call_count == 1


@pytest.mark.parametrize("status", [400, 404, 409, 422])
def test_upstream_rejections_preserve_status_without_echoing_input(status):
    sender = service()
    body = io.BytesIO(json.dumps({"detail": [{"msg": "Invalid snapshot", "input": "secret value"}]}).encode())
    sender._opener.open.side_effect = HTTPError("http://localhost/", status, "rejected", {}, body)
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(payload())
    assert failure.value.status_code == status and str(failure.value) == "Invalid snapshot"
    assert body.closed


@pytest.mark.parametrize("body,status", [(b"<html>unexpected</html>", 201), ({**RECEIPT, "board_url": "https://other/"}, 201),
                                       ({**RECEIPT, "created": 1}, 201), (RECEIPT, 200),
                                       ({**RECEIPT, "task_id": "invalid"}, 201), (b"x" * 65537, 201)],
                         ids=["html", "external-url", "not-boolean", "wrong-status", "bad-id", "oversized"])
def test_invalid_receipts_never_claim_success(body, status):
    sender = service()
    sender._opener.open.return_value = Reply(body, status)
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(payload())
    assert failure.value.status_code == 502


def test_redirects_are_rejected_without_sending_the_report_elsewhere():
    sender = service()
    sender._opener.open.side_effect = HTTPError("http://localhost/", 302, "redirect", {"Location": "http://other/"}, io.BytesIO())
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(payload())
    assert failure.value.status_code == 502 and sender._opener.open.call_count == 1


@pytest.mark.parametrize("change,status", [({"request_id": ""}, 422), ({"request_id": " changed "}, 422),
                                          ({"context": {"version": True}}, 422), ({"type": []}, 422),
                                          ({"project_id": "project-bbbbbbbb"}, 409), ({"attachments": []}, 422)])
def test_local_validation_rejects_changes_before_network_call(change, status):
    sender = service()
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task({**payload(), **change})
    assert failure.value.status_code == status
    sender._opener.open.assert_not_called()


def test_unconfigured_metadata_is_local_and_creation_does_not_contact_kanban():
    sender = service("")
    assert sender.metadata() == {"configured": False, "board_url": "http://127.0.0.1:8000/", "project_id": None,
                                 "report_context_version": 1, "zet_revision": "a" * 40}
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(payload())
    assert failure.value.status_code == 503 and "ProjectID" in str(failure.value)
    sender._opener.open.assert_not_called()


def test_thin_router_calls_zet_app_and_maps_receipt_and_failure_statuses():
    sender = service()
    zet_app = SimpleNamespace(task_service=sender, create_task=sender.create_task)
    api = FastAPI()
    api.include_router(create_task_router(lambda: zet_app))
    client = TestClient(api)
    assert client.get("/api/tasks/config").json()["project_id"] == PROJECT_ID
    assert client.post("/api/tasks", json=payload()).status_code == 201
    sender._opener.open.return_value = Reply({**RECEIPT, "created": False}, 200)
    assert client.post("/api/tasks", json=payload()).status_code == 200
    sender._opener.open.side_effect = TimeoutError()
    assert client.post("/api/tasks", json=payload()).status_code == 504


def test_zet_app_exposes_forwarding_and_dashboard_installs_router(tmp_path):
    config_path = write_project_fixture(tmp_path)
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write(f'\n[Kanban]\nProjectID = "{PROJECT_ID}"\n')
    app = create_app(config_path, validate_catalog_on_create=False)
    client = TestClient(app)
    assert isinstance(app.state.zet_app, ZetApp)
    assert client.get("/api/tasks/config").json()["project_id"] == PROJECT_ID
    with patch.object(app.state.zet_app.task_service._opener, "open", return_value=Reply()) as sent:
        assert client.post("/api/tasks", json=payload()).json()["task_id"] == RECEIPT["task_id"]
    assert json.loads(sent.call_args.args[0].data)["context"] == payload()["context"]


@pytest.mark.parametrize("path", ["/", "/narrative"])
def test_dashboard_pages_render_one_shared_task_form(tmp_path, path):
    app = create_app(write_project_fixture(tmp_path), validate_catalog_on_create=False)
    response = TestClient(app).get(path)
    assert response.status_code == 200
    assert response.text.count('id="task-capture-form"') == 1
    assert 'id="toolbar-create-task"' in response.text
    assert 'TASK_CAPTURE_FORM' not in response.text


def test_real_http_transport_refuses_redirect_and_does_not_use_ambient_proxy(tmp_path, monkeypatch):
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(302)
            self.send_header("Location", "/other")
            self.end_headers()
        def do_GET(self):
            received.append("unexpected redirect")
            self.send_response(200)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
        monkeypatch.setenv("no_proxy", "")
        sender = TaskService(f"http://127.0.0.1:{server.server_port}", PROJECT_ID, 2, project_root=tmp_path)
        with pytest.raises(TaskServiceError) as failure:
            sender.create_task(payload())
        assert failure.value.status_code == 502
        assert received == [{**payload(), "project_id": PROJECT_ID}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_failed_upstream_error_body_read_still_returns_a_safe_rejection():
    sender = service()
    broken = Mock()
    broken.read.side_effect = IncompleteRead(b"partial")
    sender._opener.open.side_effect = HTTPError("http://localhost/", 422, "rejected", {}, broken)
    with pytest.raises(TaskServiceError) as failure:
        sender.create_task(payload())
    assert failure.value.status_code == 422 and str(failure.value) == "Kanban rejected the report."
