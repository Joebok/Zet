import json
import os
import shutil
import socket
from pathlib import Path


def write_claim_file(
    path: Path,
    ask_name: str,
    worker_id: str,
    claimed_at: str,
    *,
    suppress_cleanup_error: bool = True,
) -> bool:
    data = {
        "version": 1,
        "ask_folder": ask_name,
        "worker_id": worker_id,
        "claimed_at": claimed_at,
        "host": socket.gethostname(),
        "pid": os.getpid(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(str(path), flags)
    except Exception:
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except Exception:
                pass
        return True
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            if not suppress_cleanup_error:
                raise
        return False


def move_ask_to_claimed(
    ask: Path,
    dest: Path,
    claim_file: Path,
    *,
    tolerate_claim_manifest_copy_error: bool = False,
) -> None:
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(str(ask), str(dest))
    try:
        shutil.copy2(str(claim_file), str(dest / "claim_manifest.json"))
    except Exception:
        if not tolerate_claim_manifest_copy_error:
            raise
    shutil.rmtree(ask, ignore_errors=True)


def move_to_answer(folder: Path, answer_root: Path) -> Path:
    dest = answer_root / folder.name
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(folder), str(dest))
    return dest


def remove_claim_files(folder: Path, claim_file: Path, *, suppress_errors: bool = False) -> None:
    for path in (claim_file, folder / "claim_manifest.json"):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            if not suppress_errors:
                raise


def release_to_ask_or_failed(
    folder: Path,
    ask_dest: Path,
    failed_root: Path,
    timestamp: int,
) -> tuple[Path, bool]:
    if ask_dest.exists():
        failed_dest = failed_root / f"{folder.name}__released_duplicate_{timestamp}"
        shutil.move(str(folder), str(failed_dest))
        return failed_dest, True
    shutil.move(str(folder), str(ask_dest))
    return ask_dest, False
