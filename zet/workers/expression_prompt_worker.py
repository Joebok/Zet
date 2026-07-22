from pathlib import Path

from zet.models.worker import WorkerResult
from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Expression_Jobs import PROJECT_ROOT, compile_expression_job


def _identity_key_label(asset) -> str:
    """Return the display label for the resolved Identity Key reference."""
    for reference in asset.reference_files or []:
        if reference.get("role") == "identity_key":
            return str(reference.get("label") or asset.identity_key_id or "Identity Key")
    return str(asset.identity_key_id or "Identity Key")


def run(asset, context) -> WorkerResult:
    """Compile an Expression prompt for the current asset."""
    if asset.pipeline != "Expression":
        return WorkerResult(
            success=False,
            message=f"Expression prompt worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Expression, got {asset.pipeline}.",
        )

    job = {
        "Job": f"Asset_{asset.asset_id}_{asset.pipeline}_{asset.expression or 'Expression'}",
        "Task": "expression",
        "Character": asset.character,
        "Phase": asset.phase,
        "Expression Label": asset.expression or "Expression",
        "Identity Key Label": _identity_key_label(asset),
        "Expected Output": asset.final_image_output or "",
        "Output Directory": str(context.pipeline_path),
        "Template Path": str(context.character_path / "Character_Image_Template.md"),
        "Expression Definition Path": asset.expression_definition_path or "",
        "Reference Files": asset.reference_files or [],
    }

    try:
        result = compile_expression_job(job, PROJECT_ROOT)
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
            message=f"Expression prompt compile failed: {exc}",
            advance_stage=False,
            error_code="EXPRESSION_PROMPT_COMPILE_FAILED",
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
        message=f"Compiled expression prompt for Asset {asset.asset_id}.",
        output_files=output_files,
        advance_stage=True,
        reference_files=result.get("reference_files"),
    )
