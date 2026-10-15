from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--command-json", required=True)
    parser.add_argument("--after-command-json")
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
    command = json.loads(args.command_json)
    subprocess.Popen(command, cwd=str(args.cwd), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     start_new_session=platform.system() != "Windows")
    if args.after_command_json:
        # Let the dashboard bind its port and enter startup before starting the
        # companion worker. Both processes use the same managed config.
        time.sleep(1)
        subprocess.Popen(json.loads(args.after_command_json), cwd=str(args.cwd),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         start_new_session=platform.system() != "Windows")


if __name__ == "__main__":
    main()
