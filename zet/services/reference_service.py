from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.services.path_service import PathService


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ReferenceServiceError(Exception):
    pass


class ReferenceService:
    def __init__(self, asset_repository: AssetRepository, path_service: PathService):
        self.asset_repository = asset_repository
        self.path_service = path_service

    def headshot_reference_dir(self, character: str, phase: str) -> Path:
        return self.path_service.character_path(character, phase) / "Reference_Images" / "Headshots"

    def _selected_reference(self, asset: Asset, role: str) -> dict[str, Any] | None:
        for reference in asset.reference_files or []:
            if isinstance(reference, dict) and reference.get("role") == role:
                return reference
        return None

    def _body_reference_options(self, character: str, phase: str, selected_path: str = "") -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        for asset in self.asset_repository.list_assets(character, phase):
            if asset.pipeline != "Body-Reference" or asset.asset_state != "LOCKED":
                continue
            if not asset.final_image_output:
                continue
            path = self.path_service.locked_image_path(asset)
            options.append(
                {
                    "asset_id": asset.asset_id,
                    "body_view": asset.body_view,
                    "label": f"Asset {asset.asset_id} | {asset.body_view} | {asset.final_image_output}",
                    "path": str(path),
                    "exists": path.exists(),
                    "selected": str(path) == selected_path,
                }
            )
        return options

    def _headshot_options(self, character: str, phase: str, selected_path: str = "") -> list[dict[str, Any]]:
        root = self.headshot_reference_dir(character, phase)
        if not root.exists():
            return []
        options = []
        for path in sorted(item for item in root.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS):
            options.append(
                {
                    "name": path.name,
                    "label": path.name,
                    "path": str(path),
                    "exists": path.exists(),
                    "selected": str(path) == selected_path,
                }
            )
        return options

    def head_fitment_context(self, character: str, phase: str, asset_id: int) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Head-Fitment":
            raise ReferenceServiceError("Reference picker is only available for Head-Fitment assets.")

        body_ref = self._selected_reference(asset, "body_reference") or {}
        headshot = self._selected_reference(asset, "headshot") or {}
        return {
            "asset": asset,
            "is_manifest_editable": asset.pipeline_stage in {"MANIFEST", "ADD_REF"} and asset.actor == "PYTHON",
            "body_reference_options": self._body_reference_options(character, phase, str(body_ref.get("path") or "")),
            "headshot_options": self._headshot_options(character, phase, str(headshot.get("path") or "")),
            "selected_body_reference": body_ref,
            "selected_headshot": headshot,
            "reference_files": asset.reference_files or [],
        }

    def save_head_fitment_references(
        self,
        character: str,
        phase: str,
        asset_id: int,
        body_reference_path: str,
        headshot_path: str,
    ) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Head-Fitment":
            raise ReferenceServiceError("Reference picker is only available for Head-Fitment assets.")
        if asset.pipeline_stage not in {"MANIFEST", "ADD_REF"} or asset.actor != "PYTHON":
            raise ReferenceServiceError("Head-fitment references can only be edited at MANIFEST or ADD_REF / PYTHON.")

        body_path = self.path_service.resolve_path(body_reference_path)
        head_path = self.path_service.resolve_path(headshot_path)
        if not body_path.exists() or not body_path.is_file():
            raise ReferenceServiceError(f"Body reference image not found: {body_reference_path}")
        if not head_path.exists() or not head_path.is_file():
            raise ReferenceServiceError(f"Headshot image not found: {headshot_path}")

        body_source_asset_id = None
        body_view = None
        for option in self._body_reference_options(character, phase):
            if option["path"] == str(body_path):
                body_source_asset_id = option["asset_id"]
                body_view = option["body_view"]
                break

        updated_asset = replace(
            asset,
            reference_files=[
                {
                    "role": "body_reference",
                    "label": "Locked body-reference image",
                    "path": str(body_path),
                    "source_asset_id": body_source_asset_id,
                    "body_view": body_view,
                },
                {
                    "role": "headshot",
                    "label": "Headshot reference image",
                    "path": str(head_path),
                },
            ],
        )
        self.asset_repository.save_asset(updated_asset)
        return updated_asset

    def upload_headshot(self, character: str, phase: str, filename: str, contents: bytes) -> Path:
        if not contents:
            raise ReferenceServiceError("No image data was provided.")
        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise ReferenceServiceError("Headshot must be a PNG, JPG, JPEG, or WEBP image.")
        safe_name = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in Path(filename).name)
        if not safe_name:
            raise ReferenceServiceError("Headshot filename is blank.")
        target_dir = self.headshot_reference_dir(character, phase)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_name
        if target_path.exists():
            stem = target_path.stem
            counter = 2
            while target_path.exists():
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1
        temp_path = target_path.with_name(f"{target_path.name}.tmp")
        temp_path.write_bytes(contents)
        try:
            shutil.move(str(temp_path), str(target_path))
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return target_path
