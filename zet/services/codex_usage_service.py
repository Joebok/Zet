"""Read account quota over the installed Codex stdio protocol, without a model turn."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time


def codex_executable():
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        binaries = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
        if binaries:
            return str(max(binaries, key=lambda item: item.stat().st_mtime_ns))
    executable = shutil.which("codex.exe") or shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex is unavailable on the worker host.")
    return executable


class CodexUsageService:
    def __init__(self, store, reserve_percent=10):
        self.store = store
        self.reserve = reserve_percent

    @staticmethod
    def normalize(value, reserve, now=None):
        now = now or time.time()
        buckets = value.get("rateLimitsByLimitId") or {"codex": value.get("rateLimits")}
        windows = []
        for name, bucket in buckets.items():
            if not isinstance(bucket, dict) or "codex" not in name.lower():
                continue
            for kind in ("primary", "secondary"):
                window = bucket.get(kind)
                if not isinstance(window, dict) or not isinstance(window.get("usedPercent"), (int, float)):
                    continue
                windows.append({"bucket": name, "window": kind, "remaining_percent": max(0, min(100, 100 - window["usedPercent"])),
                                "resets_at": window.get("resetsAt"), "duration_minutes": window.get("windowDurationMins")})
        allowed = bool(windows) and value.get("ordinaryUsageAllowed") is not False and all(item["remaining_percent"] >= reserve for item in windows)
        return {"checked_at": now, "known": bool(windows), "allowed": allowed, "reserve_percent": reserve,
                "windows": windows, "error": None if windows else "Codex did not return usage windows."}

    def read_account(self):
        process = subprocess.Popen([codex_executable(), "app-server", "--stdio"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        responses = queue.Queue()
        def reader():
            for line in process.stdout:
                try:
                    responses.put(json.loads(line))
                except ValueError:
                    pass
        threading.Thread(target=reader, daemon=True).start()
        def send(value):
            process.stdin.write(json.dumps(value) + "\n")
            process.stdin.flush()
        def receive(identifier):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                item = responses.get(timeout=max(.1, deadline - time.monotonic()))
                if item.get("id") == identifier:
                    if "error" in item:
                        raise RuntimeError("Codex usage access failed. Check sign-in and installed protocol support.")
                    return item["result"]
            raise RuntimeError("Codex usage access timed out.")
        try:
            send({"method": "initialize", "id": 1, "params": {"clientInfo": {"name": "zet_usage", "version": "1.0"}}})
            receive(1)
            send({"method": "initialized", "params": {}})
            send({"method": "account/rateLimits/read", "id": 2})
            return receive(2)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            process.stdin.close()
            process.stdout.close()

    def refresh(self):
        try:
            status = self.normalize(self.read_account(), self.reserve)
        except (OSError, RuntimeError, queue.Empty, ValueError) as exc:
            status = {"checked_at": time.time(), "known": False, "allowed": False, "windows": [],
                      "reserve_percent": self.reserve, "error": str(exc)[:300] or "Codex usage access timed out."}
        self.store.put("status", "usage", status)
        return status
