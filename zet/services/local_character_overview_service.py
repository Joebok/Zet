"""Read-only costume overview backed by current published pipeline outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from zet.services.character_phase_discovery_service import CharacterPhaseDiscoveryService


class LocalCharacterOverviewError(ValueError):
    pass


class LocalCharacterOverviewService:
    """List current locked Costume-Dressing FRONT images without starting work."""

    def __init__(self, app: Any, project_root: str | Path | None = None):
        self.app = app
        self.character_root = Path(app.config.base_character_path).resolve()
        self.library_root = Path(app.config.base_library_path).resolve()
        self.discovery = CharacterPhaseDiscoveryService(self.character_root)

    @staticmethod
    def _same_costume(source: dict, name: str, slug: str) -> bool:
        value = str(source.get("costume") or "").strip().casefold()
        return value in {name.casefold(), slug.casefold(), slug.replace("_", " ").casefold()}

    def _front_source(self, character: str, phase: str, costume: str) -> dict | None:
        costume_record = next((item for item in self.app.list_costumes(character, phase)
                               if item.name == costume or item.slug == costume), None)
        if costume_record is None:
            raise LocalCharacterOverviewError("Unknown costume for this character phase.")
        for source in self.app.local_asset_source_service.list_sources(
                character, phase, pipeline="costume-dressing"):
            if source.get("view") == "FRONT" and self._same_costume(
                    source, costume_record.name, costume_record.slug):
                return source
        return None

    def overview(self) -> dict[str, Any]:
        rows = []
        for character in self.discovery.list_characters():
            for phase in self.discovery.list_phases(character):
                costumes = []
                for costume in self.app.list_costumes(character, phase):
                    source = self._front_source(character, phase, costume.slug)
                    render_mode = str(source.get("render_mode") or "") if source else ""
                    image_url = ""
                    if source:
                        path = Path(source["image_path"]).resolve()
                        if path.is_relative_to(self.library_root) and path.is_file():
                            image_url = ("/api/local/character-overview/image/" + "/".join(
                                quote(part, safe="-_.") for part in (character, phase, costume.slug)
                            ) + f"?v={source.get('image_sha256', '')}")
                    costumes.append({
                        "name": costume.name,
                        "slug": costume.slug,
                        "state": "COMPLETE" if image_url else "IDLE",
                        "message": "" if image_url else "No locked FRONT image. Generate and review candidates in the Costume Dressing Asset Container.",
                        "render_mode": render_mode if image_url else "",
                        "image_url": image_url,
                    })
                rows.append({"character": character, "phase": phase, "costumes": costumes})
        return {"rows": rows}

    def image_path(self, character: str, phase: str, costume: str) -> Path:
        source = self._front_source(character, phase, costume)
        if not source:
            raise LocalCharacterOverviewError("No current locked Costume-Dressing FRONT image exists for this slot.")
        image = Path(source["image_path"]).resolve()
        if not image.is_relative_to(self.library_root) or not image.is_file():
            raise LocalCharacterOverviewError("The published Costume-Dressing image is unavailable.")
        return image
