from __future__ import annotations

from pathlib import Path


class TemplateManualService:
    MANUALS = {
        "character": ("Character Template Instructions", "Character_Template_Instructions.md"),
        "costume": ("Costume Template Instructions", "Costume_Template_Instructions.md"),
    }

    def __init__(self, project_root: Path):
        self.manual_root = project_root / "Shared_Library" / "Characters" / "_Shared"

    def get(self, manual_id: str) -> dict[str, str]:
        if manual_id not in self.MANUALS:
            raise KeyError(manual_id)
        title, filename = self.MANUALS[manual_id]
        path = self.manual_root / filename
        return {
            "id": manual_id,
            "title": title,
            "filename": filename,
            "path": str(path),
            "markdown": path.read_text(encoding="utf-8"),
        }

    def list(self) -> list[dict[str, str]]:
        return [self.get(manual_id) for manual_id in self.MANUALS]
