"""Deploy and manage the separately configured Zet Test release."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen
from uuid import uuid4

from zet.scripts.deploy_release import (atomic_json, healthy, progress, release_python, stage,
                                       start_harvester, start_release, update_log)
from zet.services.config_service import ConfigService
from zet.services.process_service import ProcessService

REPOSITORY = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get("ZET_TEST_RUNTIME", REPOSITORY.parent / "Zet_Runtime_Test")).resolve()
CONFIG_SOURCE = RUNTIME / "config.test.toml"
STATE = RUNTIME / "state"
LIBRARY = Path(r"E:\Zet\Zet_Library_Test")
HOST = "127.0.0.1"
PORT = 8082


def read_active(*, allow_previous_queue: bool = False) -> tuple[dict, Path]:
    active_path = STATE / "active-release.json"
    if not active_path.is_file():
        raise ValueError("No Test release is deployed. Run Update_Test.ps1 to deploy merged origin/main.")
    active = json.loads(active_path.read_text(encoding="utf-8"))
    release = Path(active["release"]).resolve()
    if (release.parent != (RUNTIME / "releases").resolve() or release.name != active["revision"]
            or active.get("port") != PORT or active.get("host") != HOST):
        raise ValueError("Test active-release.json is invalid or points outside the Test runtime.")
    config = ConfigService.load(release / "config.runtime.toml")
    queue_path = Path(config.base_ai_queue_path).resolve()
    valid_pair = (queue_path == Path(r"D:\Zet\AI_Queue") and config.ai_proxy_subscriber_id == "zet_test")
    previous_pair = (queue_path == Path(r"D:\Zet\Zet_Test\AI_Queue")
                     and config.ai_proxy_subscriber_id == "zet")
    if (config.runtime_role != "local" or Path(config.runtime_state_path).resolve() != STATE
            or Path(config.base_library_path).resolve() != LIBRARY
            or not (valid_pair or (allow_previous_queue and previous_pair))):
        raise ValueError("The active release config does not identify the isolated Test data roots.")
    return active, release


def test_process_service(config_path: Path) -> ProcessService:
    return ProcessService(config_path.parent, config_path=config_path)


def matching_processes(service: ProcessService) -> list:
    specs = service.specs()
    return [info for info in service.list_processes()
            if any(service._matches(info, spec) for spec in specs)]


def require_port_free() -> None:
    try:
        with urlopen(f"http://{HOST}:{PORT}/api/health", timeout=1):
            raise ValueError(f"Port {PORT} already serves an unverified Zet instance; it was left untouched.")
    except ValueError:
        raise
    except OSError:
        pass
    service = test_process_service(REPOSITORY / "config.toml")
    for process in service.list_processes():
        if "zet.web.app" in process.command_line.lower() and str(PORT) in process.command_line:
            raise ValueError(f"A Zet process already occupies port {PORT}; it was left untouched.")


def stop_release(release: Path) -> None:
    progress(f"Stopping verified Test processes for {release}")
    service = test_process_service(release / "config.runtime.toml")
    processes = matching_processes(service)
    process_ids = {process.pid for process in processes}
    roots = [process for process in processes if process.parent_pid not in process_ids]
    for process in roots:
        progress(f"Stopping Test process tree {process.pid}")
        if os.name == "nt":
            command = ("Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(process.pid)
                       + "' | Select-Object -ExpandProperty CommandLine")
            current = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True,
                                     text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if not current.stdout.strip():
                continue
            if current.stdout.strip() != process.command_line.strip():
                raise RuntimeError(f"Test process {process.pid} changed identity during shutdown; it was left untouched.")
            stopped = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                                     text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if stopped.returncode:
                current = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True,
                                         text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if current.stdout.strip() == process.command_line.strip():
                    raise RuntimeError(f"Could not stop Test process {process.pid}: {stopped.stderr.strip()}")
        else:
            os.kill(process.pid, 15)


def start_release_checked(release: Path, old_boot: str | None) -> dict:
    progress("Checking Test port ownership before starting dashboard")
    require_port_free()
    STATE.mkdir(parents=True, exist_ok=True)
    process = start_release(release, HOST, PORT, STATE)
    try:
        health = healthy(f"http://{HOST}:{PORT}", release.name, old_boot, timeout=90,
                         log_path=STATE / "production.log")
        expected = "local:" + str((release / "config.runtime.toml").resolve())
        if health.get("instance") != expected:
            raise RuntimeError("Port 8082 did not report the expected Test release config.")
        start_harvester(release)
        return health
    except Exception:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        raise


def deploy() -> None:
    progress(f"Checking isolated Test configuration: {CONFIG_SOURCE}")
    if not CONFIG_SOURCE.is_file():
        raise ValueError(f"Test config is missing: {CONFIG_SOURCE}")
    config = ConfigService.load(CONFIG_SOURCE)
    if (config.runtime_role != "local" or Path(config.base_library_path).resolve() != LIBRARY
            or Path(config.base_ai_queue_path).resolve() != Path(r"D:\Zet\AI_Queue")
            or config.ai_proxy_subscriber_id != "zet_test"):
        raise ValueError("Test config paths differ from the provisioned Test library and queue.")
    if (STATE / "active-release.json").is_file():
        progress("Checking current Test release and serving identity")
        previous, previous_release = read_active(allow_previous_queue=True)
        with urlopen(f"http://{HOST}:{PORT}/api/health", timeout=3) as response:
            previous_health = json.load(response)
        if (not previous_health.get("ready") or previous_health.get("revision") != previous["revision"]
                or previous_health.get("instance") != "local:" + str((previous_release / "config.runtime.toml").resolve())):
            raise ValueError("Port 8082 is not running the recorded Test release; no process was stopped.")
        if previous_health.get("boot_id") != previous.get("boot_id"):
            previous["boot_id"] = previous_health["boot_id"]
            atomic_json(STATE / "active-release.json", previous)
    else:
        previous = previous_release = previous_health = None
    STATE.mkdir(parents=True, exist_ok=True)
    request_id = uuid4().hex
    request = {"id": request_id, "runtime_root": str(RUNTIME), "source_root": str(REPOSITORY),
               "workflow_state_root": str(config.runtime_state_path and Path(config.runtime_state_path) or STATE),
               "config_path": str(CONFIG_SOURCE), "mutable_state_root": str(STATE),
               "library_root": str(LIBRARY), "library_container": str(LIBRARY),
               "previous_release": str(previous_release) if previous_release else ""}
    def report(state, **details):
        progress(f"Test update: {state}")
        if details.get("validation"):
            progress(f"Validation: {details['validation']}")

    release, revision = stage(request, report)
    progress("Preparing isolated Test runtime configuration")
    original_runtime_config = (release / "config.runtime.toml").read_bytes()
    test_runtime_config = CONFIG_SOURCE.read_text(encoding="utf-8-sig")
    import re
    test_runtime_config = re.sub(r"(?ms)^\[Runtime(?:ByPlatform(?:\.[^\]]+)?)?\].*?(?=^\[|\Z)", "", test_runtime_config)
    test_runtime_config += f'\n[Runtime]\nRole = "local"\nStatePath = {json.dumps(str(STATE))}\n'
    (release / "config.runtime.toml").write_text(test_runtime_config, encoding="utf-8")
    old_boot = previous_health.get("boot_id") if previous_health else None
    try:
        if previous_release:
            stop_release(previous_release)
        health = start_release_checked(release, old_boot)
        progress("Recording healthy Test release identity")
        atomic_json(STATE / "active-release.json", {"release": str(release), "revision": revision,
                    "host": HOST, "port": PORT, "config_path": str(release / "config.runtime.toml"),
                    "boot_id": health["boot_id"]})
        print(f"Test release {revision} is running at http://{HOST}:{PORT}")
    except Exception as startup_error:
        progress(f"Test startup failed: {startup_error}")
        if previous_release:
            try:
                progress(f"Recovering previous Test release: {previous_release}")
                start_release_checked(previous_release, None)
                progress("Previous Test release recovered")
            except Exception as recovery:
                raise RuntimeError(f"Test start failed: {startup_error}. Prior release recovery failed: {recovery}") from recovery
        else:
            (release / "config.runtime.toml").write_bytes(original_runtime_config)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("Deploy", "Start", "Stop"), nargs="?", default="Deploy")
    action = parser.parse_args().action
    with update_log(STATE / f"test-update-{uuid4().hex}.log"):
        return manage(action)


def manage(action: str) -> int:
    print(f"Test release manager action: {action} ({Path(__file__).resolve()})", flush=True)
    try:
        if action == "Deploy":
            deploy()
        elif action == "Start" and not (STATE / "active-release.json").is_file():
            print("No Test release exists yet. Deploying merged origin/main.", flush=True)
            deploy()
        else:
            active, release = read_active()
            if action == "Stop":
                stop_release(release)
                print("Test dashboard and harvester stopped.")
            else:
                health = start_release_checked(release, active.get("boot_id"))
                active["boot_id"] = health["boot_id"]
                atomic_json(STATE / "active-release.json", active)
                print(f"Test release {active['revision']} is running at http://{HOST}:{PORT}")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        traceback.print_exc()
        print(f"Test update failed: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
