"""Standalone stdlib deployment controller, copied outside releases before execution."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import json
import os
import queue
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import traceback
from urllib.request import urlopen

try:  # The installed controller lives outside the release and imports its sibling.
    from template_publication_core import change_lock, guard
except ImportError:
    from zet.services.template_publication_core import change_lock, guard


E2E_TEST_TIMEOUT_SECONDS = 900
COMMAND_HEARTBEAT_SECONDS = 15


def progress(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


@contextmanager
def update_log(path):
    """Keep direct Test/offline execution as observable as the detached controller."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", buffering=1) as log:
        class Tee:
            def __init__(self, terminal):
                self.terminal = terminal

            def write(self, text):
                self.terminal.write(text)
                log.write(text)
                return len(text)

            def flush(self):
                self.terminal.flush()
                log.flush()

        with redirect_stdout(Tee(sys.stdout)), redirect_stderr(Tee(sys.stderr)):
            progress(f"Update log: {path}")
            yield


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


def merge_render_presets(defaults_path, target_path, source_path=None):
    """Merge newly shipped profiles into runtime state without dropping local profiles."""
    target_path = Path(target_path)
    source_path = Path(source_path) if source_path else None
    defaults_path = Path(defaults_path)
    merged = {}
    loaded = set()

    # Keep the established mutable-state source authoritative for conflicts, while
    # preserving custom profiles that exist only in the production target.
    for path in (source_path, target_path):
        if path is None or not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in loaded:
            continue
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(catalog, dict):
            raise RuntimeError(f"Render profile catalog must be a JSON object: {path}")
        loaded.add(resolved)
        for name, profile in catalog.items():
            merged.setdefault(name, profile)

    if defaults_path.is_file():
        defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
        if not isinstance(defaults, dict):
            raise RuntimeError(f"Release render profile catalog must be a JSON object: {defaults_path}")
        for name, profile in defaults.items():
            merged.setdefault(name, profile)

    if not merged:
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(target_path, merged)


def run(command, cwd=None, env=None, timeout=600, *, stream_output=False, label=None):
    description = label or subprocess.list2cmdline(list(map(str, command)))
    progress(f"START {description} (timeout {timeout}s; cwd {cwd or Path.cwd()})")
    started = time.monotonic()
    # Explicit pipes are essential with CREATE_NO_WINDOW: inherited console
    # handles can silently discard npm/Playwright output in an ordinary terminal.
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                   start_new_session=os.name != "nt")
    except OSError as exc:
        raise RuntimeError(f"Could not start {description}: {exc}") from exc
    messages = queue.Queue()

    def read_output(pipe, channel):
        try:
            for line in pipe:
                messages.put((channel, line))
        finally:
            messages.put(None)

    readers = [threading.Thread(target=read_output, args=(pipe, channel), daemon=True)
               for pipe, channel in ((process.stdout, "stdout"), (process.stderr, "stderr"))]
    for reader in readers:
        reader.start()
    output = []
    stdout = []
    closed = 0
    next_heartbeat = started + COMMAND_HEARTBEAT_SECONDS
    timed_out = False
    try:
        while True:
            now = time.monotonic()
            if now - started >= timeout:
                timed_out = True
                raise TimeoutError(f"{description} timed out after {timeout}s.")
            try:
                message = messages.get(timeout=min(.2, max(.01, timeout - (now - started))))
            except queue.Empty:
                message = ("", "")
            if message is None:
                closed += 1
                if closed == len(readers):
                    break
                continue
            channel, line = message
            if line:
                output.append(line)
                if channel == "stdout":
                    stdout.append(line)
                if stream_output:
                    print(line, end="", flush=True)
            if now >= next_heartbeat:
                progress(f"RUNNING {description} ({now - started:.0f}s elapsed)")
                next_heartbeat = now + COMMAND_HEARTBEAT_SECONDS
        process.wait(timeout=max(.01, timeout - (time.monotonic() - started)))
    except (TimeoutError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        # Only this command's process tree is ours to stop. Release locks after
        # its fixtures have exited, rather than orphaning a listener on timeout.
        if os.name == "nt":
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=15)
        for reader in readers:
            reader.join(timeout=5)
        while not messages.empty():
            message = messages.get_nowait()
            if message:
                _, line = message
                output.append(line)
                if stream_output:
                    print(line, end="", flush=True)
        if isinstance(exc, KeyboardInterrupt):
            raise
        timed_out = True
    finally:
        if not any(reader.is_alive() for reader in readers):
            process.stdout.close()
            process.stderr.close()
    detail = "".join(output).strip()
    elapsed = time.monotonic() - started
    if timed_out or process.returncode:
        if not stream_output and detail:
            print(detail, flush=True)
        reason = f"timed out after {timeout}s" if timed_out else f"failed with exit code {process.returncode}"
        progress(f"FAILED {description}: {reason} ({elapsed:.1f}s)")
        raise RuntimeError(f"{description} {reason}.\n{detail[-6000:] or 'No command output was received.'}")
    progress(f"OK {description} ({elapsed:.1f}s)")
    return "".join(stdout).strip()


def stop_port_8765_listeners():
    """Terminate every Windows process listening on the fixed E2E port."""
    if os.name != "nt":
        raise RuntimeError("--skip-tests port cleanup is supported only on Windows.")

    def listeners():
        result = subprocess.run(["netstat.exe", "-ano", "-p", "tcp"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError(f"Could not inspect TCP listeners: {(result.stderr or result.stdout).strip()}")
        found = set()
        for line in result.stdout.splitlines():
            fields = line.split()
            if (len(fields) >= 5 and fields[0].upper() == "TCP"
                    and fields[1].rsplit(":", 1)[-1] == "8765" and fields[3].upper() == "LISTENING"
                    and fields[4].isdigit()):
                found.add(int(fields[4]))
        return found

    stopped = set()
    for _ in range(3):
        current = listeners()
        if not current:
            return sorted(stopped)
        for pid in sorted(current):
            result = subprocess.run(["taskkill.exe", "/PID", str(pid), "/F"], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace",
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                if pid in listeners():
                    detail = (result.stderr or result.stdout).strip()
                    raise RuntimeError(f"Could not stop process {pid} listening on TCP 8765: {detail}")
            else:
                stopped.add(pid)
    remaining = listeners()
    if remaining:
        raise RuntimeError("TCP port 8765 still has listening process(es): " + ", ".join(map(str, sorted(remaining))))
    return sorted(stopped)


def release_python(release):
    return release / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def validation_command(env):
    """Resolve Node/npm and give lifecycle scripts the same tool directories."""
    path = env.get("PATH", "")
    npm_name = "npm.cmd" if os.name == "nt" else "npm"
    npm = shutil.which(npm_name, path=path)
    node = shutil.which("node.exe" if os.name == "nt" else "node", path=path)
    if not node and os.name == "nt":
        # A long-running dashboard may have inherited PATH before Node was installed.
        candidates = [Path(npm).parent / "node.exe"] if npm else []
        for key in ("PROGRAMW6432", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            if env.get(key):
                candidates.append(Path(env[key]) / "nodejs" / "node.exe")
        if env.get("LOCALAPPDATA"):
            candidates.append(Path(env["LOCALAPPDATA"]) / "Programs" / "nodejs" / "node.exe")
        node = next((str(candidate) for candidate in candidates if candidate.is_file()), None)
    if not node:
        raise RuntimeError("Node.js is unavailable; install Node.js or add its directory to Zet's PATH. Production was not stopped.")
    env["PATH"] = str(Path(node).parent) + os.pathsep + path
    npm = npm or shutil.which(npm_name, path=env["PATH"])
    if not npm:
        raise RuntimeError("npm is unavailable; production was not stopped.")
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env["PATH"]
    # Keep the Windows shell command fixed; paths are supplied through the environment.
    command = "npm.cmd run test:e2e -- --reporter=line" if os.name == "nt" else [npm, "run", "test:e2e", "--", "--reporter=line"]
    return ["cmd.exe", "/d", "/c", command] if os.name == "nt" else command


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


def healthy(url, revision, old_boot, timeout=300, *, log_path=None):
    progress(f"Waiting for ready release {revision} at {url}/api/health (timeout {timeout}s)")
    deadline = time.monotonic() + timeout
    next_report = time.monotonic() + COMMAND_HEARTBEAT_SECONDS
    last_observation = "No health response received."
    while time.monotonic() < deadline:
        try:
            with urlopen(url + "/api/health", timeout=2) as response:
                value = json.load(response)
            if value.get("ready") and value.get("revision") == revision and value.get("boot_id") != old_boot:
                progress(f"Health check passed: revision {revision}, boot {value.get('boot_id')}")
                return value
            last_observation = f"ready={value.get('ready')}, revision={value.get('revision')}, boot={value.get('boot_id')}"
        except (OSError, ValueError) as exc:
            last_observation = str(exc)
        if time.monotonic() >= next_report:
            progress(f"Waiting for health: {last_observation}")
            next_report = time.monotonic() + COMMAND_HEARTBEAT_SECONDS
        time.sleep(.8)
    if log_path and Path(log_path).is_file():
        with Path(log_path).open("rb") as log:
            log.seek(max(0, log.seek(0, 2) - 12000))
            progress(f"Startup log tail ({log_path}):\n{log.read().decode('utf-8', errors='replace')}")
    raise RuntimeError(f"The expected release {revision} did not report a new ready boot at {url} before {timeout}s. "
                       f"Last health observation: {last_observation}. Startup log: {log_path or 'unavailable'}")


def start_release(release, host, port, log_root):
    command = [str(release_python(release)), "-B", "-m", "zet.web.app", "--config", str(release / "config.runtime.toml"),
               "--host", host, "--port", str(port)]
    progress(f"Starting dashboard from {release} on {host}:{port}; startup log: {log_root / 'production.log'}")
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
    def step(state, message, **values):
        update(state, step=message, **values)
        progress(message)

    step("staging", "Fetching merged origin/main")
    run(["git", "-C", str(source), "fetch", "origin", "main"], timeout=120,
        stream_output=True, label="Fetch origin/main")
    revision = run(["git", "-C", str(source), "rev-parse", "FETCH_HEAD"])
    release = root / "releases" / revision
    releases = (root / "releases").resolve()
    if release.resolve().parent != releases:
        raise RuntimeError("Release target escaped the runtime releases directory.")
    if not release.exists():
        step("staging", f"Creating release checkout: {release}", target_revision=revision, target_release=str(release))
        release.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "-c", "core.longpaths=true", "clone", "--config", "core.longpaths=true", "--no-checkout", "--no-hardlinks", str(source), str(release)], timeout=120,
            stream_output=True, label="Clone release checkout")
        run(["git", "-C", str(release), "checkout", "--detach", revision], stream_output=True, label="Check out release revision")
        origin = run(["git", "-C", str(source), "remote", "get-url", "origin"])
        run(["git", "-C", str(release), "remote", "set-url", "origin", origin], label="Set release Git origin")
    step("staging", "Checking release contract, library compatibility and saved template guards",
         target_revision=revision, target_release=str(release))
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
    guard(source, release, request.get("template_receipt"), request.get("config_path"))
    if request.get("previous_release") and Path(request["previous_release"]).resolve() != source.resolve():
        guard(Path(request["previous_release"]), release, request.get("template_receipt"))
    step("staging", "Preparing Python environment and installing declared dependencies")
    python = release_python(release)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(release / ".venv")], timeout=120, stream_output=True, label="Create Python virtual environment")
    run([str(python), "-c", "import sys; assert sys.version_info.major == 3"], label="Verify Python 3")
    run([str(python), "-u", "-m", "pip", "install", "-r", str(release / "requirements.txt")], timeout=600,
        stream_output=True, label="Install requirements.txt")
    run([str(python), "-u", "-m", "pip", "install", "-e", str(release), "--no-deps"], timeout=180,
        stream_output=True, label="Install Zet package")
    env = os.environ.copy()
    env["ZET_TEST_PYTHON"] = str(python)
    validation_root = root / "state" / "validation" / request["id"]
    results_root = validation_root / "test-results"
    env["ZET_TEST_RESULTS_ROOT"] = str(results_root)
    # The release controller writes to a file, so force Playwright to print
    # each scenario start/result on its own line instead of terminal redraws.
    env["PW_TEST_DEBUG_REPORTERS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("ZET_WORKER_MODE", None)
    if request.get("skip_tests"):
        step("validating", "Skipping E2E by request; checking TCP 8765 listener cleanup")
        stopped = stop_port_8765_listeners()
        step("validating", "E2E skipped", validation=f"E2E skipped; stopped {len(stopped)} TCP 8765 listener process(es)")
    else:
        step("validating", "Resolving Node/npm for approved E2E validation", validation="Running approved 20-scenario E2E suite")
        command = validation_command(env)
        progress(f"E2E failure evidence: {results_root}")
        try:
            step("validating", "Acquiring E2E validation lock")
            with test_lock(request["workflow_state_root"]):
                step("validating", "Running npm setup/browser checks and named Playwright scenarios")
                run(command, cwd=release, env=env, timeout=E2E_TEST_TIMEOUT_SECONDS, stream_output=True,
                    label="Approved E2E suite: npm run test:e2e")
        except Exception:
            progress(f"E2E validation failed; retained evidence: {results_root}")
            raise
        finally:
            packages = release / "node_modules"
            if packages.is_dir() and packages.resolve().parent == release.resolve():
                progress(f"Cleaning generated release dependencies: {packages}")
                validation_failed = sys.exc_info()[0] is not None
                try:
                    shutil.rmtree(packages)
                except OSError:
                    if not validation_failed:
                        raise
                    progress("Dependency cleanup also failed; preserving the original validation error")
                    traceback.print_exc()
    if validation_root.is_dir() and validation_root.resolve().parent == (root / "state" / "validation").resolve():
        shutil.rmtree(validation_root)
    step("validating", "Checking Git diff and preparing runtime configuration")
    run(["git", "-C", str(release), "diff", "--check"], label="Check release diff whitespace")
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
    step("staged", f"Release validation complete: {revision}", target_revision=revision, target_release=str(release))
    return release, revision


def execute(request_path):
    request = json.loads(request_path.read_text(encoding="utf-8"))
    status = dict(request, state="pending")
    status_path = request_path.with_name(request_path.stem + "-status.json")
    def update(state, **values):
        status.update(state=state, updated_at=time.time(), **values)
        atomic_json(status_path, status)
        progress(f"Update: {state}" + (f" - {values['step']}" if values.get("step") else ""))
        for key in ("error", "recovery_error"):
            if values.get(key):
                progress(f"{key}: {values[key]}")
    try:
        release, revision = stage(request, update)
        if request.get("stage_only"):
            return
        # Hold the cross-process master-write fence through stop/start. The old
        # release remains byte-for-byte intact, including verified template edits.
        with change_lock(Path(request["runtime_root"]) / "state"):
            update("validating", step="Rechecking checkout and template guards before promotion")
            if run(["git", "-C", str(release), "diff", "--name-only", "HEAD"]):
                raise RuntimeError("Staged release changed during validation; production was not stopped.")
            guard(Path(request["source_root"]), release, request.get("template_receipt"))
            if request.get("previous_release") and Path(request["previous_release"]).resolve() != Path(request["source_root"]).resolve():
                guard(Path(request["previous_release"]), release, request.get("template_receipt"))
            promote(request, release, revision, update)
    except Exception as exc:
        traceback.print_exc()
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
        update("restarting", step="Verifying old boot and stopping owned dashboard/harvester processes")
        time.sleep(1)
        stopped = True
        stop_owned(request["owned_processes"])
        update("restarting", step="Preparing mutable state and promoting active-release record")
        for filename in ("universe-selection.json", "Local_Render_Presets.json", "ollama-models-cache.json"):
            source = Path(request["mutable_state_root"]) / filename
            target = Path(request["runtime_root"]) / "state" / filename
            if filename == "Local_Render_Presets.json":
                merge_render_presets(release / "Config" / filename, target, source)
            elif source.is_file() and source.resolve() != target.resolve():
                shutil.copy2(source, target)
        active_path = Path(request["runtime_root"]) / "state" / "active-release.json"
        atomic_json(active_path, {"release": str(release), "revision": revision, "host": request["host"], "port": request["port"]})
        started = start_release(release, request["host"], request["port"], active_path.parent)
        health = healthy(request["health_url"], revision, request["old_boot"],
                         log_path=active_path.parent / "production.log")
        update("restarting", step="Starting configured AI answer harvester")
        start_harvester(release)
        update("succeeded", boot_id=health["boot_id"])
    except Exception as exc:
        traceback.print_exc()
        update("failed", error=str(exc))
        if stopped and request.get("previous_release"):
            progress(f"Recovering previous release: {request['previous_release']}")
            if started and started.poll() is None:
                started.terminate()
                started.wait(timeout=15)
            previous = Path(request["previous_release"])
            active_path = Path(request["runtime_root"]) / "state" / "active-release.json"
            atomic_json(active_path, {"release": str(previous), "revision": request["previous_revision"], "host": request["host"], "port": request["port"]})
            try:
                start_release(previous, request["host"], request["port"], active_path.parent)
                health = healthy(request["health_url"], request["previous_revision"], request["old_boot"],
                                 log_path=active_path.parent / "production.log")
                start_harvester(previous)
                update("rolled-back", boot_id=health["boot_id"])
            except Exception as recovery:
                traceback.print_exc()
                update("recovery-required", recovery_error=str(recovery))
        elif stopped:
            # First adoption has no managed previous release; relaunch the original exact command.
            try:
                progress("Recovering original dashboard command")
                subprocess.Popen(request["original_command"], cwd=request["source_root"],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                health = healthy(request["health_url"], request["previous_revision"], request["old_boot"])
                if request.get("original_harvester_command"):
                    subprocess.Popen(request["original_harvester_command"], cwd=request["source_root"],
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                update("rolled-back", boot_id=health["boot_id"])
            except Exception as recovery:
                traceback.print_exc()
                update("recovery-required", recovery_error=str(recovery))


def start_harvester(release):
    progress(f"Checking AI answer harvester configuration: {release / 'config.runtime.toml'}")
    with (release / "config.runtime.toml").open("rb") as handle:
        config = tomllib.load(handle)
    if config.get("AIHarvest", {}).get("AutoEnabled", True):
        env = os.environ.copy()
        env.pop("ZET_WORKER_MODE", None)
        env.pop("PYTHONPATH", None)
        subprocess.Popen([str(release_python(release)), "-B", "-m", "zet.scripts.auto_harvest_ai_answers", "--config", str(release / "config.runtime.toml")],
                         cwd=release, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        progress("AI answer harvester launched")
    else:
        progress("AI answer harvester disabled by configuration")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    execute(args.request.resolve())


if __name__ == "__main__":
    main()
