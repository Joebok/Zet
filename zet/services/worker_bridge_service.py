"""Private loopback credential bridge; no model execution or production actions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

from zet.services.atomic_file_service import write_json_atomic
from zet.services.github_client import TaskServiceError


class WorkerBridgeService:
    def __init__(self, task, usage, *, pilot_base=None):
        self.task, self.usage = task, usage
        self.token = secrets.token_urlsafe(32)
        self.registry = task.store.root / "worker-bridge.json"
        self.pilot_base = pilot_base

    def publish(self, port, boot_id):
        write_json_atomic(self.registry, {"url": f"http://127.0.0.1:{int(port)}", "token": self.token,
                                         "repository": self.task.repository, "boot_id": boot_id})

    def close(self):
        if self.registry.exists() and json.loads(self.registry.read_text(encoding="utf-8")).get("token") == self.token:
            self.registry.unlink()

    def claim(self, token):
        # Read without BEGIN IMMEDIATE: the caller may hold the coordination write lock.
        with sqlite3.connect(self.task.store.path, timeout=20) as db:
            row = db.execute("SELECT payload FROM records WHERE scope='worker' AND key=?", (self.task.repository,)).fetchone()
        claim = json.loads(row[0]) if row else None
        if not claim or not token or not hmac.compare_digest(claim["token"], token):
            raise TaskServiceError("The bridge request does not own the retained worker claim.", 409)
        return claim

    @staticmethod
    def git(root, *args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=120,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise TaskServiceError("The scoped Git delivery operation failed; retained work was not removed.", 503)
        return result.stdout.strip()

    def validated(self, token, *, require_validation=True):
        claim = self.claim(token)
        root = Path(claim["worktree"]).resolve()
        if not (root / ".git").is_file():
            raise TaskServiceError("Delivery requires the claimed isolated worktree.", 409)
        if claim["state"] != "in-progress":
            raise TaskServiceError("Delivery requires the active issue claim.", 409)
        if require_validation and not claim.get("validation", {}).get("passed"):
            raise TaskServiceError("Ready delivery requires a successful current-revision validation checkpoint.", 409)
        if not re.fullmatch(rf"codex/issue-{claim['issue_number']}-[a-z0-9-]+", claim["branch"]):
            raise TaskServiceError("The issue branch differs from the authorized claim.", 409)
        return claim

    def execute(self, action, payload, authorization, peer):
        if peer not in {"127.0.0.1", "::1"} or not hmac.compare_digest(authorization, "Bearer " + self.token):
            raise TaskServiceError("Worker actions require the private local bridge credential.", 403)
        if action == "usage":
            return self.usage.read_account()
        if action == "github":
            path, method = payload.get("path", ""), payload.get("method", "GET")
            parsed = urlsplit(path)
            allowed = re.fullmatch(r"/(?:issues(?:/\d+(?:/(?:labels|comments|dependencies/blocked_by))?)?|pulls(?:/\d+(?:/reviews)?)?|git/matching-refs/heads/codex/issue-\d+|commits/main)", parsed.path)
            if not allowed or parsed.scheme or parsed.netloc or method not in {"GET", "POST", "PUT"}:
                raise TaskServiceError("This GitHub operation is outside the worker bridge scope.", 403)
            if method != "GET":
                claim = self.claim(payload.get("claim_token", ""))
                expected = f"/issues/{claim['issue_number']}/"
                if parsed.path != expected + ("comments" if method == "POST" else "labels"):
                    raise TaskServiceError("Writes are limited to the claimed issue's comments and labels.", 403)
            return self.task.github.repo_api(path, method=method, payload=payload.get("payload"), paginate=payload.get("paginate", False))
        if action == "deliver":
            claim = self.validated(payload.get("claim_token", ""), require_validation=False)
            base = payload.get("base", "main")
            if base not in {"main", self.pilot_base}:
                raise TaskServiceError("This PR base is not authorized by the bridge.", 403)
            content = base64.b64decode(payload.get("bundle", ""), validate=True)
            if not content or len(content) > 25 * 1024 * 1024:
                raise TaskServiceError("The scoped delivery bundle exceeds 25 MiB or is empty.", 413)
            # Never execute git in an agent-controlled repository with host credentials:
            # local hooks/config could otherwise escape the worker sandbox.
            private_root = self.task.store.root.parent / "WorkerTransfers"
            private_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="delivery-", dir=private_root) as folder:
                transfer = Path(folder)
                if transfer.resolve().parent != private_root.resolve():
                    raise TaskServiceError("The private transfer escaped its owned directory.", 403)
                bundle = transfer / "change.bundle"
                bundle.write_bytes(content)
                bare = transfer / "repo.git"
                bare.mkdir()
                self.git(bare, "init", "--bare")
                remote = f"https://github.com/{self.task.repository}.git"
                self.git(bare, "fetch", "--no-tags", remote, base)
                heads = self.git(bare, "bundle", "list-heads", str(bundle))
                expected = f"{payload.get('revision')} refs/heads/{claim['branch']}"
                if heads != expected:
                    raise TaskServiceError("The delivery bundle does not contain exactly the claimed branch/revision.", 409)
                self.git(bare, "fetch", str(bundle), f"refs/heads/{claim['branch']}:refs/heads/{claim['branch']}")
                self.git(bare, "push", remote, f"refs/heads/{claim['branch']}:refs/heads/{claim['branch']}")
            existing = [pr for pr in self.task.github.pulls() if pr["head"]["ref"] == claim["branch"]]
            if existing:
                pr = existing[0]
                if not pr.get("draft"):
                    result = subprocess.run([shutil.which("gh"), "pr", "ready", str(pr["number"]), "--undo", "--repo", self.task.repository], capture_output=True, text=True, timeout=30,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if result.returncode:
                        raise TaskServiceError("GitHub could not return the retained PR to draft.", 503)
            else:
                body = payload.get("body", "")
                if f"Closes #{claim['issue_number']}" not in body:
                    raise TaskServiceError("The PR must close the claimed issue.", 422)
                pr = self.task.github.repo_api("/pulls", method="POST", payload={"title": payload["title"], "body": body,
                                               "head": claim["branch"], "base": base, "draft": True})
            return {"number": pr["number"], "url": pr["html_url"]}
        if action == "ready":
            claim = self.validated(payload.get("claim_token", ""))
            number = int(payload["pr_number"])
            pr = self.task.github.repo_api(f"/pulls/{number}")
            if pr["head"]["ref"] != claim["branch"] or pr["head"]["sha"] != claim["validation"]["revision"]:
                raise TaskServiceError("The PR does not contain the validated claim revision.", 409)
            result = subprocess.run([shutil.which("gh"), "pr", "ready", str(number), "--repo", self.task.repository],
                                    capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise TaskServiceError("GitHub could not mark the scoped PR ready.", 503)
            return {"number": number, "url": pr["html_url"]}
        if action == "evidence":
            claim = self.claim(payload.get("claim_token", ""))
            url = payload["url"]
            pattern = rf"https://raw\.githubusercontent\.com/{re.escape(self.task.repository)}/[0-9a-f]{{40}}/captures/[A-Za-z0-9_-]+/([0-9a-f]{{64}})\.(png|jpe?g|webp)"
            match = re.fullmatch(pattern, url)
            if not match:
                raise TaskServiceError("Evidence download requires this repository's pinned capture URL.", 403)
            issue = self.task.github.repo_api(f"/issues/{claim['issue_number']}")
            comments = self.task.github.repo_api(f"/issues/{claim['issue_number']}/comments?per_page=100", paginate=True)
            if url not in (issue.get("body") or "") and not any(url in (comment.get("body") or "") for comment in comments):
                raise TaskServiceError("The evidence URL is absent from the claimed report.", 403)
            with urlopen(url, timeout=20) as response:
                content = response.read(5 * 1024 * 1024 + 1)
                if urlsplit(response.geturl()).hostname != "raw.githubusercontent.com":
                    raise TaskServiceError("Evidence redirected outside GitHub capture storage.", 403)
            if len(content) > 5 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != match[1]:
                raise TaskServiceError("Evidence bytes differ from the captured hash or size limit.", 409)
            return {"content_base64": base64.b64encode(content).decode(), "sha256": match[1]}
        raise TaskServiceError("Unsupported worker action.", 404)
