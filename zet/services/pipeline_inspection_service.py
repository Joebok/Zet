from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path


IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
TEXT_EXTENSIONS = {".json", ".md"}


class PipelineInspectionService:
    def __init__(self, base_pipeline_path: str | Path):
        self.base_path = Path(base_pipeline_path).resolve()

    def list_pipelines(self) -> list[dict[str, str]]:
        if not self.base_path.is_dir():
            return []
        pipelines: list[dict[str, str]] = []
        stories_path = self.base_path / "Stories"
        if stories_path.is_dir():
            for story_path in self._directories(stories_path):
                for scene_path in self._directories(story_path):
                    pipelines.append(self._pipeline(scene_path, "scene"))
        for character_path in self._directories(self.base_path, exclude={"Stories"}):
            for phase_path in self._directories(character_path):
                for pipeline_path in self._directories(phase_path):
                    pipelines.append(self._pipeline(pipeline_path, "character"))
        return sorted(pipelines, key=lambda item: (item["kind"], item["label"].lower()))

    def list_files(self, pipeline_id: str) -> list[dict[str, str]]:
        pipeline_path = self._resolve_pipeline(pipeline_id)
        files = []
        for path in sorted(pipeline_path.rglob("*"), key=lambda item: str(item).lower()):
            if not path.is_file():
                continue
            extension = path.suffix.lower()
            kind = "text" if extension in TEXT_EXTENSIONS else "image" if extension in IMAGE_EXTENSIONS else "other"
            files.append(
                {
                    "file_id": path.relative_to(pipeline_path).as_posix(),
                    "name": path.name,
                    "path": str(path),
                    "kind": kind,
                }
            )
        return files

    def file_path(self, pipeline_id: str, file_id: str) -> Path:
        pipeline_path = self._resolve_pipeline(pipeline_id)
        path = (pipeline_path / file_id).resolve()
        if not path.is_relative_to(pipeline_path) or not path.is_file():
            raise FileNotFoundError(f"Pipeline file not found: {file_id}")
        return path

    def read_text(self, pipeline_id: str, file_id: str) -> str:
        path = self.file_path(pipeline_id, file_id)
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            raise ValueError("Only Markdown and JSON files can be read as text.")
        return path.read_text(encoding="utf-8")

    def open_folder(self, pipeline_id: str, file_id: str) -> Path:
        folder = self.file_path(pipeline_id, file_id).parent
        if platform.system() == "Windows":
            getattr(os, "startfile")(str(folder))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return folder

    def _pipeline(self, path: Path, kind: str) -> dict[str, str]:
        pipeline_id = path.relative_to(self.base_path).as_posix()
        return {
            "pipeline_id": pipeline_id,
            "label": " / ".join(Path(pipeline_id).parts),
            "path": str(path),
            "kind": kind,
        }

    def _resolve_pipeline(self, pipeline_id: str) -> Path:
        path = (self.base_path / pipeline_id).resolve()
        if not path.is_relative_to(self.base_path) or not path.is_dir():
            raise FileNotFoundError(f"Pipeline not found: {pipeline_id}")
        valid_ids = {item["pipeline_id"] for item in self.list_pipelines()}
        if pipeline_id not in valid_ids:
            raise FileNotFoundError(f"Pipeline not found: {pipeline_id}")
        return path

    @staticmethod
    def _directories(path: Path, exclude: set[str] | None = None) -> list[Path]:
        excluded = exclude or set()
        return sorted(
            (item for item in path.iterdir() if item.is_dir() and item.name not in excluded),
            key=lambda item: item.name.lower(),
        )
