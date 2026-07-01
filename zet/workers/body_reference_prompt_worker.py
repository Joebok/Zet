from pathlib import Path
import sys

from zet.models.worker import WorkerResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_PATH = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from Compile_Character_Template import TemplateCompileError
from Run_Body_Reference_Jobs import compile_body_reference_job


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Body-Reference":
        return WorkerResult(
            success=False,
            message=f"Body-reference prompt worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Body-Reference, got {asset.pipeline}.",
        )

    job = {
        "Job": f"Asset_{asset.asset_id}_{asset.pipeline}_{asset.body_view}",
        "Task": "body-reference",
        "Character": asset.character,
        "Phase": asset.phase,
        "Body View": asset.body_view,
        "Expected Output": asset.final_image_output or "",
    }

    try:
        result = compile_body_reference_job(job, PROJECT_ROOT)
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
            message=f"Body-reference prompt compile failed: {exc}",
            advance_stage=False,
            error_code="BODY_REFERENCE_PROMPT_COMPILE_FAILED",
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
        message=f"Compiled body-reference prompt for Asset {asset.asset_id}.",
        output_files=output_files,
        advance_stage=True,
    )
