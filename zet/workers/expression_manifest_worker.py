import json
from pathlib import Path

from zet.models.worker import WorkerResult


def _identity_payload(context) -> dict:
    """Load the character phase IdentityKeys.json payload."""
    identity_path = context.character_path / "IdentityKeys.json"
    if not identity_path.exists():
        raise ValueError(f"IdentityKeys.json not found: {identity_path}")
    payload = json.loads(identity_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("identity_keys"), list):
        raise ValueError(f"IdentityKeys.json is malformed: {identity_path}")
    return payload


def _identity_key_record(payload: dict, identity_key_id: str) -> dict | None:
    """Return one identity key record from a loaded payload."""
    for record in payload.get("identity_keys", []):
        if isinstance(record, dict) and record.get("identity_key_id") == identity_key_id:
            return record
    return None


def _assets_payload(context) -> tuple[Path, dict]:
    """Load the character phase Assets.json payload."""
    assets_path = context.character_path / "Assets.json"
    if not assets_path.exists():
        raise ValueError(f"Assets.json not found: {assets_path}")
    payload = json.loads(assets_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("assets"), list):
        raise ValueError(f"Assets.json is malformed: {assets_path}")
    return assets_path, payload


def _resolve_reference_path(path_text: str) -> Path:
    """Resolve a stored project-relative or absolute reference path."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def run(asset, context) -> WorkerResult:
    """Resolve the Identity Key image reference for an Expression asset."""
    if asset.pipeline != "Expression":
        return WorkerResult(
            success=False,
            message=f"Expression manifest worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Expression, got {asset.pipeline}.",
        )
    if not asset.identity_key_id:
        return WorkerResult(
            success=False,
            message=f"Asset {asset.asset_id} has no identity_key_id.",
            advance_stage=False,
            error_code="MISSING_IDENTITY_KEY_ID",
            error_message="Expression assets require identity_key_id.",
        )
    if not asset.expression_definition_path or not Path(asset.expression_definition_path).exists():
        return WorkerResult(
            success=False,
            message=f"Expression definition not found for Asset {asset.asset_id}.",
            advance_stage=False,
            error_code="MISSING_EXPRESSION_DEFINITION",
            error_message=f"Expression definition not found: {asset.expression_definition_path}",
        )

    identity_payload = _identity_payload(context)
    identity_key = _identity_key_record(identity_payload, asset.identity_key_id)
    if identity_key is None:
        return WorkerResult(
            success=False,
            message=f"Identity Key {asset.identity_key_id} not found.",
            advance_stage=False,
            error_code="IDENTITY_KEY_NOT_FOUND",
            error_message=f"Identity Key {asset.identity_key_id} not found.",
        )

    image_path = _resolve_reference_path(str(identity_key.get("image_path") or ""))
    if not image_path.exists() or not image_path.is_file():
        return WorkerResult(
            success=False,
            message=f"Identity Key image not found: {image_path}",
            advance_stage=False,
            error_code="IDENTITY_KEY_IMAGE_NOT_FOUND",
            error_message=f"Identity Key image not found: {image_path}",
        )

    references = [
        {
            "role": "identity_key",
            "label": identity_key.get("label") or asset.identity_key_id,
            "path": str(image_path),
            "identity_key_id": identity_key.get("identity_key_id"),
            "source_asset_id": identity_key.get("source_asset_id"),
            "body_view": identity_key.get("source_body_view"),
            "head_view": identity_key.get("source_head_view"),
            "costume": identity_key.get("source_costume"),
        }
    ]

    assets_path, assets_payload = _assets_payload(context)
    for record in assets_payload.get("assets", []):
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
    assets_path.write_text(json.dumps(assets_payload, indent=2) + "\n", encoding="utf-8")
    return WorkerResult(
        success=True,
        message=f"Resolved Identity Key reference for Asset {asset.asset_id}.",
        output_files=[str(image_path)],
        advance_stage=True,
    )
