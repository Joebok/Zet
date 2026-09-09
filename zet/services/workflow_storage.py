"""Durable file operations shared by character and scene workflows."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from io import BytesIO
import os
from pathlib import Path
import shutil
import threading
import time
from uuid import uuid4

from PIL import Image

from zet.services.atomic_file_service import replace_with_retry, write_json_atomic


_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}
_held = threading.local()


@contextmanager
def file_lock(path: Path, timeout: float = 30):
    """Serialize threads and processes; the OS releases locks after a crash.

    Lock files intentionally persist: unlinking them can split concurrent owners
    across different inodes. Nested calls in the same thread are supported.
    """
    key = os.path.normcase(str(path.resolve()))
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    if not lock.acquire(timeout=timeout):
        raise TimeoutError(f"Workflow is busy: {path}")
    held = getattr(_held, "paths", None)
    if held is None:
        held = _held.paths = set()
    try:
        if key in held:
            yield
            return
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
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Workflow is busy: {path}") from None
                    time.sleep(0.05)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock.release()


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        replace_with_retry(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def validate_image(contents: bytes) -> None:
    if not contents:
        raise ValueError("No image data was provided.")
    try:
        with Image.open(BytesIO(contents)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Expected a PNG, JPEG, or WEBP image.")
            image.verify()
        with Image.open(BytesIO(contents)) as image:
            image.load()
    except (OSError, SyntaxError) as exc:
        raise ValueError("The image is invalid or incomplete.") from exc


def subject_key(manifest: dict) -> tuple:
    if manifest.get("story_slug") and manifest.get("scene_slug"):
        return ("scene", manifest["story_slug"], manifest["scene_slug"], manifest.get("render_target_id") or "main")
    return ("asset", manifest.get("character"), manifest.get("phase"), str(manifest.get("asset_id")))


def task_state_path(queue_root: Path, kind: str, ask_id: str) -> Path:
    key = hashlib.sha256(ask_id.encode("utf-8")).hexdigest()
    return queue_root / "Zet_File_Proxy_State" / kind / f"{key}.json"


def supersede_task(queue_root: Path, task: Path, reason: str) -> None:
    """Fence late answers and retain asks/answers for recovery."""
    write_json_atomic(task_state_path(queue_root, "Superseded", task.name), {"ask_id": task.name, "reason": reason})
    # Answers and running work must remain available to their consumers.
    if task.parent.parent.name == "Ask":
        destination = queue_root / "Zet_File_Proxy_State" / "Superseded_Asks" / task.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if task.exists() and not destination.exists():
            task.rename(destination)


def snapshot_manual_ask(staging: Path, ready: Path, manifest: dict, resolve_path) -> dict:
    """Bind ordered attachments and prompt bytes to a single immutable ask."""
    references = []
    localized = {}
    for index, reference in enumerate(manifest.get("reference_files") or [], 1):
        item = dict(reference)
        source = resolve_path(str(item.get("path") or ""))
        if not source.is_file():
            raise FileNotFoundError(f"Reference image not found: {source}")
        relative = Path("references") / f"{index}_{source.name}"
        atomic_copy(source, staging / relative)
        item["source_path"] = str(source)
        item["sha256"] = hashlib.sha256((staging / relative).read_bytes()).hexdigest()
        item["path"] = str(ready / relative)
        localized[str(reference.get("path"))] = item["path"]
        references.append(item)
    manifest["reference_files"] = references
    manifest["image_inputs"] = [
        {**item, "path": localized.get(str(item.get("path")), item.get("path"))}
        for item in manifest.get("image_inputs") or []
    ]
    prompt = (staging / manifest["prompt_file"]).read_bytes()
    manifest["prompt_sha256"] = hashlib.sha256(prompt).hexdigest()
    manifest["render_bundle_hash"] = hashlib.sha256(json.dumps({
        "prompt": manifest["prompt_sha256"],
        "inputs": [{key: value for key, value in item.items() if key != "path"} for item in manifest["image_inputs"]],
        "images": [item["sha256"] for item in references],
    }, sort_keys=True).encode()).hexdigest()
    write_json_atomic(staging / "ask_manifest.json", manifest)
    return manifest
