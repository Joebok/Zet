from pathlib import Path

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Head_Image_Jobs import PROJECT_ROOT, compile_head_image_job
from zet.models.worker import WorkerResult


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Head-Image":
        return WorkerResult(False, f"Expected Head-Image, got {asset.pipeline}.", advance_stage=False, error_code="WRONG_PIPELINE")
    job = {
        "Job": f"Asset_{asset.asset_id}_{asset.pipeline}_{asset.head_view or asset.body_view}",
        "Task": "head-image",
        "Character": asset.character,
        "Phase": asset.phase,
        "Head View": asset.head_view or asset.body_view,
        "Expected Output": asset.final_image_output or "",
        "Output Directory": str(context.pipeline_path),
        "Template Path": str(context.character_path / "Character.md"),
        "Reference Files": asset.reference_files or [],
    }
    try:
        result = compile_head_image_job(job, PROJECT_ROOT)
    except TemplateCompileError as exc:
        return WorkerResult(False, str(exc), advance_stage=False, error_code=exc.code, error_message=str(exc))
    except Exception as exc:
        return WorkerResult(False, f"Head-Image prompt compile failed: {exc}", advance_stage=False, error_code="HEAD_IMAGE_PROMPT_COMPILE_FAILED", error_message=str(exc))
    output_files = [str(Path(result[key])) for key in ("final_prompt", "compiled_sections", "dependency_manifest", "image_review") if result.get(key)]
    return WorkerResult(True, f"Compiled Head-Image prompt for Asset {asset.asset_id}.", output_files=output_files, advance_stage=True, reference_files=result.get("reference_files"))
