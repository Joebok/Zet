import shutil
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.housekeeping_service import HousekeepingService
from zet.services.ai_proxy_service import AIProxyService
from zet.services.ai_answer_harvester import AIAnswerHarvester
from zet.services.path_service import PathService
from zet.services.prompt_artifact_service import PromptArtifactService
from zet.services.state_machine import StateMachine
from zet.services.worker_service import WorkerService

VALID_ACTORS = {"PYTHON", "AI_AGENT", "HUMAN_AGENT"}
MISSING_REFERENCE_ERROR_CODES = {
    "MISSING_REFERENCE",
    "MISSING_BODY_REFERENCE",
    "MISSING_HEADSHOT_REFERENCE",
    "MISSING_HEAD_IMAGE_REFERENCE",
    "MISSING_CHARACTER_ASSEMBLY",
    "MISSING_COSTUME_DRESSING",
}
ASSET_PIPELINE_ORDER = [
    "Body-Reference",
    "Head-Image",
    "Character-Assembly",
    "Costume-Dressing",
    "Scene-Appearance",
    "Expression",
]
ASSET_VIEW_ORDER = [
    "Front",
    "Front-Left-3-4",
    "Front-Right-3-4",
    "Left-Profile",
    "Right-Profile",
    "Back-Left-3-4",
    "Back-Right-3-4",
    "Back",
]
_ASSET_PIPELINE_RANK = {name: index for index, name in enumerate(ASSET_PIPELINE_ORDER)}
_ASSET_VIEW_RANK = {name: index for index, name in enumerate(ASSET_VIEW_ORDER)}


def asset_sort_key(asset: Asset) -> tuple[int, int, str, int]:
    costume_or_expression = asset.expression if asset.expression else asset.costume
    return (
        _ASSET_PIPELINE_RANK.get(asset.pipeline, len(_ASSET_PIPELINE_RANK)),
        _ASSET_VIEW_RANK.get(asset.body_view, len(_ASSET_VIEW_RANK)),
        str(costume_or_expression or "").casefold(),
        asset.asset_id,
    )


class AssetServiceError(Exception):
    pass


@dataclass(frozen=True)
class WorkerPollResult:
    asset_id: int
    worker_name: str
    before_stage: str
    before_actor: str
    after_stage: str
    after_actor: str
    status: str
    message: str


@dataclass(frozen=True)
class WorkerChainResult:
    asset: Asset
    worker_count: int
    messages: list[str]


@dataclass(frozen=True)
class BatchRenderResetResult:
    asset_id: int
    before_stage: str
    before_actor: str
    before_state: str
    status: str
    message: str


@dataclass(frozen=True)
class BatchRenderResetPreviewResult:
    asset_id: int
    previous_stage: str
    previous_actor: str
    previous_state: str
    preview_status: str
    reason: str


class AssetService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        state_machine: StateMachine,
        housekeeping_service: HousekeepingService,
        path_service: PathService,
        prompt_artifact_service: PromptArtifactService,
        worker_service: WorkerService,
        ai_proxy_service: AIProxyService,
        ai_answer_harvester: AIAnswerHarvester,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.state_machine = state_machine
        self.housekeeping_service = housekeeping_service
        self.path_service = path_service
        self.prompt_artifact_service = prompt_artifact_service
        self.worker_service = worker_service
        self.ai_proxy_service = ai_proxy_service
        self.ai_answer_harvester = ai_answer_harvester

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _validate_actor(self, pipeline_name: str, stage: str, actor: str | None) -> str:
        if actor is None:
            raise AssetServiceError(f"Pipeline {pipeline_name} has no actor defined for stage {stage}")
        if actor not in VALID_ACTORS:
            raise AssetServiceError(f"Pipeline {pipeline_name} uses invalid actor {actor} for stage {stage}")
        return actor

    def _actor_for_stage(self, asset: Asset, pipeline, stage: str) -> str:
        return self._validate_actor(pipeline.name, stage, pipeline.actor_by_stage.get(stage))

    def _view_folder_for_asset(self, asset: Asset) -> str:
        return self.prompt_artifact_service.view_folder_for_asset(asset, tolerate_config_errors=True)

    def _clear_body_reference_generated_artifacts(self, asset: Asset) -> None:
        if asset.pipeline != "Body-Reference":
            return

        output_dir = (
            self.path_service.character_path(asset.character, asset.phase)
            / "Body_Reference"
            / self._view_folder_for_asset(asset)
        )
        if not output_dir.exists():
            return

        generated_files = [
            "Compiled_Sections.md",
            "Final_Image_Prompt.md",
            "Condensed_Image_Prompt.md",
            "dependency_manifest.json",
            "Prompt_Review.md",
            "Image_Review.md",
        ]
        for name in generated_files:
            (output_dir / name).unlink(missing_ok=True)

        local_render_dir = output_dir / "Local_Test_Renders"
        if local_render_dir.exists():
            shutil.rmtree(local_render_dir, ignore_errors=True)

    def _clear_regeneration_outputs(self, asset: Asset) -> None:
        pipeline_path = self.path_service.pipeline_path(asset)
        if pipeline_path.exists():
            shutil.rmtree(pipeline_path, ignore_errors=True)
        self._clear_body_reference_generated_artifacts(asset)
        self.ai_proxy_service.clear_asset_queue_items(asset)

    def move_next(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage == "ERROR":
            raise AssetServiceError(f"Asset {asset_id} is in ERROR stage and cannot move next")

        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        next_stage = self.state_machine.next_stage(pipeline, asset.pipeline_stage)

        next_actor = self._actor_for_stage(asset, pipeline, next_stage)

        updated_asset = replace(asset)
        updated_asset.pipeline_stage = next_stage
        updated_asset.actor = next_actor
        updated_asset.updated_at = self._timestamp()

        if asset.pipeline_stage == "MANIFEST" and next_stage != "MANIFEST":
            updated_asset.asset_state = "IN_PROGRESS"

        if next_actor == "AI_AGENT":
            updated_asset.ai_state = "ASKED"
        else:
            updated_asset.ai_state = None

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        if next_actor == "AI_AGENT":
            self.ai_proxy_service.stage_current_ai_ask(character, phase, asset_id)
            return self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage == "PROMPT" and next_stage == "RENDER":
            self.ai_proxy_service.stage_prompt_condense_ask_if_enabled(character, phase, asset_id)
        return updated_asset

    def run_housekeeping(self, character: str, phase: str, asset_id: int) -> Path:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        return self.housekeeping_service.prepare_stage(asset)

    def _clear_render_outputs(self, asset: Asset) -> None:
        for path in (
            self.path_service.candidate_image_path(asset),
            self.path_service.pipeline_path(asset) / "LOCAL_RENDER_METADATA.json",
            self.render_review_comment_path(asset),
        ):
            path.unlink(missing_ok=True)

    def render_review_comment_path(self, asset: Asset) -> Path:
        """Return the render-review comment sidecar path for an asset."""
        return self.path_service.pipeline_path(asset) / "Render_Review_Comment.md"

    def get_render_review_comment(self, character: str, phase: str, asset_id: int) -> str:
        """Read the render-review comment for an asset."""
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        path = self.render_review_comment_path(asset)
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""

    def save_render_review_comment(self, character: str, phase: str, asset_id: int, comment: str) -> str:
        """Save the render-review comment for an asset."""
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        path = self.render_review_comment_path(asset)
        cleaned = str(comment or "").strip()
        if cleaned:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(cleaned + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        return cleaned

    def _render_reset_skip_message(self, asset: Asset) -> str | None:
        if asset.pipeline_stage in {"MANIFEST", "PROMPT"}:
            return f"Asset is at {asset.pipeline_stage}; upstream regeneration/compile work should finish before render reset."
        if asset.pipeline == "Body-Reference":
            context = self.prompt_artifact_service.get_context(asset.character, asset.phase, asset.asset_id)
            if not context.prompt_text:
                return "No Final_Image_Prompt.md found; asset is not render-ready."
        return None

    def _pipeline_render_reset_candidates(
        self,
        character: str,
        phase: str,
        pipeline_name: str,
        include_locked: bool,
    ) -> tuple[str, list[tuple[Asset, str | None]]]:
        pipeline = self.pipeline_repository.get_pipeline(character, phase, pipeline_name)
        if "RENDER" not in pipeline.stages:
            raise AssetServiceError(f"Pipeline {pipeline_name} has no RENDER stage.")
        sample = next(
            (asset for asset in self.asset_repository.list_assets(character, phase) if asset.pipeline == pipeline_name),
            None,
        )
        render_actor = (
            self._actor_for_stage(sample, pipeline, "RENDER")
            if sample is not None
            else self._validate_actor(pipeline.name, "RENDER", pipeline.actor_by_stage.get("RENDER"))
        )

        candidates: list[tuple[Asset, str | None]] = []
        for asset in self.asset_repository.list_assets(character, phase):
            if asset.pipeline != pipeline_name:
                continue
            skip_message = None
            if asset.asset_state == "LOCKED" and not include_locked:
                skip_message = "Asset is LOCKED. Enable include locked assets to reset it."
            if skip_message is None:
                skip_message = self._render_reset_skip_message(asset)
            candidates.append((asset, skip_message))
        return render_actor, candidates

    def preview_pipeline_assets_to_render(
        self,
        character: str,
        phase: str,
        pipeline_name: str,
        include_locked: bool = False,
    ) -> list[BatchRenderResetPreviewResult]:
        _, candidates = self._pipeline_render_reset_candidates(character, phase, pipeline_name, include_locked)
        return [
            BatchRenderResetPreviewResult(
                asset_id=asset.asset_id,
                previous_stage=asset.pipeline_stage,
                previous_actor=asset.actor,
                previous_state=asset.asset_state,
                preview_status="SKIPPED" if skip_message else "WOULD_RESET",
                reason=skip_message or "Asset will be moved to RENDER and its queued/render outputs cleared.",
            )
            for asset, skip_message in candidates
        ]

    def reset_pipeline_assets_to_render(
        self,
        character: str,
        phase: str,
        pipeline_name: str,
        include_locked: bool = False,
    ) -> list[BatchRenderResetResult]:
        render_actor, candidates = self._pipeline_render_reset_candidates(character, phase, pipeline_name, include_locked)

        results: list[BatchRenderResetResult] = []
        for asset, skip_message in candidates:
            if skip_message is not None:
                results.append(
                    BatchRenderResetResult(
                        asset_id=asset.asset_id,
                        before_stage=asset.pipeline_stage,
                        before_actor=asset.actor,
                        before_state=asset.asset_state,
                        status="SKIPPED",
                        message=skip_message,
                    )
                )
                continue

            try:
                self.ai_proxy_service.clear_asset_queue_items(asset)
                self._clear_render_outputs(asset)

                updated_asset = replace(asset)
                updated_asset.asset_state = "IN_PROGRESS"
                updated_asset.pipeline_stage = "RENDER"
                updated_asset.actor = render_actor
                updated_asset.ai_state = "ASKED" if render_actor == "AI_AGENT" else None
                updated_asset.error_code = None
                updated_asset.error_message = None
                updated_asset.last_ai_update = f"Batch render reset requested at {self._timestamp()}"
                updated_asset.updated_at = self._timestamp()
                self.asset_repository.save_asset(updated_asset)
                self.housekeeping_service.prepare_stage(updated_asset)

                ask_path = None
                if render_actor == "AI_AGENT":
                    ask_path = self.ai_proxy_service.stage_current_ai_ask(character, phase, asset.asset_id)
                refreshed = self.asset_repository.get_asset(character, phase, asset.asset_id)
                results.append(
                    BatchRenderResetResult(
                        asset_id=asset.asset_id,
                        before_stage=asset.pipeline_stage,
                        before_actor=asset.actor,
                        before_state=asset.asset_state,
                        status="RESET",
                        message=(
                            f"Moved to RENDER and staged ask {ask_path.name}."
                            if ask_path is not None
                            else "Moved to masked-local RENDER."
                        ),
                    )
                )
                self.housekeeping_service.prepare_stage(refreshed)
            except Exception as exc:
                failed_asset = replace(asset)
                failed_asset.asset_state = "BLOCKED"
                failed_asset.pipeline_stage = "ERROR"
                failed_asset.actor = "HUMAN_AGENT"
                failed_asset.ai_state = None
                failed_asset.error_code = "BATCH_RENDER_RESET_FAILED"
                failed_asset.error_message = str(exc)
                failed_asset.updated_at = self._timestamp()
                self.asset_repository.save_asset(failed_asset)
                self.housekeeping_service.prepare_stage(failed_asset)
                results.append(
                    BatchRenderResetResult(
                        asset_id=asset.asset_id,
                        before_stage=asset.pipeline_stage,
                        before_actor=asset.actor,
                        before_state=asset.asset_state,
                        status="ERROR",
                        message=str(exc),
                    )
                )

        return results

    def regenerate(self, character: str, phase: str, asset_id: int, clear_references: bool = False) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        manifest_actor = self._validate_actor(
            pipeline.name,
            "MANIFEST",
            pipeline.actor_by_stage.get("MANIFEST"),
        )
        self._clear_regeneration_outputs(asset)

        updated_asset = replace(asset)
        updated_asset.asset_state = "IN_PROGRESS"
        updated_asset.pipeline_stage = "MANIFEST"
        updated_asset.actor = manifest_actor
        updated_asset.ai_state = "ASKED" if manifest_actor == "AI_AGENT" else None
        updated_asset.error_code = None
        updated_asset.error_message = None
        if clear_references:
            updated_asset.reference_files = []
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def regenerate_and_advance(self, character: str, phase: str, asset_id: int) -> WorkerChainResult:
        self.regenerate(character, phase, asset_id)
        return self.run_current_worker_chain(character, phase, asset_id)

    def promote_to_locked(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        candidate_image_path = self.path_service.candidate_image_path(asset)
        locked_image_path = self.path_service.locked_image_path(asset)

        if not candidate_image_path.exists():
            raise AssetServiceError("Cannot promote: candidate image does not exist.")

        locked_image_path.parent.mkdir(parents=True, exist_ok=True)
        if locked_image_path.exists():
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_name = f"{locked_image_path.stem}.backup.{backup_suffix}{locked_image_path.suffix}"
            backup_dir = self.path_service.character_backup_path(character, phase)
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(locked_image_path, backup_dir / backup_name)

        shutil.copy2(candidate_image_path, locked_image_path)

        updated_asset = replace(asset)
        updated_asset.asset_state = "LOCKED"
        updated_asset.pipeline_stage = "LOCKED"
        updated_asset.actor = "HUMAN_AGENT"
        updated_asset.ai_state = None
        updated_asset.error_code = None
        updated_asset.error_message = None
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def discard_candidate(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        candidate_image_path = self.path_service.candidate_image_path(asset)
        locked_image_path = self.path_service.locked_image_path(asset)

        if asset.pipeline_stage != "RENDER_REVIEW" or asset.actor != "HUMAN_AGENT":
            raise AssetServiceError("Candidate discard is only available at RENDER_REVIEW / HUMAN_AGENT.")
        if not candidate_image_path.exists():
            raise AssetServiceError("Cannot discard: candidate image does not exist.")
        if not locked_image_path.exists():
            raise AssetServiceError("Cannot discard: locked image does not exist.")

        candidate_image_path.unlink()
        self.render_review_comment_path(asset).unlink(missing_ok=True)

        updated_asset = replace(asset)
        updated_asset.asset_state = "LOCKED"
        updated_asset.pipeline_stage = "LOCKED"
        updated_asset.actor = "HUMAN_AGENT"
        updated_asset.ai_state = None
        updated_asset.error_code = None
        updated_asset.error_message = None
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def keep_locked(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        locked_image_path = self.path_service.locked_image_path(asset)

        if not locked_image_path.exists():
            raise AssetServiceError("Cannot keep locked: locked image does not exist.")

        self.ai_proxy_service.clear_asset_queue_items(asset)
        self.path_service.candidate_image_path(asset).unlink(missing_ok=True)
        self.render_review_comment_path(asset).unlink(missing_ok=True)

        updated_asset = replace(asset)
        updated_asset.asset_state = "LOCKED"
        updated_asset.pipeline_stage = "LOCKED"
        updated_asset.actor = "HUMAN_AGENT"
        updated_asset.ai_state = None
        updated_asset.error_code = None
        updated_asset.error_message = None
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return updated_asset

    def regenerate_and_clear_references(self, character: str, phase: str, asset_id: int) -> Asset:
        return self.regenerate(character, phase, asset_id, clear_references=True)

    def fail_render_review_to_render(self, character: str, phase: str, asset_id: int, reason: str = "") -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage != "RENDER_REVIEW" or asset.actor != "HUMAN_AGENT":
            raise AssetServiceError("Render retry is only available at RENDER_REVIEW / HUMAN_AGENT.")

        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        render_actor = self._actor_for_stage(asset, pipeline, "RENDER")

        self.ai_proxy_service.clear_asset_queue_items(asset)
        self._clear_render_outputs(asset)

        updated_asset = replace(asset)
        updated_asset.asset_state = "IN_PROGRESS"
        updated_asset.pipeline_stage = "RENDER"
        updated_asset.actor = render_actor
        updated_asset.ai_state = "ASKED" if render_actor == "AI_AGENT" else None
        updated_asset.error_code = None
        updated_asset.error_message = None
        updated_asset.last_ai_update = reason.strip() or f"Render review retry requested at {self._timestamp()}"
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        if render_actor == "AI_AGENT":
            self.ai_proxy_service.stage_current_ai_ask(character, phase, asset_id)
        return self.asset_repository.get_asset(character, phase, asset_id)

    def run_current_worker(self, character: str, phase: str, asset_id: int) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.actor != "PYTHON":
            raise AssetServiceError("Current worker can only run when Actor is PYTHON.")

        self.housekeeping_service.prepare_stage(asset)
        result = self.worker_service.run_current_worker(character, phase, asset_id)

        if result.success:
            refreshed_asset = self.asset_repository.get_asset(character, phase, asset_id)
            if result.reference_files is not None:
                refreshed_asset = replace(refreshed_asset)
                refreshed_asset.reference_files = result.reference_files
                refreshed_asset.updated_at = self._timestamp()
                self.asset_repository.save_asset(refreshed_asset)
            if result.advance_stage:
                updated_asset = self.move_next(character, phase, asset_id)
            else:
                updated_asset = replace(refreshed_asset)
                updated_asset.error_code = None
                updated_asset.error_message = None
                updated_asset.updated_at = self._timestamp()
                self.asset_repository.save_asset(updated_asset)
                self.housekeeping_service.prepare_stage(updated_asset)
            return updated_asset

        if (result.error_code or "") in MISSING_REFERENCE_ERROR_CODES:
            refreshed_asset = self.asset_repository.get_asset(character, phase, asset_id)
            pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
            if "ADD_REF" not in pipeline.stages:
                add_ref_stage = refreshed_asset.pipeline_stage
            else:
                add_ref_stage = "ADD_REF"
            add_ref_actor = self._validate_actor(pipeline.name, add_ref_stage, pipeline.actor_by_stage.get(add_ref_stage))
            waiting_asset = replace(refreshed_asset)
            waiting_asset.asset_state = "IN_PROGRESS"
            waiting_asset.pipeline_stage = add_ref_stage
            waiting_asset.actor = add_ref_actor
            waiting_asset.ai_state = None
            waiting_asset.error_code = result.error_code or "MISSING_REFERENCE"
            waiting_asset.error_message = result.error_message or result.message
            waiting_asset.updated_at = self._timestamp()

            self.asset_repository.save_asset(waiting_asset)
            self.housekeeping_service.prepare_stage(waiting_asset)
            return waiting_asset

        failed_asset = replace(asset)
        failed_asset.asset_state = "BLOCKED"
        failed_asset.pipeline_stage = "ERROR"
        failed_asset.actor = "HUMAN_AGENT"
        failed_asset.ai_state = None
        failed_asset.error_code = result.error_code or "WORKER_FAILED"
        failed_asset.error_message = result.error_message or result.message
        failed_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(failed_asset)
        self.housekeeping_service.prepare_stage(failed_asset)
        return failed_asset

    def stage_ai_ask(self, character: str, phase: str, asset_id: int) -> Path:
        return self.ai_proxy_service.stage_current_ai_ask(character, phase, asset_id)

    def run_current_worker_chain(self, character: str, phase: str, asset_id: int, max_steps: int = 10) -> WorkerChainResult:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.actor != "PYTHON":
            raise AssetServiceError("Current worker can only run when Actor is PYTHON.")

        messages: list[str] = []
        worker_count = 0
        updated_asset = asset

        while worker_count < max_steps and updated_asset.actor == "PYTHON":
            before_stage = updated_asset.pipeline_stage
            before_actor = updated_asset.actor
            updated_asset = self.run_current_worker(character, phase, asset_id)
            worker_count += 1

            worker_result = self.worker_service.last_worker_result
            if worker_result is not None:
                messages.append(f"{before_stage}/{before_actor}: {worker_result.message}")
            else:
                messages.append(f"{before_stage}/{before_actor}: Worker executed.")

            if updated_asset.actor != "PYTHON":
                break
            if updated_asset.pipeline_stage == "ERROR":
                break
            if updated_asset.pipeline_stage == "ADD_REF" and (updated_asset.error_code or "") in MISSING_REFERENCE_ERROR_CODES:
                break
            if updated_asset.pipeline_stage == before_stage:
                break

        return WorkerChainResult(asset=updated_asset, worker_count=worker_count, messages=messages)

    def _worker_name_for_asset(self, character: str, phase: str, asset: Asset) -> str | None:
        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        return pipeline.worker_by_stage.get(asset.pipeline_stage)

    def run_available_workers(self, character: str, phase: str, max_jobs: int = 100) -> list[WorkerPollResult]:
        results: list[WorkerPollResult] = []
        processed_stage_keys: set[tuple[int, str]] = set()

        while len(results) < max_jobs:
            progressed = False
            for asset in self.asset_repository.list_assets(character, phase):
                if asset.actor != "PYTHON":
                    continue
                stage_key = (asset.asset_id, asset.pipeline_stage)
                if stage_key in processed_stage_keys:
                    continue
                worker_name = self._worker_name_for_asset(character, phase, asset)
                if not worker_name:
                    continue

                processed_stage_keys.add(stage_key)
                before_stage = asset.pipeline_stage
                before_actor = asset.actor
                try:
                    updated_asset = self.run_current_worker(character, phase, asset.asset_id)
                    if updated_asset.pipeline_stage == "ADD_REF":
                        status = "WAITING"
                    else:
                        status = "SUCCESS" if updated_asset.pipeline_stage != "ERROR" else "ERROR"
                    worker_result = self.worker_service.last_worker_result
                    message = worker_result.message if worker_result is not None else "Worker executed."
                except Exception as exc:
                    updated_asset = self.asset_repository.get_asset(character, phase, asset.asset_id)
                    status = "ERROR"
                    message = str(exc)

                results.append(
                    WorkerPollResult(
                        asset_id=asset.asset_id,
                        worker_name=worker_name,
                        before_stage=before_stage,
                        before_actor=before_actor,
                        after_stage=updated_asset.pipeline_stage,
                        after_actor=updated_asset.actor,
                        status=status,
                        message=message,
                    )
                )
                progressed = True
                if len(results) >= max_jobs:
                    break

            if not progressed:
                break

        return results

    def harvest_ai_answers(self):
        return self.ai_answer_harvester.harvest_once()
