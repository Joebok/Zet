from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from Scripts.Compile_Character_Template import (
    TemplateCompileError,
    load_template_sections_with_sources,
    select_sections,
)
from zet.services.character_phase_discovery_service import (
    CharacterPhaseDiscoveryService,
)
from zet.services.view_service import ViewService


SECTION_GROUPS = {
    "identity anchors": (
        "GENERAL_DESCRIPTION_FACTS",
        "IDENTITY_PRESERVATION_CORE",
    ),
    "face": (
        "HEAD_DESCRIPTION_FACTS",
        "HEAD_DESCRIPTION_VIEW_{VIEW}",
        "IDENTITY_PRESERVATION_FACE",
    ),
    "hair": (
        "HAIR_DESCRIPTION_FACTS",
        "HAIR_DESCRIPTION_VIEW_{VIEW}",
        "IDENTITY_PRESERVATION_HAIR",
    ),
    "eyes": ("IDENTITY_PRESERVATION_EYES",),
    "ears": ("IDENTITY_PRESERVATION_EARS",),
    "body proportions": (
        "BODY_DESCRIPTION_FACTS",
        "BODY_DESCRIPTION_VIEW_{VIEW}",
        "IDENTITY_PRESERVATION_BODY",
    ),
    "age": ("GENERAL_DESCRIPTION_FACTS",),
    "canonical art style": ("GENERAL_DESCRIPTION_FACTS",),
    "selected costume": (
        "COSTUME_DESCRIPTION_FACTS",
        "COSTUME_DESCRIPTION_VIEW_{VIEW}",
        "IDENTITY_PRESERVATION_COSTUME",
    ),
    "signature worn items": (
        "EQUIPMENT_DESCRIPTION_FACTS",
        "EQUIPMENT_DESCRIPTION_VIEW_{VIEW}",
    ),
    "view/orientation requirements": (
        "BODY_DESCRIPTION_VIEW_{VIEW}",
        "HEAD_DESCRIPTION_VIEW_{VIEW}",
        "HAIR_DESCRIPTION_VIEW_{VIEW}",
        "COSTUME_DESCRIPTION_VIEW_{VIEW}",
        "EQUIPMENT_DESCRIPTION_VIEW_{VIEW}",
    ),
    "negative or forbidden traits": ("NEGATIVE_GUIDANCE_GENERAL",),
}

NON_CONTENT_SECTION_OVERLAPS = {"COMPILER_NOTES", "LOCAL_IMAGE_GEN_OVERRIDES"}


class CharacterSourceError(ValueError):
    """Report an invalid or unavailable character source selection."""


class CharacterSourceService:
    """Expose stable character-source discovery and compilation for consumers."""

    def __init__(
        self,
        path_service,
        costume_service,
        story_service,
        project_root: str | Path,
    ):
        self.path_service = path_service
        self.costume_service = costume_service
        self.story_service = story_service
        self.project_root = Path(project_root)
        self.discovery = CharacterPhaseDiscoveryService(
            path_service.config.base_character_path
        )
        self.views = ViewService(self.project_root)

    def options(self, character: str = "", phase: str = "") -> dict[str, Any]:
        characters = self.discovery.list_characters()
        character_rows = []
        for value in characters:
            ready = any(
                self._template_readiness(self.path_service.character_template_path(value, candidate))[0]
                for candidate in self.discovery.list_phases(value)
            )
            character_rows.append(
                self._option(
                    value,
                    value,
                    ready,
                    "No compile-ready phases.",
                )
            )
        phases = self.discovery.list_phases(character) if character in characters else []
        phase_rows = []
        for value in phases:
            template = self.path_service.character_template_path(character, value)
            available, reason = self._template_readiness(template)
            phase_rows.append(self._option(value, value, available, reason))

        costumes = []
        if character in characters and phase in phases:
            for costume in self._costumes(character, phase):
                costumes.append(
                    self._option(
                        costume["slug"],
                        costume["name"],
                        costume["path"].is_file(),
                    )
                )

        views = []
        for token, data in sorted(self.views.load_view_options().items()):
            label = str(data.get("label") or token) if isinstance(data, dict) else token
            views.append(self._option(token, label, True))

        return {
            "schema_version": 1,
            "characters": character_rows,
            "phases": phase_rows,
            "costumes": costumes,
            "views": views,
        }

    def compile(
        self,
        *,
        character: str,
        phase: str,
        costume_slug: str | None,
        view_token: str,
        selected_sections: tuple[str, ...],
        reference_tags: tuple[str, ...],
    ) -> dict[str, Any]:
        options = self.options(character, phase)
        self._require_available(options["characters"], character, "character")
        self._require_available(options["phases"], phase, "phase")
        self._require_available(options["views"], view_token, "view")

        costume = None
        if costume_slug:
            self._require_available(options["costumes"], costume_slug, "costume")
            costume = next(
                item
                for item in self._costumes(character, phase)
                if item["slug"] == costume_slug
            )

        character_path = self.path_service.character_template_path(character, phase)
        sections, sources = self._load_sections(
            character_path,
            "character_template_section",
            f"Character template: {character}/{phase}",
        )
        source_files = [character_path]
        if costume is not None:
            costume_path = costume["path"]
            costume_sections, costume_sources = self._load_sections(
                costume_path,
                "costume_template_section",
                f"Costume template: {costume['name']}",
            )
            overlap = set(sections).intersection(costume_sections)
            for name in overlap.intersection(NON_CONTENT_SECTION_OVERLAPS):
                costume_sections.pop(name, None)
                costume_sources.pop(name, None)
            overlap.difference_update(NON_CONTENT_SECTION_OVERLAPS)
            if overlap:
                raise CharacterSourceError(
                    "Duplicate character/costume sections: "
                    + ", ".join(sorted(overlap))
                )
            sections.update(costume_sections)
            sources.update(costume_sources)
            source_files.append(costume_path)

        requested = self._requested_section_names(
            selected_sections,
            sections,
            view_token,
            include_costume=costume is not None,
        )
        selection = select_sections(
            sections,
            {"required_sections": requested},
            view_token,
            sources,
        )
        if selection.missing_required:
            raise CharacterSourceError(
                "Missing requested Zet sections: "
                + ", ".join(selection.missing_required)
            )
        if selection.forbidden_matches:
            raise CharacterSourceError(
                "Forbidden Zet sections selected: "
                + ", ".join(selection.forbidden_matches)
            )

        locked = {
            "identity": [],
            "body_proportions": [],
            "costume": [],
            "required_elements": [],
            "forbidden_elements": [],
        }
        for name, text in selection.sections.items():
            if name.startswith("NEGATIVE_"):
                locked["forbidden_elements"].append(text)
            elif name.startswith(("COSTUME_", "IDENTITY_PRESERVATION_COSTUME")):
                locked["costume"].append(text)
            elif name.startswith("EQUIPMENT_"):
                locked["required_elements"].append(text)
            elif name.startswith(("BODY_", "IDENTITY_PRESERVATION_BODY")):
                locked["body_proportions"].append(text)
            else:
                locked["identity"].append(text)

        references = []
        for tag in reference_tags:
            resolved = self.story_service.story_reference_service.resolve_image_tag(tag)
            references.append(
                {
                    "tag": tag,
                    "role": str(resolved.get("role") or "story_reference"),
                    "path": str(resolved.get("path") or ""),
                    "label": str(resolved.get("label") or tag),
                    "kind": str(resolved.get("kind") or "reference"),
                }
            )

        snapshot = {
            "character": character,
            "phase": phase,
            "costume": costume["name"] if costume else None,
            "costume_slug": costume["slug"] if costume else None,
            "view": view_token,
            "reference_tags": list(reference_tags),
            "selected_sections": selection.sections,
            "section_sources": {
                name: {
                    **{
                        key: value
                        for key, value in source.items()
                        if key != "source_path"
                    },
                    "source_name": Path(
                        str(source.get("source_path", ""))
                    ).name,
                }
                for name, source in selection.section_sources.items()
            },
            "source_files": [
                {
                    "source_name": path.name,
                    "sha256": self._sha256(path),
                    "content": path.read_text(encoding="utf-8"),
                }
                for path in source_files
            ],
        }
        source_reference = f"zet://{character}/{phase}"
        if costume is not None:
            source_reference += f"/costumes/{costume['slug']}"
        return {
            "source_kind": (
                "zet_character_costume" if costume is not None else "zet_character"
            ),
            "source_reference": source_reference,
            "locked": locked,
            "tunable": {
                "style_guidance": [],
                "checkpoint_vocabulary": [],
                "prompt_ordering_notes": [],
                "negative_prompt_candidates": [],
            },
            "source_snapshot": snapshot,
            "references": references,
            "required_checks": [
                name
                for name in selection.sections
                if not name.startswith("NEGATIVE_")
            ],
            "critical_failures": [
                name
                for name in selection.sections
                if name.startswith("NEGATIVE_")
            ],
            "optional_checks": [],
        }

    @staticmethod
    def _option(
        value: str,
        label: str,
        available: bool,
        disabled_reason: str = "",
    ) -> dict[str, Any]:
        return {
            "value": value,
            "label": label,
            "available": available,
            "disabled_reason": "" if available else disabled_reason or "Unavailable",
        }

    def _costumes(self, character: str, phase: str) -> list[dict[str, Any]]:
        root = self.path_service.character_path(character, phase)
        rows = []
        for path in sorted(root.glob("Costume_*.md")):
            raw_slug = path.stem.removeprefix("Costume_")
            name = self.costume_service.costume_name_from_slug(raw_slug)
            rows.append(
                {
                    "slug": self.costume_service.safe_costume_slug(name),
                    "name": name,
                    "path": path,
                }
            )
        return sorted(rows, key=lambda item: item["name"].lower())

    @staticmethod
    def _template_readiness(path: Path) -> tuple[bool, str]:
        if not path.is_file():
            return False, "Character.md is missing."
        try:
            load_template_sections_with_sources(
                path,
                source_kind="character_template_section",
                source_label=path.name,
            )
        except TemplateCompileError as exc:
            return False, str(exc)
        return True, ""

    @staticmethod
    def _load_sections(
        path: Path,
        source_kind: str,
        source_label: str,
    ) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        try:
            return load_template_sections_with_sources(
                path,
                source_kind=source_kind,
                source_label=source_label,
            )
        except TemplateCompileError as exc:
            raise CharacterSourceError(str(exc)) from exc

    @staticmethod
    def _require_available(
        options: list[dict[str, Any]],
        value: str,
        label: str,
    ) -> None:
        option = next((item for item in options if item["value"] == value), None)
        if option is None:
            raise CharacterSourceError(f"Unknown Zet {label}: {value}")
        if not option["available"]:
            raise CharacterSourceError(
                f"Unavailable Zet {label}: {value}: {option['disabled_reason']}"
            )

    @staticmethod
    def _requested_section_names(
        selected_sections: tuple[str, ...],
        available: dict[str, str],
        view_token: str,
        *,
        include_costume: bool,
    ) -> list[str]:
        requested = []
        for label in selected_sections:
            names = SECTION_GROUPS.get(label.strip().casefold())
            if names is None:
                names = (label.strip().upper().replace(" ", "_"),)
            for name in names:
                if not include_costume and name.startswith(
                    ("COSTUME_", "EQUIPMENT_", "IDENTITY_PRESERVATION_COSTUME")
                ):
                    continue
                resolved = name.replace("{VIEW}", view_token)
                if resolved in available and resolved not in requested:
                    requested.append(resolved)
        return requested

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
