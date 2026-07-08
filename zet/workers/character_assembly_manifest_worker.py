from zet.models.worker import WorkerResult


def _assets_payload(context) -> tuple[object, dict]:
    assets_path = context.character_path / "Assets.json"
    if not assets_path.exists():
        raise ValueError(f"Assets.json not found: {assets_path}")

    import json

    return assets_path, json.loads(assets_path.read_text(encoding="utf-8"))


def _matching_asset(context, payload: dict, *, pipeline: str, body_view: str, head_view: str | None = None):
    for record in payload.get("assets", []):
        if record.get("pipeline") != pipeline:
            continue
        if record.get("asset_state") != "LOCKED" or record.get("pipeline_stage") != "LOCKED":
            continue
        if record.get("body_view") != body_view:
            continue
        if head_view is not None and record.get("head_view") != head_view:
            continue
        final_image_output = str(record.get("final_image_output") or "").strip()
        if not final_image_output:
            continue
        path = context.character_asset_path / final_image_output
        if not path.exists() or not path.is_file():
            continue
        return record, path
    return None, None


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Character-Assembly":
        return WorkerResult(
            success=False,
            message=f"Character-assembly manifest worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Character-Assembly, got {asset.pipeline}.",
        )

    assets_path, payload = _assets_payload(context)
    body_record, body_path = _matching_asset(
        context,
        payload,
        pipeline="Body-Reference",
        body_view=asset.body_view,
    )
    if body_record is None or body_path is None:
        return WorkerResult(
            success=False,
            message=f"No locked body-reference image found for body view {asset.body_view}.",
            advance_stage=False,
            error_code="MISSING_BODY_REFERENCE",
            error_message=f"No locked Body-Reference asset found for body view {asset.body_view}.",
        )

    head_view = asset.head_view or asset.body_view
    head_record, head_path = _matching_asset(
        context,
        payload,
        pipeline="Head-Fitment",
        body_view=asset.body_view,
        head_view=head_view,
    )
    if head_record is None or head_path is None:
        return WorkerResult(
            success=False,
            message=f"No locked head-fitment image found for {asset.body_view} / {head_view}.",
            advance_stage=False,
            error_code="MISSING_HEAD_FITMENT",
            error_message=f"No locked Head-Fitment asset found for body view {asset.body_view} and head view {head_view}.",
        )

    references = [
        {
            "role": "body_reference",
            "label": "Locked body-reference image",
            "path": str(body_path),
            "source_asset_id": body_record.get("asset_id"),
            "body_view": body_record.get("body_view"),
        },
        {
            "role": "head_fitment",
            "label": "Locked head-fitment image",
            "path": str(head_path),
            "source_asset_id": head_record.get("asset_id"),
            "body_view": head_record.get("body_view"),
            "head_view": head_record.get("head_view"),
        },
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
        message=f"Resolved character-assembly references for Asset {asset.asset_id}.",
        output_files=[str(body_path), str(head_path)],
        advance_stage=True,
    )
