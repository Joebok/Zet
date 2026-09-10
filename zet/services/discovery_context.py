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
        with self._lock:
            if self._scene_records is not None:
                return self._scene_records

            records: list[SceneDiscoveryRecord] = []
            for story in self.story_service.list_stories():
                for scene in self.story_service.list_scenes(story.slug):
                    story_slug = str(story.slug)
                    scene_slug = str(scene.slug)
                    main_locked = self.path_service.scene_locked_image_path(story_slug, scene_slug)
                    main_candidate = self.path_service.scene_candidate_image_path(story_slug, scene_slug)
                    record("candidate_path_checks", count=1)
                    records.append(SceneDiscoveryRecord(
                        story_slug=story_slug,
                        story_title=str(story.title),
                        scene_slug=scene_slug,
                        scene_title=str(scene.title),
                        render_target_id="main",
                        render_target_label="Full Scene",
                        locked_path=main_locked,
                        candidate_path=main_candidate,
                    ))

                    loader = getattr(self.story_service, "load_scene_builder_data", None)
                    document = loader(story_slug, scene_slug) if loader is not None else None
                    data = getattr(document, "data", {}) if document is not None else {}
                    elements = tuple(
                        copy.deepcopy(item)
                        for item in (data.get("scene_elements") or [])
                        if isinstance(item, dict)
                    )
                    for definition in data.get("subscenes") or []:
                        if not isinstance(definition, dict):
                            continue
                        target_id = str(definition.get("id") or "").strip()
                        if not target_id:
                            continue
                        record("candidate_path_checks", count=1)
                        records.append(SceneDiscoveryRecord(
                            story_slug=story_slug,
                            story_title=str(story.title),
                            scene_slug=scene_slug,
                            scene_title=str(scene.title),
                            render_target_id=target_id,
                            render_target_label=str(definition.get("name") or target_id),
                            locked_path=self.path_service.scene_subscene_locked_path(story_slug, scene_slug, target_id),
                            candidate_path=self.path_service.scene_subscene_candidate_path(story_slug, scene_slug, target_id),
                            definition=copy.deepcopy(definition),
                            scene_elements=elements,
                        ))
            self._scene_records = tuple(records)
            return self._scene_records

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
