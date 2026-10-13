"""Deterministic issue selection and fenced checkpoints; Codex does the coding."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from uuid import uuid4

from zet.services.github_client import TaskServiceError


WORKFLOW_LABELS = {"codex-ready", "in-progress", "needs-input", "needs-review"}


def labels(issue):
    return {item["name"] for item in issue.get("labels", [])}


def timestamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0


class IssueWorkerService:
    def __init__(self, github, store, usage, trusted_users=("Joebok",)):
        self.github, self.store, self.usage = github, store, usage
        self.trusted = {user.casefold() for user in trusted_users}

    def transition(self, number, state):
        issue = self.github.repo_api(f"/issues/{number}")
        desired = sorted((labels(issue) - WORKFLOW_LABELS) | {state})
        self.github.repo_api(f"/issues/{number}/labels", method="PUT", payload={"labels": desired})

    def claim(self, worktree):
        now = time.time()
        self.store.put("status", "worker", {"checked_at": now, "state": "checking", "error": None})
        quota = self.usage.refresh()
        if not quota["allowed"]:
            self.store.put("status", "worker", {"checked_at": now, "state": "usage-wait", "error": quota.get("error")})
            return {"state": "usage-wait", "usage": quota}
        with self.store.transaction() as db:
            active = self.store.read(db, "worker", self.github.repository)
            if active and active.get("state") == "in-progress":
                return {"state": "busy", "claim": active, "stale": now - active["updated_at"] > 3600}
            issues, pulls = self.github.issues(), self.github.pulls()
            claims = {key: value for key, payload in db.execute("SELECT key,payload FROM records WHERE scope='issue-work'")
                      for value in [json.loads(payload)]}
            def previous(number):
                return claims.get(f"{self.github.repository}#{number}")
            def associated(issue):
                pattern = rf"(?i)(?:closes|fixes|resolves)\s+(?:{re.escape(self.github.repository)}#|#){issue['number']}\b"
                return [pr for pr in pulls if re.match(rf"codex/issue-{issue['number']}(?:-|$)", pr["head"]["ref"]) or re.search(pattern, pr.get("body") or "")]
            candidates = []
            for issue in issues:
                number, state = issue["number"], labels(issue)
                old = previous(number)
                linked = associated(issue)
                if "in-progress" in state:
                    if old and old.get("state") == "usage-wait":
                        candidates.append((0, issue, old, "resume"))
                        continue
                    return {"state": "attention", "reason": f"Issue #{number} has an unresolved claim. Inspect its work before recovery."}
                if old and "needs-input" in state:
                    comments = self.github.repo_api(f"/issues/{number}/comments?per_page=100", paginate=True)
                    answers = [comment for comment in comments if comment["user"]["login"].casefold() in self.trusted
                               and "<!-- zet-worker-checkpoint -->" not in (comment.get("body") or "")
                               and (comment.get("id", 0) > old["question_comment_id"] if old.get("question_comment_id") else timestamp(comment["created_at"]) > old["updated_at"])]
                    if answers:
                        candidates.append((0, issue, old, "resume"))
                    continue
                if old and "needs-review" in state and linked:
                    reviews = self.github.repo_api(f"/pulls/{linked[0]['number']}/reviews?per_page=100", paginate=True)
                    if any(review["state"] == "CHANGES_REQUESTED" and review["user"]["login"].casefold() in self.trusted
                           and timestamp(review.get("submitted_at")) > old["updated_at"] for review in reviews):
                        candidates.append((0, issue, old, "review-feedback"))
                    continue
                if "codex-ready" not in state or issue.get("assignees") or linked:
                    continue
                dependencies = self.github.repo_api(f"/issues/{number}/dependencies/blocked_by?per_page=100", paginate=True)
                if any(item.get("state") == "open" for item in dependencies):
                    continue
                if old:
                    candidates.append((0, issue, old, "resume"))
                    continue
                refs = self.github.repo_api(f"/git/matching-refs/heads/codex/issue-{number}")
                if any(re.match(rf"refs/heads/codex/issue-{number}(?:-|$)", ref["ref"]) for ref in refs):
                    continue
                priorities = [int(item[9:]) for item in state if re.fullmatch(r"priority:\d+", item)]
                candidates.append((1 + min(priorities, default=1000), issue, None, "new"))
            if not candidates:
                self.store.write(db, "status", "worker", {"checked_at": now, "state": "idle", "error": None})
                return {"state": "idle"}
            _, issue, old, mode = min(candidates, key=lambda item: (item[0], item[1]["created_at"]))
            slug = re.sub(r"[^a-z0-9]+", "-", issue["title"].lower()).strip("-")[:50] or "task"
            claim = {"token": uuid4().hex, "repository": self.github.repository, "issue_number": issue["number"],
                     "branch": old["branch"] if old else f"codex/issue-{issue['number']}-{slug}",
                     "worktree": old["worktree"] if old else str(worktree), "mode": mode,
                     "state": "in-progress", "updated_at": now}
            self.store.write(db, "worker", self.github.repository, claim)
            self.store.write(db, "issue-work", f"{self.github.repository}#{issue['number']}", claim)
            db.commit()  # A failed label update leaves a visible fenced claim, never a second worker.
            self.transition(issue["number"], "in-progress")
            return {"state": "claimed", "claim": claim, "issue": issue}

    def checkpoint(self, token, state, message="", pr_number=None):
        if state not in {"in-progress", "needs-input", "needs-review", "stopped", "usage-wait"}:
            raise TaskServiceError("Unsupported worker checkpoint.", 422)
        with self.store.transaction() as db:
            claim = self.store.read(db, "worker", self.github.repository)
            if not claim or claim["token"] != token:
                raise TaskServiceError("This worker no longer owns the issue claim.", 409)
            if state == "needs-review":
                validation = claim.get("validation", {})
                revision = subprocess.run(["git", "-C", claim["worktree"], "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
                dirty = subprocess.run(["git", "-C", claim["worktree"], "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
                if not validation.get("passed") or validation.get("revision") != revision or dirty:
                    raise TaskServiceError("Commit the scoped change and run the worker validation command at this revision before delivery.", 409)
                if not pr_number:
                    raise TaskServiceError("A validated ready PR number is required.", 422)
                pr = self.github.repo_api(f"/pulls/{pr_number}")
                if pr.get("draft") or pr["head"]["ref"] != claim["branch"] or pr["head"].get("sha") != revision or pr.get("state") != "open":
                    raise TaskServiceError("The PR must be ready, open and on the claimed issue branch.", 409)
            if message and state not in {"in-progress", "usage-wait"}:
                comment = self.github.repo_api(f"/issues/{claim['issue_number']}/comments", method="POST", payload={"body": "<!-- zet-worker-checkpoint -->\n\n" + message})
                if state == "needs-input" and comment.get("id"):
                    claim["question_comment_id"] = comment["id"]
            if state in WORKFLOW_LABELS:
                self.transition(claim["issue_number"], state)
            claim.update(state=state, updated_at=time.time(), pr_number=pr_number or claim.get("pr_number"))
            self.store.write(db, "worker", self.github.repository, claim)
            self.store.write(db, "issue-work", f"{self.github.repository}#{claim['issue_number']}", claim)
            self.store.write(db, "status", "worker", {"checked_at": time.time(), "state": state, "error": message if state == "stopped" else None})
            return claim

    def validate(self, token):
        from zet.scripts.deploy_release import test_lock
        claim = self.store.get("worker", self.github.repository)
        if not claim or claim["token"] != token or claim["state"] != "in-progress":
            raise TaskServiceError("Validation requires the current active claim.", 409)
        root = Path(claim["worktree"])
        self.checkpoint(token, "in-progress")
        command = ["cmd.exe", "/d", "/c", "npm.cmd run test:e2e"] if os.name == "nt" else ["npm", "run", "test:e2e"]
        env = os.environ.copy()
        env.setdefault("npm_config_cache", str(root / "test-results" / "npm-cache"))
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(root / "test-results" / "playwright-browsers"))
        python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if python.exists():
            subprocess.run([str(python), "-c", "import sys; assert sys.version_info.major == 3"], check=True, timeout=10)
            env["ZET_TEST_PYTHON"] = str(python)
        with test_lock(self.store.root):
            try:
                result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired as exc:
                def decoded(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                result = subprocess.CompletedProcess(command, 124, decoded(exc.stdout), decoded(exc.stderr) + "\nApproved baseline timed out; retained output follows.\n")
        diff = subprocess.run(["git", "diff", "--check"], cwd=root, capture_output=True, text=True)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        log = root / "test-results" / "issue-worker-validation.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout + result.stderr + diff.stdout + diff.stderr, encoding="utf-8")
        validation = {"passed": result.returncode == 0 and diff.returncode == 0, "revision": revision,
                      "command": "npm run test:e2e; git diff --check", "checked_at": time.time(), "log": str(log)}
        with self.store.transaction() as db:
            current = self.store.read(db, "worker", self.github.repository)
            if not current or current["token"] != token:
                raise TaskServiceError("The validation result belongs to a superseded claim.", 409)
            current.update(validation=validation, updated_at=time.time())
            self.store.write(db, "worker", self.github.repository, current)
            self.store.write(db, "issue-work", f"{self.github.repository}#{claim['issue_number']}", current)
        return validation

    def recover(self, token):
        # Explicit operator action only; a timer never takes ownership from a possibly live agent.
        with self.store.transaction() as db:
            claim = self.store.read(db, "worker", self.github.repository)
            if not claim or claim["token"] != token:
                raise TaskServiceError("Recovery token does not match the retained claim.", 409)
            self.transition(claim["issue_number"], "needs-input")
            claim.update(state="needs-input", updated_at=time.time())
            self.store.write(db, "worker", self.github.repository, claim)
            self.store.write(db, "issue-work", f"{self.github.repository}#{claim['issue_number']}", claim)
            return claim
