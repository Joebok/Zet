from pathlib import Path

from zet.models.worker import WorkerResult
from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Costume_Dressing_Jobs import PROJECT_ROOT, compile_costume_dressing_job


def run(asset, context) -> WorkerResult:
    """Compile a Costume-Dressing prompt for the current asset."""
    if asset.pipeline != "Costume-Dressing":
        return WorkerResult(
            success=False,
            message=f"Costume-dressing prompt worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Costume-Dressing, got {asset.pipeline}.",
        )

    costume_name = asset.costume or "Canonical Adventure Gear"
    costume_path = asset.costume_path or str(context.character_path / f"Costume_{costume_name.replace(' ', '_')}.md")
    job = {
        "Job": f"Asset_{asset.asset_id}_{asset.pipeline}_{asset.body_view}_{asset.head_view or '_'}_{costume_name}",
        "Task": "costume-dressing",
        "Character": asset.character,
        "Phase": asset.phase,
        "Body View": asset.body_view,
        "Head View": asset.head_view or asset.body_view,
        "Costume": costume_name,
        "Expected Output": asset.final_image_output or "",
        "Output Directory": str(context.pipeline_path),
        "Template Path": str(context.character_path / "Character.md"),
        "Costume Path": costume_path,
        "Reference Files": asset.reference_files or [],
    }

    try:
        result = compile_costume_dressing_job(job, PROJECT_ROOT)
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
            message=f"Costume-dressing prompt compile failed: {exc}",
            advance_stage=False,
            error_code="COSTUME_DRESSING_PROMPT_COMPILE_FAILED",
            error_message=str(exc),
        )

    output_paths = [
        result.get("final_prompt"),
        result.get("compiled_sections"),
        result.get("dependency_manifest"),
        result.get("prompt_review"),
        result.get("image_review"),
    ]
    output_files = [str(Path(path)) for path in output_paths if path]

    return WorkerResult(
        success=True,
        message=f"Compiled costume-dressing prompt for Asset {asset.asset_id}.",
        output_files=output_files,
        advance_stage=True,
        reference_files=result.get("reference_files"),
    )
