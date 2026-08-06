from __future__ import annotations

import json
from pathlib import Path

from zet.models.worker import WorkerResult


def _assets_payload(context) -> tuple[Path, dict]:
    assets_path = context.character_path / "Assets.json"
    if not assets_path.exists():
        raise ValueError(f"Assets.json not found: {assets_path}")
    return assets_path, json.loads(assets_path.read_text(encoding="utf-8"))


def _valid_reference(reference: dict | None) -> bool:
    if not isinstance(reference, dict):
        return False
    raw_path = str(reference.get("path") or "").strip()
    return bool(raw_path) and Path(raw_path).exists() and Path(raw_path).is_file()


def _reference_by_role(asset, role: str) -> dict | None:
    for reference in asset.reference_files or []:
        if isinstance(reference, dict) and reference.get("role") == role:
            return reference
    return None


def _locked_body_reference(context, payload: dict, body_view: str) -> tuple[dict | None, Path | None]:
    for record in payload.get("assets", []):
        if record.get("pipeline") != "Body-Reference":
            continue
        if record.get("asset_state") != "LOCKED" or record.get("pipeline_stage") != "LOCKED":
            continue
        if record.get("body_view") != body_view:
            continue
        final_image_output = str(record.get("final_image_output") or "").strip()
        if not final_image_output:
            continue
        path = context.character_asset_path / final_image_output
        if path.exists() and path.is_file():
            return record, path
    return None, None


def _locked_head_image(context, payload: dict, head_view: str) -> tuple[dict | None, Path | None]:
    for record in payload.get("assets", []):
        if record.get("pipeline") != "Head-Image":
            continue
        if record.get("asset_state") != "LOCKED" or record.get("pipeline_stage") != "LOCKED":
            continue
        if (record.get("head_view") or record.get("body_view")) != head_view:
            continue
        final_image_output = str(record.get("final_image_output") or "").strip()
        if not final_image_output:
            continue
        path = context.character_asset_path / final_image_output
        if path.is_file():
            return record, path
    return None, None


def _save_references(assets_path: Path, payload: dict, asset_id: int, references: list[dict]) -> bool:
    for record in payload.get("assets", []):
        if record.get("asset_id") == asset_id:
            record["reference_files"] = references
            assets_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return True
    return False


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Head-Fitment":
        return WorkerResult(
            success=False,
            message=f"Head-fitment manifest worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Head-Fitment, got {asset.pipeline}.",
        )

    assets_path, payload = _assets_payload(context)
    existing_body_reference = _reference_by_role(asset, "body_reference")
    existing_head_image = _reference_by_role(asset, "head_image") or _reference_by_role(asset, "headshot")

    body_record = None
    if _valid_reference(existing_body_reference):
        body_reference = dict(existing_body_reference)
    else:
        body_record, body_path = _locked_body_reference(context, payload, asset.body_view)
        if body_record is None or body_path is None:
            return WorkerResult(
                success=False,
                message=f"No locked body-reference image found for body view {asset.body_view}.",
                advance_stage=False,
                error_code="MISSING_BODY_REFERENCE",
                error_message=f"No locked Body-Reference asset found for body view {asset.body_view}.",
            )
        body_reference = {
            "role": "body_reference",
            "label": "Locked body-reference image",
            "path": str(body_path),
            "source_asset_id": body_record.get("asset_id"),
            "body_view": body_record.get("body_view"),
        }

    if _valid_reference(existing_head_image):
        head_image_reference = dict(existing_head_image)
    else:
        head_view = asset.head_view or asset.body_view
        head_record, head_image_path = _locked_head_image(context, payload, head_view)
        if head_record is None or head_image_path is None:
            _save_references(assets_path, payload, asset.asset_id, [body_reference])
            return WorkerResult(
                success=False,
                message=f"No locked Head-Image found for head view {head_view}.",
                advance_stage=False,
                error_code="MISSING_HEADSHOT_REFERENCE",
                error_message=(
                    f"No locked Head-Image found for head view {head_view}. "
                    "Lock a matching Head-Image or explicitly select a legacy headshot override."
                ),
            )
        head_image_reference = {
            "role": "head_image",
            "label": "Locked Head-Image",
            "path": str(head_image_path),
            "source_asset_id": head_record.get("asset_id"),
            "head_view": head_record.get("head_view") or head_record.get("body_view"),
        }

    references = [body_reference, head_image_reference]
    if not _save_references(assets_path, payload, asset.asset_id, references):
        return WorkerResult(
            success=False,
            message=f"Asset {asset.asset_id} not found in Assets.json.",
            advance_stage=False,
            error_code="ASSET_NOT_FOUND",
            error_message=f"Asset {asset.asset_id} not found in {assets_path}.",
        )

    return WorkerResult(
        success=True,
        message=f"Resolved head-fitment references for Asset {asset.asset_id}.",
        output_files=[str(Path(item["path"])) for item in references],
        advance_stage=True,
    )
