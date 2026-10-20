"""Stdlib-only template snapshot guards, also copied beside the deployment helper."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time


TEMPLATE_PATHS = frozenset({"Config/Prompt_Global_Sections.md", *(
    f"Config/Prompt_Templates/{name}_v2.md" for name in
    ("body_reference", "head_image", "character_assembly", "costume_dressing"))})
BUSY = {"preparing", "validating", "publishing"}
_mutex = threading.Lock()
_locks = {}
_held = threading.local()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *args, input=None, binary=False, timeout=120):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], input=input,
                                capture_output=True, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Git is unavailable or timed out. Retain the captured work and retry.") from exc
    if result.returncode:
        raise ValueError("Git operation failed: " + (result.stderr or result.stdout).decode("utf-8", "replace")[-1200:])
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def canonical(raw):
    # These five Markdown templates are text; Git's Windows checkout may use CRLF.
    return raw.replace(b"\r\n", b"\n")


@contextmanager
def change_lock(state, timeout=30):
    """Fence master writes and the final deployment check/stop, across processes."""
    key = os.path.normcase(str(Path(state).resolve()))
    with _mutex:
        mutex = _locks.setdefault(key, threading.RLock())
    if not mutex.acquire(timeout=timeout):
        raise ValueError("Template/update operation is busy; retry later.")
    try:
        held = getattr(_held, "paths", set())
        _held.paths = held
        if key in held:
            yield
            return
        path = Path(state) / "template-changes.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise ValueError("Template/update operation is busy; retry later.") from None
                    time.sleep(.05)
            try:
                held.add(key)
                yield
            finally:
                held.remove(key)
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        mutex.release()


def inspect(root):
    root = Path(root).resolve()
    revision = git(root, "rev-parse", "HEAD")
    rows = []
    # --raw -z accounts for staged and unstaged changes, deletions and type changes.
    fields = git(root, "diff", "--raw", "--no-renames", "-z", "HEAD", binary=True).split(b"\0")
    for index in range(0, len(fields) - 1, 2):
        metadata, name = fields[index:index + 2]
        path = name.decode("utf-8")
        target = root / path
        kind = metadata.decode().split()[-1]
        modes = metadata.decode().split()[:2]
        eligible = (path in TEMPLATE_PATHS and kind == "M" and modes == [":100644", "100644"]
                    and not target.is_symlink() and target.resolve().is_relative_to(root) and target.is_file())
        raw = target.read_bytes() if eligible else b""
        rows.append({"path": path, "eligible": eligible, "raw_sha256": digest(raw) if eligible else None,
                     "reason": "Unpublished governing template edit." if eligible else
                     "This tracked edit cannot be published by template recovery.",
                     "diff": git(root, "diff", "--no-ext-diff", "--no-textconv", "HEAD", "--", path) if eligible else ""})
    identity = digest(json.dumps([str(root), revision, rows], sort_keys=True).encode())
    return {"root": str(root), "revision": revision, "snapshot_id": identity, "files": rows}


def guard(root, target, receipt=None):
    """Allow only unchanged captures whose merged published blobs are in target."""
    report = inspect(root)
    receipt = receipt or {}
    valid = (receipt.get("state") == "ready" and receipt.get("source_root") == report["root"]
             and receipt.get("source_revision") == report["revision"])
    if valid:
        merge = receipt.get("merge_commit")
        if not isinstance(merge, str) or len(merge) != 40 or any(c not in "0123456789abcdef" for c in merge):
            valid = False
        else:
            try:
                git(target, "merge-base", "--is-ancestor", merge, "HEAD")
            except ValueError:
                valid = False
    captured = {row["path"]: row for row in receipt.get("files", [])} if valid else {}
    blockers = []
    for row in report["files"]:
        saved = captured.get(row["path"], {})
        accepted = row["eligible"] and row["raw_sha256"] == saved.get("raw_sha256")
        if accepted:
            blob = git(target, "show", f"HEAD:{row['path']}", binary=True)
            accepted = digest(canonical(blob)) == saved.get("published_sha256")
        if not accepted:
            blockers.append(row["path"])
    if blockers:
        raise ValueError("Production has local tracked edits. Publish and merge unchanged template edits before update: "
                         + ", ".join(blockers))
    return report
