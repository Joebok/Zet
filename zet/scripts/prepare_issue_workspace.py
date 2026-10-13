"""Prepare the existing disposable inspection fixture for an issue worktree."""
import importlib.util
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").is_file():
        raise RuntimeError("Prepare issue data only inside an isolated Git worktree.")
    spec = importlib.util.spec_from_file_location("zet_fixture_setup", root / "tests" / "e2e" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.prepare("inspection")
    print(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
