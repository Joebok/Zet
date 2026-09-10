"""Process-local single-flight cache for production summaries."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock
from time import monotonic
from typing import Any, Callable


SUMMARY_CACHE_SECONDS = 15.0


@dataclass
class _Entry:
    created_at: float
    value: dict[str, Any]


class SummaryCache:
    """Share identical summary computations without cancelling backend work."""

    _lock = RLock()
    _entries: dict[tuple[Any, ...], _Entry] = {}
    _in_flight: dict[tuple[Any, ...], Event] = {}
    _generation = 0

    @classmethod
    def get_or_compute(cls, key: tuple[Any, ...], factory: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        while True:
            owner = False
            with cls._lock:
                entry = cls._entries.get(key)
                if entry is not None and monotonic() - entry.created_at < SUMMARY_CACHE_SECONDS:
                    return entry.value
                event = cls._in_flight.get(key)
                if event is None:
                    event = Event()
                    cls._in_flight[key] = event
                    generation = cls._generation
                    owner = True
            if owner:
                break
            event.wait()

        try:
            value = factory()
        except BaseException:
            with cls._lock:
                cls._in_flight.pop(key, None)
                event.set()
            raise
        with cls._lock:
            if generation == cls._generation:
                cls._entries[key] = _Entry(monotonic(), value)
            cls._in_flight.pop(key, None)
            event.set()
        return value

    @classmethod
    def invalidate(cls) -> None:
        with cls._lock:
            cls._generation += 1
            cls._entries.clear()

    @classmethod
    def clear(cls) -> None:
        """Clear cache state for isolated tests."""

        with cls._lock:
            cls._generation += 1
            cls._entries.clear()


def invalidate_summary_cache() -> None:
    SummaryCache.invalidate()
