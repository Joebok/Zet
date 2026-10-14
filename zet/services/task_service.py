"""Publish frozen Zet reports as GitHub issues with durable delivery receipts."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote

from PIL import Image

from zet.repositories.task_workflow_repository import TaskWorkflowRepository
from zet.services.github_client import GitHubClient, TaskServiceError
from zet.services.task_report_service import format_report, marker, request_id, validate_report, validate_repository


MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
MAX_SCREENSHOT_REQUEST_BYTES = 7 * 1024 * 1024
ATTACHMENT_ID = r"attachment-[0-9a-f]{32}"
EVIDENCE_BRANCH = "codex/issue-evidence"


class TaskService:
    def __init__(self, repository: str, timeout_seconds: float = 20, *, project_root: Path, state_root: Path, github=None):
        self.repository = validate_repository(repository)
        self.github = github or GitHubClient(repository, timeout_seconds)
        self.store = TaskWorkflowRepository(state_root)
        self.zet_revision = self._revision(project_root)
        self.zet_revision_at = self._revision_timestamp(project_root, self.zet_revision)

    @staticmethod
    def _revision(project_root):
        try:
            result = subprocess.run(["git", "-C", str(project_root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2)
            value = result.stdout.strip()
            return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def _revision_timestamp(project_root, revision):
        if not revision:
            return None
        try:
            result = subprocess.run(
                ["git", "-C", str(project_root), "show", "-s", "--format=%cI", revision],
                capture_output=True,
                text=True,
                timeout=2,
            )
            value = result.stdout.strip()
            return value if result.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", value) else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    def metadata(self):
        return {"configured": bool(self.repository), "repository": self.repository,
                "issues_url": f"https://github.com/{self.repository}/issues" if self.repository else None,
                "report_context_version": 1, "zet_revision": self.zet_revision}

    def require_configured(self):
        if not self.repository:
            raise TaskServiceError("Set GitHub.Repository on the Zet host. Your draft is retained.")

    def _evidence(self, report):
        result = []
        for attachment_id in report["attachment_ids"]:
            item = self.store.get("attachments", attachment_id)
            if not item or item["repository"] != self.repository or item["request_id"] != report["request_id"]:
                raise TaskServiceError("Screenshot receipt does not belong to this report.", 409)
            result.append(item)
        return result

    def preview(self, payload):
        self.require_configured()
        report = validate_report(payload, self.repository)
        return {"body": format_report(report), "repository": self.repository}

    def create_task(self, payload):
        self.require_configured()
        report = validate_report(payload, self.repository)
        evidence = self._evidence(report)
        body = format_report(report, evidence)
        if len(body) > 60000:
            raise TaskServiceError("The issue preview is too long; shorten this draft before submission.", 413)
        digest = hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()
        key = report["request_id"]
        with self.store.transaction() as db:
            existing = self.store.read(db, "captures", key)
            if existing and (existing["hash"] != digest or existing["repository"] != self.repository):
                raise TaskServiceError("This request ID is bound to a different frozen report or repository.", 409)
            if existing and existing.get("receipt"):
                return dict(existing["receipt"], created=False)
            if existing and existing.get("uncertain"):
                matches = [item for item in self.github.issues("all") if marker(report) in (item.get("body") or "")]
                if len(matches) != 1:
                    raise TaskServiceError("Delivery is still uncertain. No new issue was created; retain this draft and retry reconciliation.", 409)
                issue = matches[0]
                if issue.get("body") != body or issue.get("title") != report["title"]:
                    raise TaskServiceError("The recovered GitHub issue was edited; inspect it before reconciling this frozen draft.", 409)
                created = False
            else:
                # Commit BEFORE the external write. A crash can never cause a blind repost.
                self.store.write(db, "captures", key, {"repository": self.repository, "hash": digest, "uncertain": True, "attempted_at": time.time()})
                db.commit()
                try:
                    issue = self.github.repo_api("/issues", method="POST", payload={"title": report["title"], "body": body,
                                                    "labels": ["bug" if report["type"] == "bug" else "enhancement"]})
                except TaskServiceError as exc:
                    if exc.status_code in {400, 401, 403, 404, 422}:
                        db.execute("BEGIN IMMEDIATE")
                        self.store.write(db, "captures", key, {"repository": self.repository, "hash": digest, "uncertain": False})
                        db.commit()
                    raise
                created = True
                db.execute("BEGIN IMMEDIATE")
            number = issue.get("number") if isinstance(issue, dict) else None
            if type(number) is not int or number < 1 or issue.get("html_url") != f"https://github.com/{self.repository}/issues/{number}":
                raise TaskServiceError("GitHub returned an invalid issue receipt; reconcile the saved draft.", 502)
            if report["start_codex"]:
                self.github.repo_api(f"/issues/{number}/labels", method="POST", payload={"labels": ["codex-ready"]})
            receipt = {"repository": self.repository, "issue_number": number, "issue_url": issue["html_url"], "created": created}
            self.store.write(db, "captures", key, {"repository": self.repository, "hash": digest, "receipt": receipt})
            return receipt

    def upload_task_attachment(self, payload):
        self.require_configured()
        if not isinstance(payload, dict) or set(payload) != {"request_id", "repository", "filename", "content_type", "content_base64"}:
            raise TaskServiceError("Expected request, repository, filename, image type and encoded screenshot.", 422)
        request_id(payload["request_id"])
        if payload["repository"] != self.repository:
            raise TaskServiceError("Screenshot repository differs from its frozen draft.", 409)
        name, mime, encoded = (payload[key] for key in ("filename", "content_type", "content_base64"))
        types = {"image/png": ("PNG", {".png"}), "image/jpeg": ("JPEG", {".jpg", ".jpeg"}), "image/webp": ("WEBP", {".webp"})}
        if not isinstance(name, str) or not name.strip() or len(name) > 240 or re.search(r"[\\/\x00-\x1f\x7f]", name) or not isinstance(mime, str) or mime not in types or Path(name).suffix.lower() not in types[mime][1]:
            raise TaskServiceError("Choose PNG, JPEG or WebP with a matching plain filename.", 422)
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_SCREENSHOT_BYTES + 2) // 3):
            raise TaskServiceError("Screenshots must be at most 5 MiB.", 413)
        try:
            content = base64.b64decode(encoded, validate=True)
            if not content or len(content) > MAX_SCREENSHOT_BYTES:
                raise ValueError()
            with Image.open(io.BytesIO(content)) as image:
                if image.format != types[mime][0]:
                    raise ValueError()
                image.verify()
        except (ValueError, OSError, Image.DecompressionBombError) as exc:
            raise TaskServiceError("Screenshot bytes must be a valid image matching its filename and MIME type.", 422) from exc
        digest = hashlib.sha256(content).hexdigest()
        identity = hashlib.sha256(f"{self.repository}:{payload['request_id']}:{name}:{digest}".encode()).hexdigest()[:32]
        attachment_id = "attachment-" + identity
        with self.store.transaction() as db:
            receipt = self.store.read(db, "attachments", attachment_id)
            if receipt:
                return dict(receipt, created=False)
            bound = [json.loads(row[0]) for row in db.execute("SELECT payload FROM records WHERE scope='attachments'")]
            if sum(item["request_id"] == payload["request_id"] for item in bound) >= 4:
                raise TaskServiceError("This report already has four staged screenshots.", 422)
            branch = quote(EVIDENCE_BRANCH, safe="")
            try:
                self.github.repo_api(f"/git/ref/heads/{branch}")
            except TaskServiceError as exc:
                if exc.status_code != 404:
                    raise
                repo = self.github.repo_api()
                head = self.github.repo_api(f"/git/ref/heads/{quote(repo['default_branch'], safe='')}")
                self.github.repo_api("/git/refs", method="POST", payload={"ref": f"refs/heads/{EVIDENCE_BRANCH}", "sha": head["object"]["sha"]})
            path = f"captures/{payload['request_id']}/{digest}{Path(name).suffix.lower()}"
            endpoint = f"/contents/{path}"
            try:
                existing = self.github.repo_api(endpoint + "?ref=" + branch)
                uploaded = {"commit": {"sha": self.github.repo_api(f"/git/ref/heads/{branch}")["object"]["sha"]}, "content": existing}
                blob_sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
                if existing.get("sha") != blob_sha:
                    raise TaskServiceError("Existing screenshot bytes do not match their content address.", 409)
            except TaskServiceError as exc:
                if exc.status_code != 404:
                    raise
                uploaded = self.github.repo_api(endpoint, method="PUT", payload={"message": f"Capture evidence {payload['request_id']}",
                                                    "branch": EVIDENCE_BRANCH, "content": encoded})
            sha = uploaded["commit"]["sha"]
            receipt = {"attachment_id": attachment_id, "request_id": payload["request_id"], "repository": self.repository,
                       "filename": name, "content_type": mime, "size_bytes": len(content), "sha256": digest,
                       "url": f"https://raw.githubusercontent.com/{self.repository}/{sha}/{path}", "created": True}
            self.store.write(db, "attachments", attachment_id, receipt)
            return receipt
