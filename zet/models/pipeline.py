from dataclasses import dataclass


@dataclass
class PipelineDefinition:
    name: str
    stages: list[str]
    actor_by_stage: dict[str, str]
    worker_by_stage: dict[str, str]
