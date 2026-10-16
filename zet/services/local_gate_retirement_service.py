"""Inventory and explicitly retire persisted local character gate data."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from zet.services.atomic_file_service import write_json_atomic
from zet.services.library_reference_service import (
    pipeline_library_root_for_path, read_library_json, write_library_json,
)


GATE_FIELDS = {
    "gates", "face_gate", "gate_history", "face_gate_history", "gate_rejection_history",
    "gate_results", "gate_attempts", "gate_retries", "gate_errors", "gate_rejections",
    "gate_verdicts", "gate_answers", "gate_evidence", "gate_counters",
    "rejection_gate", "failed_gate", "legacy_review_stale", "gate_rejection_count",
    "gate_count", "gate_failure_count", "gate_status", "gates_status", "gate_profile",
    "gate_profiles", "gate_policy", "gate_settings", "gate_prompt", "gate_prompt_hash",
    "gate_model", "gate_models",
}
WAITING_GATE_STATES = {"WAITING_FOR_GATES", "WAITING_FOR_FACE_GATE", "GATE_REJECTED"}


class LocalGateRetirementService:
    """Plan/apply a backed-up cleanup of gate-owned character pipeline records."""

    def __init__(self, library_root: str | Path, queue_root: str | Path | None = None):
        self.library_root = Path(library_root).expanduser().resolve()
        self.queue_root = Path(queue_root).expanduser().resolve() if queue_root else None
        self._image_hashes_by_run: dict[str, dict[str, str]] = {}

    def _roots(self) -> list[Path]:
        """Mirror UniverseService's descriptor/sibling and legacy-Moonsea rules."""
        roots = [path for path in self.library_root.iterdir()
                 if path.is_dir() and (path / "universe.json").is_file()] if self.library_root.is_dir() else []
        if not any(path.name.casefold() == "moonsea" for path in roots):
            roots.append(self.library_root)
        return sorted(set(roots))

    def _run_dirs(self) -> list[Path]:
        found: set[Path] = set()
        pipeline_kinds = {"local_body_reference", "local_head_image", "character-assembly", "costume-dressing"}
        for root in self._roots():
            candidates = root / "PipelineCandidates"
            if not candidates.is_dir():
                continue
            for spec_path in candidates.rglob("spec.json"):
                run_root = spec_path.parent
                # A malformed spec under the character-pipeline namespace must be
                # reported instead of silently escaping the all-or-nothing migration.
                if "Character-Pipeline" in spec_path.parts:
                    found.add(run_root)
                    continue
                try:
                    spec = json.loads(spec_path.read_text(encoding="utf-8"))
                    if isinstance(spec, dict) and spec.get("kind") in pipeline_kinds:
                        found.add(run_root)
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
        return sorted(found)

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _clean_run(spec: dict[str, Any], state: dict[str, Any], run_root: Path) -> tuple[dict[str, Any], dict[str, Any], bool]:
        before = json.dumps([spec, state], sort_keys=True)
        changed = False

        def clean_record(record: dict[str, Any]) -> None:
            nonlocal changed
            for key in list(record):
                if key in GATE_FIELDS or key.startswith("gate_") or key.startswith("gates_"):
                    record.pop(key)
                    changed = True
            if record.get("status") in WAITING_GATE_STATES:
                image = Path(str(record.get("image_path") or ""))
                if not image.is_absolute():
                    image = run_root / image
                if image.is_file() and image.stat().st_size > 0:
                    record["status"] = "WAITING_FOR_HUMAN_REVIEW"
                    record.pop("render_error", None)
                else:
                    record["status"] = "FAILED"
                    record["render_error"] = "The candidate image is missing after gate retirement."
                changed = True

        def clean_tree(value: Any) -> None:
            if isinstance(value, dict):
                clean_record(value)
                for child in value.values():
                    clean_tree(child)
            elif isinstance(value, list):
                for child in value:
                    clean_tree(child)

        old_review_version = spec.get("review_version", 1)
        spec["review_version"] = 3
        clean_tree(spec)
        clean_tree(state)
        # The old ranking prompt explicitly referenced gate results. Preserve it
        # as history, but require a fresh comparison under the new review contract.
        for ranking in (state.get("rankings") or {}).values():
            if (isinstance(ranking, dict) and ranking.get("status") == "COMPLETE"
                    and (old_review_version != 3 or ranking.get("gate_input_hashes"))):
                ranking.update(status="STALE", stale_reason="Ranking review contract changed when gates were removed.")
                changed = True
        return spec, state, changed or before != json.dumps([spec, state], sort_keys=True)

    @staticmethod
    def _clean_legacy_copy(value: Any, run_root: Path) -> tuple[Any, bool]:
        before = json.dumps(value, sort_keys=True)

        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for key in list(item):
                    if key in GATE_FIELDS or key.startswith("gate_") or key.startswith("gates_"):
                        item.pop(key, None)
                if item.get("status") in WAITING_GATE_STATES:
                    image = Path(str(item.get("image_path") or ""))
                    if not image.is_absolute():
                        image = run_root / image
                    if image.is_file() and image.stat().st_size:
                        item["status"] = "WAITING_FOR_HUMAN_REVIEW"
                        item.pop("render_error", None)
                    else:
                        item["status"] = "FAILED"
                        item["render_error"] = "The candidate image is missing after gate retirement."
                for child in item.values():
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)

        walk(value)
        return value, before != json.dumps(value, sort_keys=True)

    def inventory(self) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for run_root in self._run_dirs():
            if run_root.is_symlink() or not run_root.resolve().is_relative_to(self.library_root):
                errors.append({"path": str(run_root), "error": "linked or out-of-library pipeline run"})
                continue
            records = {}
            try:
                for name in ("spec.json", "state.json"):
                    records[name] = read_library_json(run_root / name, pipeline_library_root_for_path(run_root))
                    if not isinstance(records[name], dict):
                        raise ValueError(f"{name} must contain a JSON object")
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append({"path": str(run_root), "error": str(exc)})
                continue
            spec, state = records["spec.json"], records["state.json"]
            if not isinstance(spec.get("candidates", []), list) or not isinstance(state.get("candidates", {}), dict):
                errors.append({"path": str(run_root), "error": "candidate collections have an unsupported shape"})
                continue
            _, _, changed = self._clean_run(json.loads(json.dumps(spec)), json.loads(json.dumps(state)), run_root)
            combined = list(spec.get("candidates") or []) + list((state.get("candidates") or {}).values())
            image_paths = {str(item.get("image_path") or "") for item in combined if isinstance(item, dict)}
            image_hashes = {path: self._digest(Path(path) if Path(path).is_absolute() else run_root / path)
                            for path in image_paths if path and (Path(path) if Path(path).is_absolute() else run_root / path).is_file()}
            missing_images = sum(bool(path) and not (Path(path) if Path(path).is_absolute() else run_root / path).is_file()
                                 for path in image_paths)
            self._image_hashes_by_run[str(run_root)] = image_hashes
            image_set_hash = hashlib.sha256(json.dumps(sorted(image_hashes.items()), separators=(",", ":")).encode()).hexdigest()
            legacy_json_files = []
            for legacy_dir in run_root.rglob("legacy_review_v1"):
                if not legacy_dir.is_dir() or legacy_dir.is_symlink():
                    continue
                for legacy_path in legacy_dir.rglob("*.json"):
                    try:
                        if legacy_path.is_symlink() or not legacy_path.resolve().is_relative_to(run_root.resolve()):
                            raise ValueError("linked or out-of-run legacy review record")
                        legacy_value = read_library_json(legacy_path, pipeline_library_root_for_path(run_root))
                        _, legacy_changed = self._clean_legacy_copy(json.loads(json.dumps(legacy_value)), run_root)
                    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                        errors.append({"path": str(legacy_path), "error": str(exc)})
                        continue
                    if legacy_changed:
                        legacy_json_files.append(str(legacy_path))
            runs.append({"path": str(run_root), "run_id": spec.get("run_id", run_root.name),
                         "pipeline": spec.get("kind", ""), "changed": changed,
                         "candidate_count": len(spec.get("candidates") or []),
                         "image_count": len(image_hashes), "missing_image_count": missing_images,
                         "image_set_sha256": image_set_hash, "legacy_json_files": legacy_json_files})
        rig_roots = sorted({root / "PipelineCandidates" / "Gate-Test-Rig" for root in self._roots()
                            if (root / "PipelineCandidates" / "Gate-Test-Rig").exists()})
        rig_files = []
        for rig in rig_roots:
            if rig.is_symlink() or not rig.resolve().is_relative_to(self.library_root):
                errors.append({"path": str(rig), "error": "linked or out-of-library rig path"})
                continue
            rig_files.extend({"path": str(path), "bytes": path.stat().st_size}
                             for path in rig.rglob("*") if path.is_file())
        queue_jobs, queue_errors = self._queue_inventory()
        errors.extend(queue_errors)
        gate_evidence = []
        if self.queue_root is not None:
            evidence_root = self.queue_root / "Zet_File_Proxy_State" / "GateEvidence"
            if evidence_root.is_dir() and not evidence_root.is_symlink():
                gate_evidence = [{"path": str(path), "bytes": sum(child.stat().st_size for child in path.rglob("*") if child.is_file())}
                                 for path in evidence_root.iterdir() if path.is_dir() and not path.is_symlink()]
        return {"library_root": str(self.library_root), "runs": runs, "rig_roots": [str(p) for p in rig_roots],
                "rig_files": rig_files, "queue_root": str(self.queue_root or ""), "queue_jobs": queue_jobs,
                "gate_evidence": gate_evidence,
                "malformed": errors, "apply_blocked": bool(errors)}

    def _queue_inventory(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        if self.queue_root is None:
            return [], []
        known = {"local_head_image_gate", "local_body_reference_gate", "gate_test_rig", "gate_test_data"}
        queue_state = self.queue_root / "Zet_File_Proxy_State"
        roots = [self.queue_root / "File_Proxy" / name for name in ("Ask", "Running", "Answer")]
        roots.extend((queue_state / "Inbox", queue_state / "Receipts", queue_state / "Jobs"))
        jobs: dict[str, dict[str, Any]] = {}
        errors: list[dict[str, str]] = []
        for root in roots:
            if not root.is_dir() or root.is_symlink():
                continue
            manifest_name = "*.json" if root.name in {"Receipts", "Jobs"} else "ask_manifest.json"
            for manifest_path in root.rglob(manifest_name):
                if manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(root.resolve()):
                    errors.append({"path": str(manifest_path), "error": "linked or out-of-root queue manifest"})
                    continue
                try:
                    ask = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if not isinstance(ask, dict):
                        raise ValueError("ask manifest must be an object")
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                    if manifest_path.name == "ask_manifest.json":
                        errors.append({"path": str(manifest_path), "error": str(exc)})
                    continue
                task_type = str(ask.get("task_type") or "")
                if task_type not in known:
                    continue
                ask_id = str(ask.get("ask_id") or (manifest_path.parent.name if manifest_path.name == "ask_manifest.json" else ""))
                if not ask_id:
                    continue
                if Path(ask_id).name != ask_id or ask_id in {".", ".."}:
                    errors.append({"path": str(manifest_path), "error": "unsafe ask identifier"})
                    continue
                if manifest_path.name == "ask_manifest.json" and ask_id != manifest_path.parent.name:
                    errors.append({"path": str(manifest_path), "error": "ask id does not match its queue folder"})
                    continue
                key = ask_id
                location = manifest_path.parent if manifest_path.name == "ask_manifest.json" else manifest_path
                jobs[key] = {"ask_id": ask_id, "task_type": task_type,
                             "universe_id": str(ask.get("universe_id") or ""),
                             "locations": sorted(set([*jobs.get(key, {}).get("locations", []),
                                                       str(location)]))}
        receipt_root = queue_state / "Receipts"
        if receipt_root.is_dir() and not receipt_root.is_symlink():
            for receipt_path in receipt_root.glob("*.json"):
                try:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                if not isinstance(receipt, dict) or str(receipt.get("task_type") or "") not in known:
                    continue
                ask_id = str(receipt.get("ask_id") or "")
                if ask_id:
                    if Path(ask_id).name != ask_id or ask_id in {".", ".."}:
                        errors.append({"path": str(receipt_path), "error": "unsafe ask identifier"})
                        continue
                    jobs.setdefault(ask_id, {"ask_id": ask_id, "task_type": receipt.get("task_type", ""),
                                             "universe_id": receipt.get("universe_id", ""), "locations": []})
                    jobs[ask_id]["locations"] = sorted(set(jobs[ask_id]["locations"] + [str(receipt_path)]))
        return sorted(jobs.values(), key=lambda item: item["ask_id"]), errors

    def apply(self, backup_root: str | Path) -> dict[str, Any]:
        backup = Path(backup_root).expanduser().resolve()
        if backup == self.library_root or self.library_root in backup.parents:
            raise ValueError("Backup directory must be outside the active library.")
        if self.queue_root and (backup == self.queue_root or self.queue_root in backup.parents):
            raise ValueError("Backup directory must be outside the active queue.")
        report = self.inventory()
        if report["apply_blocked"]:
            raise ValueError(f"Migration blocked by {len(report['malformed'])} malformed run(s).")
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        backup = backup / stamp
        changes = []
        for item in report["runs"]:
            if not item["changed"] and not item["legacy_json_files"]:
                continue
            root = Path(item["path"])
            if item["changed"]:
                output = {}
                for name in ("spec.json", "state.json"):
                    path = root / name
                    output[name] = read_library_json(path, pipeline_library_root_for_path(root))
                    destination = backup / path.relative_to(self.library_root)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
                spec, state, _ = self._clean_run(output["spec.json"], output["state.json"], root)
                write_library_json(root / "spec.json", spec, pipeline_library_root_for_path(root))
                write_library_json(root / "state.json", state, pipeline_library_root_for_path(root))
                for image_path, expected_hash in self._image_hashes_by_run.get(item["path"], {}).items():
                    image = Path(image_path)
                    if image.is_file() and self._digest(image) != expected_hash:
                        raise ValueError(f"Candidate image changed during retirement: {image}")
            for legacy_name in item["legacy_json_files"]:
                legacy_path = Path(legacy_name)
                destination = backup / legacy_path.relative_to(self.library_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_path, destination)
                value = read_library_json(legacy_path, pipeline_library_root_for_path(root))
                cleaned, _ = self._clean_legacy_copy(value, root)
                write_library_json(legacy_path, cleaned, pipeline_library_root_for_path(root))
            changes.append(item["path"])
        deleted_rigs = []
        for rig_name in report["rig_roots"]:
            rig = Path(rig_name).resolve()
            if not rig.is_relative_to(self.library_root) or rig.is_symlink():
                raise ValueError(f"Refusing to remove an unsafe rig path: {rig_name}")
            destination = backup / rig.relative_to(self.library_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(rig, destination, dirs_exist_ok=True)
            shutil.rmtree(rig)
            deleted_rigs.append(str(rig))
        fenced_running = []
        removed_queue_items = []
        if self.queue_root is not None and (report["queue_jobs"] or report["gate_evidence"]):
            state_root = self.queue_root / "Zet_File_Proxy_State"
            superseded_root = state_root / "Superseded"
            superseded_root.mkdir(parents=True, exist_ok=True)
            for job in report["queue_jobs"]:
                ask_id = job["ask_id"]
                marker = superseded_root / f"{hashlib.sha256(ask_id.encode('utf-8')).hexdigest()}.json"
                write_json_atomic(marker, {"ask_id": ask_id, "reason": "Character gate feature retired.",
                                          "created_at": datetime.now().astimezone().isoformat()})
                for location in job["locations"]:
                    path = Path(location)
                    if path.is_symlink() or not path.resolve().is_relative_to(self.queue_root):
                        raise ValueError(f"Refusing to modify an unsafe queue path: {location}")
                    path = path.resolve()
                    destination = backup / "queue" / path.relative_to(self.queue_root)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if path.is_dir():
                        shutil.copytree(path, destination, dirs_exist_ok=True)
                    elif path.is_file():
                        shutil.copy2(path, destination)
                    else:
                        continue
                    if "\\Running\\" in str(path):
                        fenced_running.append(ask_id)
                        continue
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    removed_queue_items.append(str(path))
                route = state_root / "Routes" / f"{ask_id}.json"
                if route.is_file():
                    if route.is_symlink() or not route.resolve().is_relative_to(self.queue_root):
                        raise ValueError(f"Refusing to remove an unsafe route path: {route}")
                    backup_route = backup / "queue" / route.relative_to(self.queue_root)
                    backup_route.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(route, backup_route)
                    route.unlink()
            for record in report["gate_evidence"]:
                path = Path(record["path"])
                if path.is_symlink() or not path.resolve().is_relative_to(self.queue_root):
                    raise ValueError(f"Refusing to remove unsafe evidence path: {record['path']}")
                path = path.resolve()
                destination = backup / "queue" / path.relative_to(self.queue_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(path, destination, dirs_exist_ok=True)
                shutil.rmtree(path)
                removed_queue_items.append(str(path))
        return {**report, "backups": str(backup), "changed_runs": changes, "deleted_rigs": deleted_rigs,
                "fenced_running": sorted(set(fenced_running)), "removed_queue_items": removed_queue_items}
