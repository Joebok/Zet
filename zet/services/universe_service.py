"""Discover and resolve universe folders inside the configured library container."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import threading
import time
from typing import Any

from zet.services.atomic_file_service import write_json_atomic


class UniverseServiceError(ValueError):
    """Invalid, missing, or malformed universe configuration."""


class UniverseService:
    """Resolve per-universe roots while keeping queue and template roots shared."""

    def __init__(self, container: str | Path, selection_path: str | Path):
        self.container = Path(container).expanduser().resolve()
        self.selection_path = Path(selection_path).expanduser().resolve()
        self._cache_lock = threading.RLock()
        self._universe_cache: list[dict[str, Any]] | None = None
        self._universe_cache_at = 0.0

    @staticmethod
    def _safe_id(value: str) -> str:
        value = str(value or "").strip()
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
        if (not value or len(value) > 80 or value in {".", ".."} or value[-1:] in {".", " "}
                or any(char in value for char in '<>:"/\\|?*') or any(ord(char) < 32 for char in value)
                or value.split(".", 1)[0].upper() in reserved):
            raise UniverseServiceError("A valid universe id is required.")
        return value

    def _descriptor(self, path: Path) -> dict[str, Any]:
        marker = path / "universe.json"
        if marker.is_file():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                universe_id = self._safe_id(data.get("universe_id") or path.name)
                name = str(data.get("name") or path.name).strip()
                if not name:
                    raise UniverseServiceError(f"Universe name is empty in {marker}")
                return {"universe_id": universe_id, "name": name,
                        "canonical_art_style": str(data.get("canonical_art_style") or "").strip(),
                        "scene_text_style": data.get("scene_text_style", {}),
                        "layout_version": int(data.get("layout_version", 1)), "root": path, "legacy": False}
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise UniverseServiceError(f"Cannot read universe descriptor {marker}: {exc}") from exc
        return {"universe_id": path.name, "name": path.name, "canonical_art_style": "",
                "layout_version": 0, "root": path, "legacy": True}

    def invalidate_cache(self) -> None:
        with self._cache_lock:
            self._universe_cache = None
            self._universe_cache_at = 0.0

    def list_universes(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        with self._cache_lock:
            if (not refresh and self._universe_cache is not None
                    and time.monotonic() - self._universe_cache_at < 2.0):
                return [dict(item) for item in self._universe_cache]
            result = self._discover_universes()
            self._universe_cache = [dict(item) for item in result]
            self._universe_cache_at = time.monotonic()
            return [dict(item) for item in result]

    def _discover_universes(self) -> list[dict[str, Any]]:
        if not self.container.is_dir():
            return []
        result = [self._descriptor(path) for path in sorted(self.container.iterdir(), key=lambda item: item.name.casefold())
                  if path.is_dir() and (path / "universe.json").is_file()]
        # Keep the pre-migration library root available as Moonsea alongside new sibling universes.
        moonsea_folder = self.container / "Moonsea" / "universe.json"
        if not any(item["universe_id"].casefold() == "moonsea" for item in result) and not moonsea_folder.is_file():
            result.append({"universe_id": "Moonsea", "name": "Moonsea", "canonical_art_style": "",
                           "layout_version": 0, "root": self.container, "legacy": True})
        return result

    def get_universe(self, universe_id: str, *, refresh: bool = False) -> dict[str, Any]:
        wanted = self._safe_id(universe_id)
        for universe in self.list_universes(refresh=refresh):
            if universe["universe_id"] == wanted:
                return universe
        raise UniverseServiceError(f"Universe not found: {wanted}")

    def selection(self) -> str:
        universes = self.list_universes()
        if not universes:
            raise UniverseServiceError(f"No universe folders found under {self.container}")
        try:
            saved = json.loads(self.selection_path.read_text(encoding="utf-8"))
            selected = str(saved.get("universe_id") or "")
        except FileNotFoundError:
            selected = ""
        except (OSError, json.JSONDecodeError) as exc:
            if isinstance(exc, OSError):
                raise UniverseServiceError(f"Cannot read universe selection {self.selection_path}: {exc}") from exc
            import logging
            logging.getLogger(__name__).warning("Ignoring malformed universe selection %s: %s", self.selection_path, exc)
            selected = ""
        except (AttributeError, TypeError) as exc:
            import logging
            logging.getLogger(__name__).warning("Ignoring malformed universe selection %s: %s", self.selection_path, exc)
            selected = ""
        return selected if isinstance(selected, str) and any(item["universe_id"] == selected for item in universes) else universes[0]["universe_id"]

    def select(self, universe_id: str) -> dict[str, Any]:
        universe = self.get_universe(universe_id)
        self.selection_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.selection_path, {"universe_id": universe["universe_id"]})
        return universe

    def bind_config(self, config, universe_id: str):
        root = Path(self.get_universe(universe_id)["root"])
        format_marker = root / "_state" / "library-reference-format.json"
        if format_marker.is_file():
            try:
                marker_data = json.loads(format_marker.read_text(encoding="utf-8"))
                version = marker_data.get("library_path_format_version", 0)
                if isinstance(version, bool) or not isinstance(version, int):
                    raise ValueError("library_path_format_version must be an integer")
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise UniverseServiceError(f"Cannot read library path format marker {format_marker}: {exc}") from exc
            if version > 1:
                raise UniverseServiceError(f"Library path format {version} requires a newer Zet release.")
        # All universe-owned stores follow this root; the queue and shared templates stay external.
        descriptor = self.get_universe(universe_id)
        return replace(config, base_library_path=str(root),
                       base_character_path=(config.base_character_path if descriptor["legacy"] else str(root / "Characters")),
                       base_asset_path=(config.base_asset_path if descriptor["legacy"] else str(root / "Assets")),
                       base_pipeline_path=(config.base_pipeline_path if descriptor["legacy"] else str(root / "PipelineCandidates")),
                       universe_id=descriptor["universe_id"], universe_is_legacy=descriptor["legacy"],
                       library_container_path=str(self.container))

    def initialize(self, name: str, canonical_art_style: str = "") -> dict[str, Any]:
        cleaned = str(name or "").strip()
        if not cleaned:
            raise UniverseServiceError("Universe name is required.")
        universe_id = self._safe_id(cleaned)
        self.container.mkdir(parents=True, exist_ok=True)
        selected_before = self.selection() if self.list_universes() else ""
        if any(item["universe_id"].casefold() == universe_id.casefold() for item in self.list_universes()):
            raise UniverseServiceError(f"Universe already exists: {universe_id}")
        root = self.container / universe_id
        if root.exists():
            raise UniverseServiceError(f"Universe already exists: {universe_id}")
        root.mkdir(parents=True)
        for folder in ("Characters", "Stories", "PipelineCandidates", "_state", "images"):
            (root / folder).mkdir()
        write_json_atomic(root / "universe.json", {
            "universe_id": universe_id, "name": cleaned, "layout_version": 1,
            "canonical_art_style": str(canonical_art_style or "").strip(),
        })
        if selected_before:
            self.select(selected_before)
        self.invalidate_cache()
        return self.get_universe(universe_id, refresh=True)

    def update_settings(self, universe_id: str, *, canonical_art_style: str = None, scene_text_style: dict = None) -> dict[str, Any]:
        universe = self.get_universe(universe_id)
        marker = Path(universe["root"]) / "universe.json"
        if not marker.is_file():
            raise UniverseServiceError("Universe settings cannot be edited until its library migration is complete.")
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UniverseServiceError(f"Cannot read universe descriptor {marker}: {exc}") from exc
        if canonical_art_style is not None:
            data["canonical_art_style"] = str(canonical_art_style or "").strip()
        if scene_text_style is not None:
            from zet.services.scene_text_style_service import validate_style
            data["scene_text_style"] = validate_style(scene_text_style)
        write_json_atomic(marker, data)
        self.invalidate_cache()
        return self.get_universe(universe_id, refresh=True)
