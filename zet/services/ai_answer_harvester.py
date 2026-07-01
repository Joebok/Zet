import json
import shutil
from dataclasses import replace
from pathlib import Path

from zet.models.ai_proxy import AIProxyAnswer, HarvestResult
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.housekeeping_service import HousekeepingService
from zet.services.path_service import PathService
from zet.services.state_machine import StateMachine


class AIAnswerHarvesterError(Exception):
    pass


class AIAnswerHarvester:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        ai_proxy_path_service: AIProxyPathService,
        path_service: PathService,
        housekeeping_service: HousekeepingService,
        state_machine: StateMachine,
        timestamp_provider,
        ai_proxy_service=None,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.ai_proxy_path_service = ai_proxy_path_service
        self.path_service = path_service
        self.housekeeping_service = housekeeping_service
        self.state_machine = state_machine
        self.timestamp_provider = timestamp_provider
        self.ai_proxy_service = ai_proxy_service

    def _harvest_manifest_path(self, answer_path: Path) -> Path:
        return answer_path / "harvest_manifest.json"

    def _read_json(self, path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AIAnswerHarvesterError(f"Invalid JSON file at {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise AIAnswerHarvesterError(f"JSON file must contain an object: {path}")
        return data

    def _load_answer(self, answer_path: Path) -> AIProxyAnswer:
        manifest_path = answer_path / "answer_manifest.json"
        if not manifest_path.exists():
            raise AIAnswerHarvesterError(f"Missing answer_manifest.json in {answer_path}")
        data = self._read_json(manifest_path)
        try:
            return AIProxyAnswer(
                ask_id=str(data["ask_id"]),
                asset_id=int(data["asset_id"]),
                ollama_attempt_id=str(data["ollama_attempt_id"]),
                worker_id=str(data["worker_id"]),
                status=str(data["status"]),
                expected_output=str(data["expected_output"]),
                error_type=str(data.get("error_type") or "") or None,
                error_message=str(data.get("error_message") or "") or None,
            )
        except Exception as exc:
            raise AIAnswerHarvesterError(f"Invalid answer manifest at {manifest_path}: {exc}") from exc

    def _load_ask_manifest(self, answer_path: Path) -> dict:
        manifest_path = answer_path / "ask_manifest.json"
        if not manifest_path.exists():
            raise AIAnswerHarvesterError(f"Missing ask_manifest.json in {answer_path}")
        return self._read_json(manifest_path)

    def _expected_attempt(self, asset) -> str | None:
        last_ai_update = asset.last_ai_update or ""
        if "(" in last_ai_update and last_ai_update.endswith(")"):
            return last_ai_update.rsplit("(", 1)[1][:-1]
        return None

    def _write_harvest_manifest(self, answer_path: Path, result: HarvestResult) -> None:
        payload = {
            "version": 1,
            "ask_id": result.ask_id,
            "asset_id": result.asset_id,
            "status": result.status,
            "message": result.message,
            "harvested_at": self.timestamp_provider(),
        }
        self._harvest_manifest_path(answer_path).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def _apply_successful_answer(self, answer_path: Path, answer: AIProxyAnswer, character: str, phase: str):
        asset = self.asset_repository.get_asset(character, phase, answer.asset_id)
        response_path = answer_path / answer.expected_output
        if not response_path.exists():
            raise AIAnswerHarvesterError(f"Missing expected output file {answer.expected_output} in {answer_path}")

        pipeline_path = self.path_service.pipeline_path(asset)
        pipeline_path.mkdir(parents=True, exist_ok=True)
        dest_response_path = pipeline_path / response_path.name
        shutil.copy2(response_path, dest_response_path)
        for metadata_name in ("LOCAL_RENDER_METADATA.json", "COMFYUI_RENDER_METADATA.json"):
            metadata_path = answer_path / metadata_name
            if metadata_path.exists():
                shutil.copy2(metadata_path, pipeline_path / metadata_path.name)

        updated_asset = replace(asset)
        updated_asset.ai_state = None
        updated_asset.last_ai_update = f"AI answer harvested: {answer.ask_id} ({answer.ollama_attempt_id})"
        updated_asset.updated_at = self.timestamp_provider()
        updated_asset.error_code = None
        updated_asset.error_message = None
        self.asset_repository.save_asset(updated_asset)

        refreshed_asset = self.asset_repository.get_asset(character, phase, answer.asset_id)
        pipeline = self.pipeline_repository.get_pipeline(character, phase, refreshed_asset.pipeline)
        next_stage = self.state_machine.next_stage(pipeline, refreshed_asset.pipeline_stage)
        next_actor = pipeline.actor_by_stage.get(next_stage)
        if next_actor is None:
            raise AIAnswerHarvesterError(
                f"Pipeline {pipeline.name} has no actor configured for stage {next_stage}"
            )
        final_asset = replace(refreshed_asset)
        final_asset.pipeline_stage = next_stage
        final_asset.actor = next_actor
        final_asset.asset_state = "IN_PROGRESS"
        final_asset.ai_state = "ASKED" if next_actor == "AI_AGENT" else None
        final_asset.updated_at = self.timestamp_provider()
        self.asset_repository.save_asset(final_asset)
        self.housekeeping_service.prepare_stage(final_asset)
        return final_asset

    def _apply_auxiliary_answer(self, answer_path: Path, answer: AIProxyAnswer, ask_manifest: dict) -> HarvestResult:
        task_type = str(ask_manifest.get("task_type") or "auxiliary")
        if answer.status != "SUCCESS":
            result = HarvestResult(
                answer_path=answer_path,
                ask_id=answer.ask_id,
                asset_id=answer.asset_id,
                status=f"{task_type.upper()}_{answer.status}",
                message=f"Auxiliary task {task_type} completed with status {answer.status}: {answer.error_message or ''}".strip(),
            )
            self._write_harvest_manifest(answer_path, result)
            return result

        response_path = answer_path / answer.expected_output
        if not response_path.exists():
            raise AIAnswerHarvesterError(f"Missing expected output file {answer.expected_output} in {answer_path}")

        target_output_dir_text = str(ask_manifest.get("target_output_dir") or "").strip()
        if not target_output_dir_text:
            raise AIAnswerHarvesterError(f"Auxiliary answer {answer_path} is missing target_output_dir.")
        target_output_dir = Path(target_output_dir_text)
        target_output_file = str(ask_manifest.get("target_output_file") or answer.expected_output)
        target_output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(response_path, target_output_dir / target_output_file)

        result = HarvestResult(
            answer_path=answer_path,
            ask_id=answer.ask_id,
            asset_id=answer.asset_id,
            status=f"{task_type.upper()}_APPLIED",
            message=f"Applied auxiliary task {task_type} output to {target_output_dir / target_output_file}.",
        )
        self._write_harvest_manifest(answer_path, result)
        if task_type == "prompt_condense" and self.ai_proxy_service is not None:
            character = str(ask_manifest.get("character") or "")
            phase = str(ask_manifest.get("phase") or "")
            try:
                render_ask_path = self.ai_proxy_service.stage_prompt_review_render_ask_if_enabled(
                    character,
                    phase,
                    answer.asset_id,
                )
                if render_ask_path is not None:
                    result = HarvestResult(
                        answer_path=answer_path,
                        ask_id=answer.ask_id,
                        asset_id=answer.asset_id,
                        status=f"{task_type.upper()}_APPLIED",
                        message=(
                            f"Applied auxiliary task {task_type} output to {target_output_dir / target_output_file}. "
                            f"Queued prompt review render ask at {render_ask_path}."
                        ),
                    )
                    self._write_harvest_manifest(answer_path, result)
            except Exception as exc:
                result = HarvestResult(
                    answer_path=answer_path,
                    ask_id=answer.ask_id,
                    asset_id=answer.asset_id,
                    status=f"{task_type.upper()}_APPLIED_RENDER_QUEUE_FAILED",
                    message=(
                        f"Applied auxiliary task {task_type} output to {target_output_dir / target_output_file}, "
                        f"but auto-queue render failed: {exc}"
                    ),
                )
                self._write_harvest_manifest(answer_path, result)
        return result

    def apply_answer_folder(self, answer_path: Path) -> HarvestResult:
        if self._harvest_manifest_path(answer_path).exists():
            payload = self._read_json(self._harvest_manifest_path(answer_path))
            if payload.get("status") == "APPLIED":
                answer = self._load_answer(answer_path)
                ask_manifest = self._load_ask_manifest(answer_path)
                character = str(ask_manifest.get("character") or "")
                phase = str(ask_manifest.get("phase") or "")
                if character and phase and answer.status == "SUCCESS":
                    asset = self.asset_repository.get_asset(character, phase, answer.asset_id)
                    expected_attempt = self._expected_attempt(asset)
                    if (
                        asset.pipeline_stage == str(ask_manifest.get("pipeline_stage") or "")
                        and asset.actor == "AI_AGENT"
                        and expected_attempt == answer.ollama_attempt_id
                    ):
                        final_asset = self._apply_successful_answer(answer_path, answer, character, phase)
                        result = HarvestResult(
                            answer_path=answer_path,
                            ask_id=answer.ask_id,
                            asset_id=answer.asset_id,
                            status="REAPPLIED",
                            message=(
                                f"Re-applied harvested answer and advanced asset {answer.asset_id} "
                                f"to {final_asset.pipeline_stage}."
                            ),
                        )
                        self._write_harvest_manifest(answer_path, result)
                        return result
            return HarvestResult(
                answer_path=answer_path,
                ask_id=str(payload.get("ask_id", answer_path.name)),
                asset_id=int(payload["asset_id"]) if str(payload.get("asset_id", "")).isdigit() else None,
                status=f"ALREADY_{str(payload.get('status', 'SKIPPED'))}",
                message=f"Already harvested. {str(payload.get('message', ''))}".strip(),
            )

        answer = self._load_answer(answer_path)
        ask_manifest = self._load_ask_manifest(answer_path)

        character = str(ask_manifest.get("character") or "")
        phase = str(ask_manifest.get("phase") or "")
        if not character or not phase:
            raise AIAnswerHarvesterError(f"Answer folder {answer_path} is missing character or phase in ask_manifest.json")

        if bool(ask_manifest.get("auxiliary", False)):
            return self._apply_auxiliary_answer(answer_path, answer, ask_manifest)

        asset = self.asset_repository.get_asset(character, phase, answer.asset_id)
        expected_attempt = self._expected_attempt(asset)
        if expected_attempt and answer.ollama_attempt_id != expected_attempt:
            result = HarvestResult(
                answer_path=answer_path,
                ask_id=answer.ask_id,
                asset_id=answer.asset_id,
                status="STALE",
                message=f"Stale answer ignored. Expected attempt {expected_attempt}, got {answer.ollama_attempt_id}.",
            )
            self._write_harvest_manifest(answer_path, result)
            return result

        if answer.status == "SUCCESS":
            final_asset = self._apply_successful_answer(answer_path, answer, character, phase)

            result = HarvestResult(
                answer_path=answer_path,
                ask_id=answer.ask_id,
                asset_id=answer.asset_id,
                status="APPLIED",
                message=f"Applied successful answer and advanced asset {answer.asset_id} to {final_asset.pipeline_stage}.",
            )
            self._write_harvest_manifest(answer_path, result)
            return result

        if answer.status == "RETRY_LATER":
            updated_asset = replace(asset)
            updated_asset.ai_state = "ASKED"
            updated_asset.last_ai_update = (
                f"AI answer retry requested: {answer.ask_id} ({answer.ollama_attempt_id})"
            )
            updated_asset.updated_at = self.timestamp_provider()
            self.asset_repository.save_asset(updated_asset)
            self.housekeeping_service.prepare_stage(updated_asset)
            result = HarvestResult(
                answer_path=answer_path,
                ask_id=answer.ask_id,
                asset_id=answer.asset_id,
                status="RETRY_LATER",
                message=f"Recorded retry-later result for asset {answer.asset_id} without changing stage.",
            )
            self._write_harvest_manifest(answer_path, result)
            return result

        if answer.status == "REJECTED":
            updated_asset = replace(asset)
            updated_asset.ai_state = None
            updated_asset.last_ai_update = (
                f"AI answer rejected: {answer.ask_id} ({answer.ollama_attempt_id})"
            )
            updated_asset.updated_at = self.timestamp_provider()
            self.asset_repository.save_asset(updated_asset)
            self.housekeeping_service.prepare_stage(updated_asset)
            result = HarvestResult(
                answer_path=answer_path,
                ask_id=answer.ask_id,
                asset_id=answer.asset_id,
                status="REJECTED",
                message=f"Recorded rejected answer for asset {answer.asset_id} without changing stage.",
            )
            self._write_harvest_manifest(answer_path, result)
            return result

        if answer.status == "ERROR":
            updated_asset = replace(asset)
            updated_asset.asset_state = "BLOCKED"
            updated_asset.pipeline_stage = "ERROR"
            updated_asset.actor = "HUMAN_AGENT"
            updated_asset.ai_state = None
            updated_asset.error_code = answer.error_type or "AI_PROXY_ERROR"
            updated_asset.error_message = answer.error_message or f"AI proxy answer status {answer.status}"
            updated_asset.updated_at = self.timestamp_provider()
            self.asset_repository.save_asset(updated_asset)
            self.housekeeping_service.prepare_stage(updated_asset)
            result = HarvestResult(
                answer_path=answer_path,
                ask_id=answer.ask_id,
                asset_id=answer.asset_id,
                status="BLOCKED",
                message=f"Applied {answer.status} answer and blocked asset {answer.asset_id}.",
            )
            self._write_harvest_manifest(answer_path, result)
            return result

        raise AIAnswerHarvesterError(f"Unsupported answer status {answer.status} in {answer_path}")

    def harvest_once(self) -> list[HarvestResult]:
        answer_root = self.ai_proxy_path_service.answer_root()
        if not answer_root.exists():
            return []

        results: list[HarvestResult] = []
        for answer_path in sorted(path for path in answer_root.iterdir() if path.is_dir()):
            results.append(self.apply_answer_folder(answer_path))
        return results
