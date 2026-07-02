from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    command_line: str


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
        ollama_root = Path("C:/Users/Joe/Ollama")
        return [
            ManagedProcessSpec(
                process_id="dashboard",
                label="Dashboard",
                match_terms=("streamlit", "zet/dashboard/app.py"),
                manageable=False,
            ),
            ManagedProcessSpec(
                process_id="proxy_worker",
                label="Unified Proxy Worker",
                match_terms=("proxy_worker.py", "Ollama_Proxy"),
                command="run_proxy_worker.bat",
                cwd=ollama_root,
            ),
            ManagedProcessSpec(
                process_id="auto_harvest",
                label="Auto Harvester",
                match_terms=("zet.scripts.auto_harvest_ai_answers",),
                command="run_auto_harvest.bat",
                cwd=self.project_root,
            ),
            ManagedProcessSpec(
                process_id="render_console",
                label="Render Console",
                match_terms=("zet.render_console.app",),
                command="run_render_console.bat",
                cwd=self.project_root,
            ),
        ]

    def _list_windows_processes(self) -> list[ProcessInfo]:
        command = (
            "$items = Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -ne $null -and $_.Name -like 'python*' } | "
            "Select-Object ProcessId,Name,CommandLine; "
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
                    )
                )
            except Exception:
                continue
        return processes

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
        if platform.system() == "Windows":
            subprocess.Popen(
                ["cmd.exe", "/k", "call", spec.command],
                cwd=str(spec.cwd),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            subprocess.Popen(spec.command, cwd=str(spec.cwd), shell=True)

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
        stopped = self.stop(process_id)
        self.start(process_id)
        return stopped
