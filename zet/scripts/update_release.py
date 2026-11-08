"""Deploy merged origin/main using the terminal environment and local controller."""
from __future__ import annotations

import argparse
import json
import socket
import sqlite3
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from urllib.request import urlopen
from uuid import uuid4

from zet.services.config_service import ConfigService, ConfigServiceError
from zet.services.deployment_service import DeploymentService
from zet.services.process_service import ProcessService
from zet.services.runtime_state_service import workflow_root
from zet.services.task_service import TaskService


def active_runtime(runtime_root):
    root = Path(runtime_root).resolve()
    active_path = root / "state" / "active-release.json"
    if not active_path.is_file():
        raise ValueError("No promoted release exists. Use the dashboard for the first production deployment.")
    active = json.loads(active_path.read_text(encoding="utf-8"))
    release = Path(active["release"]).resolve()
    if release.parent != root / "releases" or release.name != active["revision"]:
        raise ValueError("Active release does not match its revision inside Runtime.Root/releases.")
    config_path = release / "config.runtime.toml"
    config = ConfigService.load(config_path)
    if config.runtime_role != "production" or Path(config.runtime_root).resolve() != root:
        raise ValueError("Active config does not identify this production runtime.")
    host, port = active.get("host", "0.0.0.0"), active.get("port", 8081)
    if not isinstance(host, str) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Active runtime host/port is invalid.")
    task = TaskService(config.github_repository, config.github_timeout_seconds,
                       project_root=release, state_root=workflow_root(config))
    if task.zet_revision != active["revision"]:
        raise ValueError("Active checkout revision differs from the promoted release record.")
    # Assemble deployment dependencies only; do not construct ZetApp or start creative services.
    context = SimpleNamespace(config=config, config_path=config_path, task_service=task,
                              process_service=ProcessService(release, config_path=config_path))
    return DeploymentService(context), (host, port)


def wait_for_update(service, operation, *, stage_only=False, timeout=1800):
    path = service.root / "state" / f"deployment-{operation['id']}-status.json"
    print(f"Operation {operation['id']}\nStatus: {path}", flush=True)
    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        # Read final status after observing exit, avoiding a stale in-flight
        # snapshot if the controller finishes between these two operations.
        exited = service.controller_process.poll() is not None
        status = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else operation
        if status.get("id") != operation["id"]:
            raise ValueError("Deployment status belongs to a different operation.")
        state = status.get("state")
        if state != last_state:
            print(f"Update: {state}", flush=True)
            last_state = state
        # The controller briefly reports failed before attempting rollback. Wait
        # for its exit so the terminal reports the completed recovery outcome.
        if exited and (state == "succeeded" or (stage_only and state == "staged")):
            print(f"{'Validated' if stage_only else 'Released'} {status.get('target_revision', '')}", flush=True)
            return 0
        if exited and state in {"failed", "rolled-back", "recovery-required"}:
            print(status.get("error") or f"Update ended with {state}.", file=sys.stderr, flush=True)
            if status.get("recovery_error"):
                print(status["recovery_error"], file=sys.stderr, flush=True)
            return 1
        if exited:
            raise ValueError(f"Deployment controller exited before completing the update. Inspect {path}.")
        time.sleep(1)
    raise TimeoutError(f"Stopped waiting; deployment may still be running. Inspect {path} before retrying.")


def deploy_stopped(service, address, *, stage_only=False):
    """Stage and start a compatible release when the old release cannot boot."""
    from contextlib import closing
    from zet.scripts.deploy_release import atomic_json, healthy, release_python, run, stage, start_harvester, start_release
    from zet.services.template_publication_core import BUSY, change_lock, guard

    host, port = address
    state = service.root / "state"
    context = service.app
    config = context.config

    def require_offline():
        try:
            connection = socket.create_connection(("127.0.0.1", port), timeout=2)
        except ConnectionRefusedError:
            pass
        else:
            connection.close()
            raise ValueError("A server is listening on the production port.")
        process = context.process_service
        if any(process._matches(info, spec) for info in process.list_processes() for spec in process.specs()):
            raise ValueError("Stop the managed dashboard and harvester before using --offline.")

    service.templates.require_enabled()
    with change_lock(state):
        require_offline()
        if service.templates.record().get("state") in BUSY:
            raise ValueError("Finish or retry the active template publication before updating.")
        operation = service.status()["operation"]
        if operation.get("state") in {"pending", "staging", "validating", "restarting"}:
            raise ValueError("Another update is active or interrupted. Inspect its status before using --offline.")
        source = context.config_path.parent
        library = Path(config.base_library_path).resolve()
        container = Path(config.library_container_path or library).resolve()
        request = {"id": uuid4().hex, "runtime_root": str(service.root), "source_root": str(source),
                   "workflow_state_root": str(service.store.root), "config_path": str(context.config_path),
                   "mutable_state_root": config.runtime_state_path or str(source / "Config"),
                   "template_receipt": service.templates.deployment_receipt(),
                   "library_root": str(library), "library_container": str(container),
                   "previous_release": str(source)}
        release, revision = stage(request, lambda status, **_: print(f"Update: {status}", flush=True))
        supported = int(run([str(release_python(release)), "-B", "-c",
                             "from zet.repositories.entity_library_repository import EntityLibraryRepository; "
                             "print(EntityLibraryRepository.SCHEMA_VERSION)"], cwd=release))
        roots = [container, *(path for path in container.iterdir()
                              if path.is_dir() and (path / "universe.json").is_file())]
        for root in {*roots, library}:
            catalog = root / "catalog.sqlite3"
            if catalog.is_file():
                with closing(sqlite3.connect(catalog.as_uri() + "?mode=ro", uri=True)) as db:
                    version = db.execute("PRAGMA user_version").fetchone()[0]
                if version > supported:
                    raise ValueError(f"The staged release cannot open catalog v{version}: {catalog}")
        if stage_only:
            print(f"Validated {revision}", flush=True)
            return 0
        require_offline()
        guard(source, release, request["template_receipt"], request["config_path"])
        print("Update: starting offline release", flush=True)
        started = start_release(release, host, port, state)
        try:
            healthy(f"http://127.0.0.1:{port}", revision, None, timeout=60)
            atomic_json(state / "active-release.json",
                        {"release": str(release), "revision": revision, "host": host, "port": port})
        except Exception:
            if started.poll() is None:
                started.terminate()
                started.wait(timeout=15)
            raise
        start_harvester(release)
        print(f"Released {revision}", flush=True)
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, help="Defaults to Runtime.Root in the project config.toml.")
    parser.add_argument("--stage-only", action="store_true", help="Validate without stopping or promoting production.")
    parser.add_argument("--offline", action="store_true", help="Stage and start with production stopped.")
    args = parser.parse_args(argv)
    try:
        root = args.runtime_root
        if root is None:
            root = ConfigService.load(Path(__file__).resolve().parents[2] / "config.toml").runtime_root
            if not root:
                raise ValueError("Runtime.Root is not configured; pass --runtime-root.")
        service, address = active_runtime(root)
        if args.offline:
            return deploy_stopped(service, address, stage_only=args.stage_only)
        with urlopen(f"http://127.0.0.1:{address[1]}/api/health", timeout=5) as response:
            health = json.load(response)
        if not health.get("boot_id"):
            raise ValueError("The running dashboard did not report its boot identity.")
        print("Validating merged origin/main" if args.stage_only else "Updating production from merged origin/main", flush=True)
        operation = service.start(health["boot_id"], stage_only=args.stage_only, runtime_address=address)
        return wait_for_update(service, operation, stage_only=args.stage_only)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ConfigServiceError) as exc:
        print(f"Update failed: {exc}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("Stopped waiting. An already launched deployment continues; inspect its status before retrying.", file=sys.stderr, flush=True)
        return 130


if __name__ == "__main__":
    sys.exit(main())
