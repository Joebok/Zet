from zet.models.worker import WorkerResult
from zet.workers.character_assembly_manifest_worker import _assets_payload, _matching_asset


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Costume-Dressing":
        return WorkerResult(
            success=False,
            message=f"Costume-dressing manifest worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Costume-Dressing, got {asset.pipeline}.",
        )

    assets_path, payload = _assets_payload(context)
    head_view = asset.head_view or asset.body_view
    assembled_record, assembled_path = _matching_asset(
        context,
        payload,
        pipeline="Character-Assembly",
        body_view=asset.body_view,
        head_view=head_view,
    )
    if assembled_record is None or assembled_path is None:
        return WorkerResult(
            success=False,
            message=f"No locked character-assembly image found for {asset.body_view} / {head_view}.",
            advance_stage=False,
            error_code="MISSING_CHARACTER_ASSEMBLY",
            error_message=f"No locked Character-Assembly asset found for body view {asset.body_view} and head view {head_view}.",
        )

    references = [
        {
            "role": "character_assembly",
            "label": "Locked assembled character image",
            "path": str(assembled_path),
            "source_asset_id": assembled_record.get("asset_id"),
            "body_view": assembled_record.get("body_view"),
            "head_view": assembled_record.get("head_view"),
        }
    ]

    import json

    for record in payload.get("assets", []):
        if record.get("asset_id") == asset.asset_id:
            record["reference_files"] = references
            break
    else:
        return WorkerResult(
            success=False,
            message=f"Asset {asset.asset_id} not found in Assets.json.",
            advance_stage=False,
            error_code="ASSET_NOT_FOUND",
            error_message=f"Asset {asset.asset_id} not found in {assets_path}.",
        )
    assets_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return WorkerResult(
        success=True,
        message=f"Resolved costume-dressing reference for Asset {asset.asset_id}.",
        output_files=[str(assembled_path)],
        advance_stage=True,
    )
