"""Standalone stdlib deployment controller, copied outside releases before execution."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
from urllib.request import urlopen

try:  # The installed controller lives outside the release and imports its sibling.
    from template_publication_core import change_lock, guard
except ImportError:
    from zet.services.template_publication_core import change_lock, guard


@contextmanager
def test_lock(state_root):
    """Serialize the approved fixed-port suite across workers and release staging."""
    path = Path(state_root) / "e2e.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another approved E2E check is running; retry validation later.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def run(command, cwd=None, env=None, timeout=600):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} failed: {(result.stderr or result.stdout)[-1800:]}")
    return result.stdout.strip()


def release_python(release):
    return release / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def library_reference_version(container):
    """Return the highest path format declared by a universe in this library container."""
    container = Path(container)
    roots = [container]
    if container.is_dir():
        roots.extend(path for path in container.iterdir() if path.is_dir() and not path.name.startswith("."))
    versions = []
    for root in roots:
        marker = root / "_state" / "library-reference-format.json"
        if marker.is_file():
            versions.append(int(json.loads(marker.read_text(encoding="utf-8")).get("library_path_format_version", 0)))
    return max(versions, default=0)


def healthy(url, revision, old_boot, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url + "/api/health", timeout=2) as response:
                value = json.load(response)
            if value.get("ready") and value.get("revision") == revision and value.get("boot_id") != old_boot:
                return value
        except (OSError, ValueError):
            pass
        time.sleep(.8)
    raise RuntimeError("The expected release did not report a new ready boot before the deadline.")


def start_release(release, host, port, log_root):
    command = [str(release_python(release)), "-B", "-m", "zet.web.app", "--config", str(release / "config.runtime.toml"),
               "--host", host, "--port", str(port)]
    log = (log_root / "production.log").open("ab")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("ZET_WORKER_MODE", None)
    try:
        process = subprocess.Popen(command, cwd=release, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
        return process
    finally:
        log.close()


def stop_owned(processes):
    for item in processes:
        pid = int(item["pid"])
        if os.name == "nt":
            result = run(["powershell", "-NoProfile", "-Command",
                          f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' | Select-Object -ExpandProperty CommandLine"], timeout=15)
            if result.strip() != item["command_line"].strip():
                continue
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def stage(request, update):
    root, source = Path(request["runtime_root"]), Path(request["source_root"])
    run(["git", "-C", str(source), "fetch", "origin", "main"], timeout=120)
    revision = run(["git", "-C", str(source), "rev-parse", "FETCH_HEAD"])
    release = root / "releases" / revision
    releases = (root / "releases").resolve()
    if release.resolve().parent != releases:
        raise RuntimeError("Release target escaped the runtime releases directory.")
    if not release.exists():
        release.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "-c", "core.longpaths=true", "clone", "--config", "core.longpaths=true", "--no-checkout", "--no-hardlinks", str(source), str(release)], timeout=120)
        run(["git", "-C", str(release), "checkout", "--detach", revision])
        origin = run(["git", "-C", str(source), "remote", "get-url", "origin"])
        run(["git", "-C", str(release), "remote", "set-url", "origin", origin])
    contract_path = release / "Config" / "Runtime_Contract.json"
    if not contract_path.exists():
        raise RuntimeError("Merged main does not yet contain the deployment contract. Merge the workflow implementation before updating.")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("requires_manual_migration") or contract.get("deployment_contract") != 1:
        raise RuntimeError("This release requires an explicit data migration; automatic promotion is blocked.")
    required_library_version = library_reference_version(request.get("library_container", request["library_root"]))
    if int(contract.get("library_reference_version", 0)) < required_library_version:
        raise RuntimeError("This release cannot read the configured library's path format; production was not stopped.")
    if request.get("previous_release"):
        previous = Path(request["previous_release"])
        old_contract = json.loads((previous / "Config" / "Runtime_Contract.json").read_text(encoding="utf-8"))
        if old_contract["deployment_contract"] != contract["deployment_contract"]:
            raise RuntimeError("Release data compatibility changed; migration and rollback need explicit review.")
        if int(old_contract.get("library_reference_version", 0)) < required_library_version:
            raise RuntimeError("The previous release cannot read the configured library path format; promotion is blocked to preserve rollback compatibility.")
    if git_dirty := run(["git", "-C", str(release), "diff", "--name-only", "HEAD"]):
        raise RuntimeError("Staged release has tracked edits; retained release needs inspection: " + git_dirty[:500])
    guard(source, release, request.get("template_receipt"))
    if request.get("previous_release") and Path(request["previous_release"]).resolve() != source.resolve():
        guard(Path(request["previous_release"]), release, request.get("template_receipt"))
    update("staging", target_revision=revision, target_release=str(release))
    python = release_python(release)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(release / ".venv")], timeout=120)
    run([str(python), "-c", "import sys; assert sys.version_info.major == 3"])
    run([str(python), "-m", "pip", "install", "-r", str(release / "requirements.txt")], timeout=600)
    run([str(python), "-m", "pip", "install", "-e", str(release), "--no-deps"], timeout=180)
    env = os.environ.copy()
    env["ZET_TEST_PYTHON"] = str(python)
    env.pop("PYTHONPATH", None)
    env.pop("ZET_WORKER_MODE", None)
    update("validating")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("npm is unavailable; production was not stopped.")
    # npm's Windows command shim is invoked directly via cmd with a fixed command, no data interpolation.
    command = ["cmd.exe", "/d", "/c", "npm.cmd run test:e2e"] if os.name == "nt" else [npm, "run", "test:e2e"]
    with test_lock(request["workflow_state_root"]):
        run(command, cwd=release, env=env, timeout=600)
    run(["git", "-C", str(release), "diff", "--check"])
    config = Path(request["config_path"]).read_text(encoding="utf-8")
    if "[Runtime]" in config:
        import re
        config = re.sub(r"(?ms)^\[Runtime(?:ByPlatform(?:\.[^\]]+)?)?\].*?(?=^\[|\Z)", "", config)
    config += '\n[Runtime]\nRole = "production"\nRoot = ' + json.dumps(str(root)) + '\nStatePath = ' + json.dumps(str(root / "state")) + '\n'
    (release / "config.runtime.toml").write_text(config, encoding="utf-8")
    for filename in ("universe-selection.json", "Local_Render_Presets.json", "ollama-models-cache.json"):
        target = root / "state" / filename
        existing = Path(request["mutable_state_root"]) / filename
        if not target.exists():
            if existing.exists():
                shutil.copy2(existing, target)
            elif (release / "Config" / filename).exists():
                shutil.copy2(release / "Config" / filename, target)
    # No app is constructed against production data during staging.
    update("staged", target_revision=revision, target_release=str(release))
    return release, revision


def execute(request_path):
    request = json.loads(request_path.read_text(encoding="utf-8"))
    status = dict(request, state="pending")
    status_path = request_path.with_name(request_path.stem + "-status.json")
    def update(state, **values):
        status.update(state=state, updated_at=time.time(), **values)
        atomic_json(status_path, status)
    try:
        release, revision = stage(request, update)
        if request.get("stage_only"):
            return
        # Hold the cross-process master-write fence through stop/start. The old
        # release remains byte-for-byte intact, including verified template edits.
        with change_lock(Path(request["runtime_root"]) / "state"):
            if run(["git", "-C", str(release), "diff", "--name-only", "HEAD"]):
                raise RuntimeError("Staged release changed during validation; production was not stopped.")
            guard(Path(request["source_root"]), release, request.get("template_receipt"))
            if request.get("previous_release") and Path(request["previous_release"]).resolve() != Path(request["source_root"]).resolve():
                guard(Path(request["previous_release"]), release, request.get("template_receipt"))
            promote(request, release, revision, update)
    except Exception as exc:
        update("failed", error=str(exc))


def promote(request, release, revision, update):
    started = None
    stopped = False
    try:
        # Verify the exact old boot is still serving before touching any captured PID.
        with urlopen(request["health_url"] + "/api/health", timeout=3) as response:
            old = json.load(response)
        if old.get("boot_id") != request["old_boot"]:
            raise RuntimeError("Production boot changed during staging; no processes were stopped.")
        update("restarting")
        time.sleep(1)
        stopped = True
        stop_owned(request["owned_processes"])
        for filename in ("universe-selection.json", "Local_Render_Presets.json", "ollama-models-cache.json"):
            source = Path(request["mutable_state_root"]) / filename
            target = Path(request["runtime_root"]) / "state" / filename
            if source.is_file() and source.resolve() != target.resolve():
                shutil.copy2(source, target)
        active_path = Path(request["runtime_root"]) / "state" / "active-release.json"
        atomic_json(active_path, {"release": str(release), "revision": revision, "host": request["host"], "port": request["port"]})
        started = start_release(release, request["host"], request["port"], active_path.parent)
        health = healthy(request["health_url"], revision, request["old_boot"])
        start_harvester(release)
        update("succeeded", boot_id=health["boot_id"])
    except Exception as exc:
        update("failed", error=str(exc))
        if stopped and request.get("previous_release"):
            if started and started.poll() is None:
                started.terminate()
                started.wait(timeout=15)
            previous = Path(request["previous_release"])
            active_path = Path(request["runtime_root"]) / "state" / "active-release.json"
            atomic_json(active_path, {"release": str(previous), "revision": request["previous_revision"], "host": request["host"], "port": request["port"]})
            try:
                start_release(previous, request["host"], request["port"], active_path.parent)
                health = healthy(request["health_url"], request["previous_revision"], request["old_boot"])
                start_harvester(previous)
                update("rolled-back", boot_id=health["boot_id"])
            except Exception as recovery:
                update("recovery-required", recovery_error=str(recovery))
        elif stopped:
            # First adoption has no managed previous release; relaunch the original exact command.
            try:
                subprocess.Popen(request["original_command"], cwd=request["source_root"],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                health = healthy(request["health_url"], request["previous_revision"], request["old_boot"])
                if request.get("original_harvester_command"):
                    subprocess.Popen(request["original_harvester_command"], cwd=request["source_root"],
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                update("rolled-back", boot_id=health["boot_id"])
            except Exception as recovery:
                update("recovery-required", recovery_error=str(recovery))


def start_harvester(release):
    with (release / "config.runtime.toml").open("rb") as handle:
        config = tomllib.load(handle)
    if config.get("AIHarvest", {}).get("AutoEnabled", True):
        env = os.environ.copy()
        env.pop("ZET_WORKER_MODE", None)
        env.pop("PYTHONPATH", None)
        subprocess.Popen([str(release_python(release)), "-B", "-m", "zet.scripts.auto_harvest_ai_answers", "--config", str(release / "config.runtime.toml")],
                         cwd=release, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    execute(args.request.resolve())


if __name__ == "__main__":
    main()
