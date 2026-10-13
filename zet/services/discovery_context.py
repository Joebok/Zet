"""Request-scoped discovery data shared by review, catalog, and summaries."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from zet.services.performance_instrumentation import record


@dataclass(frozen=True)
class SceneDiscoveryRecord:
    """Cheap filesystem facts and one loaded subscene definition."""

    story_slug: str
    story_title: str
    scene_slug: str
    scene_title: str
    render_target_id: str
    render_target_label: str
    locked_path: Path
    candidate_path: Path
    definition: dict[str, Any] | None = None
    scene_elements: tuple[dict[str, Any], ...] = ()

    @property
    def candidate_exists(self) -> bool:
        return self.candidate_path.is_file()

    @property
    def locked_exists(self) -> bool:
        return self.locked_path.is_file()


class DiscoveryContext:
    """Cache one logical discovery pass for the lifetime of a request."""

    def __init__(self, story_service, path_service):
        self.story_service = story_service
        self.path_service = path_service
        self._scene_records: tuple[SceneDiscoveryRecord, ...] | None = None
        self._catalog_sources: dict[int, tuple[dict[str, Any], ...]] = {}
        self._lock = RLock()

    def scene_records(self) -> tuple[SceneDiscoveryRecord, ...]:
        """Retired Scene Builder review records are excluded from active discovery."""
        return ()

    def filtered_scene_records(self, story_slug: str = "", scene_slug: str = "") -> tuple[SceneDiscoveryRecord, ...]:
        return tuple(
            item for item in self.scene_records()
            if (not story_slug or item.story_slug == story_slug)
            and (not scene_slug or item.scene_slug == scene_slug)
        )

    def catalog_sources(
        self,
        owner: object,
        factory: Callable[[], list[dict[str, Any]]],
    ) -> tuple[dict[str, Any], ...]:
        """Return raw catalog sources once for one catalog service/request pair."""

        key = id(owner)
        with self._lock:
            if key not in self._catalog_sources:
                self._catalog_sources[key] = tuple(factory())
            return self._catalog_sources[key]
