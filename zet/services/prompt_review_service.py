from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import shutil
import sys

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.services.asset_service import AssetService
from zet.services.path_service import PathService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_PATH = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from Local_Render_Adapters import LocalRenderResult, LocalRenderUnavailable, render_image

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
        condensed_prompt_path = self.resolve_condensed_prompt_file(prompt_path) if prompt_path else None
        condensed_prompt_text = condensed_prompt_path.read_text(encoding="utf-8") if condensed_prompt_path else None
        render_prompt_path = condensed_prompt_path or prompt_path
        render_prompt_text = condensed_prompt_text or prompt_text
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

    def resolve_condensed_prompt_file(self, prompt_path: Path) -> Path | None:
        path = prompt_path.parent / "Condensed_Image_Prompt.md"
        return path if path.exists() and path.is_file() else None

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
        proxy_root = Path(self.path_service.config.base_ai_queue_path) / "Ollama_Proxy"
        roots = [
            ("ASKED", proxy_root / "Ask"),
            ("ANSWER", proxy_root / "Answer"),
        ]
        claimed_root = proxy_root / "Claimed"
        if claimed_root.exists():
            roots.extend((f"CLAIMED:{worker_dir.name}", worker_dir) for worker_dir in claimed_root.iterdir() if worker_dir.is_dir())

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

    def clear_local_test_renders(self, workspace: Path) -> None:
        render_dir = workspace / "Local_Test_Renders"
        if render_dir.exists() and render_dir.is_dir():
            shutil.rmtree(render_dir)

    def approve(self, character: str, phase: str, asset_id: int) -> Asset:
        return self.asset_service.approve_prompt_review(character, phase, asset_id)

    def fail(self, character: str, phase: str, asset_id: int, reason: str = "") -> Asset:
        return self.asset_service.fail_prompt_review(character, phase, asset_id, reason)

    def recompile(
        self,
        character: str,
        phase: str,
        asset_id: int,
        invalidate_review_artifacts: bool = False,
    ) -> PromptReviewContext:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if not is_prompt_review_asset(asset):
            raise ValueError(f"Asset {asset_id} is not currently in prompt review.")

        prompt_path = self.resolve_prompt_file(asset, self.prompt_file_candidates(asset))
        if invalidate_review_artifacts and prompt_path is not None:
            self._clear_review_aids(prompt_path)

        pipeline = self.asset_service.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        worker_name = pipeline.worker_by_stage.get("PROMPT")
        if not worker_name:
            raise ValueError(f"Pipeline {asset.pipeline} has no PROMPT worker configured.")
        module_name = self.asset_service.worker_service._normalize_worker_name(worker_name)
        module = importlib.import_module(module_name)
        run_func = getattr(module, "run", None)
        if not callable(run_func):
            raise ValueError(f"Prompt worker module {module_name} has no callable run function.")
        context = self.asset_service.worker_service._build_context(asset)
        result = run_func(asset, context)
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
        return render_image(
            project_root=self.project_root,
            final_prompt_path=context.render_prompt_path,
            job_output_dir=context.render_prompt_path.parent,
            prompt_review_path=context.prompt_review_path,
            preset_name=str(getattr(self.path_service.config, "local_render_preset", "body-reference-preview")),
            reference_files=context.asset.reference_files or [],
            governing_template_path=self.governing_template_path(context.asset),
        )

    def governing_template_path(self, asset: Asset) -> Path:
        if asset.pipeline == "Costume-Dressing":
            return self.path_service.resolve_path(asset.costume_path) if asset.costume_path else self.path_service.costume_template_path(
                asset.character,
                asset.phase,
                asset.costume or "Costume",
            )
        if asset.pipeline == "Expression" and asset.expression_definition_path:
            return self.path_service.resolve_path(asset.expression_definition_path)
        return self.path_service.character_path(asset.character, asset.phase) / "Character_Image_Template.md"

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
