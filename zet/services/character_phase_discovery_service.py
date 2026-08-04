from __future__ import annotations

from pathlib import Path


class CharacterPhaseDiscoveryService:
    def __init__(self, base_character_path: str | Path):
        self.root = Path(base_character_path)

    def list_characters(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(path.name for path in self.root.iterdir() if path.is_dir())

    def list_phases(self, character: str) -> list[str]:
        root = self.root / character
        if not root.is_dir():
            return []
        return sorted(path.name for path in root.iterdir() if path.is_dir())
