from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.path_service import PathService
from zet.services.prompt_artifact_service import PromptArtifactService
from zet.services.worker_service import WorkerService, WorkerServiceError

from Scripts.Local_Render_Adapters import LocalRenderResult, LocalRenderUnavailable, render_image

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PromptReviewContext:
    asset: Asset
    prompt_path: Path | None
    prompt_text: str | None
    condensed_prompt_path: Path | None
    condensed_prompt_text: str | None
    render_prompt_path: Path | None
    render_prompt_text: str | None
    source_map_path: Path | None
    source_map: dict
    prompt_review_path: Path | None
    prompt_candidates: list[Path]
    latest_local_test_render: Path | None
    condense_status: dict


class PromptReviewService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        prompt_artifact_service: PromptArtifactService,
        worker_service: WorkerService,
        path_service: PathService,
        project_root: Path = PROJECT_ROOT,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.prompt_artifact_service = prompt_artifact_service
        self.worker_service = worker_service
        self.path_service = path_service
        self.project_root = project_root

    def get_context(self, character: str, phase: str, asset_id: int) -> PromptReviewContext:
        artifacts = self.prompt_artifact_service.get_context(character, phase, asset_id)
        asset = artifacts.asset
        prompt_candidates = artifacts.prompt_candidates
        prompt_path = artifacts.prompt_path
        prompt_text = artifacts.prompt_text
        condensed_prompt_path = artifacts.condensed_prompt_path
        condensed_prompt_text = artifacts.condensed_prompt_text
        render_prompt_path = artifacts.render_prompt_path
        render_prompt_text = artifacts.render_prompt_text
        source_map_path = self.resolve_source_map_file(prompt_path) if prompt_path else None
        source_map = self._read_json_if_exists(source_map_path) if source_map_path else {}
        prompt_review_path = self.resolve_prompt_review_file(prompt_path) if prompt_path else None
        latest_render = self.latest_local_test_render(prompt_path) if prompt_path else None
        condense_status = self.prompt_condense_status(asset, prompt_path, condensed_prompt_path)
        return PromptReviewContext(
            asset=asset,
            prompt_path=prompt_path,
            prompt_text=prompt_text,
            condensed_prompt_path=condensed_prompt_path,
            condensed_prompt_text=condensed_prompt_text,
            render_prompt_path=render_prompt_path,
            render_prompt_text=render_prompt_text,
            source_map_path=source_map_path,
            source_map=source_map,
            prompt_review_path=prompt_review_path,
            prompt_candidates=prompt_candidates,
            latest_local_test_render=latest_render,
            condense_status=condense_status,
        )

    def prompt_file_candidates(self, asset: Asset) -> list[Path]:
        return self.prompt_artifact_service.prompt_file_candidates(asset)

    def resolve_prompt_file(self, asset: Asset, candidates: list[Path] | None = None) -> Path | None:
        return self.prompt_artifact_service.resolve_prompt_file(asset, candidates)

    def resolve_prompt_review_file(self, prompt_path: Path) -> Path | None:
        path = prompt_path.parent / "Prompt_Review.md"
        return path if path.exists() else None

    def resolve_condensed_prompt_file(self, prompt_path: Path) -> Path | None:
        return self.prompt_artifact_service.resolve_condensed_prompt_file(prompt_path)

    def resolve_source_map_file(self, prompt_path: Path) -> Path | None:
        for name in ("Prompt_Source_Map.json", "source_map.json"):
            path = prompt_path.parent / name
            if path.exists() and path.is_file():
                return path
        return None

    def _read_json_if_exists(self, path: Path) -> dict:
        if not path.exists() or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _condense_answer_status(self, answer_path: Path) -> str:
        harvest_manifest = self._read_json_if_exists(answer_path / "harvest_manifest.json")
        if harvest_manifest:
            return str(harvest_manifest.get("status") or "HARVESTED")
        answer_manifest = self._read_json_if_exists(answer_path / "answer_manifest.json")
        return str(answer_manifest.get("status") or "ANSWER_READY")

    def _condense_queue_items(self, asset: Asset) -> list[dict]:
        proxy_root = Path(self.path_service.config.base_ai_queue_path) / "File_Proxy"
        roots = [
            ("ASKED", proxy_root / "Ask" / "zet"),
            ("ANSWER", proxy_root / "Answer" / "zet"),
            ("RUNNING", proxy_root / "Running" / "zet"),
        ]

        items: list[dict] = []
        for state, root in roots:
            if not root.exists():
                continue
            for ask_path in root.iterdir():
                if not ask_path.is_dir():
                    continue
                manifest = self._read_json_if_exists(ask_path / "ask_manifest.json")
                if manifest.get("asset_id") != asset.asset_id or manifest.get("task_type") != "prompt_condense":
                    continue
                item_state = self._condense_answer_status(ask_path) if state == "ANSWER" else state
                items.append(
                    {
                        "state": item_state,
                        "ask_id": manifest.get("ask_id") or ask_path.name,
                        "attempt_id": manifest.get("ollama_attempt_id"),
                        "worker_type": manifest.get("worker_type"),
                        "model": manifest.get("ollama_model"),
                        "path": ask_path,
                        "updated_at": ask_path.stat().st_mtime,
                    }
                )
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return items

    def prompt_condense_status(
        self,
        asset: Asset,
        prompt_path: Path | None,
        condensed_prompt_path: Path | None,
    ) -> dict:
        enabled = bool(getattr(self.path_service.config, "prompt_condense_enabled", False))
        model = str(getattr(self.path_service.config, "prompt_condense_model", ""))
        queue_items = self._condense_queue_items(asset)
        latest_queue_item = queue_items[0] if queue_items else None
        condensed_exists = condensed_prompt_path is not None
        condensed_current = False
        if prompt_path is not None and condensed_prompt_path is not None:
            condensed_current = condensed_prompt_path.stat().st_mtime >= prompt_path.stat().st_mtime

        if latest_queue_item is not None and latest_queue_item["state"] in {"ASKED", "ANSWER_READY", "SUCCESS"}:
            state = latest_queue_item["state"]
        elif latest_queue_item is not None and str(latest_queue_item["state"]).startswith("CLAIMED:"):
            state = latest_queue_item["state"]
        elif condensed_exists and condensed_current:
            state = "READY"
        elif condensed_exists:
            state = "STALE"
        elif enabled:
            state = "NOT_CREATED"
        else:
            state = "DISABLED"

        return {
            "enabled": enabled,
            "model": model,
            "state": state,
            "condensed_exists": condensed_exists,
            "condensed_current": condensed_current,
            "condensed_prompt_path": condensed_prompt_path,
            "latest_queue_item": latest_queue_item,
            "queue_items": queue_items,
        }

    def latest_local_test_render(self, prompt_path: Path) -> Path | None:
        render_dir = prompt_path.parent / "Local_Test_Renders"
        if not render_dir.exists():
            return None
        images = sorted(render_dir.glob("test_*.png"), key=lambda path: path.stat().st_mtime, reverse=True)
        return images[0] if images else None

    def recompile(
        self,
        character: str,
        phase: str,
        asset_id: int,
        invalidate_review_artifacts: bool = False,
    ) -> PromptReviewContext:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage != "RENDER":
            raise ValueError(f"Asset {asset_id} has no render prompt available for inspection.")

        prompt_path = self.resolve_prompt_file(asset, self.prompt_file_candidates(asset))
        if invalidate_review_artifacts and prompt_path is not None:
            self._clear_review_aids(prompt_path)

        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        worker_name = pipeline.worker_by_stage.get("PROMPT")
        if not worker_name:
            raise ValueError(f"Pipeline {asset.pipeline} has no PROMPT worker configured.")
        try:
            result = self.worker_service.run_named_worker(asset, worker_name)
        except WorkerServiceError as exc:
            raise ValueError(str(exc)) from exc
        if not result.success:
            raise ValueError(result.error_message or result.message)
        return self.get_context(character, phase, asset_id)

    def _clear_review_aids(self, prompt_path: Path) -> None:
        condensed_prompt = prompt_path.parent / "Condensed_Image_Prompt.md"
        if condensed_prompt.exists():
            condensed_prompt.unlink()
        local_render_dir = prompt_path.parent / "Local_Test_Renders"
        if local_render_dir.exists() and local_render_dir.is_dir():
            shutil.rmtree(local_render_dir)

    def generate_local_test_render(self, character: str, phase: str, asset_id: int) -> LocalRenderResult:
        context = self.get_context(character, phase, asset_id)
        if context.render_prompt_path is None:
            raise FileNotFoundError(f"No prompt file was found for asset {asset_id}.")
        config = self.path_service.config
        backend = str(getattr(config, "local_render_backend", "stable_matrix")).strip().lower()
        profile_name = (
            str(getattr(config, "comfyui_profile", "comfyui-core-preview"))
            if backend == "comfyui"
            else str(getattr(config, "local_render_preset", "body-reference-preview"))
        )
        return render_image(
            project_root=self.project_root,
            final_prompt_path=context.render_prompt_path,
            job_output_dir=context.render_prompt_path.parent,
            prompt_review_path=context.prompt_review_path,
            preset_name=profile_name,
            reference_files=context.asset.reference_files or [],
        )

    def view_folder_for_asset(self, asset: Asset) -> str:
        return self.prompt_artifact_service.view_folder_for_asset(asset)

    def load_view_options(self) -> dict:
        return self.prompt_artifact_service.load_view_options()
