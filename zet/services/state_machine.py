from zet.models.pipeline import PipelineDefinition


class StateMachineError(Exception):
    pass


class StateMachine:
    def next_stage(self, pipeline: PipelineDefinition, current_stage: str) -> str:
        if current_stage not in pipeline.stages:
            raise StateMachineError(
                f"Current stage {current_stage} is not valid for pipeline {pipeline.name}"
            )
        current_index = pipeline.stages.index(current_stage)
        if current_index == len(pipeline.stages) - 1:
            raise StateMachineError(f"Asset is already at final pipeline stage: {current_stage}")
        return pipeline.stages[current_index + 1]
