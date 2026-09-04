from pathlib import Path

from Scripts.Run_Scene_Appearance_Jobs import PROJECT_ROOT, compile_scene_appearance_job
from zet.models.worker import WorkerResult


def run(asset, context) -> WorkerResult:
    """Compile the short static prompt for one Scene Appearance asset."""
    if asset.pipeline != "Scene-Appearance":
        return WorkerResult(
            success=False,
            message=f"Scene-Appearance prompt worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Scene-Appearance, got {asset.pipeline}.",
        )
    job = {
        "Job": f"Asset_{asset.asset_id}_{asset.pipeline}_{asset.body_view}_{asset.scene_appearance_id}",
        "Task": "scene-appearance",
        "Character": asset.character,
        "Phase": asset.phase,
        "Body View": asset.body_view,
        "Head View": asset.head_view or asset.body_view,
        "Costume": asset.costume or "",
        "Scene Appearance ID": asset.scene_appearance_id or "",
        "Definition Path": asset.scene_appearance_definition_path or "",
        "Expected Output": asset.final_image_output or "",
        "Output Directory": str(context.pipeline_path),
        "Reference Files": asset.reference_files or [],
    }
    try:
        result = compile_scene_appearance_job(job, PROJECT_ROOT)
    except Exception as exc:
        return WorkerResult(
            success=False,
            message=f"Scene-Appearance prompt compile failed: {exc}",
            advance_stage=False,
            error_code=getattr(exc, "code", "SCENE_APPEARANCE_PROMPT_COMPILE_FAILED"),
            error_message=str(exc),
        )
    output_files = [
        str(Path(path))
        for key in ("final_prompt", "compiled_sections", "source_map", "dependency_manifest", "prompt_review", "image_review")
        if (path := result.get(key))
    ]
    return WorkerResult(
        success=True,
        message=f"Compiled Scene Appearance prompt for Asset {asset.asset_id}.",
        output_files=output_files,
        reference_files=result.get("reference_files"),
        advance_stage=True,
    )
