from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
TEXT_EXTENSIONS = {".json", ".log", ".md", ".txt"}


class PipelineInspectionService:
    def __init__(self, base_pipeline_path: str | Path, asset_repository=None, path_service=None):
        self.base_path = Path(base_pipeline_path).resolve()
        self.asset_repository = asset_repository
        self.path_service = path_service

    def list_pipelines(self) -> list[dict[str, Any]]:
        if not self.base_path.is_dir():
            return []
        pipelines: list[dict[str, Any]] = []
        stories_path = self.base_path / "Stories"
        if stories_path.is_dir():
            for story_path in self._directories(stories_path):
                for scene_path in self._directories(story_path):
                    pipelines.append(self._pipeline(scene_path, "scene"))
        for character_path in self._directories(self.base_path, exclude={"Stories"}):
            for phase_path in self._directories(character_path):
                for pipeline_path in self._directories(phase_path):
                    pipelines.append(self._character_pipeline(pipeline_path, character_path.name, phase_path.name))
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
            raise ValueError("Only Markdown, JSON, TXT, and LOG files can be read as text.")
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

    def _character_pipeline(self, path: Path, character: str, phase: str) -> dict[str, Any]:
        pipeline = self._pipeline(path, "character")
        if self.asset_repository is None or self.path_service is None:
            return pipeline
        assets = [
            asset
            for asset in self.asset_repository.list_assets(character, phase)
            if asset.pipeline == path.name and self.path_service.pipeline_path(asset).is_dir()
        ]
        if len(assets) <= 1:
            if assets:
                pipeline.update(self._selectable_path(self.path_service.pipeline_path(assets[0])))
            return pipeline
        groups: dict[str, list] = {}
        for asset in assets:
            group = asset.costume or asset.expression or asset.identity_key_id or ""
            groups.setdefault(group, []).append(asset)
        if set(groups) == {""}:
            pipeline["children"] = self._asset_nodes(assets)
        else:
            pipeline["children"] = [
                {"label": label or "Other", "children": self._asset_nodes(group_assets)}
                for label, group_assets in sorted(groups.items(), key=lambda item: item[0].lower())
            ]
        pipeline.pop("pipeline_id", None)
        return pipeline

    def _asset_nodes(self, assets: list) -> list[dict[str, str]]:
        labels: dict[str, int] = {}
        for asset in assets:
            label = asset.body_view
            if asset.head_view and asset.head_view != asset.body_view:
                label = f"{asset.body_view} / {asset.head_view}"
            labels[label] = labels.get(label, 0) + 1
        nodes = []
        for asset in sorted(assets, key=lambda item: (item.body_view.lower(), (item.head_view or "").lower(), item.asset_id)):
            label = asset.body_view
            if asset.head_view and asset.head_view != asset.body_view:
                label = f"{asset.body_view} / {asset.head_view}"
            if labels[label] > 1:
                label = f"{label} · Asset {asset.asset_id}"
            nodes.append({"label": label, **self._selectable_path(self.path_service.pipeline_path(asset))})
        return nodes

    def _selectable_path(self, path: Path) -> dict[str, str]:
        return {"pipeline_id": path.relative_to(self.base_path).as_posix(), "path": str(path)}

    def _resolve_pipeline(self, pipeline_id: str) -> Path:
        path = (self.base_path / pipeline_id).resolve()
        if not path.is_relative_to(self.base_path) or not path.is_dir():
            raise FileNotFoundError(f"Pipeline not found: {pipeline_id}")
        valid_ids = self._selectable_ids(self.list_pipelines())
        if pipeline_id not in valid_ids:
            raise FileNotFoundError(f"Pipeline not found: {pipeline_id}")
        return path

    @classmethod
    def _selectable_ids(cls, nodes: list[dict[str, Any]]) -> set[str]:
        ids = {node["pipeline_id"] for node in nodes if node.get("pipeline_id")}
        for node in nodes:
            ids.update(cls._selectable_ids(node.get("children") or []))
        return ids

    @staticmethod
    def _directories(path: Path, exclude: set[str] | None = None) -> list[Path]:
        excluded = exclude or set()
        return sorted(
            (item for item in path.iterdir() if item.is_dir() and item.name not in excluded),
            key=lambda item: item.name.lower(),
        )
