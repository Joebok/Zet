"""Durable library-wide coordinator for remaining local image work."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
from pathlib import Path
import threading
import time
from typing import Any
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_image_pipeline_policy import ACTIVE_RUN_STATUSES
from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
from zet.services.workflow_storage import file_lock


PIPELINES = ("body-reference", "head-image", "character-assembly", "costume-dressing")
_CAMPAIGN_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="zet-run-all-remaining")
_RENDER_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zet-local-render-batch")
_REVIEW_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zet-local-image-review")
_ACTIVE: set[str] = set()
_ACTIVE_LOCK = threading.Lock()


class LocalRunAllRemainingError(ValueError):
    pass


class LocalRunAllRemainingService:
    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
        self.root = self.library_root / "Experiments" / "Character-Pipeline" / "RunAllRemaining"
        self.active_path = self.root / "active.json"

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _adapter(self, pipeline: str):
        return LocalImagePipelineWorkflowService(self.app, self.project_root, pipeline).adapter

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _campaign_path(self, campaign_id: str) -> Path:
        if not campaign_id or any(ch not in "0123456789abcdef-" for ch in campaign_id.lower()):
            raise LocalRunAllRemainingError("Invalid run-all campaign ID.")
        return self.root / "campaigns" / f"{campaign_id}.json"

    def _update(self, campaign_id: str, mutator) -> dict[str, Any]:
        path = self._campaign_path(campaign_id)
        with file_lock(path.with_suffix(".lock")):
            campaign = self._read(path)
            mutator(campaign)
            campaign["updated_at"] = self._now()
            write_json_atomic(path, campaign)
            return campaign

    def _discover(self) -> list[dict[str, Any]]:
        batches: list[dict[str, Any]] = []
        for pipeline in PIPELINES:
            adapter = self._adapter(pipeline)
            for summary in adapter.list_runs():
                run_id = str(summary.get("run_id") or "")
                if not run_id:
                    continue
                costume = str(summary.get("costume") or "") if pipeline in {"character-assembly", "costume-dressing"} else ""
                kwargs = {"costume": costume} if pipeline in {"character-assembly", "costume-dressing"} else {}
                try:
                    run = adapter.detail(run_id, **kwargs)
                except Exception:
                    continue
                images = [Path(str(item.get("image_path") or "")) for item in run.get("candidates") or []]
                missing = sum(not path.is_file() or path.stat().st_size <= 0 for path in images)
                batches.append({
                    "pipeline": pipeline, "run_id": run_id,
                    "character": str(run.get("character") or ""), "phase": str(run.get("phase") or ""),
                    "costume": costume, "status": str(run.get("status") or "UNKNOWN"),
                    "candidate_count": len(images), "images_complete": len(images) - missing,
                    "images_remaining": missing, "result": "QUEUED" if missing else "REVIEW_PENDING",
                    "error": "",
                })
        return [item for item in batches if item["run_id"]]

    def start(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        with file_lock(self.root / "campaign.lock"):
            active_id = str(self._read(self.active_path).get("campaign_id") or "")
            if active_id:
                current = self._read(self._campaign_path(active_id))
                if current.get("status") in {"QUEUED", "RUNNING", "RECOVERING"}:
                    with _ACTIVE_LOCK:
                        active = active_id in _ACTIVE
                    if not active:
                        self._launch(active_id)
                    return current
            campaign_id = uuid4().hex
            batches = self._discover()
            campaign = {
                "campaign_id": campaign_id, "status": "QUEUED", "created_at": self._now(),
                "updated_at": self._now(), "max_parallel_batches": 4,
                "batch_count": len(batches), "batches": batches,
            }
            path = self._campaign_path(campaign_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(path, campaign)
            write_json_atomic(self.active_path, {"campaign_id": campaign_id, "updated_at": self._now()})
        self._launch(campaign_id)
        return campaign

    def _launch(self, campaign_id: str) -> None:
        with _ACTIVE_LOCK:
            if campaign_id in _ACTIVE:
                return
            _ACTIVE.add(campaign_id)
        _CAMPAIGN_POOL.submit(self._run, campaign_id)

    def status(self, campaign_id: str) -> dict[str, Any]:
        campaign = self._read(self._campaign_path(campaign_id))
        if not campaign:
            raise LocalRunAllRemainingError("Run-all campaign not found.")
        batches = campaign.get("batches") or []
        progress = {key: 0 for key in ("QUEUED", "RUNNING", "COMPLETE", "WAITING_FOR_SELECTION",
                                       "WAITING_FOR_REFERENCE", "FAILED", "REVIEW_PENDING")}
        for item in batches:
            key = str(item.get("result") or "QUEUED")
            progress[key] = progress.get(key, 0) + 1
        campaign["progress"] = progress
        campaign["images_complete"] = sum(int(item.get("images_complete") or 0) for item in batches)
        campaign["images_remaining"] = sum(int(item.get("images_remaining") or 0) for item in batches)
        return campaign

    def recover(self) -> None:
        active_id = str(self._read(self.active_path).get("campaign_id") or "")
        if not active_id:
            return
        campaign = self._read(self._campaign_path(active_id))
        if campaign.get("status") in {"QUEUED", "RUNNING", "RECOVERING"}:
            # A RUNNING marker belongs to a previous server process. Reopen it as
            # interrupted so the coordinator reconciles each proxy ask before retrying.
            for index, job in enumerate(campaign.get("batches") or []):
                if job.get("result") != "RUNNING":
                    continue
                adapter = self._adapter(str(job.get("pipeline") or ""))
                kwargs = {"costume": job.get("costume") or ""} if job.get("pipeline") in {"character-assembly", "costume-dressing"} else {}
                try:
                    adapter._run_update(str(job.get("run_id") or ""), **kwargs,
                                        status="INTERRUPTED", interrupted=True)
                except Exception:
                    pass
                self._set_batch(active_id, index, result="QUEUED", error="")
            self._update(active_id, lambda item: item.update(status="RECOVERING"))
            self._launch(active_id)

    def _run(self, campaign_id: str) -> None:
        try:
            self._update(campaign_id, lambda item: item.update(status="RUNNING", started_at=item.get("started_at") or self._now()))
            campaign = self._read(self._campaign_path(campaign_id))
            jobs = list(campaign.get("batches") or [])
            futures = {}
            for index, job in enumerate(jobs):
                if job.get("result") in {"COMPLETE", "WAITING_FOR_SELECTION", "WAITING_FOR_REFERENCE"}:
                    continue
                future = _RENDER_POOL.submit(self._run_batch, campaign_id, index, dict(job))
                futures[future] = index
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    index = futures[future]
                    self._set_batch(campaign_id, index, result="FAILED", error=str(exc))
            campaign = self._read(self._campaign_path(campaign_id))
            review_futures = {}
            for index, job in enumerate(campaign.get("batches") or []):
                if job.get("result") != "REVIEW_PENDING":
                    continue
                future = _REVIEW_POOL.submit(self._review_campaign_batch, campaign_id, index, dict(job))
                review_futures[future] = index
            for future in as_completed(review_futures):
                try:
                    future.result()
                except Exception as exc:
                    self._set_batch(campaign_id, review_futures[future], review_error=str(exc))
            campaign = self._read(self._campaign_path(campaign_id))
            self._update(campaign_id, lambda item: item.update(status="COMPLETE", completed_at=self._now(),
                                                                batches=campaign.get("batches") or []))
        except Exception as exc:
            self._update(campaign_id, lambda item: item.update(status="FAILED", error=str(exc), completed_at=self._now()))
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE.discard(campaign_id)

    def _set_batch(self, campaign_id: str, index: int, **changes: Any) -> None:
        def apply(campaign: dict[str, Any]) -> None:
            batches = campaign.setdefault("batches", [])
            if 0 <= index < len(batches):
                batches[index].update(changes, updated_at=self._now())
        self._update(campaign_id, apply)

    def _run_batch(self, campaign_id: str, index: int, job: dict[str, Any]) -> None:
        pipeline, run_id = job["pipeline"], job["run_id"]
        adapter = self._adapter(pipeline)
        kwargs = {"costume": job.get("costume") or ""} if pipeline in {"character-assembly", "costume-dressing"} else {}
        self._set_batch(campaign_id, index, result="RUNNING", error="")
        run = adapter.detail(run_id, **kwargs)
        while run.get("status") in ACTIVE_RUN_STATUSES and not run.get("interrupted"):
            time.sleep(2)
            run = adapter.detail(run_id, **kwargs)
        if run.get("status") in {"INTERRUPTED", "CANCELLED", "STOPPED", "ERROR"}:
            if pipeline == "body-reference":
                (Path(run["root"]) / "cancelled.json").unlink(missing_ok=True)
            adapter._run_update(run_id, **kwargs, status="QUEUED", stop_requested=False, error="")
            run = adapter.detail(run_id, **kwargs)

        missing_views = set()
        for candidate in run.get("candidates") or []:
            image = Path(str(candidate.get("image_path") or ""))
            if not image.is_file() or image.stat().st_size <= 0:
                missing_views.add(str(candidate.get("view") or ""))
        needs_anchor = pipeline in {"body-reference", "head-image"} or bool(run.get("use_front_anchor", False))
        if not run.get("front_anchor") and needs_anchor:
            missing_views.intersection_update({"FRONT"})
            if not missing_views:
                remaining = sum(not Path(str(item.get("image_path") or "")).is_file()
                                for item in run.get("candidates") or [])
                self._set_batch(campaign_id, index, result="REVIEW_PENDING", images_remaining=remaining,
                                images_complete=len(run.get("candidates") or []) - remaining,
                                message="Dependent views need a human FRONT selection.")
                return
        if not missing_views:
            self._set_batch(campaign_id, index, result="REVIEW_PENDING", images_remaining=0,
                            images_complete=len(run.get("candidates") or []))
            return

        selected_views = set(run.get("views") or []) & missing_views
        if needs_anchor and not run.get("front_anchor"):
            selected_views = {"FRONT"} if "FRONT" in missing_views else set()
        if not selected_views:
            self._set_batch(campaign_id, index, result="WAITING_FOR_SELECTION",
                            message="Dependent views need a human FRONT selection.")
            return
        # Reconcile missing images with the proxy before deciding whether to retry.
        blocked_candidate_ids: set[str] = set()
        for candidate in run.get("candidates") or []:
            if candidate.get("view") not in selected_views or Path(str(candidate.get("image_path") or "")).is_file():
                continue
            proxy_status = "UNKNOWN"
            ask_id = str(candidate.get("ask_id") or "")
            if ask_id and hasattr(adapter, "_proxy_answer"):
                try:
                    proxy_status, answer = adapter._proxy_answer(ask_id)
                    if str(answer.get("status") or "").upper() in {"ERROR", "RETRY_LATER"}:
                        error = str(answer.get("error_message") or "Render proxy failed.")
                        blocked_candidate_ids.add(str(candidate["candidate_id"]))
                        changes = {"status": "FAILED", "render_error": error}
                        if pipeline == "body-reference":
                            adapter._candidate_update(run_id, candidate["candidate_id"], changes)
                        elif pipeline in {"character-assembly", "costume-dressing"}:
                            adapter._update(run_id, candidate["candidate_id"], kwargs["costume"], **changes)
                        else:
                            adapter._update(run_id, candidate["candidate_id"], **changes)
                        continue
                except Exception:
                    proxy_status = "UNKNOWN"
            if ask_id and proxy_status in {"QUEUED", "RUNNING", "ANSWERED"}:
                changes = {"status": "QUEUED" if proxy_status == "QUEUED" else "RUNNING",
                           "render_error": ""}
                if pipeline == "body-reference":
                    adapter._candidate_update(run_id, candidate["candidate_id"], changes)
                elif pipeline in {"character-assembly", "costume-dressing"}:
                    adapter._update(run_id, candidate["candidate_id"], kwargs["costume"], **changes)
                else:
                    adapter._update(run_id, candidate["candidate_id"], **changes)
                continue
            if candidate.get("status") in {"FAILED", "WAITING_FOR_GATES"} or (
                candidate.get("status") in {"QUEUED", "RUNNING"} and proxy_status == "UNKNOWN"
            ):
                try:
                    if pipeline in {"character-assembly", "costume-dressing"}:
                        adapter.retry_candidate(run_id, candidate["candidate_id"], kwargs["costume"])
                    else:
                        adapter.retry_candidate(run_id, candidate["candidate_id"])
                except Exception:
                    pass
        candidate_ids = {str(item["candidate_id"]) for item in run.get("candidates") or []
                         if item.get("view") in selected_views and item.get("candidate_id") not in blocked_candidate_ids
                         and not Path(str(item.get("image_path") or "")).is_file()}
        if candidate_ids:
            adapter.execute_run(run_id, views=selected_views, candidate_ids=candidate_ids,
                                render_only=True, **kwargs)
        refreshed = adapter.detail(run_id, **kwargs)
        remaining = sum(not Path(str(item.get("image_path") or "")).is_file()
                        for item in refreshed.get("candidates") or [])
        errors = [str(item.get("render_error") or "") for item in refreshed.get("candidates") or []
                  if item.get("render_error") and not Path(str(item.get("image_path") or "")).is_file()]
        reference_errors = [item for item in errors if any(token in item.casefold() for token in ("reference", "anchor", "source image"))]
        if reference_errors:
            self._set_batch(campaign_id, index, result="WAITING_FOR_REFERENCE", images_remaining=remaining,
                            images_complete=len(refreshed.get("candidates") or []) - remaining,
                            message="Required reference images are missing.", error="; ".join(dict.fromkeys(reference_errors))[:2000])
        elif errors:
            self._set_batch(campaign_id, index, result="FAILED", images_remaining=remaining,
                            images_complete=len(refreshed.get("candidates") or []) - remaining,
                            error="; ".join(dict.fromkeys(errors))[:2000])
        elif remaining and not refreshed.get("front_anchor") and needs_anchor and selected_views == {"FRONT"}:
            self._set_batch(campaign_id, index, result="REVIEW_PENDING", images_remaining=remaining,
                            images_complete=len(refreshed.get("candidates") or []) - remaining,
                            message="FRONT images are ready for human selection before dependent views.")
        elif remaining:
            self._set_batch(campaign_id, index, result="WAITING_FOR_REFERENCE", images_remaining=remaining,
                            images_complete=len(refreshed.get("candidates") or []) - remaining,
                            message="Some views are blocked by missing required reference images.")
        else:
            self._set_batch(campaign_id, index, result="REVIEW_PENDING", images_remaining=0,
                            images_complete=len(refreshed.get("candidates") or []))

    def _review_campaign_batch(self, campaign_id: str, index: int, job: dict[str, Any]) -> None:
        pipeline, run_id = job["pipeline"], job["run_id"]
        adapter = self._adapter(pipeline)
        kwargs = {"costume": job.get("costume") or ""} if pipeline in {"character-assembly", "costume-dressing"} else {}
        run = adapter.detail(run_id, **kwargs)
        views = {str(item.get("view")) for item in run.get("candidates") or []
                 if Path(str(item.get("image_path") or "")).is_file()}
        if not run.get("front_anchor") and (pipeline in {"body-reference", "head-image"} or run.get("use_front_anchor")):
            views.intersection_update({"FRONT"})
        self._set_batch(campaign_id, index, review_status="RUNNING")
        try:
            if pipeline in {"character-assembly", "costume-dressing"}:
                adapter.execute_run(run_id, views=views, render_only=False, **kwargs)
            elif pipeline == "head-image":
                adapter.execute_run(run_id, views=views, render_only=False)
            else:
                adapter.execute_run(run_id, views=views, render_only=False)
        except Exception:
            # Advisory review failures remain visible in batch review status.
            pass
        refreshed = adapter.detail(run_id, **kwargs)
        unselected = len(refreshed.get("views") or []) - len(refreshed.get("selected_views") or {})
        remaining = sum(not Path(str(item.get("image_path") or "")).is_file()
                        for item in refreshed.get("candidates") or [])
        review_errors = bool(refreshed.get("review_errors")) or any(
            item.get("review_error") or any(gate.get("status") in {"FAILED", "ERROR"}
                                             for gate in (item.get("gates") or {}).values())
            for item in refreshed.get("candidates") or []) or any(
                ranking.get("status") == "FAILED" for ranking in (refreshed.get("rankings") or {}).values())
        result = "WAITING_FOR_SELECTION" if unselected or remaining else "COMPLETE"
        self._set_batch(campaign_id, index, result=result, review_status="FAILED" if review_errors else "COMPLETE",
                        images_remaining=remaining, images_complete=len(refreshed.get("candidates") or []) - remaining,
                        review_error="One or more advisory gates or rankings need re-evaluation." if review_errors else "")
