"""Bounded, non-blocking workers for local image gate and ranking jobs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import threading
from pathlib import Path
from typing import Any, Callable


_LOCK = threading.Lock()
_ACTIVE: set[tuple[str, str, str]] = set()


def supersede_evaluations(state: dict[str, Any], views: set[str], reason: str) -> None:
    """Make outstanding advice in the selected views unable to commit results."""
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    for view in views:
        evaluation = (state.get("evaluations") or {}).get(view)
        if not evaluation or evaluation.get("status") not in {"STAGING", "RUNNING"}:
            continue
        evaluation.update(status="SUPERSEDED", gates_status="SUPERSEDED",
                          ranking_status="SUPERSEDED", superseded_at=stamp,
                          superseded_reason=reason)


def update_view_evaluation(run_root: Path, view: str, changes: dict[str, Any], *,
                           evaluation_id: str = "") -> dict[str, Any] | None:
    """Merge one view's evaluation under the run's state lock."""
    from zet.services.local_image_pipeline_policy import mutate_local_run_state

    saved: list[dict[str, Any] | None] = []
    def apply(state: dict[str, Any]) -> None:
        evaluations = state.setdefault("evaluations", {})
        current = dict(evaluations.get(view) or {})
        if evaluation_id and current.get("evaluation_id") != evaluation_id:
            saved.append(None)
            return
        current.update(changes)
        evaluations[view] = current
        saved.append(dict(current))
    mutate_local_run_state(run_root, apply)
    return saved[-1] if saved else None


class LocalImageEvaluationService:
    """Stage one immutable view evaluation, then collect gates and rank in parallel."""

    def __init__(self) -> None:
        self._gate_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zet-image-gates")
        self._rank_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zet-image-rank")

    def stage_view_evaluation(
        self,
        run_id: str,
        view: str,
        evaluation_id: str,
        *,
        stage_gates: Callable[[], Any],
        collect_gates: Callable[[], Any],
        rank: Callable[[], Any],
        save_evaluation: Callable[[dict[str, Any]], Any],
        input_hashes: dict[str, str],
    ) -> dict[str, Any]:
        key = (str(run_id), str(view), str(evaluation_id))
        with _LOCK:
            if key in _ACTIVE:
                return {"evaluation_id": evaluation_id, "status": "RUNNING"}
            _ACTIVE.add(key)
        record = {"evaluation_id": evaluation_id, "status": "STAGING", "input_hashes": input_hashes,
                  "gates_status": "STAGING", "ranking_status": "QUEUED"}
        try:
            # Publish every enabled gate before either background task can wait
            # on an answer. Individual staging failures are persisted by adapter.
            stage_gates()
            record["status"] = "RUNNING"
            record["gates_status"] = "QUEUED"
            save_evaluation(record)
            self._gate_pool.submit(self._run, key, collect_gates)
            self._rank_pool.submit(self._run, key, rank)
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
        stage_gates: Callable[[], Any],
        collect_gates: Callable[[], Any],
        rank: Callable[[], Any],
    ) -> bool:
        """Reattach persisted work after restart without creating duplicate asks."""
        key = (str(run_id), str(view), str(evaluation_id))
        with _LOCK:
            if key in _ACTIVE:
                return False
            _ACTIVE.add(key)
        try:
            stage_gates()
        except Exception:
            with _LOCK:
                _ACTIVE.discard(key)
            raise
        self._gate_pool.submit(self._run, key, collect_gates)
        self._rank_pool.submit(self._run, key, rank)
        return True

    @staticmethod
    def _run(key: tuple[str, str, str], operation: Callable[[], Any]) -> None:
        try:
            operation()
        finally:
            # A ranking and gate collector share an evaluation key. Keep it
            # reserved until both submitted operations have finished.
            with _LOCK:
                active = getattr(LocalImageEvaluationService._run, "active_counts", {})
                remaining = active.get(key, 2) - 1
                if remaining <= 0:
                    active.pop(key, None)
                    _ACTIVE.discard(key)
                else:
                    active[key] = remaining
                LocalImageEvaluationService._run.active_counts = active


_EVALUATION_SERVICE = LocalImageEvaluationService()


def local_image_evaluation_service() -> LocalImageEvaluationService:
    return _EVALUATION_SERVICE
