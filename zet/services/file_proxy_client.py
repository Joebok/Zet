from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import shutil
import socket
import time
from typing import Iterator


class FileProxyClient:
    """Zet subscriber client for the standalone file proxy protocol."""

    subscriber_id = "zet"
    worker_names = {
        "ollama_generate": "ollama",
        "local_image_render": "local_image",
    }

    def __init__(self, base_queue_path: str | Path):
        self.base_queue_path = Path(base_queue_path)
        self.root = self.base_queue_path / "File_Proxy"
        self.route_root = self.base_queue_path / "Zet_File_Proxy_State" / "Routes"

    @property
    def ask_root(self) -> Path:
        return self.root / "Ask" / self.subscriber_id

    @property
    def running_root(self) -> Path:
        return self.root / "Running" / self.subscriber_id

    @property
    def answer_root(self) -> Path:
        return self.root / "Answer" / self.subscriber_id

    def ensure_layout(self) -> None:
        for path in (self.ask_root, self.running_root, self.answer_root):
            path.mkdir(parents=True, exist_ok=True)

    def staging_path(self, job_id: str) -> Path:
        return self.ask_root / f".{job_id}.staging"

    def ready_path(self, job_id: str) -> Path:
        return self.ask_root / job_id

    def create_staging(self, job_id: str) -> Path:
        self.ensure_layout()
        staging = self.staging_path(job_id)
        staging.mkdir(parents=False, exist_ok=False)
        return staging

    def publish(self, staging: Path, job_id: str, worker_type: str) -> Path:
        worker = self.worker_names.get(worker_type)
        if worker is None:
            raise ValueError(f"Unsupported Zet file-proxy worker type: {worker_type}")
        route_required = self._externalize_routes(staging, job_id)
        resource_key = self._resource_key(staging, worker_type)
        job_manifest = {
            "protocol_version": 1,
            "job_id": job_id,
            "subscriber_id": self.subscriber_id,
            "worker": worker,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "files": self._file_inventory(staging),
            "route_required": route_required,
            "producer_id": socket.gethostname(),
            "resource_key": resource_key,
        }
        temp = staging / ".job.json.tmp"
        temp.write_text(json.dumps(job_manifest, indent=2) + "\n", encoding="utf-8")
        self._replace_with_retry(temp, staging / "job.json")
        ready = self.ready_path(job_id)
        self._replace_with_retry(staging, ready)
        return ready

    @staticmethod
    def _resource_key(staging: Path, worker_type: str) -> str:
        manifest = json.loads((staging / "ask_manifest.json").read_text(encoding="utf-8"))
        if worker_type == "ollama_generate":
            model = str(manifest.get("ollama_model") or "").strip() or "general-purpose:latest"
            return f"ollama:{model}"
        backend = str(manifest.get("image_generation") or "").strip().lower() or "stable_matrix"
        checkpoint = str(manifest.get("checkpoint") or "").strip() or "default"
        return f"image:{backend}:{checkpoint}"

    @staticmethod
    def _replace_with_retry(source: Path, destination: Path, timeout_seconds: float = 15.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        delay = 0.05
        while True:
            try:
                os.replace(source, destination)
                return
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 1.0)

    def _externalize_routes(self, staging: Path, job_id: str) -> bool:
        manifest_path = staging / "ask_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        localized_paths = self._localize_references(staging, manifest)
        route: dict[str, str] = {}
        for key in (
            "target_output_dir",
            "artifact_output_dir",
            "prompt_condense_template",
            "pipeline_path",
            "target_output_file",
        ):
            value = manifest.get(key)
            if isinstance(value, str) and Path(value).is_absolute():
                route[key] = value
                del manifest[key]
        self._localize_json_paths(staging, manifest, localized_paths)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for json_path in staging.glob("*.json"):
            if json_path == manifest_path or json_path.name == "job.json":
                continue
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self._localize_json_paths(staging, payload, localized_paths)
            json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if route:
            route["_producer_id"] = socket.gethostname()
            self.route_root.mkdir(parents=True, exist_ok=True)
            route_path = self.route_root / f"{job_id}.json"
            temp = route_path.with_name(f".{route_path.name}.tmp")
            temp.write_text(json.dumps(route, indent=2) + "\n", encoding="utf-8")
            self._replace_with_retry(temp, route_path)
        return bool(route)

    @staticmethod
    def _file_inventory(folder: Path) -> list[dict[str, str | int]]:
        inventory: list[dict[str, str | int]] = []
        for path in sorted(item for item in folder.rglob("*") if item.is_file()):
            if path.name.startswith("."):
                continue
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            inventory.append(
                {
                    "path": path.relative_to(folder).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": digest.hexdigest(),
                }
            )
        return inventory

    @staticmethod
    def _inventory_complete(folder: Path, records) -> bool:
        if not isinstance(records, list):
            return False
        try:
            for record in records:
                relative = str(record["path"])
                posix = PurePosixPath(relative)
                windows = PureWindowsPath(relative)
                if (
                    posix.is_absolute()
                    or windows.is_absolute()
                    or ".." in posix.parts
                    or ".." in windows.parts
                ):
                    return False
                path = folder.joinpath(*posix.parts)
                if not path.is_file() or path.stat().st_size != int(record["size"]):
                    return False
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != str(record["sha256"]).lower():
                    return False
        except (KeyError, OSError, TypeError, ValueError):
            return False
        return True

    def answer_is_ready(self, answer: Path) -> bool:
        if (answer / "harvest_manifest.json").is_file():
            return True
        try:
            job = json.loads((answer / "job.json").read_text(encoding="utf-8"))
            result = json.loads((answer / "proxy_result.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
        producer_id = str(job.get("producer_id") or "")
        if producer_id and producer_id.casefold() != socket.gethostname().casefold():
            return False
        if job.get("route_required") and not (self.route_root / f"{answer.name}.json").is_file():
            return False
        return self._inventory_complete(answer, result.get("output_files"))

    def _localize_references(self, staging: Path, manifest: dict) -> dict[str, str]:
        references = manifest.get("reference_files")
        if not isinstance(references, list):
            return {}
        reference_root = staging / "references"
        used_names: set[str] = set()
        localized: dict[str, str] = {}
        for index, reference in enumerate(references, start=1):
            if not isinstance(reference, dict):
                continue
            value = reference.get("path")
            if not isinstance(value, str) or not Path(value).is_absolute():
                continue
            source = Path(value)
            if not source.is_file():
                raise FileNotFoundError(f"Reference file does not exist: {source}")
            reference_root.mkdir(exist_ok=True)
            name = source.name
            if name in used_names:
                name = f"{index}_{name}"
            used_names.add(name)
            shutil.copy2(source, reference_root / name)
            relative = f"references/{name}"
            localized[str(source.resolve()).casefold()] = relative
            reference["path"] = relative
        return localized

    def _localize_json_paths(
        self,
        staging: Path,
        value,
        localized_paths: dict[str, str],
    ):
        if isinstance(value, dict):
            for key, child in value.items():
                value[key] = self._localize_json_paths(staging, child, localized_paths)
            return value
        if isinstance(value, list):
            for index, child in enumerate(value):
                value[index] = self._localize_json_paths(staging, child, localized_paths)
            return value
        if not isinstance(value, str) or not Path(value).is_absolute():
            return value

        source = Path(value)
        source_key = str(source.resolve()).casefold()
        if source_key in localized_paths:
            return localized_paths[source_key]
        if not source.is_file():
            raise FileNotFoundError(f"Referenced job input does not exist: {source}")

        input_root = staging / "inputs"
        input_root.mkdir(exist_ok=True)
        name = source.name
        destination = input_root / name
        suffix = 2
        while destination.exists():
            destination = input_root / f"{source.stem}_{suffix}{source.suffix}"
            suffix += 1
        relative = f"inputs/{destination.name}"
        localized_paths[source_key] = relative
        if source.suffix.lower() == ".json":
            try:
                payload = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                shutil.copy2(source, destination)
            else:
                self._localize_json_paths(staging, payload, localized_paths)
                destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        else:
            shutil.copy2(source, destination)
        return relative

    def load_route(self, job_id: str) -> dict[str, str]:
        path = self.route_root / f"{job_id}.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def remove_route(self, job_id: str) -> None:
        (self.route_root / f"{job_id}.json").unlink(missing_ok=True)

    def task_paths(self, *states: str) -> Iterator[Path]:
        roots = {"ask": self.ask_root, "running": self.running_root, "answer": self.answer_root}
        for state in states:
            root = roots[state]
            if root.exists():
                paths = sorted(
                    path for path in root.iterdir()
                    if path.is_dir() and not path.name.startswith(".")
                )
                if state == "answer":
                    paths = [path for path in paths if self.answer_is_ready(path)]
                yield from paths

    def queue_snapshot(self) -> dict[str, list[str]]:
        return {
            state: [path.name for path in self.task_paths(state)]
            for state in ("ask", "running", "answer")
        }

    def scan_answers(self) -> list[Path]:
        return list(self.task_paths("answer"))

    def remove_answer(self, job_id: str) -> bool:
        answer = self.answer_root / job_id
        if not answer.exists():
            return False
        shutil.rmtree(answer)
        return True

    def archive_answer(self, job_id: str, archive_root: Path) -> Path:
        answer = self.answer_root / job_id
        if not answer.is_dir():
            raise FileNotFoundError(answer)
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = archive_root / job_id
        if destination.exists():
            destination = archive_root / f"{job_id}_{datetime.now().strftime('%H%M%S_%f')}"
        return Path(shutil.move(str(answer), str(destination)))
