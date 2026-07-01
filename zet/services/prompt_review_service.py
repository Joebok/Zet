from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.services.asset_service import AssetService
from zet.services.path_service import PathService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_PATH = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from Local_Render_Adapters.comfyui_adapter import LocalRenderResult, LocalRenderUnavailable, render_preview


@dataclass(frozen=True)
class PromptReviewContext:
    asset: Asset
    prompt_path: Path | None
    prompt_text: str | None
    prompt_review_path: Path | None
    prompt_candidates: list[Path]
    latest_local_test_render: Path | None


def is_prompt_review_asset(asset: Asset) -> bool:
    return asset.pipeline_stage == "PROMPT_REVIEW" and asset.actor == "HUMAN_AGENT"


class PromptReviewService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        asset_service: AssetService,
        path_service: PathService,
        project_root: Path = PROJECT_ROOT,
    ):
        self.asset_repository = asset_repository
        self.asset_service = asset_service
        self.path_service = path_service
        self.project_root = project_root

    def get_context(self, character: str, phase: str, asset_id: int) -> PromptReviewContext:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        prompt_candidates = self.prompt_file_candidates(asset)
        prompt_path = self.resolve_prompt_file(asset, prompt_candidates)
        prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path else None
        prompt_review_path = self.resolve_prompt_review_file(prompt_path) if prompt_path else None
        latest_render = self.latest_local_test_render(prompt_path) if prompt_path else None
        return PromptReviewContext(
            asset=asset,
            prompt_path=prompt_path,
            prompt_text=prompt_text,
            prompt_review_path=prompt_review_path,
            prompt_candidates=prompt_candidates,
            latest_local_test_render=latest_render,
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

    def resolve_prompt_review_file(self, prompt_path: Path) -> Path | None:
        path = prompt_path.parent / "Prompt_Review.md"
        return path if path.exists() else None

    def latest_local_test_render(self, prompt_path: Path) -> Path | None:
        render_dir = prompt_path.parent / "Local_Test_Renders"
        if not render_dir.exists():
            return None
        images = sorted(render_dir.glob("test_*.png"), key=lambda path: path.stat().st_mtime, reverse=True)
        return images[0] if images else None

    def approve(self, character: str, phase: str, asset_id: int) -> Asset:
        return self.asset_service.approve_prompt_review(character, phase, asset_id)

    def fail(self, character: str, phase: str, asset_id: int, reason: str = "") -> Asset:
        return self.asset_service.fail_prompt_review(character, phase, asset_id, reason)

    def generate_local_test_render(self, character: str, phase: str, asset_id: int) -> LocalRenderResult:
        context = self.get_context(character, phase, asset_id)
        if context.prompt_path is None:
            raise FileNotFoundError(f"No prompt file was found for asset {asset_id}.")
        return render_preview(
            project_root=self.project_root,
            final_prompt_path=context.prompt_path,
            job_output_dir=context.prompt_path.parent,
            prompt_review_path=context.prompt_review_path,
        )

    def view_folder_for_asset(self, asset: Asset) -> str:
        views = self.load_view_options()
        for view in views.values():
            if not isinstance(view, dict):
                continue
            if asset.body_view in {view.get("folder_name"), view.get("output_name_fragment")}:
                return str(view.get("folder_name"))
        return str(asset.body_view).replace("-", "_")

    def load_view_options(self) -> dict:
        path = self.project_root / "Config" / "Prompt_View_Text.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("views", data)
