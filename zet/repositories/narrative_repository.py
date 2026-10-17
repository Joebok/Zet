"""Independent, atomic storage; no legacy story templates or pipeline records."""
from dataclasses import asdict
from pathlib import Path
import re
import shutil

from zet.services.workflow_storage import file_lock
from zet.services.library_reference_service import read_library_json, write_library_json


class NarrativeRepository:
    def __init__(self, library_root: str | Path):
        self.library_root = Path(library_root).resolve()
        self.root = self.library_root / "NarrativeStories"
        self.usage_provider = None

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
        # Coordinate readers with atomic replacements, which can briefly deny reads on Windows.
        with self.lock():
            if not path.is_file():
                raise KeyError("Narrative record not found.")
            record = read_library_json(path, self.library_root)
        if target:
            from zet.models.narrative import NarrativeTarget
            for key, value in asdict(NarrativeTarget(record["title"], record["kind"])).items():
                if key == "assembly_mode" and record["kind"] == "assembly":
                    value = "harmonize_composite"
                record.setdefault(key, value)
        elif scene:
            from zet.models.narrative import NarrativeScene
            # Existing scenes keep their authored style until explicitly switched.
            record.setdefault("use_universe_style", False)
            for key, value in asdict(NarrativeScene(record["title"])).items():
                record.setdefault(key, value)
            for element in record["elements"]:
                element.setdefault("reference_key", "")
        else:
            record.setdefault("source_provenance", {})
        return record

    def write(self, record, story: str, scene: str = "", target: str = "") -> dict:
        data = record if isinstance(record, dict) else asdict(record)
        path = self.path(story, scene, target)
        library = self.usage_provider() if self.usage_provider else None
        if library is None:
            write_library_json(path, data, self.library_root)
        else:
            library.image_usages.write_consumer(path, data, lambda: write_library_json(path, data, self.library_root))
        return data

    def stories(self) -> list[dict]:
        return [read_library_json(path, self.library_root) for path in sorted(self.root.glob("*/story.json"))]

    def delete(self, story: str, scene: str = "", target: str = "") -> None:
        self.read(story, scene, target)
        folder = self.folder(story, scene, target).resolve()
        if not folder.is_relative_to(self.root) or folder == self.root:
            raise ValueError("Deletion must stay inside narrative storage.")
        shutil.rmtree(folder)
