"""Prepare the existing disposable inspection fixture for an issue worktree."""
import importlib.util
from pathlib import Path
import sys
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    if not (root / ".git").is_file():
        raise RuntimeError("Prepare issue data only inside an isolated Git worktree.")
    python = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    original = subprocess.check_output(["git", "-C", str(root), "show", "origin/main:requirements.txt"], text=True).replace("\r\n", "\n")
    current = (root / "requirements.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
    if original != current:
        raise RuntimeError("Worker setup cannot install changed dependency declarations without Joe's approval.")
    available = subprocess.run([str(python), "-c", "import sys, uvicorn, fastapi, PIL, numpy, cv2, markdown; assert sys.version_info.major == 3"], capture_output=True)
    if available.returncode:
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")], check=True)
    if python.exists() and Path(sys.executable).resolve() != python.resolve():
        subprocess.run([str(python), "-c", "import sys; assert sys.version_info.major == 3"], check=True)
        return subprocess.run([str(python), "-B", "-m", "zet.scripts.prepare_issue_workspace"], check=False).returncode
    spec = importlib.util.spec_from_file_location("zet_fixture_setup", root / "tests" / "e2e" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.prepare("inspection")
    print(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
