"""Coordinator for durable local character preparation operations.

The handler is injected so the coordinator never imports web presentation code.
An interrupted handler is fenced for explicit reconciliation, not replayed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
from typing import Callable
from uuid import UUID

from zet.repositories.local_pipeline_operation_repository import LocalPipelineOperationRepository
from zet.services.local_pipeline_operation_context import OperationBlocked, OperationInputsChanged, OperationWaiting
from zet.services.local_image_pipeline_policy import LOCAL_IMAGE_PIPELINES

PIPELINES = frozenset(LOCAL_IMAGE_PIPELINES)
ACTIONS = frozenset({"run_available", "start", "resume", "generate_slots", "regenerate_slot", "retry_render_slot", "rerun_view", "rerun_failed", "retry_candidate", "reevaluate"})
REQUEST_FIELDS = frozenset({"operation_id", "universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume", "action", "render_mode", "view", "slot", "count", "candidate_id", "expected_candidate_id", "aspect_ratio", "scope", "recompile", "expected_context"})
logger = logging.getLogger(__name__)


class CheckedLocalPipelineOperationHandler:
    """Resolve the recorded workflow and check context before invoking its adapter."""

    def __init__(self, resolve_workflow: Callable[[str, str], object], dispatch: Callable[[object, dict], dict]):
        self.resolve_workflow = resolve_workflow
        self.dispatch = dispatch

    def __call__(self, record: dict) -> dict:
        request = record["request"]
        workflow = self.resolve_workflow(request["universe_id"], request["pipeline"])
        workflow.check_operation_context(request)
        return self.dispatch(workflow, request)


class LocalPipelineOperationDispatcher:
    def __init__(self, *handlers):
        self.handlers = handlers

    def can_resume(self, record: dict) -> bool:
        return any(handler.can_resume(record) for handler in self.handlers)

    def __call__(self, record: dict) -> dict:
        handler = next((item for item in self.handlers if item.can_resume(record)), None)
        if handler is None:
            raise ValueError("No handler is registered for this operation.")
        return handler(record)


class LocalPipelineOperationService:
    def __init__(self, repository: LocalPipelineOperationRepository, handler: Callable[[dict], dict], *, interval: float = 2, supported_actions=None):
        self.repository = repository
        self.handler = handler
        self.interval = interval
        self.supported_actions = frozenset(supported_actions) if supported_actions is not None else ACTIONS
        self._stop = threading.Event()
        self._active: set[str] = set()
        self._lock = threading.Lock()
        self._pool: ThreadPoolExecutor | None = None
        self._thread: threading.Thread | None = None
        self._next_prune = 0.0

    def admit(self, request: dict) -> dict:
        if not isinstance(request, dict) or set(request) - REQUEST_FIELDS:
            raise ValueError("Unknown operation fields.")
        record = dict(request)
        try:
            operation_id = UUID(str(record.pop("operation_id"))).hex
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValueError("Choose a valid operation ID.") from None
        if record.get("pipeline") not in PIPELINES or record.get("action") not in ACTIONS:
            raise ValueError("Unknown pipeline operation.")
        if record["action"] not in self.supported_actions:
            raise ValueError("This operation is not available yet.")
        if record["action"] == "run_available":
            allowed = {"universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume",
                       "action", "render_mode", "scope", "aspect_ratio", "expected_context"}
            if set(record) - allowed or record.get("scope") not in {"front", "available"}:
                raise ValueError("Invalid Run available parameters.")
        elif record["action"] in {"generate_slots", "regenerate_slot", "retry_render_slot"}:
            allowed = {"universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume",
                       "action", "render_mode", "view", "slot", "count", "expected_candidate_id", "aspect_ratio", "expected_context"}
            if set(record) - allowed or not record.get("view"):
                raise ValueError("Invalid render-slot parameters.")
            if record["action"] != "generate_slots" and ("slot" not in record or not record.get("expected_candidate_id")):
                raise ValueError("Choose the current candidate and slot.")
        elif record["action"] in {"rerun_view", "rerun_failed"}:
            allowed = {"universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume",
                       "action", "render_mode", "view", "aspect_ratio", "recompile", "expected_context"}
            if set(record) - allowed or not record.get("view"):
                raise ValueError("Invalid view regeneration parameters.")
        elif record["action"] in {"start", "resume"}:
            allowed = {"universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume",
                       "action", "render_mode", "expected_context"}
            if set(record) - allowed:
                raise ValueError("Invalid batch lifecycle parameters.")
        elif record["action"] == "reevaluate":
            allowed = {"universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume",
                       "action", "render_mode", "view", "expected_context"}
            if set(record) - allowed:
                raise ValueError("Invalid evaluation parameters.")
        elif record["action"] == "retry_candidate":
            allowed = {"universe_id", "pipeline", "run_id", "character", "phase", "batch_name", "costume",
                       "action", "render_mode", "view", "candidate_id", "expected_context"}
            if set(record) - allowed or not record.get("view") or not record.get("candidate_id"):
                raise ValueError("Choose a candidate and view to retry.")
        if record.get("pipeline") != "costume-dressing" and record.get("costume"):
            raise ValueError("Only Costume-Dressing operations accept a costume.")
        for key in ("universe_id", "run_id", "expected_context"):
            value = record.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"A valid {key} is required.")
            if "/" in value or "\\" in value:
                raise ValueError(f"Invalid {key}.")
        for key in ("character", "phase", "batch_name", "costume", "view", "candidate_id", "expected_candidate_id", "aspect_ratio", "scope"):
            value = record.get(key, "")
            if (not isinstance(value, str) or len(value) > 256
                    or key not in {"character", "phase", "batch_name"} and ("/" in value or "\\" in value)):
                raise ValueError(f"Invalid {key}.")
        if record.get("view"):
            from zet.services.local_image_pipeline_policy import VIEW_CANDIDATE_PREFIXES
            if record["view"] not in VIEW_CANDIDATE_PREFIXES:
                raise ValueError("Unknown character view.")
        if record.get("render_mode") not in {"draft", "final"}:
            raise ValueError("Choose Draft or Final mode.")
        if len(record["expected_context"]) != 64 or any(c not in "0123456789abcdef" for c in record["expected_context"]):
            raise ValueError("Invalid expected context.")
        for key in ("slot", "count"):
            if key in record and (type(record[key]) is not int or not 1 <= record[key] <= 8):
                raise ValueError(f"Invalid {key}.")
        if "recompile" in record and type(record["recompile"]) is not bool:
            raise ValueError("Invalid recompile flag.")
        result, _ = self.repository.admit(operation_id, record)
        return result

    def list(self, *, universe_id: str = "", run_id: str = "", offset: int = 0, limit: int = 50) -> dict:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid operation page.")
        rows = [record for record in self.repository.list_activity()
                if (not universe_id or record["request"].get("universe_id") == universe_id)
                and (not run_id or record["request"].get("run_id") == run_id)]
        rows.sort(key=lambda record: record.get("created_at", ""), reverse=True)
        rows.sort(key=lambda record: record.get("status") not in {"QUEUED", "PREPARING", "WAITING"})
        return {"operations": rows[offset:offset + limit], "next_offset": offset + limit if offset + limit < len(rows) else None}

    def dismiss(self, operation_id: str) -> dict:
        return self.repository.dismiss(operation_id)

    def stop_batch(self, workflow, run_id: str, costume: str = "") -> dict:
        """Fence admitted preparation before applying the existing Stop behavior."""
        from pathlib import Path
        from zet.services.local_image_pipeline_policy import ACTIVE_RUN_STATUSES
        from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
        from zet.services.workflow_storage import file_lock, runner_lock_active

        with self.repository.batch_handoff_lock(workflow.app.universe_id, workflow.pipeline, run_id, costume):
            cancelled = self.repository.cancel_batch(workflow.app.universe_id, workflow.pipeline, run_id, costume)
            run = workflow.prompt_improvement.detail(run_id, costume)
            root = Path(run["root"])
            library = pipeline_library_root_for_path(root)
            from zet.services.local_pipeline_candidate_retry_reservation import LocalPipelineCandidateRetryReservation
            retry_reservations = LocalPipelineCandidateRetryReservation(root)
            for record in self.repository.list():
                request = record.get("request") or {}
                if (request.get("universe_id"), request.get("pipeline"), request.get("run_id"), request.get("costume") or "") != (workflow.app.universe_id, workflow.pipeline, run_id, costume):
                    continue
                if request.get("action") != "retry_candidate" or record.get("status") not in {"PREPARING", "RECOVERY_REQUIRED"}:
                    continue
                try:
                    saved = retry_reservations.find(record["id"])
                    if saved and saved.get("status") == "PREPARING":
                        retry_reservations.cancel(record["id"])
                        if record.get("status") == "RECOVERY_REQUIRED":
                            self.repository.update(record["id"], status="CANCELLED", cancel_requested=True,
                                                   stage="Candidate retry restored after Stop")
                            cancelled.append(record["id"])
                except Exception:
                    logger.exception("Candidate retry %s needs artifact reconciliation after Stop.", record["id"])
            if cancelled:
                with file_lock(root / "state.lock"):
                    state = read_library_json(root / "state.json", library)
                    state["slot_paused"] = True
                    write_library_json(root / "state.json", state, library)
                if runner_lock_active(root) or (run.get("status") in ACTIVE_RUN_STATUSES and not run.get("interrupted")):
                    result = workflow.action("stop", run_id=run_id, costume=costume)
                else:
                    result = workflow.action("detail", run_id=run_id, costume=costume)
            elif run.get("slot_paused") or run.get("stop_requested"):
                result = workflow.action("detail", run_id=run_id, costume=costume)
            else:
                result = workflow.action("stop", run_id=run_id, costume=costume)
            # Invalidate requests formed before this Stop, even if their HTTP
            # admission arrives only after the cancellation scan above.
            with file_lock(root / "state.lock"):
                state = read_library_json(root / "state.json", library)
                previous = state.get("stop_generation", 0)
                state["stop_generation"] = previous + 1 if type(previous) is int and previous >= 0 else 1
                write_library_json(root / "state.json", state, library)
            return {**result, "stop_generation": state["stop_generation"],
                    **({"slot_paused": True, "cancelled_operations": cancelled} if cancelled else {})}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zet-operation")
        self._thread = threading.Thread(target=self._sweep_loop, name="zet-operation-sweep", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        if self._pool:
            self._pool.shutdown(wait=True)
        self._thread = None
        self._pool = None

    def _sweep_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sweep()
                if time.monotonic() >= self._next_prune:
                    self.repository.prune_successes()
                    self._next_prune = time.monotonic() + 24 * 60 * 60
            except Exception:
                logger.exception("Local pipeline operation sweep failed; it will retry.")
            self._stop.wait(self.interval)

    def sweep(self) -> None:
        if self._pool is None:
            return
        for record in self.repository.list():
            if record.get("status") not in {"QUEUED", "WAITING", "PREPARING"}:
                continue
            operation_id = record["id"]
            with self._lock:
                if operation_id in self._active:
                    continue
                self._active.add(operation_id)
            try:
                self._pool.submit(self._execute, operation_id)
            except BaseException:
                with self._lock:
                    self._active.discard(operation_id)
                raise

    def _execute(self, operation_id: str) -> None:
        try:
            try:
                with self.repository.ownership_lock(operation_id):
                    record = self.repository.get(operation_id)
                    if record["status"] == "PREPARING":
                        can_resume = getattr(self.handler, "can_resume", lambda record: False)
                        if not can_resume(record):
                            self.repository.update(operation_id, status="RECOVERY_REQUIRED", stage="Preparation stopped unexpectedly")
                            return
                    elif record["status"] in {"QUEUED", "WAITING"}:
                        record = self.repository.transition(operation_id, {"QUEUED", "WAITING"}, status="PREPARING", stage="Checking inputs")
                        if record is None:
                            return
                    else:
                        return
                    try:
                        result = self.handler(record)
                    except OperationWaiting as exc:
                        self.repository.settle_unstarted(operation_id, "WAITING", str(exc))
                    except OperationBlocked as exc:
                        self.repository.settle_unstarted(operation_id, "BLOCKED", "Action blocked", str(exc))
                    except OperationInputsChanged as exc:
                        self.repository.settle_unstarted(operation_id, "BLOCKED", "Inputs changed", str(exc))
                    except Exception as exc:
                        self.repository.update(operation_id, status="RECOVERY_REQUIRED", stage="Preparation failed", error=str(exc))
                    else:
                        self.repository.complete_preparation(operation_id, result)
            except TimeoutError:
                pass
            except Exception:
                logger.exception("Local pipeline operation %s could not be inspected; it will be retried.", operation_id)
        finally:
            with self._lock:
                self._active.discard(operation_id)
