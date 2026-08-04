from pathlib import Path

from zet.models.worker import WorkerResult
from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Head_Fitment_Jobs import PROJECT_ROOT, compile_head_fitment_job


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Head-Fitment":
        return WorkerResult(
            success=False,
            message=f"Head-fitment prompt worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Head-Fitment, got {asset.pipeline}.",
        )

    job = {
        "Job": f"Asset_{asset.asset_id}_{asset.pipeline}_{asset.body_view}_{asset.head_view or '_'}",
        "Task": "head-fitment",
        "Character": asset.character,
        "Phase": asset.phase,
        "Body View": asset.body_view,
        "Head View": asset.head_view or asset.body_view,
        "Expected Output": asset.final_image_output or "",
        "Output Directory": str(context.pipeline_path),
        "Template Path": str(context.character_path / "Character_Image_Template.md"),
        "Reference Files": asset.reference_files or [],
    }

    try:
        result = compile_head_fitment_job(job, PROJECT_ROOT)
    except TemplateCompileError as exc:
        return WorkerResult(
            success=False,
            message=str(exc),
            advance_stage=False,
            error_code=exc.code,
            error_message=str(exc),
        )
    except Exception as exc:
        return WorkerResult(
            success=False,
            message=f"Head-fitment prompt compile failed: {exc}",
            advance_stage=False,
            error_code="HEAD_FITMENT_PROMPT_COMPILE_FAILED",
            error_message=str(exc),
        )

    output_paths = [
        result.get("final_prompt"),
        result.get("compiled_sections"),
        result.get("dependency_manifest"),
        result.get("image_review"),
    ]
    output_files = [str(Path(path)) for path in output_paths if path]

    return WorkerResult(
        success=True,
        message=f"Compiled head-fitment prompt for Asset {asset.asset_id}.",
        output_files=output_files,
        advance_stage=True,
        reference_files=result.get("reference_files"),
    )
