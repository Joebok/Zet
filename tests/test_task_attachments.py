import base64
import hashlib
import json
from types import SimpleNamespace
from urllib.error import URLError

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from zet.services.task_service import MAX_SCREENSHOT_BYTES, MAX_SCREENSHOT_REQUEST_BYTES, TaskServiceError
from zet.web.task_router import create_task_router
from test_task_service import PROJECT_ID, Reply, payload, service


PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII="
ATTACHMENT_ID = "attachment-" + "a" * 32


def upload():
    return dict(request_id="capture-1", project_id=PROJECT_ID, filename="screen.png",
                content_type="image/png", content_base64=PNG)


def receipt(created=True):
    content = base64.b64decode(PNG)
    return dict(attachment_id=ATTACHMENT_ID, filename="screen.png", content_type="image/png",
                size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), created=created)


def test_upload_retries_preserve_bytes_binding_and_verified_receipt():
    sender = service()
    sender._opener.open.side_effect = [URLError("offline"), Reply(receipt(False), 200)]
    original = upload()
    with pytest.raises(TaskServiceError) as error:
        sender.upload_task_attachment(original)
    assert error.value.status_code == 503
    assert sender.upload_task_attachment(original) == receipt(False)
    requests = [call.args[0] for call in sender._opener.open.call_args_list]
    assert requests[0].full_url.endswith("/api/v1/attachments")
    assert requests[0].data == requests[1].data
    assert json.loads(requests[0].data) == original == upload()


@pytest.mark.parametrize("change,status", [
    ({"project_id": "project-bbbbbbbb"}, 409), ({"request_id": " bad "}, 422),
    ({"filename": "../screen.png"}, 422), ({"filename": "screen.jpg"}, 422),
    ({"content_type": "image/svg+xml"}, 422), ({"content_base64": "invalid"}, 422),
    ({"content_base64": ""}, 422), ({"content_base64": "a" * (4 * ((MAX_SCREENSHOT_BYTES + 2) // 3) + 1)}, 413),
    ({"unexpected": True}, 422),
])
def test_bad_uploads_are_rejected_without_contacting_kanban(change, status):
    sender = service()
    with pytest.raises(TaskServiceError) as error:
        sender.upload_task_attachment({**upload(), **change})
    assert error.value.status_code == status
    sender._opener.open.assert_not_called()


@pytest.mark.parametrize("change", [dict(sha256="b" * 64), dict(size_bytes=True), dict(filename="other.png"),
                                    dict(attachment_id="bad"), dict(created=False)])
def test_invalid_upload_receipt_does_not_claim_success(change):
    sender = service()
    sender._opener.open.return_value = Reply({**receipt(), **change})
    with pytest.raises(TaskServiceError, match="invalid screenshot receipt"):
        sender.upload_task_attachment(upload())


def test_intake_forwards_only_valid_unique_attachment_references():
    sender = service()
    sender.create_task({**payload(), "attachment_ids": [ATTACHMENT_ID]})
    assert json.loads(sender._opener.open.call_args.args[0].data)["attachment_ids"] == [ATTACHMENT_ID]
    for value in [[ATTACHMENT_ID, ATTACHMENT_ID], ["unknown"], "not-a-list", [ATTACHMENT_ID] * 5]:
        sender._opener.open.reset_mock()
        with pytest.raises(TaskServiceError):
            sender.create_task({**payload(), "attachment_ids": value})
        sender._opener.open.assert_not_called()


def test_upload_router_bounds_stream_and_preserves_creation_replay_and_timeout():
    sender = service()
    app = FastAPI()
    app.include_router(create_task_router(lambda: SimpleNamespace(upload_task_attachment=sender.upload_task_attachment)))
    client = TestClient(app)
    sender._opener.open.return_value = Reply(receipt())
    assert client.post("/api/tasks/attachments", json=upload()).status_code == 201
    sender._opener.open.return_value = Reply(receipt(False), 200)
    assert client.post("/api/tasks/attachments", json=upload()).status_code == 200
    sender._opener.open.side_effect = TimeoutError()
    assert client.post("/api/tasks/attachments", json=upload()).status_code == 504
    sender._opener.open.reset_mock()
    assert client.post("/api/tasks/attachments", content=b"bad", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/tasks/attachments", content=b"text").status_code == 415
    assert client.post("/api/tasks/attachments", content=b"x" * (MAX_SCREENSHOT_REQUEST_BYTES + 1),
                       headers={"Content-Type": "application/json", "Content-Length": "1"}).status_code == 413
    sender._opener.open.assert_not_called()
