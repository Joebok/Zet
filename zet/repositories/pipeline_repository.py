import json
from pathlib import Path

from zet.models.pipeline import PipelineDefinition
from zet.services.path_service import PathService


class PipelineRepositoryError(Exception):
    pass


class PipelineRepository:
    def __init__(self, path_service: PathService):
        self.path_service = path_service

    def _pipelines_json_path(self, character: str, phase: str) -> Path:
        return self.path_service.character_path(character, phase) / "Pipelines.json"

    def _load_payload(self, character: str, phase: str) -> dict:
        path = self._pipelines_json_path(character, phase)
        if not path.exists():
            raise PipelineRepositoryError(f"Pipelines.json not found at {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise PipelineRepositoryError(f"Pipelines.json is malformed at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise PipelineRepositoryError(f"Pipelines.json must contain a JSON object at {path}")
        return payload

    def _pipeline_from_dict(self, name: str, record: dict) -> PipelineDefinition:
        if not isinstance(record, dict):
            raise PipelineRepositoryError(f"Pipeline definition for {name} must be an object")
        required_keys = {"stages", "actor_by_stage", "worker_by_stage"}
        missing = sorted(required_keys - set(record))
        if missing:
            raise PipelineRepositoryError(
                f"Pipeline definition for {name} is missing required keys: {', '.join(missing)}"
            )
        stages = record["stages"]
        actor_by_stage = record["actor_by_stage"]
        worker_by_stage = record["worker_by_stage"]
        if not isinstance(stages, list) or not stages:
            raise PipelineRepositoryError(f"Pipeline {name} must define a non-empty stages list")
        if not isinstance(actor_by_stage, dict):
            raise PipelineRepositoryError(f"Pipeline {name} must define actor_by_stage as an object")
        if not isinstance(worker_by_stage, dict):
            raise PipelineRepositoryError(f"Pipeline {name} must define worker_by_stage as an object")
        if "PROMPT_REVIEW" in stages or "PROMPT_REVIEW" in actor_by_stage or "PROMPT_REVIEW" in worker_by_stage:
            raise PipelineRepositoryError(f"Pipeline {name} uses unsupported stage PROMPT_REVIEW")
        for stage in stages:
            if stage not in actor_by_stage:
                raise PipelineRepositoryError(f"Pipeline {name} has no actor assignment for stage {stage}")
        return PipelineDefinition(
            name=name,
            stages=stages,
            actor_by_stage=actor_by_stage,
            worker_by_stage=worker_by_stage,
        )

    def list_pipelines(self, character: str, phase: str) -> list[PipelineDefinition]:
        payload = self._load_payload(character, phase)
        pipelines = payload.get("pipelines")
        if not isinstance(pipelines, dict):
            raise PipelineRepositoryError("Pipelines.json must contain a 'pipelines' object")
        return [self._pipeline_from_dict(name, record) for name, record in pipelines.items()]

    def get_pipeline(self, character: str, phase: str, pipeline_name: str) -> PipelineDefinition:
        payload = self._load_payload(character, phase)
        pipelines = payload.get("pipelines")
        if not isinstance(pipelines, dict):
            raise PipelineRepositoryError("Pipelines.json must contain a 'pipelines' object")
        if pipeline_name not in pipelines:
            raise PipelineRepositoryError(f"Pipeline {pipeline_name} not found for {character}/{phase}")
        return self._pipeline_from_dict(pipeline_name, pipelines[pipeline_name])
