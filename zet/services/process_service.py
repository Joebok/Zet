from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    command_line: str
    parent_pid: int | None = None


@dataclass(frozen=True)
class ManagedProcessSpec:
    process_id: str
    label: str
    match_terms: tuple[str, ...]
    command: str | None = None
    cwd: Path | None = None
    manageable: bool = True


@dataclass(frozen=True)
class ManagedProcessStatus:
    process_id: str
    label: str
    running: bool
    duplicate_count: int
    manageable: bool
    pids: list[int]
    command_lines: list[str]

    def to_dict(self) -> dict:
        return {
            "process_id": self.process_id,
            "label": self.label,
            "running": "yes" if self.running else "no",
            "duplicates": self.duplicate_count,
            "manageable": "yes" if self.manageable else "no",
            "pids": ", ".join(str(pid) for pid in self.pids),
            "command": "\n".join(self.command_lines),
        }


class ProcessService:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()

    def specs(self) -> list[ManagedProcessSpec]:
        return [
            ManagedProcessSpec(
                process_id="zet_web",
                label="Zet Web Dashboard",
                match_terms=("zet.web.app",),
                command="run_zet_web.bat",
                cwd=self.project_root,
            ),
            ManagedProcessSpec(
                process_id="auto_harvest",
                label="Auto Harvester",
                match_terms=("zet.scripts.auto_harvest_ai_answers",),
                command="run_auto_harvest.bat",
                cwd=self.project_root,
            ),
        ]

    def _list_windows_processes(self) -> list[ProcessInfo]:
        command = (
            "$items = Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -ne $null -and $_.Name -like 'python*' } | "
            "Select-Object ProcessId,Name,CommandLine,ParentProcessId; "
            "@($items) | ConvertTo-Json -Depth 3"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        payload = json.loads(result.stdout)
        if isinstance(payload, dict):
            payload = [payload]
        processes: list[ProcessInfo] = []
        for item in payload:
            try:
                processes.append(
                    ProcessInfo(
                        pid=int(item.get("ProcessId")),
                        name=str(item.get("Name") or ""),
                        command_line=str(item.get("CommandLine") or ""),
                        parent_pid=int(item.get("ParentProcessId")) if item.get("ParentProcessId") is not None else None,
                    )
                )
            except Exception:
                continue
        python_core_parent_pids = {
            process.parent_pid
            for process in processes
            if process.name.lower() == "python.exe" and process.parent_pid is not None
        }
        return [
            process
            for process in processes
            if not (process.name.lower() == "python3.exe" and process.pid in python_core_parent_pids)
        ]

    def _list_posix_processes(self) -> list[ProcessInfo]:
        result = subprocess.run(
            ["ps", "-eo", "pid=,comm=,args="],
            capture_output=True,
            text=True,
            check=False,
        )
        processes: list[ProcessInfo] = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue
            try:
                processes.append(ProcessInfo(pid=int(parts[0]), name=parts[1], command_line=parts[2]))
            except Exception:
                continue
        return processes

    def list_processes(self) -> list[ProcessInfo]:
        if platform.system() == "Windows":
            return self._list_windows_processes()
        return self._list_posix_processes()

    def _matches(self, process: ProcessInfo, spec: ManagedProcessSpec) -> bool:
        text = process.command_line.lower()
        return all(term.lower() in text for term in spec.match_terms)

    def statuses(self) -> list[ManagedProcessStatus]:
        processes = self.list_processes()
        statuses: list[ManagedProcessStatus] = []
        for spec in self.specs():
            matches = [process for process in processes if self._matches(process, spec)]
            statuses.append(
                ManagedProcessStatus(
                    process_id=spec.process_id,
                    label=spec.label,
                    running=bool(matches),
                    duplicate_count=max(0, len(matches) - 1),
                    manageable=spec.manageable,
                    pids=[process.pid for process in matches],
                    command_lines=[process.command_line for process in matches],
                )
            )
        return statuses

    def _spec_by_id(self, process_id: str) -> ManagedProcessSpec:
        for spec in self.specs():
            if spec.process_id == process_id:
                return spec
        raise ValueError(f"Unknown process id: {process_id}")

    def start(self, process_id: str) -> None:
        spec = self._spec_by_id(process_id)
        if not spec.manageable:
            raise ValueError(f"{spec.label} is status-only.")
        if spec.command is None or spec.cwd is None:
            raise ValueError(f"{spec.label} has no configured start command.")
        spec.cwd.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["ZET_PROJECT_ROOT"] = str(self.project_root)
        python_paths = [str(self.project_root), str(self.project_root / "Scripts")]
        if env.get("PYTHONPATH"):
            python_paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_paths)
        if platform.system() == "Windows":
            subprocess.Popen(
                ["cmd.exe", "/k", "call", spec.command],
                cwd=str(spec.cwd),
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            subprocess.Popen(spec.command, cwd=str(spec.cwd), env=env, shell=True)
        if process_id == "zet_web":
            self.start_if_stopped("auto_harvest")

    def start_if_stopped(self, process_id: str) -> bool:
        spec = self._spec_by_id(process_id)
        if any(self._matches(process, spec) for process in self.list_processes()):
            return False
        self.start(process_id)
        return True

    def stop(self, process_id: str) -> int:
        spec = self._spec_by_id(process_id)
        if not spec.manageable:
            raise ValueError(f"{spec.label} is status-only.")
        matches = [process for process in self.list_processes() if self._matches(process, spec)]
        for process in matches:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, text=True)
            else:
                os.kill(process.pid, signal.SIGTERM)
        return len(matches)

    def restart(self, process_id: str) -> int:
        spec = self._spec_by_id(process_id)
        matches = [process for process in self.list_processes() if self._matches(process, spec)]
        if process_id == "zet_web" and any(process.pid == os.getpid() for process in matches):
            self._schedule_self_restart(spec, matches)
            self.start_if_stopped("auto_harvest")
            return len(matches)
        stopped = self.stop(process_id)
        self.start(process_id)
        return stopped

    def restart_zet(self) -> tuple[int, int]:
        harvester_stopped = self.stop("auto_harvest")
        dashboard_stopped = self.restart("zet_web")
        return harvester_stopped, dashboard_stopped

    def _schedule_self_restart(self, spec: ManagedProcessSpec, matches: list[ProcessInfo]) -> None:
        if spec.command is None or spec.cwd is None:
            raise ValueError(f"{spec.label} has no configured start command.")
        command = [
            sys.executable,
            "-B",
            "-m",
            "zet.scripts.restart_managed_process",
            "--cwd",
            str(spec.cwd),
            "--command",
            spec.command,
        ]
        for process in matches:
            command.extend(["--pid", str(process.pid)])
        kwargs = {
            "cwd": str(self.project_root),
            "env": os.environ.copy(),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(command, **kwargs)
