"""Server-side GitHub API transport using the existing authenticated gh CLI."""
from __future__ import annotations

import json
import re
import shutil
import subprocess


class TaskServiceError(ValueError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    def __init__(self, repository: str, timeout: float = 20):
        self.repository = repository
        self.timeout = timeout
        self.runner = subprocess.run

    def api(self, path: str, *, method: str = "GET", payload=None, paginate: bool = False):
        executable = shutil.which("gh")
        if not executable:
            raise TaskServiceError("GitHub CLI is unavailable. Install/sign in to gh on the Zet host.")
        command = [executable, "api", path, "--method", method,
                   "-H", "Accept: application/vnd.github+json"]
        if paginate:
            command += ["--paginate", "--slurp"]
        if payload is not None:
            command += ["--input", "-"]
        try:
            result = self.runner(command, input=json.dumps(payload, allow_nan=False) if payload is not None else None,
                                 capture_output=True, text=True, encoding="utf-8", timeout=self.timeout,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TaskServiceError("GitHub delivery is uncertain or unavailable. Keep the draft and reconcile on retry.", 504) from exc
        if result.returncode:
            status = re.search(r"HTTP (\d{3})", result.stderr or "")
            code = int(status[1]) if status else 503
            if "gh auth login" in (result.stderr or ""):
                code = 401
            message = {401: "GitHub authentication expired; sign in on the Zet host.",
                       403: "GitHub permission or rate limit prevents this action.",
                       429: "GitHub rate limit reached. Keep the draft and retry after capacity resets.",
                       404: "The configured GitHub resource is unavailable.",
                       409: "GitHub changed concurrently; retry the saved request.",
                       422: "GitHub rejected this action; verify repository settings and labels."}.get(code,
                       "GitHub is unavailable; keep the draft and retry.")
            raise TaskServiceError(message, code)
        try:
            value = json.loads(result.stdout) if result.stdout.strip() else None
        except ValueError as exc:
            raise TaskServiceError("GitHub returned an unreadable response; keep the draft.", 502) from exc
        if paginate:
            return [item for page in value for item in page]
        return value

    def repo_api(self, suffix: str = "", **kwargs):
        return self.api(f"repos/{self.repository}{suffix}", **kwargs)

    def issues(self, state="open"):
        return [item for item in self.repo_api(f"/issues?state={state}&per_page=100", paginate=True)
                if "pull_request" not in item]

    def pulls(self, state="open"):
        return self.repo_api(f"/pulls?state={state}&per_page=100", paginate=True)
