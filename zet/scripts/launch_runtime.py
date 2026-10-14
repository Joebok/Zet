"""Start the last promoted production release without using development config."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from zet.scripts.deploy_release import library_reference_version, release_python, run, start_harvester, start_release


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
    contract = json.loads((release / "Config" / "Runtime_Contract.json").read_text(encoding="utf-8"))
    if int(contract.get("library_reference_version", 0)) < library_reference_version_from_release(release):
        raise RuntimeError("The active release cannot read the configured library path format; restore a compatible release or library copy.")
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


def library_reference_version_from_release(release):
    from zet.services.config_service import ConfigService

    config = ConfigService.load(Path(release) / "config.runtime.toml")
    return library_reference_version(config.library_container_path or config.base_library_path)


if __name__ == "__main__":
    main()
