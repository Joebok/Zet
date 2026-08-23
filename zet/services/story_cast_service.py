from __future__ import annotations


class StoryCastService:
    """Resolve story-scoped character defaults to stable image-reference tags."""

    def __init__(self, story_service):
        self.story_service = story_service

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value or "").replace("-", " ").replace("_", " ").casefold().split())

    def _story_default(self, story_slug: str, character: str) -> dict:
        try:
            path = self.story_service.get_story_settings_path_from_story_md(
                self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug))
            )
            settings = self.story_service.load_story_settings(path)
        except Exception:
            return {}
        target = self._normalize(character)
        for item in settings.get("cast_defaults") or []:
            if isinstance(item, dict) and self._normalize(item.get("character")) == target:
                return item
        return {}

    @staticmethod
    def _explicit(explicit: str) -> dict:
        parts = [part.strip() for part in str(explicit or "").split("|")]
        return {
            "phase": parts[0] if parts else "",
            "costume": parts[1] if len(parts) > 1 else "",
            "reference_kind": parts[2] if len(parts) > 2 else "",
            "view": parts[3] if len(parts) > 3 else "",
        }

    def resolve(self, story_slug: str, character: str, phase: str = "", explicit: str = "") -> dict:
        supplied = self._explicit(explicit) if explicit else {}
        default = self._story_default(story_slug, character)
        resolved_phase = str(supplied.get("phase") or default.get("phase") or phase or "").strip()
        costume = str(supplied.get("costume") or default.get("costume") or "").strip()
        reference_kind = self._normalize(supplied.get("reference_kind") or default.get("reference_kind") or "")
        view = self._normalize(supplied.get("view") or default.get("view") or "")
        if not resolved_phase:
            return {"phase": "", "costume": costume, "tag": "", "error": "Character phase is not established."}
        rows = self.story_service.image_reference_rows(
            character_filter=character,
            phase_filter=resolved_phase,
            costume_filter=costume,
            scope="context",
            include_unavailable=False,
        )
        if reference_kind in {"turnaround", "costume turnaround"}:
            rows = [row for row in rows if row.kind == "locked-turnaround" and (not costume or row.costume)]
        elif reference_kind:
            rows = [row for row in rows if self._normalize(row.kind) == reference_kind or self._normalize(row.pipeline) == reference_kind]
        elif costume:
            rows = [row for row in rows if row.kind == "locked-turnaround" and row.costume]
        else:
            turnarounds = [row for row in rows if row.kind == "locked-turnaround"]
            rows = turnarounds if len(turnarounds) == 1 else []
        if view:
            rows = [row for row in rows if self._normalize(row.view) == view]
        if len(rows) != 1:
            return {
                "phase": resolved_phase,
                "costume": costume,
                "tag": "",
                "error": "No unique locked character reference matches the story cast default.",
            }
        return {"phase": resolved_phase, "costume": costume or rows[0].costume, "tag": rows[0].tag, "error": ""}
