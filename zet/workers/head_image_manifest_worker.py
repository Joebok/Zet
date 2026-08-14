from pathlib import Path

from zet.models.worker import WorkerResult


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Head-Image":
        return WorkerResult(False, f"Expected Head-Image, got {asset.pipeline}.", advance_stage=False, error_code="WRONG_PIPELINE")
    references = [item for item in asset.reference_files or [] if isinstance(item, dict) and item.get("role") == "head_image_source"]
    if len(references) != 1:
        return WorkerResult(False, "Head-Image requires exactly one source image.", advance_stage=False, error_code="MISSING_REFERENCE" if not references else "INVALID_REFERENCE")
    path = Path(str(references[0].get("path") or ""))
    if not path.is_file():
        return WorkerResult(False, f"Head-Image source not found: {path}", advance_stage=False, error_code="MISSING_REFERENCE")
    return WorkerResult(True, f"Resolved required Head-Image source for Asset {asset.asset_id}.", advance_stage=True, reference_files=references)
