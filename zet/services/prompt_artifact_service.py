from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.services.path_service import PathService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PromptArtifactContext:
    asset: Asset
    prompt_path: Path | None
    prompt_text: str | None
    condensed_prompt_path: Path | None
    condensed_prompt_text: str | None
    render_prompt_path: Path | None
    render_prompt_text: str | None
    prompt_candidates: list[Path]


class PromptArtifactService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        path_service: PathService,
        project_root: Path = PROJECT_ROOT,
    ):
        self.asset_repository = asset_repository
        self.path_service = path_service
        self.project_root = project_root

    def get_context(self, character: str, phase: str, asset_id: int) -> PromptArtifactContext:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        prompt_candidates = self.prompt_file_candidates(asset)
        prompt_path = self.resolve_prompt_file(asset, prompt_candidates)
        prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path else None
        condensed_prompt_path = self.resolve_condensed_prompt_file(prompt_path) if prompt_path else None
        condensed_prompt_text = condensed_prompt_path.read_text(encoding="utf-8") if condensed_prompt_path else None
        return PromptArtifactContext(
            asset=asset,
            prompt_path=prompt_path,
            prompt_text=prompt_text,
            condensed_prompt_path=condensed_prompt_path,
            condensed_prompt_text=condensed_prompt_text,
            render_prompt_path=condensed_prompt_path or prompt_path,
            render_prompt_text=condensed_prompt_text or prompt_text,
            prompt_candidates=prompt_candidates,
        )

    def prompt_file_candidates(self, asset: Asset) -> list[Path]:
        pipeline_path = self.path_service.pipeline_path(asset)
        character_path = self.path_service.character_path(asset.character, asset.phase)
        view_folder = self.view_folder_for_asset(asset)
        return [
            pipeline_path / "Final_Image_Prompt.md",
            pipeline_path / "OLLAMA_PROMPT.md",
            character_path / "Body_Reference" / view_folder / "Final_Image_Prompt.md",
            character_path / "Body_Reference" / str(asset.body_view) / "Final_Image_Prompt.md",
        ]

    def resolve_prompt_file(self, asset: Asset, candidates: list[Path] | None = None) -> Path | None:
        for path in candidates or self.prompt_file_candidates(asset):
            if path.exists() and path.is_file():
                return path
        return None

    def resolve_condensed_prompt_file(self, prompt_path: Path) -> Path | None:
        path = prompt_path.parent / "Condensed_Image_Prompt.md"
        return path if path.exists() and path.is_file() else None

    def view_folder_for_asset(self, asset: Asset) -> str:
        path = self.project_root / "Config" / "Prompt_View_Text.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        views = data.get("views", data)
        for view in views.values():
            if not isinstance(view, dict):
                continue
            if asset.body_view in {view.get("folder_name"), view.get("output_name_fragment")}:
                return str(view.get("folder_name"))
        return str(asset.body_view).replace("-", "_")
