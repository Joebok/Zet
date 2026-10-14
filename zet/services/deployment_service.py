"""Stage merged code and hand off promotion to a controller outside the release."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.github_client import TaskServiceError


class DeploymentService:
    def __init__(self, app):
        self.app = app
        self.root = Path(app.config.runtime_root).resolve() if app.config.runtime_root else None
        self.store = app.task_service.store

    def status(self):
        record = self.store.get("deployment", "current", {}) if self.root else {}
        if record.get("status_path"):
            path = Path(record["status_path"])
            if path.is_file():
                record = json.loads(path.read_text(encoding="utf-8"))
        main = self.store.get("status", "github", {}).get("main_revision") if self.app.config.github_repository else None
        return {"configured": bool(self.root), "role": self.app.config.runtime_role,
                "running_revision": self.app.task_service.zet_revision, "available_revision": main,
                "update_available": bool(main and main != self.app.task_service.zet_revision),
                "operation": {key: record[key] for key in ("id", "state", "target_revision", "error", "recovery_error", "boot_id") if key in record}}

    def start(self, boot_id, *, stage_only=False):
        if not self.root or self.app.config.runtime_role == "development":
            raise TaskServiceError("Production deployment is not configured for this instance.", 409)
        for parent in (self.root, *self.root.parents):
            if (parent / ".git").exists():
                raise TaskServiceError("Runtime.Root must be outside Git working trees.", 409)
        for path in (self.app.config.base_library_path, self.app.config.base_ai_queue_path):
            data = Path(path).resolve()
            if self.root == data or data in self.root.parents or self.root in data.parents:
                raise TaskServiceError("Runtime.Root must not overlap the creative library or queue.", 409)
        with self.store.transaction() as db:
            existing = self.store.read(db, "deployment", "current", {})
            if existing.get("status_path") and Path(existing["status_path"]).is_file():
                existing = json.loads(Path(existing["status_path"]).read_text(encoding="utf-8"))
            if existing.get("state") in {"pending", "staging", "validating", "restarting"}:
                raise TaskServiceError("An update is already running or interrupted; inspect its status before retrying.", 409)
            state = self.root / "state"
            state.mkdir(parents=True, exist_ok=True)
            helper = state / "deploy_release.py"
            shutil.copy2(Path(__file__).parents[1] / "scripts" / "deploy_release.py", helper)
            active = state / "active-release.json"
            previous = json.loads(active.read_text(encoding="utf-8")) if active.exists() else {}
            process = self.app.process_service
            owned = [info for info in process.list_processes() if any(process._matches(info, spec) for spec in process.specs())]
            pids = [info.pid for info in owned]
            if not stage_only and os.getpid() not in pids:
                raise TaskServiceError("This server is not identified by the managed production config; no restart was scheduled.", 409)
            identifier = uuid4().hex
            request_path = state / f"deployment-{identifier}.json"
            role_state = self.app.config.runtime_state_path or str(self.app.config_path.resolve().parent / "Config")
            request = {"id": identifier, "state": "pending", "runtime_root": str(self.root), "source_root": str(process.project_root),
                       "workflow_state_root": str(self.store.root),
                       "config_path": str(self.app.config_path.resolve()), "mutable_state_root": role_state,
                       "library_root": str(Path(self.app.config.base_library_path).resolve()),
                       "library_container": str(Path(self.app.config.library_container_path or self.app.config.base_library_path).resolve()),
                       "previous_release": previous.get("release"), "previous_revision": self.app.task_service.zet_revision,
                       "old_boot": boot_id, "pids": pids, "host": os.environ.get("ZET_WEB_HOST", "0.0.0.0"),
                       "owned_processes": [{"pid": info.pid, "command_line": info.command_line} for info in owned],
                       "port": int(os.environ.get("ZET_WEB_PORT", "8081")), "health_url": "http://127.0.0.1:" + os.environ.get("ZET_WEB_PORT", "8081"),
                       "original_command": process.specs()[0].command, "original_harvester_command": process.specs()[1].command, "stage_only": stage_only}
            write_json_atomic(request_path, request)
            self.store.write(db, "deployment", "current", {**request, "status_path": str(request_path.with_name(request_path.stem + "-status.json"))})
            db.commit()
            try:
                subprocess.Popen([sys.executable, "-B", str(helper), "--request", str(request_path)],
                                 cwd=state, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
            except OSError as exc:
                self.store.put("deployment", "current", {"id": identifier, "state": "failed", "error": "Could not launch the deployment controller."})
                raise TaskServiceError("Could not launch the deployment controller.", 503) from exc
            return {"id": identifier, "state": "pending", "previous_boot": boot_id}
