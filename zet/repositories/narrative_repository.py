"""Independent, atomic storage; no legacy story templates or pipeline records."""
from dataclasses import asdict
import json
from pathlib import Path
import re
import shutil

from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


class NarrativeRepository:
    def __init__(self, library_root: str | Path):
        self.root = Path(library_root).resolve() / "NarrativeStories"

    def lock(self):
        return file_lock(self.root / ".workflow.lock")

    def folder(self, story: str, scene: str = "", target: str = "") -> Path:
        parts = []
        for value in (story, scene, target):
            if value:
                if not re.fullmatch(r"[a-f0-9]{32}", value):
                    raise ValueError("Invalid narrative record ID.")
                parts.append(value)
        return self.root.joinpath(*parts)

    def path(self, story: str, scene: str = "", target: str = "") -> Path:
        return self.folder(story, scene, target) / ("target.json" if target else "scene.json" if scene else "story.json")

    def read(self, story: str, scene: str = "", target: str = "") -> dict:
        path = self.path(story, scene, target)
        if not path.is_file():
            raise KeyError("Narrative record not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, record, story: str, scene: str = "", target: str = "") -> dict:
        data = record if isinstance(record, dict) else asdict(record)
        write_json_atomic(self.path(story, scene, target), data)
        return data

    def stories(self) -> list[dict]:
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.root.glob("*/story.json"))]

    def delete(self, story: str, scene: str = "", target: str = "") -> None:
        self.read(story, scene, target)
        folder = self.folder(story, scene, target).resolve()
        if not folder.is_relative_to(self.root) or folder == self.root:
            raise ValueError("Deletion must stay inside narrative storage.")
        shutil.rmtree(folder)
