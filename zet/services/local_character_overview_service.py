"""Character and costume overview with durable local FRONT autogeneration jobs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from dataclasses import is_dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import re
import threading
import time
from typing import Any
from uuid import uuid4

from zet.services.character_phase_discovery_service import CharacterPhaseDiscoveryService
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_character_asset_pipeline_service import LocalCharacterAssetPipelineService
from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
from zet.services.workflow_storage import file_lock
from zet.services.atomic_file_service import write_json_atomic


PIPELINE_ORDER = ("body-reference", "head-image", "character-assembly", "costume-dressing")
ACTIVE_STATUSES = {"QUEUED", "RUNNING"}
_JOBS = ThreadPoolExecutor(max_workers=16, thread_name_prefix="zet-local-autogenerate")
_SUBMITTED: set[str] = set()
_SUBMITTED_LOCK = threading.Lock()


def submit_local_pipeline_task(function, *args: Any, **kwargs: Any):
    """Run a local pipeline operation outside the web server's shared task pool."""
    return _JOBS.submit(function, *args, **kwargs)


class LocalCharacterOverviewError(ValueError):
    pass


class LocalCharacterOverviewService:
    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.character_root = Path(app.config.base_character_path).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
        self.store = LocalAssetStoreService(self.library_root)
        self.jobs_root = self.library_root / "Experiments" / "Character-Pipeline" / "Autogenerate"
        self._discovery = CharacterPhaseDiscoveryService(self.character_root)

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _date_order(value: Any) -> float:
        try:
            return datetime.fromisoformat(str(value)).timestamp()
        except (TypeError, ValueError, OverflowError):
            return 0.0

    @staticmethod
    def _safe(value: str) -> str:
        token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
        if not token or token in {".", ".."}:
            raise LocalCharacterOverviewError("Character, phase, and costume are required.")
        return token

    def _job_path(self, character: str, phase: str, costume: str) -> Path:
        return self.jobs_root / self._safe(character) / self._safe(phase) / self._safe(costume) / "job.json"

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def slot_status(self, character: str, phase: str, costume: str) -> dict[str, Any]:
        return self._read(self._job_path(character, phase, costume))

    def _validate_slot(self, character: str, phase: str, costume: str) -> None:
        if character not in self._discovery.list_characters() or phase not in self._discovery.list_phases(character):
            raise LocalCharacterOverviewError("Unknown character phase.")
        if costume not in {item.name for item in self.app.list_costumes(character, phase)}:
            raise LocalCharacterOverviewError("Unknown costume for this character phase.")

    def _locked_dressing(self, character: str, phase: str, costume: str) -> dict[str, Any] | None:
        qualifier = LocalCharacterAssetPipelineService._safe(costume)
        matches = self.store.locked_assets(character, phase, pipeline="Costume-Dressing", qualifier=qualifier)
        return next((item for item in matches if item.get("view") == "FRONT"), None)

    def overview(self) -> dict[str, Any]:
        characters = self._discovery.list_characters()
        rows = []
        for character in characters:
            for phase in self._discovery.list_phases(character):
                costumes = []
                for costume in self.app.list_costumes(character, phase):
                    record = self._locked_dressing(character, phase, costume.name)
                    job = self.slot_status(character, phase, costume.name)
                    costumes.append({
                        "name": costume.name,
                        "slug": costume.slug,
                        "state": "COMPLETE" if record else str(job.get("status") or "IDLE"),
                        "pipeline": str(job.get("pipeline") or ""),
                        "message": str(job.get("message") or ""),
                        "job_id": str(job.get("job_id") or ""),
                        "image_url": (f"/api/local/character-overview/image/{self._safe(character)}/{self._safe(phase)}/{self._safe(costume.name)}?v={record['image_sha256']}" if record else ""),
                        "image_sha256": str((record or {}).get("image_sha256") or ""),
                    })
                rows.append({"character": character, "phase": phase, "costumes": costumes})
        return {"rows": rows}

    def image_path(self, character: str, phase: str, costume: str) -> Path:
        record = self._locked_dressing(character, phase, costume)
        if not record:
            raise LocalCharacterOverviewError("No verified locked Costume-Dressing FRONT image exists for this slot.")
        return Path(record["image_path"])

    def _write_job(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(path, value)

    def start(self, character: str, phase: str, costume: str) -> dict[str, Any]:
        self._validate_slot(character, phase, costume)
        path = self._job_path(character, phase, costume)
        with file_lock(path.with_suffix(".lock")):
            current = self._read(path)
            if current.get("status") in ACTIVE_STATUSES:
                result = current
            elif self._locked_dressing(character, phase, costume):
                result = {"status": "COMPLETE", "pipeline": "costume-dressing", "message": "Locked FRONT image is already available."}
            else:
                result = {
                    "schema_version": 1,
                    "job_id": uuid4().hex,
                    "character": character,
                    "phase": phase,
                    "costume": costume,
                    "status": "QUEUED",
                    "pipeline": "body-reference",
                    "message": "Autogeneration queued.",
                    "created_at": self._now(),
                    "updated_at": self._now(),
                    "run_id": "",
                    "owns_run": False,
                    "error": "",
                }
                self._write_job(path, result)
        if result.get("status") in ACTIVE_STATUSES:
            self._submit(path, result["job_id"])
        return result

    def stop(self, character: str, phase: str, costume: str) -> dict[str, Any]:
        path = self._job_path(character, phase, costume)
        with file_lock(path.with_suffix(".lock")):
            job = self._read(path)
            if job.get("status") not in ACTIVE_STATUSES:
                return job or {"status": "IDLE"}
            job.update(status="CANCELLED", message="Autogeneration stopped.", updated_at=self._now())
            self._write_job(path, job)
        self._cancel_run_if_owned(job)
        return job

    def _cancel_run_if_owned(self, job: dict[str, Any]) -> None:
        if job.get("run_id") and job.get("owns_run") and not self._run_has_other_autogenerate_users(job):
            try:
                self._pipeline_service(job["pipeline"]).adapter.request_stop(job["run_id"], **(
                    {"costume": job["costume"]} if job["pipeline"] in {"character-assembly", "costume-dressing"} else {}
                ))
            except Exception:
                pass

    def _run_has_other_autogenerate_users(self, job: dict[str, Any]) -> bool:
        pipeline = str(job.get("pipeline") or "")
        pipeline_index = PIPELINE_ORDER.index(pipeline) if pipeline in PIPELINE_ORDER else len(PIPELINE_ORDER)
        for path in self.jobs_root.glob("*/*/*/job.json"):
            other = self._read(path)
            if other.get("job_id") == job.get("job_id") or other.get("status") not in ACTIVE_STATUSES:
                continue
            if other.get("run_id") == job.get("run_id") and job.get("run_id"):
                return True
            other_pipeline = str(other.get("pipeline") or "")
            if (other.get("character") == job.get("character") and other.get("phase") == job.get("phase")
                    and other_pipeline in PIPELINE_ORDER and PIPELINE_ORDER.index(other_pipeline) <= pipeline_index
                    and (pipeline != "costume-dressing" or other.get("costume") == job.get("costume"))):
                return True
        return False

    def recover(self) -> int:
        count = 0
        for path in self.jobs_root.glob("*/*/*/job.json"):
            job = self._read(path)
            if job.get("status") in ACTIVE_STATUSES and job.get("job_id"):
                self._submit(path, job["job_id"])
                count += 1
        return count

    def _submit(self, path: Path, job_id: str) -> None:
        with _SUBMITTED_LOCK:
            if job_id in _SUBMITTED:
                return
            _SUBMITTED.add(job_id)
        _JOBS.submit(self._run_job, path, job_id)

    def _update(self, path: Path, job_id: str, **changes: Any) -> dict[str, Any]:
        with file_lock(path.with_suffix(".lock")):
            job = self._read(path)
            if job.get("job_id") != job_id or job.get("status") not in ACTIVE_STATUSES:
                return job
            job.update(changes, updated_at=self._now())
            self._write_job(path, job)
            return job

    def _pipeline_service(self, pipeline: str) -> LocalImagePipelineWorkflowService:
        # Autogenerated choices must be Luna-ranked regardless of the model selected for manual reviews.
        pipeline_app = copy.copy(self.app)
        config = self.app.config
        if is_dataclass(config):
            pipeline_app.config = replace(config, codex_default_model="gpt-6-luna")
        else:
            pipeline_config = copy.copy(config)
            pipeline_config.codex_default_model = "gpt-6-luna"
            pipeline_app.config = pipeline_config
        return LocalImagePipelineWorkflowService(pipeline_app, self.project_root, pipeline)

    def _front_selection(self, pipeline: str, character: str, phase: str, costume: str) -> dict[str, Any] | None:
        adapter = self._pipeline_service(pipeline).adapter
        kwargs = {"costume": costume} if pipeline == "costume-dressing" else {}
        runs = adapter.list_runs(character, phase, **kwargs) if pipeline in {"character-assembly", "costume-dressing"} else adapter.list_runs(character, phase)
        candidates = []
        for summary in runs:
            run_id = str(summary.get("run_id") or "")
            if not run_id:
                continue
            try:
                run = adapter.detail(run_id, **kwargs) if pipeline in {"character-assembly", "costume-dressing"} else adapter.detail(run_id)
            except Exception:
                continue
            candidate_id = (run.get("selected_views") or {}).get("FRONT")
            candidate = next((item for item in run.get("candidates", []) if item.get("candidate_id") == candidate_id), None)
            image = Path(str((candidate or {}).get("image_path") or ""))
            if not candidate or not image.is_file() or candidate.get("human_review", {}).get("decision") == "reject":
                continue
            ranking = (run.get("rankings") or {}).get("FRONT") or {}
            digest = adapter._hash(image)
            try:
                finished = (ranking.get("status") == "COMPLETE"
                            and ranking.get("input_hashes", {}).get(candidate_id) == digest
                            and adapter._candidate_gates_current(run, candidate))
            except Exception:
                finished = False
            rendered_at = str(candidate.get("rendered_at") or "")
            try:
                rendered_sort = datetime.fromisoformat(rendered_at).timestamp() if rendered_at else image.stat().st_mtime
            except ValueError:
                rendered_sort = image.stat().st_mtime
            candidates.append({
                "run_id": run_id,
                "candidate_id": candidate_id,
                "image_path": str(image),
                "image_sha256": digest,
                "created_at": str(run.get("created_at") or summary.get("created_at") or ""),
                "created_sort": self._date_order(run.get("created_at") or summary.get("created_at") or ""),
                "rendered_sort": rendered_sort,
                "finished": finished,
                "ranking": ranking,
            })
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item["finished"], item["rendered_sort"], item["created_sort"], item["run_id"], item["candidate_id"]))
        return candidates[-1]

    def _existing_batch(self, pipeline: str, character: str, phase: str, costume: str) -> dict[str, Any] | None:
        adapter = self._pipeline_service(pipeline).adapter
        runs = adapter.list_runs(character, phase, costume) if pipeline in {"character-assembly", "costume-dressing"} else adapter.list_runs(character, phase)
        if not runs:
            return None
        runs.sort(key=lambda item: (self._date_order(item.get("created_at") or ""), str(item.get("run_id") or "")))
        run_id = str(runs[-1].get("run_id") or "")
        kwargs = {"costume": costume} if pipeline in {"character-assembly", "costume-dressing"} else {}
        return adapter.detail(run_id, **kwargs) if pipeline in {"character-assembly", "costume-dressing"} else adapter.detail(run_id)

    def _create_batch(self, pipeline: str, character: str, phase: str, costume: str) -> dict[str, Any]:
        service = self._pipeline_service(pipeline)
        payload: dict[str, Any] = {"character": character, "phase": phase}
        if pipeline in {"character-assembly", "costume-dressing"}:
            payload.update(costume=costume, front_only=True)
        return service.adapter.create_run(payload)

    def _rerank_front(self, adapter: Any, pipeline: str, run: dict[str, Any], costume: str) -> dict[str, Any]:
        run_id = str(run["run_id"])
        root = Path(run["root"])
        state_path = root / "state.json"
        state = self._read(state_path)
        state.setdefault("rankings", {}).pop("FRONT", None)
        if pipeline == "body-reference":
            adapter._save_state(run_id, state)
            return adapter.rank_view(run_id, "FRONT")
        adapter._write(state_path, state)
        return adapter.rank_view(run_id, "FRONT", costume) if pipeline in {"character-assembly", "costume-dressing"} else adapter.rank_view(run_id, "FRONT")

    def _execute_front(self, pipeline: str, run_id: str, costume: str) -> None:
        service = self._pipeline_service(pipeline)
        adapter = service.adapter
        if pipeline in {"character-assembly", "costume-dressing"}:
            adapter.execute_run(run_id, views={"FRONT"}, costume=costume)
        elif pipeline == "head-image":
            adapter.execute_run(run_id, views={"FRONT"})
        else:
            adapter.execute_run(run_id, views={"FRONT"})

    def _wait_for_front(self, pipeline: str, run_id: str, costume: str, path: Path, job_id: str) -> dict[str, Any]:
        adapter = self._pipeline_service(pipeline).adapter
        kwargs = {"costume": costume} if pipeline in {"character-assembly", "costume-dressing"} else {}
        deadline = time.monotonic() + 1860
        active = {"PREFLIGHT", "RUNNING", "STOPPING", "REEVALUATING", "WAITING_FOR_FACE_GATE",
                  "WAITING_FOR_GATES", "WAITING_FOR_ANALYSIS"}
        while True:
            job = self._read(path)
            if job.get("job_id") != job_id or job.get("status") not in ACTIVE_STATUSES:
                raise LocalCharacterOverviewError("Autogeneration stopped while waiting for FRONT candidates.")
            run = adapter.detail(run_id, **kwargs) if pipeline in {"character-assembly", "costume-dressing"} else adapter.detail(run_id)
            if run.get("status") not in active:
                return run
            if time.monotonic() >= deadline:
                raise LocalCharacterOverviewError(f"Timed out waiting for {pipeline} FRONT candidates.")
            time.sleep(max(0.5, float(getattr(self.app.config, "comfyui_poll_seconds", 2))))

    def _pipeline_lock_path(self, job: dict[str, Any], pipeline: str) -> Path:
        root = self.jobs_root / "locks" / self._safe(job["character"]) / self._safe(job["phase"])
        root /= self._safe(pipeline)
        if pipeline == "costume-dressing":
            root /= self._safe(job["costume"])
        return root.with_suffix(".lock")

    def _choose_and_lock(self, job: dict[str, Any], pipeline: str) -> dict[str, Any]:
        with file_lock(self._pipeline_lock_path(job, pipeline), timeout=1860):
            current = self._read(self._job_path(job["character"], job["phase"], job["costume"]))
            if current.get("job_id") != job.get("job_id") or current.get("status") not in ACTIVE_STATUSES:
                raise LocalCharacterOverviewError("Autogeneration stopped before the next pipeline could start.")
            return self._choose_and_lock_locked(job, pipeline)

    def _choose_and_lock_locked(self, job: dict[str, Any], pipeline: str) -> dict[str, Any]:
        character, phase, costume = job["character"], job["phase"], job["costume"]
        qualifier = LocalCharacterAssetPipelineService._safe(costume) if pipeline == "costume-dressing" else ""
        locked = self.store.locked_assets(character, phase, pipeline=pipeline, qualifier=qualifier)
        existing_lock = next((item for item in locked if item.get("view") == "FRONT"), None)
        if existing_lock:
            return existing_lock
        selected = self._front_selection(pipeline, character, phase, costume)
        adapter = self._pipeline_service(pipeline).adapter
        kwargs = {"costume": costume} if pipeline in {"character-assembly", "costume-dressing"} else {}
        if selected:
            run = adapter.detail(selected["run_id"], **kwargs) if pipeline in {"character-assembly", "costume-dressing"} else adapter.detail(selected["run_id"])
            if not (run.get("selected_views") or {}).get("FRONT"):
                if pipeline == "body-reference":
                    adapter.select_view(selected["run_id"], "FRONT", selected["candidate_id"], autogenerate=True)
                elif pipeline == "head-image":
                    adapter.select_view(selected["run_id"], "FRONT", selected["candidate_id"], autogenerate=True)
                else:
                    adapter.select_view(selected["run_id"], "FRONT", selected["candidate_id"], costume, autogenerate=True)
            lock_kwargs = {"costume": costume} if pipeline in {"character-assembly", "costume-dressing"} else {}
            try:
                return adapter.lock_selected_view(selected["run_id"], "FRONT", **lock_kwargs)
            except Exception:
                self._execute_front(pipeline, selected["run_id"], costume)
                refreshed = self._wait_for_front(pipeline, selected["run_id"], costume,
                                                 self._job_path(character, phase, costume), job["job_id"])
                if (refreshed.get("selected_views") or {}).get("FRONT") != selected["candidate_id"]:
                    raise LocalCharacterOverviewError(f"Selected FRONT image could not be refreshed for {pipeline}.")
                return adapter.lock_selected_view(selected["run_id"], "FRONT", **lock_kwargs)

        run = self._existing_batch(pipeline, character, phase, costume)
        owns_run = run is None
        if run is None:
            run = self._create_batch(pipeline, character, phase, costume)
        run_id = str(run["run_id"])
        self._update(self._job_path(character, phase, costume), job["job_id"], run_id=run_id, owns_run=owns_run)
        ranking = (run.get("rankings") or {}).get("FRONT") or {}
        selected_id = (run.get("selected_views") or {}).get("FRONT")
        if (ranking.get("status") == "COMPLETE" and not ranking.get("luna_ordered_candidate_ids")
                and len(ranking.get("ordered_candidate_ids") or []) > 1):
            run = self._rerank_front(adapter, pipeline, run, costume)
            ranking = (run.get("rankings") or {}).get("FRONT") or {}
        luna_order = list(ranking.get("luna_ordered_candidate_ids") or [])
        if not luna_order and len(ranking.get("ordered_candidate_ids") or []) == 1:
            luna_order = list(ranking["ordered_candidate_ids"])
        valid_ranking = ranking.get("status") == "COMPLETE" and bool(luna_order)
        if not valid_ranking:
            front_candidates = [item for item in run.get("candidates", []) if item.get("view") == "FRONT"]
            if ranking.get("status") == "FAILED":
                raise LocalCharacterOverviewError(f"Luna ranking failed for {pipeline}: {ranking.get('error') or 'unknown error'}")
            if ranking.get("status") == "EMPTY" and front_candidates and all(
                item.get("status") in {"FAILED", "GATE_REJECTED"} for item in front_candidates
            ):
                raise LocalCharacterOverviewError(f"All FRONT candidates failed or were rejected for {pipeline}.")
            self._execute_front(pipeline, run_id, costume)
            run = self._wait_for_front(pipeline, run_id, costume, self._job_path(character, phase, costume), job["job_id"])
            ranking = (run.get("rankings") or {}).get("FRONT") or {}
        luna_order = list(ranking.get("luna_ordered_candidate_ids") or [])
        if not luna_order and len(ranking.get("ordered_candidate_ids") or []) == 1:
            luna_order = list(ranking["ordered_candidate_ids"])
        if not luna_order:
            if ranking.get("status") == "FAILED":
                raise LocalCharacterOverviewError(f"Luna ranking failed for {pipeline}: {ranking.get('error') or 'unknown error'}")
            raise LocalCharacterOverviewError(f"No eligible #1 Luna FRONT candidate for {pipeline}.")
        candidate_id = luna_order[0]
        candidate = next((item for item in run.get("candidates", []) if item.get("candidate_id") == candidate_id), None)
        if not candidate or not Path(str(candidate.get("image_path") or "")).is_file():
            raise LocalCharacterOverviewError(f"The #1 Luna FRONT image is missing for {pipeline}.")
        if candidate.get("human_review", {}).get("decision") == "reject" or candidate.get("rejection_gate"):
            raise LocalCharacterOverviewError(f"The #1 Luna FRONT candidate was rejected for {pipeline}.")
        if pipeline == "body-reference":
            adapter.select_view(run_id, "FRONT", candidate_id, autogenerate=True)
        elif pipeline == "head-image":
            adapter.select_view(run_id, "FRONT", candidate_id, autogenerate=True)
        else:
            adapter.select_view(run_id, "FRONT", candidate_id, costume, autogenerate=True)
        lock_kwargs = {"costume": costume} if pipeline in {"character-assembly", "costume-dressing"} else {}
        return adapter.lock_selected_view(run_id, "FRONT", **lock_kwargs)

    def _run_job(self, path: Path, job_id: str) -> None:
        try:
            while True:
                job = self._read(path)
                if job.get("job_id") != job_id or job.get("status") not in ACTIVE_STATUSES:
                    return
                if self._locked_dressing(job["character"], job["phase"], job["costume"]):
                    self._update(path, job_id, status="COMPLETE", pipeline="costume-dressing", message="Locked Costume-Dressing FRONT image is ready.", error="")
                    return
                pipeline = str(job.get("pipeline") or "body-reference")
                self._update(path, job_id, status="RUNNING", message=f"Checking {pipeline} FRONT image…")
                try:
                    self._choose_and_lock(job, pipeline)
                except Exception as exc:
                    message = str(exc)
                    if "still running" in message.lower() or "wait" in message.lower() or "busy" in message.lower():
                        time.sleep(1)
                        continue
                    self._cancel_run_if_owned(job)
                    self._update(path, job_id, status="ERROR", message=message, error=message)
                    return
                index = PIPELINE_ORDER.index(pipeline)
                if index + 1 >= len(PIPELINE_ORDER):
                    self._update(path, job_id, status="COMPLETE", pipeline=pipeline, message="Locked Costume-Dressing FRONT image is ready.", error="")
                    return
                self._update(path, job_id, pipeline=PIPELINE_ORDER[index + 1], run_id="", message=f"Locked {pipeline} FRONT image; advancing.")
        finally:
            with _SUBMITTED_LOCK:
                _SUBMITTED.discard(job_id)
