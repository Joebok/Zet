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

    def head_image_source_dir(self, character: str, phase: str) -> Path:
        return self.path_service.character_path(character, phase) / "Reference_Images" / "Head_Image_Sources"

    def _selected_reference(self, asset: Asset, role: str) -> dict[str, Any] | None:
        for reference in asset.reference_files or []:
            if isinstance(reference, dict) and reference.get("role") == role:
                return reference
        return None

    def _body_reference_options(
        self,
        character: str,
        phase: str,
        selected_path: str = "",
        *,
        view: str = "",
    ) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        for asset in self.asset_repository.list_assets(character, phase):
            if asset.pipeline != "Body-Reference" or asset.asset_state != "LOCKED":
                continue
            if view and asset.body_view != view:
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

    def _locked_head_image_options(
        self,
        character: str,
        phase: str,
        selected_path: str = "",
        *,
        view: str = "",
        other_phases: bool = False,
    ) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        character_root = Path(self.path_service.config.base_character_path) / character
        phases = [item.name for item in character_root.iterdir() if item.is_dir()] if character_root.is_dir() else []
        for candidate_phase in sorted(phases):
            if other_phases != (candidate_phase != phase):
                continue
            try:
                assets = self.asset_repository.list_assets(character, candidate_phase)
            except Exception:
                continue
            for asset in assets:
                if asset.pipeline != "Head-Image" or asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
                    continue
                if view and (asset.head_view or asset.body_view) != view:
                    continue
                if not asset.final_image_output:
                    continue
                path = self.path_service.locked_image_path(asset)
                options.append({
                    "asset_id": asset.asset_id,
                    "character": character,
                    "phase": candidate_phase,
                    "head_view": asset.head_view or asset.body_view,
                    "label": f"{candidate_phase} | {asset.head_view or asset.body_view} | {asset.final_image_output}",
                    "path": str(path),
                    "exists": path.is_file(),
                    "selected": str(path) == selected_path,
                })
        return options

    def _uploaded_head_image_source_options(self, character: str, phase: str, selected_path: str = "") -> list[dict[str, Any]]:
        root = self.head_image_source_dir(character, phase)
        if not root.is_dir():
            return []
        return [{
            "name": path.name,
            "label": f"Uploaded | {path.name}",
            "path": str(path),
            "exists": True,
            "selected": str(path) == selected_path,
        } for path in sorted(root.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]

    def head_image_context(self, character: str, phase: str, asset_id: int) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Head-Image":
            raise ReferenceServiceError("Reference picker is only available for Head-Image assets.")
        selected = self._selected_reference(asset, "head_image_source") or {}
        selected_path = str(selected.get("path") or "")
        return {
            "asset": asset,
            "is_manifest_editable": asset.pipeline_stage == "MANIFEST" and asset.actor == "PYTHON",
            "source_options": [
                *self._locked_head_image_options(character, phase, selected_path, other_phases=True),
                *self._uploaded_head_image_source_options(character, phase, selected_path),
            ],
            "selected_source": selected,
            "reference_files": asset.reference_files or [],
        }

    def save_head_image_source(self, character: str, phase: str, asset_id: int, source_path: str) -> Asset:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Head-Image" or asset.pipeline_stage != "MANIFEST" or asset.actor != "PYTHON":
            raise ReferenceServiceError("Head-Image sources can only be edited at MANIFEST / PYTHON.")
        reference_files: list[dict[str, Any]] = []
        if source_path.strip():
            path = self.path_service.resolve_path(source_path)
            if not path.is_file():
                raise ReferenceServiceError(f"Head-Image source not found: {source_path}")
            reference = {"role": "head_image_source", "label": "Head-Image source", "path": str(path)}
            for option in self._locked_head_image_options(character, phase, str(path), other_phases=True):
                if option["path"] == str(path):
                    reference.update({
                        "source_asset_id": option["asset_id"],
                        "source_character": option["character"],
                        "source_phase": option["phase"],
                        "head_view": option["head_view"],
                    })
                    break
            reference_files = [reference]
        updated = replace(asset, reference_files=reference_files)
        self.asset_repository.save_asset(updated)
        return updated

    def upload_head_image_source(self, character: str, phase: str, filename: str, contents: bytes) -> Path:
        return self._upload_image(self.head_image_source_dir(character, phase), filename, contents, "Head-Image source")

    def character_assembly_context(self, character: str, phase: str, asset_id: int) -> dict[str, Any]:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline != "Character-Assembly":
            raise ReferenceServiceError("Reference picker is only available for Character-Assembly assets.")
        body_ref = self._selected_reference(asset, "body_reference") or {}
        head_image = self._selected_reference(asset, "head_image") or {}
        head_view = asset.head_view or asset.body_view
        return {
            "asset": asset,
            "is_manifest_editable": asset.pipeline_stage == "MANIFEST" and asset.actor == "PYTHON",
            "body_reference_options": self._body_reference_options(
                character,
                phase,
                str(body_ref.get("path") or ""),
                view=asset.body_view,
            ),
            "head_image_options": self._locked_head_image_options(
                character, phase, str(head_image.get("path") or ""), view=head_view
            ),
            "selected_body_reference": body_ref,
            "selected_head_image": head_image,
            "reference_files": asset.reference_files or [],
        }

    def save_character_assembly_references(
        self,
        character: str,
        phase: str,
        asset_id: int,
        body_reference_path: str,
        head_image_path: str,
    ) -> Asset:
        context = self.character_assembly_context(character, phase, asset_id)
        asset = context["asset"]
        if not context["is_manifest_editable"]:
            raise ReferenceServiceError("Character-assembly references can only be edited at MANIFEST / PYTHON.")
        body_option = next((item for item in context["body_reference_options"] if item["path"] == body_reference_path), None)
        head_option = next((item for item in context["head_image_options"] if item["path"] == head_image_path), None)
        if body_option is None:
            raise ReferenceServiceError(f"Body reference does not match view {asset.body_view}.")
        if head_option is None:
            raise ReferenceServiceError(f"Head-Image does not match view {asset.head_view or asset.body_view}.")
        updated = replace(asset, reference_files=[
            {
                "role": "body_reference",
                "label": "Locked body-reference image",
                "path": body_option["path"],
                "source_asset_id": body_option["asset_id"],
                "character": character,
                "phase": phase,
                "body_view": body_option["body_view"],
            },
            {
                "role": "head_image",
                "label": "Locked Head-Image",
                "path": head_option["path"],
                "source_asset_id": head_option["asset_id"],
                "character": character,
                "phase": phase,
                "body_view": head_option["head_view"],
                "head_view": head_option["head_view"],
            },
        ])
        self.asset_repository.save_asset(updated)
        return updated

    def _upload_image(self, target_dir: Path, filename: str, contents: bytes, label: str) -> Path:
        if not contents:
            raise ReferenceServiceError("No image data was provided.")
        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise ReferenceServiceError(f"{label} must be a PNG, JPG, JPEG, or WEBP image.")
        safe_name = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in Path(filename).name)
        if not safe_name:
            raise ReferenceServiceError(f"{label} filename is blank.")
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
