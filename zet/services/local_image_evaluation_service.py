"""Bounded, non-blocking workers for local image ranking jobs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import threading
from pathlib import Path
from typing import Any, Callable


_LOCK = threading.Lock()
_ACTIVE: set[tuple[str, str, str, str]] = set()


def mode_field(name: str, render_mode: str = "draft") -> str:
    if render_mode not in {"draft", "final"}:
        raise ValueError("Render mode must be draft or final.")
    return name if render_mode == "draft" else f"final_{name}"


def is_evaluation_replay(previous: dict[str, Any], evaluation_id: str, hashes: dict[str, str]) -> bool:
    """Recognize an operation-owned evaluation without starting it again."""
    if not evaluation_id:
        return False
    if previous.get("evaluation_id") != evaluation_id:
        if previous.get("status") in {"RUNNING", "STAGING"}:
            from zet.services.local_pipeline_operation_context import OperationBlocked
            raise OperationBlocked("Another evaluation is already active for this view.")
        return False
    if previous.get("input_hashes") != hashes:
        from zet.services.local_pipeline_operation_context import OperationInputsChanged
        raise OperationInputsChanged("Evaluation images changed. Review the view before retrying.")
    if previous.get("status") == "STAGING":
        from zet.services.local_pipeline_operation_reservation import ReservationConflict
        raise ReservationConflict("The saved evaluation handoff needs reconciliation.")
    if previous.get("status") not in {"RUNNING", "COMPLETE"}:
        from zet.services.local_pipeline_operation_context import OperationBlocked
        raise OperationBlocked("The previous evaluation did not complete normally. Review the batch before retrying.")
    return True


def supersede_evaluations(state: dict[str, Any], views: set[str], reason: str, *, render_mode: str = "draft") -> None:
    """Make outstanding advice in the selected views unable to commit results."""
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    for view in views:
        evaluation = (state.get(mode_field("evaluations", render_mode)) or {}).get(view)
        if not evaluation or evaluation.get("status") not in {"STAGING", "RUNNING"}:
            continue
        evaluation.update(status="SUPERSEDED", ranking_status="SUPERSEDED", superseded_at=stamp,
                          superseded_reason=reason)


def update_view_evaluation(run_root: Path, view: str, changes: dict[str, Any], *,
                           evaluation_id: str = "", replace: bool = False,
                           render_mode: str = "draft") -> dict[str, Any] | None:
    """Stage a replacement evaluation or merge an update fenced by its identity."""
    from zet.services.local_image_pipeline_policy import mutate_local_run_state

    saved: list[dict[str, Any] | None] = []
    def apply(state: dict[str, Any]) -> None:
        evaluations = state.setdefault(mode_field("evaluations", render_mode), {})
        current = dict(evaluations.get(view) or {})
        if not replace and evaluation_id and current.get("evaluation_id") not in {None, "", evaluation_id}:
            saved.append(None)
            return
        if replace:
            current = {}
        current.update(changes)
        evaluations[view] = current
        saved.append(dict(current))
    mutate_local_run_state(run_root, apply)
    return saved[-1] if saved else None


def finish_evaluation(run_root: Path, view: str, evaluation_id: str, *, render_mode: str = "draft") -> None:
    """Finish a recovered ranking only while its evaluation still owns the view."""
    from zet.services.local_image_pipeline_policy import mutate_local_run_state

    def finish(state):
        evaluation = (state.get(mode_field("evaluations", render_mode)) or {}).get(view) or {}
        if evaluation.get("evaluation_id") != evaluation_id or evaluation.get("status") not in {"STAGING", "RUNNING"}:
            return
        if evaluation.get("ranking_status") not in {"COMPLETE", "FAILED", "EMPTY", "SKIPPED"}:
            evaluation["ranking_status"] = "FAILED"
        evaluation["status"] = "COMPLETE"
    mutate_local_run_state(run_root, finish)


class LocalImageEvaluationService:
    """Stage one immutable view evaluation and rank the candidate set."""

    def __init__(self) -> None:
        self._rank_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zet-image-rank")

    def stage_view_evaluation(
        self,
        run_id: str,
        view: str,
        evaluation_id: str,
        *,
        rank: Callable[[], Any],
        finish: Callable[[], Any],
        save_evaluation: Callable[[dict[str, Any]], Any],
        input_hashes: dict[str, str],
        render_mode: str = "draft",
    ) -> dict[str, Any]:
        mode_field("evaluations", render_mode)
        key = (str(run_id), str(view), render_mode, str(evaluation_id))
        with _LOCK:
            if key in _ACTIVE:
                return {"evaluation_id": evaluation_id, "status": "RUNNING"}
            _ACTIVE.add(key)
        record = {"evaluation_id": evaluation_id, "status": "RUNNING", "input_hashes": input_hashes,
                  "ranking_status": "QUEUED"}
        try:
            save_evaluation(record)
            self._rank_pool.submit(self._run, key, rank, finish)
            return record
        except Exception:
            with _LOCK:
                _ACTIVE.discard(key)
            raise

    def reconcile_review_jobs(
        self,
        run_id: str,
        view: str,
        evaluation_id: str,
        *,
        rank: Callable[[], Any],
        finish: Callable[[], Any],
        render_mode: str = "draft",
    ) -> bool:
        """Reattach persisted work after restart without creating duplicate asks."""
        mode_field("evaluations", render_mode)
        key = (str(run_id), str(view), render_mode, str(evaluation_id))
        with _LOCK:
            if key in _ACTIVE:
                return False
            _ACTIVE.add(key)
        self._rank_pool.submit(self._run, key, rank, finish)
        return True

    @staticmethod
    def _run(key: tuple[str, str, str, str], operation: Callable[[], Any], finish: Callable[[], Any]) -> None:
        try:
            operation()
        finally:
            try:
                finish()
            finally:
                with _LOCK:
                    _ACTIVE.discard(key)


_EVALUATION_SERVICE = LocalImageEvaluationService()


def local_image_evaluation_service() -> LocalImageEvaluationService:
    return _EVALUATION_SERVICE
