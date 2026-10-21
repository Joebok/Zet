"""Explicit, durable publication of production's accepted governing templates."""
import base64
import json
from pathlib import Path
import shutil
import sys
import threading
import time
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.github_client import TaskServiceError
from zet.services.template_publication_core import BUSY, canonical, change_lock, digest, git, inspect


class TemplatePublicationService:
    def __init__(self, app):
        self.app = app
        self.state = Path(app.config.runtime_root).resolve() / "state" if app.config.runtime_root else None
        self.github = app.task_service.github

    @property
    def root(self):
        return self.app.process_service.project_root.resolve()

    @property
    def path(self):
        return self.state / "template-publication.json"

    def require_enabled(self):
        if not self.state or self.app.config.runtime_role == "development":
            raise TaskServiceError("Template publication requires a configured production runtime.", 409)
        for parent in (self.state.parent, *self.state.parent.parents):
            if (parent / ".git").exists():
                raise TaskServiceError("Runtime.Root must be outside Git working trees.", 409)
        for value in (self.app.config.base_library_path, self.app.config.base_ai_queue_path):
            data = Path(value).resolve()
            if self.state.parent == data or data in self.state.parent.parents or self.state.parent in data.parents:
                raise TaskServiceError("Runtime.Root must not overlap the creative library or queue.", 409)

    def record(self):
        if not self.state or not self.path.exists():
            return {}
        record = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("version") != 1:
            raise TaskServiceError("Unsupported template-publication receipt; retain it for inspection.", 409)
        return record

    def save(self, record, *, new=False, **values):
        record.update(values, updated_at=time.time())
        with change_lock(self.state):
            # Retain receipts/snapshots even when a later publication becomes current.
            write_json_atomic(self.state / "template-publications" / record["id"] / "receipt.json", record)
            current = self.record()
            if new or not current or current.get("id") == record["id"]:
                write_json_atomic(self.path, record)

    @staticmethod
    def public(record):
        return {key: record[key] for key in ("id", "state", "branch", "commit", "pr_number", "pr_url",
                "error", "updated_at", "newer_edits", "validation") if key in record}

    def preview(self):
        self.require_enabled()
        report = inspect(self.root)
        record = self.record()
        if record.get("source_root") != report["root"]:
            record = {}
        captured = {row["path"]: row for row in record.get("files", [])}
        for row in report["files"]:
            row["reconciled"] = (record.get("state") == "ready" and record.get("source_root") == report["root"]
                                 and record.get("source_revision") == report["revision"] and row["eligible"]
                                 and row["raw_sha256"] == captured.get(row["path"], {}).get("raw_sha256"))
        return {**report, "publication": self.public(record)}

    def status(self):
        if not self.state or self.app.config.runtime_role == "development":
            return {"files": [], "publication": {}}
        try:
            report = self.preview()
            for row in report["files"]:
                row.pop("diff", None)
            return report
        except (ValueError, OSError) as exc:
            return {"files": [], "publication": {}, "error": str(exc)}

    def _deployment_busy(self):
        current = self.app.task_service.store.get("deployment", "current", {})
        if current.get("status_path") and Path(current["status_path"]).is_file():
            current = json.loads(Path(current["status_path"]).read_text(encoding="utf-8"))
        return current.get("state") in {"pending", "staging", "validating", "restarting"}

    def start(self, payload):
        self.require_enabled()
        self.app.task_service.require_configured()
        with change_lock(self.state):
            if self._deployment_busy():
                raise TaskServiceError("An update is active; finish or inspect it before publishing templates.", 409)
            current = self.record()
            if current.get("state") in BUSY | {"awaiting-merge"}:
                raise TaskServiceError("A retained template publication exists. Refresh or retry it first.", 409)
            report = inspect(self.root)
            if payload.get("snapshot_id") != report["snapshot_id"]:
                raise TaskServiceError("Local edits changed. Reload and review the current diff.", 409)
            paths = payload.get("paths")
            allowed = {row["path"]: row for row in report["files"] if row["eligible"]}
            if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or p not in allowed for p in paths) or len(set(paths)) != len(paths):
                raise TaskServiceError("Select modified governing templates from the current preview.", 400)
            previous = {row["path"]: row for row in current.get("files", [])}
            if (current.get("state") == "ready" and current.get("source_root") == report["root"]
                    and current.get("source_revision") == report["revision"]
                    and all(allowed[path]["raw_sha256"] == previous.get(path, {}).get("raw_sha256") for path in paths)):
                return self.public(current)
            files = []
            for path in paths:
                raw = (self.root / path).read_bytes()
                if digest(raw) != allowed[path]["raw_sha256"]:
                    raise TaskServiceError("A template changed while capturing it. Review again.", 409)
                if len(raw) > 2 * 1024 * 1024:
                    raise TaskServiceError("Template exceeds the 2 MiB publication limit.", 413)
                files.append({"path": path, "raw_sha256": digest(raw), "content": base64.b64encode(raw).decode()})
            identifier = uuid4().hex
            record = {"version": 1, "id": identifier, "state": "preparing", "branch": f"codex/template-edits-{identifier}",
                      "source_root": str(self.root), "source_revision": report["revision"],
                      "repository": self.app.task_service.repository, "files": files}
            # Freeze a patch from captured bytes, never from a subsequently changed live index.
            self.save(record, new=True)
            self._launch(identifier)
            return self.public(record)

    def retry(self, identifier):
        self.require_enabled()
        with change_lock(self.state):
            record = self._owned(identifier)
            if self._deployment_busy():
                raise TaskServiceError("An update is active; retry after it finishes.", 409)
            if record.get("state") in {"awaiting-merge", "ready", "closed"}:
                raise TaskServiceError("Check merge status for this PR; it does not need publication retry.", 409)
            try:
                with change_lock(self.state / "template-publications" / identifier, timeout=.01):
                    self.save(record, state="preparing", error="")
            except ValueError:
                return self.public(self.record())
            self._launch(identifier)
            return self.public(record)

    def _owned(self, identifier):
        record = self.record()
        if (record.get("id") != identifier or record.get("repository") != self.app.task_service.repository
                or record.get("source_root") != str(self.root)):
            raise TaskServiceError("This publication does not belong to the running release.", 409)
        return record

    def _launch(self, identifier):
        threading.Thread(target=self._run, args=(identifier,), daemon=True,
                         name="zet-template-publication").start()

    def _run(self, identifier):
        try:
            with change_lock(self.state / "template-publications" / identifier, timeout=.01):
                self._publish(identifier)
        except ValueError:
            # A duplicate click must not overwrite another runner's progress.
            return

    def _publish(self, identifier):
        record = self._owned(identifier)
        try:
            self.save(record, state="preparing", error="")
            folder = self.state / "template-publications" / identifier
            # Before a commit checkpoint, use a fresh attempt rather than resetting
            # an interrupted index or an unresolved three-way application.
            checkout = folder / (record["checkout"] if record.get("commit") else "checkout-" + uuid4().hex)
            if checkout.resolve().parent != folder.resolve():
                raise ValueError("Publication checkout escaped its owned operation directory.")
            if not record.get("commit"):
                self.save(record, checkout=checkout.name)
            if not checkout.exists():
                git(folder, "-c", "core.longpaths=true", "clone", "--no-hardlinks", "--no-checkout", str(self.root), str(checkout))
            # All network destinations come from configured repository, not request data.
            remote = f"https://github.com/{record['repository']}.git"
            git(checkout, "remote", "set-url", "origin", remote)
            # Private runtime paths are deeper than the source checkout on Windows.
            git(checkout, "config", "core.longpaths", "true")
            git(checkout, "config", "core.autocrlf", "false")
            git(checkout, "fetch", "origin", "main")
            if not record.get("commit"):
                base = git(checkout, "rev-parse", "FETCH_HEAD")
                # Build the snapshot commit on its original baseline, in isolation.
                git(checkout, "checkout", "--detach", record["source_revision"])
                git(checkout, "config", "user.name", "Zet template publication")
                git(checkout, "config", "user.email", "zet-template-publication@localhost")
                for row in record["files"]:
                    target = checkout / row["path"]
                    content = base64.b64decode(row["content"])
                    baseline = git(checkout, "show", f"HEAD:{row['path']}", binary=True)
                    target.write_bytes(content if b"\r\n" in baseline else canonical(content))
                git(checkout, "add", "--", *(row["path"] for row in record["files"]))
                patch = git(checkout, "diff", "--cached", "--binary", "--full-index", binary=True)
                (folder / "change.patch").write_bytes(patch)
                git(checkout, "restore", "--source=HEAD", "--staged", "--worktree", "--", *(row["path"] for row in record["files"]))
                # A retained conflict is inspected, never erased by retry.
                git(checkout, "checkout", "--detach", base)
                if patch:
                    try:
                        git(checkout, "apply", "--3way", "--index", input=patch)
                    except ValueError as exc:
                        self.save(record, state="conflict", error="The template edits conflict with main. Retained snapshot and checkout need reconciliation. " + str(exc))
                        return
                git(checkout, "checkout", "-b", record["branch"])
                git(checkout, "commit", "--allow-empty", "-m", "Preserve accepted governing template edits")
                names = git(checkout, "diff", "--name-only", base, "HEAD").splitlines()
                if not names:
                    self.save(record, state="conflict", error="Selected edits already match main; GitHub cannot create an empty PR. The snapshot is retained for explicit reconciliation.")
                    return
                if set(names) - {row["path"] for row in record["files"]}:
                    raise ValueError("Publication contains unexpected files; retained checkout requires inspection.")
                for row in record["files"]:
                    row["published_sha256"] = digest(canonical(git(checkout, "show", f"HEAD:{row['path']}", binary=True)))
                self.save(record, commit=git(checkout, "rev-parse", "HEAD"), base_revision=base)
            if git(checkout, "rev-parse", "HEAD") != record["commit"] or git(checkout, "status", "--porcelain", "--untracked-files=no"):
                raise ValueError("Retained publication checkout changed; inspect it before retrying.")
            git(checkout, "-c", "core.whitespace=trailing-space,space-before-tab,cr-at-eol",
                "diff", "--check", record["base_revision"], record["commit"])
            validation = record.get("validation", {})
            if not validation.get("passed") or validation.get("revision") != record["commit"]:
                self.save(record, state="validating")
                self.validate(checkout)
                self.save(record, validation={"passed": True, "revision": record["commit"],
                          "command": "npm run test:e2e; git diff --check base..HEAD"})
            self.save(record, state="publishing")
            # No force pushes. A timed-out successful push is harmless on retry.
            git(checkout, "push", "origin", f"{record['commit']}:refs/heads/{record['branch']}")
            pulls = self.github.repo_api("/pulls?state=all&per_page=100&head=" + record["repository"].split("/")[0] + ":" + record["branch"], paginate=True)
            matches = [pr for pr in pulls if self._matches_pr(record, pr)]
            if matches:
                pr = matches[0]
            else:
                body = ("Preserves accepted governing-template edits from production " + record["source_revision"] + ".\n\n"
                        + "\n".join("- " + row["path"] for row in record["files"])
                        + "\n\nValidation: approved isolated E2E baseline and git diff --check passed.\n"
                        + "Production templates remain unchanged. Merge this PR, then use Zet's Update and restart.\n\n"
                        + f"<!-- zet-template-publication:{identifier} -->")
                pr = self.github.repo_api("/pulls", method="POST", payload={"title": "Preserve accepted governing template edits",
                           "body": body, "head": record["branch"], "base": "main", "draft": False})
            if not self._matches_pr(record, pr) or pr["head"]["sha"] != record["commit"]:
                raise ValueError("The recovery PR has an unexpected repository, base or revision.")
            self.save(record, state="awaiting-merge", pr_number=pr["number"], pr_url=pr["html_url"])
            report = inspect(self.root)
            current = {row["path"]: row.get("raw_sha256") for row in report["files"]}
            saved = {row["path"]: row["raw_sha256"] for row in record["files"]}
            self.save(record, newer_edits=any(current.get(path) != value for path, value in saved.items())
                      or any(row["eligible"] and row["path"] not in saved for row in report["files"]))
        except Exception as exc:
            self.save(record, state="failed", error=str(exc))

    def validate(self, checkout):
        from zet.scripts.deploy_release import run, test_lock, release_python
        python = release_python(checkout)
        if not python.exists():
            run([sys.executable, "-m", "venv", str(checkout / ".venv")], timeout=120)
        run([str(python), "-c", "import sys; assert sys.version_info.major == 3"])
        run([str(python), "-m", "pip", "install", "-r", str(checkout / "requirements.txt")])
        run([str(python), "-m", "pip", "install", "-e", str(checkout), "--no-deps"])
        import os
        env = os.environ.copy()
        env["ZET_TEST_PYTHON"] = str(python)
        env.pop("PYTHONPATH", None)
        env.pop("ZET_WORKER_MODE", None)
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise ValueError("npm is unavailable; publication snapshot is retained.")
        command = ["cmd.exe", "/d", "/c", "npm.cmd run test:e2e"] if os.name == "nt" else [npm, "run", "test:e2e"]
        with test_lock(self.app.task_service.store.root):
            run(command, cwd=checkout, env=env, timeout=600)
        git(checkout, "diff", "--check")
        if git(checkout, "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Validation modified tracked publication files.")

    @staticmethod
    def _matches_pr(record, pr):
        return (pr.get("base", {}).get("ref") == "main"
                and (pr.get("base", {}).get("repo") or {}).get("full_name") == record["repository"]
                and pr.get("head", {}).get("ref") == record["branch"]
                and (pr.get("head", {}).get("repo") or {}).get("full_name") == record["repository"])

    def refresh(self, identifier):
        self.require_enabled()
        with change_lock(self.state):
            record = self._owned(identifier)
            if not record.get("pr_number"):
                return self.public(record)
            pr = self.github.repo_api(f"/pulls/{record['pr_number']}")
            if not self._matches_pr(record, pr) or pr["head"]["sha"] != record["commit"]:
                self.save(record, state="failed", error="The PR repository, base or contents changed; inspect it before updating.")
                return self.public(record)
            git(self.root, "fetch", f"https://github.com/{record['repository']}.git", "main")
            main = git(self.root, "rev-parse", "FETCH_HEAD")
            unchanged = all((self.root / row["path"]).is_file() and not (self.root / row["path"]).is_symlink()
                            and digest((self.root / row["path"]).read_bytes()) == row["raw_sha256"] for row in record["files"])
            target_matches = all(digest(canonical(git(self.root, "show", f"{main}:{row['path']}", binary=True)))
                                 == row["published_sha256"] for row in record["files"])
            merge = pr.get("merge_commit_sha")
            included = False
            if pr.get("merged") and isinstance(merge, str) and len(merge) == 40 and all(c in "0123456789abcdef" for c in merge):
                try:
                    git(self.root, "merge-base", "--is-ancestor", merge, main)
                    included = True
                except ValueError:
                    pass
            state = "ready" if included and unchanged and target_matches else "awaiting-merge"
            error = ""
            if pr.get("merged") and (not unchanged or not target_matches or not included):
                state, error = "conflict", "Templates or merge history changed locally or on main since publication. Review a fresh snapshot."
            elif pr.get("state") == "closed" and not pr.get("merged"):
                state, error = "closed", "This PR was closed without merging. Local edits remain preserved."
            self.save(record, state=state, newer_edits=not unchanged, error=error, checked_main=main,
                      merge_commit=pr.get("merge_commit_sha") if pr.get("merged") else None)
            return self.public(record)

    def deployment_receipt(self):
        record = self.record()
        if record.get("source_root") != str(self.root) or not inspect(self.root)["files"]:
            return {}
        if record.get("pr_number"):
            self.refresh(record["id"])
            record = self.record()
        return {key: value for key, value in record.items() if key != "validation"}
