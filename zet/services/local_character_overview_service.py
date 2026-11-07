"""Read-only selected-character overview backed by current published images."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from typing import Any

from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_asset_source_service import LocalAssetSourceService


class LocalCharacterOverviewError(ValueError):
    pass


class LocalCharacterOverviewService:
    PIPELINES = (
        ("body-reference", "Body-Reference"),
        ("head-image-edit", "Head-Image (Edit)"),
        ("head-image", "Head-Image (Construct)"),
        ("character-assembly", "Character Assembly"),
    )

    def __init__(self, app: Any, project_root: str | Path | None = None):
        self.app = app
        self.library_root = Path(app.config.base_library_path).resolve()
        self.sources = LocalAssetSourceService(LocalAssetStoreService(self.library_root))
        runtime = str(getattr(app.config, "runtime_root", "") or "")
        if not runtime:
            import os
            runtime = str(Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache") / "Zet")
        self.thumbnail_cache = Path(runtime).resolve() / "cache" / "character-overview-thumbnails"
        from zet.services.view_conditioning_service import VIEW_ORDER
        self.views = list(VIEW_ORDER)

    def overview(self, character: str, phase: str, universe_id: str = "") -> dict[str, Any]:
        if universe_id and universe_id != str(self.app.universe_id):
            raise LocalCharacterOverviewError("The requested universe is not active.")
        character, phase = str(character).strip(), str(phase).strip()
        if not character or not phase:
            raise LocalCharacterOverviewError("Choose a character and phase.")
        source_rows = self.sources.list_sources(character, phase)
        costumes = self.app.list_costumes(character, phase)
        groups = [{"pipeline": pipeline, "label": label, "costume": "", "views": []}
                  for pipeline, label in self.PIPELINES]
        for costume in costumes:
            groups.append({"pipeline": "costume-dressing", "label": costume.name,
                           "costume": costume.slug, "template_path": costume.path, "views": []})
        lookup = {(str(row.get("pipeline") or "").casefold(),
                   str(row.get("costume") or "").replace("_", " ").casefold(),
                   str(row.get("view") or "").upper()): row for row in source_rows}
        for group in groups:
            for view in self.views:
                row = lookup.get((group["pipeline"], group["costume"].replace("_", " ").casefold(), view.upper()))
                thumb = ""
                version = ""
                if row:
                    image = Path(row["image_path"]).resolve()
                    if image.is_relative_to(self.library_root) and image.is_file():
                        stat = image.stat()
                        version = f"{stat.st_size}-{stat.st_mtime_ns}"
                        params = f"character={quote(character)}&phase={quote(phase)}&view={quote(view)}&universe_id={quote(str(self.app.universe_id))}"
                        if group["costume"]:
                            params += f"&costume={quote(group['costume'])}"
                        thumb = f"/api/local/character-overview/thumbnail/{group['pipeline']}?{params}&v={version}"
                group["views"].append({"view": view, "thumbnail_url": thumb,
                                       "locked": bool(thumb), "render_mode": row.get("render_mode", "") if row and thumb else ""})
        status = self.app.character_onboarding_status(character, phase)
        return {"character": character, "phase": phase, "ready": bool(status.template_ready),
                "character_template_path": status.template_path,
                "groups": groups, "views": self.views}

    def thumbnail(self, character: str, phase: str, pipeline: str, view: str,
                  costume: str = "", universe_id: str = "", version: str = "") -> Path:
        if universe_id and universe_id != str(self.app.universe_id):
            raise LocalCharacterOverviewError("The requested universe is not active.")
        row = next((item for item in self.sources.list_sources(character, phase, pipeline=pipeline)
                    if str(item.get("view") or "").upper() == view.upper()
                    and str(item.get("costume") or "").replace("_", " ").casefold() == costume.replace("_", " ").casefold()), None)
        if not row:
            raise LocalCharacterOverviewError("No locked image exists for this view.")
        image = Path(row["image_path"]).resolve()
        if not image.is_relative_to(self.library_root) or not image.is_file():
            raise LocalCharacterOverviewError("The locked image is unavailable.")
        return _thumbnail(image, self.thumbnail_cache, version)


def _thumbnail(source: Path, cache: Path, version: str) -> Path:
    from zet.services.image_thumbnail_service import ImageThumbnailService
    return ImageThumbnailService(cache, max_side=480).create(source, version)
