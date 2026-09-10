"""Opt-in counters and timings for reliability and scale measurements."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


_CURRENT: ContextVar["PerformanceInstrumentation | None"] = ContextVar(
    "zet_performance_instrumentation", default=None
)


class PerformanceInstrumentation:
    """Collect bounded operation counts and durations when explicitly enabled."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.durations_seconds: dict[str, list[float]] = defaultdict(list)

    def record(self, operation: str, *, count: int = 1) -> None:
        self.counts[str(operation)] += int(count)

    def record_duration(self, operation: str, elapsed_seconds: float) -> None:
        self.record(operation)
        self.durations_seconds[str(operation)].append(float(elapsed_seconds))

    @contextmanager
    def measure(self, operation: str) -> Iterator[None]:
        started = perf_counter()
        try:
            yield
        finally:
            self.record_duration(operation, perf_counter() - started)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counts": dict(sorted(self.counts.items())),
            "durations_seconds": {
                key: [round(value, 6) for value in values]
                for key, values in sorted(self.durations_seconds.items())
            },
        }


@contextmanager
def collect(
    instrumentation: PerformanceInstrumentation | None = None,
    *,
    patch_path_reads: bool = True,
) -> Iterator[PerformanceInstrumentation]:
    """Activate collection for the current context."""

    collector = instrumentation or PerformanceInstrumentation()
    token = _CURRENT.set(collector)
    original_read_text = Path.read_text
    original_read_bytes = Path.read_bytes

    if patch_path_reads:
        def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
            collector.record("file_reads")
            return original_read_text(path, *args, **kwargs)

        def read_bytes(path: Path, *args: Any, **kwargs: Any) -> bytes:
            collector.record("file_reads")
            return original_read_bytes(path, *args, **kwargs)

        Path.read_text = read_text  # type: ignore[method-assign]
        Path.read_bytes = read_bytes  # type: ignore[method-assign]

    try:
        yield collector
    finally:
        if patch_path_reads:
            Path.read_text = original_read_text  # type: ignore[method-assign]
            Path.read_bytes = original_read_bytes  # type: ignore[method-assign]
        _CURRENT.reset(token)


def current() -> PerformanceInstrumentation | None:
    return _CURRENT.get()


def record(operation: str, *, count: int = 1) -> None:
    collector = current()
    if collector is not None:
        collector.record(operation, count=count)


def record_duration(operation: str, elapsed_seconds: float) -> None:
    collector = current()
    if collector is not None:
        collector.record_duration(operation, elapsed_seconds)

