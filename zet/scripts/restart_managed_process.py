from __future__ import annotations

import argparse
import os
import platform
import signal
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--pid", type=int, action="append", default=[])
    args = parser.parse_args()

    time.sleep(1)
    for pid in args.pid:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    time.sleep(0.5)
    if platform.system() == "Windows":
        subprocess.Popen(
            ["cmd.exe", "/k", "call", args.command],
            cwd=str(args.cwd),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        subprocess.Popen(args.command, cwd=str(args.cwd), shell=True, start_new_session=True)


if __name__ == "__main__":
    main()
