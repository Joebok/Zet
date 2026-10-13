"""Start the last promoted production release without using development config."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from zet.scripts.deploy_release import release_python, run, start_harvester, start_release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    active_path = root / "state" / "active-release.json"
    if not active_path.exists():
        raise RuntimeError("No release has been promoted. Merge the workflow PR and use Update and restart in Zet first.")
    active = json.loads(active_path.read_text(encoding="utf-8"))
    release = Path(active["release"]).resolve()
    if release.parent != root / "releases":
        raise RuntimeError("Active release is outside Runtime.Root/releases.")
    host, port = active.get("host", "0.0.0.0"), active.get("port", 8081)
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            health = json.load(response)
        if health.get("instance", "").startswith("production:") and health.get("revision") == active["revision"]:
            print("Production is already running.")
            return
        raise RuntimeError("Another Zet instance occupies the production port. No process was stopped.")
    except OSError:
        pass
    run([str(release_python(release)), "-c", "import sys; assert sys.version_info.major == 3"])
    start_release(release, host, port, root / "state")
    start_harvester(release)
    print(f"Starting production revision {active['revision']} on port {port}.")


if __name__ == "__main__":
    main()
