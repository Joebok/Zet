from __future__ import annotations

import re
import json

from zet.services.auxiliary_resource_tags import auxiliary_resource_image_for_tag, auxiliary_resource_tags_in_text
from zet.services.local_asset_source_service import LocalAssetSourceService
from zet.services.local_asset_store_service import LocalAssetStoreService


class StoryReferenceService:
    """Resolve persisted scene reference tags into render reference records."""

    def __init__(
        self,
        path_service,
        asset_repository,
        auxiliary_resource_repository,
        identity_key_repository,
        error_type,
        turnaround_repository=None,
    ):
        self.path_service = path_service
        self.asset_repository = asset_repository
        self.auxiliary_resource_repository = auxiliary_resource_repository
        self.identity_key_repository = identity_key_repository
        self.error_type = error_type
        self.turnaround_repository = turnaround_repository
        self.local_asset_sources = LocalAssetSourceService(LocalAssetStoreService(path_service.config.base_library_path))
        self.image_catalog_service = None
        self.entity_library_service = None

    def resolve_library_asset(self, asset_id: str) -> dict:
        service = self.entity_library_service
        if service is None:
            raise self.error_type("The entity image library is unavailable.")
        asset = service.get_asset(asset_id)
        if asset.get("status") != "approved":
            raise self.error_type(f"Image asset is not approved: {asset_id}")
        return {
            "role": "story_reference", "label": asset.get("label") or asset["file_name"], "tag": f"{{{{LIB:ASSET:{asset_id}}}}}",
            "path": asset["image_path"], "kind": "entity-library", "asset_id": asset_id,
            "checksum": asset["checksum"],
        }

    def resolve_library_reference(self, reference_key: str) -> dict:
        service = self.entity_library_service
        if service is None:
            raise self.error_type("The entity image library is unavailable.")
        asset = service.resolve_reference(reference_key)
        return {
            "role": "story_reference", "label": asset.get("label") or asset["file_name"], "tag": f"{{{{LIB:REF:{reference_key}}}}}",
            "path": asset["image_path"], "kind": "entity-library", "asset_id": asset["asset_id"],
            "reference_key": reference_key, "set_id": asset.get("reference_set_id") or "",
            "checksum": asset["checksum"],
        }

    def resolve_aux_reference(self, tag: str) -> dict:
        if self.image_catalog_service is not None:
            item = self.image_catalog_service.managed_item_for_tag(tag)
            if item is not None:
                return {"role": "story_reference", "label": item.label, "tag": item.tag, "path": item.image_path, "kind": "imported"}
        if self.entity_library_service is not None:
            try:
                asset = self.entity_library_service.resolve_legacy_reference(tag)
                return {"role": "story_reference", "label": asset["label"], "tag": tag,
                        "path": asset["image_path"], "kind": "entity-library", "asset_id": asset["asset_id"],
                        "checksum": asset["checksum"]}
            except Exception:
                pass
        try:
            resource, image = auxiliary_resource_image_for_tag(self.auxiliary_resource_repository.list_resources(), tag)
        except LookupError as exc:
            raise self.error_type(str(exc)) from exc
        path = self.path_service.resolve_path(str(image.get("image_path") or ""))
        if not path.exists():
            raise self.error_type(f"Auxiliary image not found: {path}")
        return {
            "role": "story_reference",
            "label": f"{resource.label} - {image.get('label') or ''}",
            "tag": tag,
            "path": str(path),
            "kind": f"aux:{resource.category}",
        }

    def resolve_managed_reference(self, tag: str) -> dict:
        item = self.image_catalog_service.managed_item_for_tag(tag) if self.image_catalog_service is not None else None
        if item is None:
            raise self.error_type(f"Imported image reference not found: {tag}")
        return {"role": "story_reference", "label": item.label, "tag": item.tag, "path": item.image_path, "kind": "imported"}

    def resolve_local_asset_reference(self, tag: str, character: str, phase: str, source_key: str) -> dict:
        try:
            source = self.local_asset_sources.get_source(character, phase, source_key)
        except Exception as exc:
            raise self.error_type(f"Local image reference is no longer locked: {tag}") from exc
        return {"role": "story_reference", "label": " | ".join(
                    part for part in [source["pipeline"], source["view"], source["costume"]] if part),
                "tag": tag, "path": source["image_path"], "kind": "local-pipeline",
                "source_character": character, "source_phase": phase,
                "source_local_key": source_key, "checksum": source["image_sha256"]}

    def resolve_asset_reference(self, tag: str, character: str, phase: str, asset_id: str) -> dict:
        descriptor = tag.removesuffix("}}").split(":", 4)
        if len(descriptor) == 5 and "turnaround" in {
            part.strip().lower() for part in descriptor[4].split("|")
        }:
            return self.resolve_turnaround_reference(tag, character, phase, asset_id)
        asset = self.asset_repository.get_asset(character, phase, int(asset_id))
        if asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
            raise self.error_type(f"Asset reference is not locked: {tag}")
        if not asset.final_image_output:
            raise self.error_type(f"Asset reference has no final image output: {tag}")
        path = self.path_service.character_asset_path(character, phase) / asset.final_image_output
        if not path.exists():
            raise self.error_type(f"Asset reference image not found: {path}")
        return {
            "role": "story_reference",
            "label": f"{character} {phase} {asset.pipeline} {asset.body_view}",
            "tag": tag,
            "path": str(path),
            "kind": "asset",
            "source_character": character,
            "source_phase": phase,
            "source_asset_id": asset.asset_id,
        }

    def resolve_turnaround_reference(self, tag: str, character: str, phase: str, asset_id: str) -> dict:
        if self.turnaround_repository is None:
            raise self.error_type(f"Turnaround repository is not configured: {tag}")
        sheets = [
            sheet
            for sheet in self.turnaround_repository.list_sheets(character, phase)
            if sheet.sheet_type == "full"
            and int(asset_id) in sheet.source_asset_ids
            and self.path_service.resolve_path(str(sheet.locked_image_path or "")).is_file()
        ]
        if len(sheets) != 1:
            raise self.error_type(f"Locked turnaround reference not found: {tag}")
        sheet = sheets[0]
        path = self.path_service.resolve_path(str(sheet.locked_image_path or ""))
        if not path.exists():
            raise self.error_type(f"Turnaround reference image not found: {path}")
        return {
            "role": "story_reference",
            "label": sheet.label or sheet.turnaround_id,
            "tag": tag,
            "path": str(path),
            "kind": "turnaround",
            "source_character": character,
            "source_phase": phase,
            "source_asset_id": int(asset_id),
            "turnaround_id": sheet.turnaround_id,
        }

    def resolve_turnaround_sheet_reference(self, tag: str, character: str, phase: str, turnaround_id: str) -> dict:
        if self.turnaround_repository is None:
            raise self.error_type(f"Turnaround repository is not configured: {tag}")
        sheet = next((item for item in self.turnaround_repository.list_sheets(character, phase)
                      if item.turnaround_id == turnaround_id and item.sheet_type == "full"), None)
        path = self.path_service.resolve_path(str(sheet.locked_image_path or "")) if sheet else None
        if not sheet or not path or not path.is_file():
            raise self.error_type(f"Locked turnaround reference not found: {tag}")
        return {"role": "story_reference", "label": sheet.label or sheet.turnaround_id,
                "tag": tag, "path": str(path), "kind": "turnaround",
                "source_character": character, "source_phase": phase,
                "turnaround_id": sheet.turnaround_id, "source_local_keys": sheet.source_local_keys}

    def resolve_identity_reference(self, tag: str, character: str, phase: str, identity_key_id: str) -> dict:
        if self.identity_key_repository is None:
            raise self.error_type(f"Identity Key repository is not configured: {tag}")
        identity_key = self.identity_key_repository.get_identity_key(character, phase, identity_key_id)
        path = self.path_service.resolve_path(identity_key.image_path)
        if not path.exists():
            raise self.error_type(f"Identity Key image not found: {path}")
        return {
            "role": "story_reference",
            "label": identity_key.label,
            "tag": tag,
            "path": str(path),
            "kind": "identity-key",
            "source_character": character,
            "source_phase": phase,
            "identity_key_id": identity_key.identity_key_id,
            "source_asset_id": identity_key.source_asset_id,
            "source_local_key": identity_key.source_local_key,
        }

    def resolve_scene_reference(self, tag: str, story_slug: str, scene_slug: str) -> dict:
        safe_story_slug = re.sub(r"[^A-Za-z0-9]+", "-", story_slug).strip("-")
        safe_scene_slug = re.sub(r"[^A-Za-z0-9]+", "-", scene_slug).strip("-")
        if not safe_story_slug or not safe_scene_slug or safe_story_slug != story_slug or safe_scene_slug != scene_slug:
            raise self.error_type(f"Invalid scene image reference: {tag}")
        path = self.path_service.story_folder_path(safe_story_slug) / f"{safe_scene_slug}.png"
        if not path.exists() or not path.is_file():
            raise self.error_type(f"Scene image not found: {path}")
        return {
            "role": "story_reference",
            "label": f"{safe_story_slug} - {safe_scene_slug}",
            "tag": tag,
            "path": str(path),
            "kind": "scene",
            "story_slug": safe_story_slug,
            "scene_slug": safe_scene_slug,
        }

    def resolve_scene_render_reference(self, tag: str, story_slug: str, scene_slug: str, target_id: str) -> dict:
        safe_story_slug = re.sub(r"[^A-Za-z0-9]+", "-", story_slug).strip("-")
        safe_scene_slug = re.sub(r"[^A-Za-z0-9]+", "-", scene_slug).strip("-")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", target_id or ""):
            raise self.error_type(f"Invalid scene render reference: {tag}")
        if safe_story_slug != story_slug or safe_scene_slug != scene_slug:
            raise self.error_type(f"Invalid scene render reference: {tag}")
        path = self.path_service.scene_subscene_locked_path(safe_story_slug, safe_scene_slug, target_id)
        if not path.is_file():
            raise self.error_type(f"Scene render image not found: {path}")
        return {
            "role": "story_reference",
            "label": f"{safe_story_slug} - {safe_scene_slug} - {target_id}",
            "tag": tag,
            "path": str(path),
            "kind": "scene-render",
            "story_slug": safe_story_slug,
            "scene_slug": safe_scene_slug,
            "render_target_id": target_id,
        }

    def resolve_image_tag(self, tag: str) -> dict:
        """Resolve exactly one complete Zet image tag."""
        cleaned = str(tag or "").strip()
        references = self.resolve_scene_references(cleaned)
        if len(references) != 1 or references[0].get("tag") != cleaned:
            raise self.error_type(f"Expected one image reference tag: {cleaned or '(blank)'}")
        return references[0]

    def resolve_scene_references(self, scene_text: str) -> list[dict]:
        references = []
        seen = set()
        pattern = (
            r"\{\{ASSET:([^:}]+):([^:}]+):(\d+)(?::[^}]*)?\}\}"
            r"|\{\{IDENTITY:([^:}]+):([^:}]+):([^:}]+)\}\}"
            r"|\{\{SCENE:([^:}]+):([^:}]+)\}\}"
            r"|\{\{TURNAROUND:([^:}]+):([^:}]+):([^:}]+)\}\}"
            r"|\{\{LOCAL:([^:}]+):([^:}]+):([^}]+)\}\}"
        )
        for tag, _, _, _ in auxiliary_resource_tags_in_text(scene_text):
            if tag not in seen:
                seen.add(tag)
                references.append(self.resolve_aux_reference(tag))
        for match in re.finditer(r"\{\{IMAGE:(img_[A-Za-z0-9_-]+)\}\}", scene_text or ""):
            tag = match.group(0)
            if tag not in seen:
                seen.add(tag)
                references.append(self.resolve_managed_reference(tag))
        for match in re.finditer(r"\{\{SCENE_RENDER:([^:}]+):([^:}]+):([^:}]+)\}\}", scene_text or ""):
            tag = match.group(0)
            if tag not in seen:
                seen.add(tag)
                references.append(self.resolve_scene_render_reference(tag, match.group(1), match.group(2), match.group(3)))
        for match in re.finditer(pattern, scene_text or ""):
            tag = match.group(0)
            if tag in seen:
                continue
            seen.add(tag)
            if match.group(1):
                references.append(self.resolve_asset_reference(tag, match.group(1), match.group(2), match.group(3)))
            elif match.group(4):
                references.append(self.resolve_identity_reference(tag, match.group(4), match.group(5), match.group(6)))
            elif match.group(9):
                references.append(self.resolve_turnaround_sheet_reference(tag, match.group(9), match.group(10), match.group(11)))
            elif match.group(12):
                references.append(self.resolve_local_asset_reference(tag, match.group(12), match.group(13), match.group(14)))
            else:
                references.append(self.resolve_scene_reference(tag, match.group(7), match.group(8)))
        for match in re.finditer(r"\{\{LIB:ASSET:([0-9a-fA-F-]{36})\}\}", scene_text or ""):
            tag = match.group(0)
            if tag not in seen:
                seen.add(tag)
                references.append(self.resolve_library_asset(match.group(1)))
        for match in re.finditer(r"\{\{LIB:REF:([a-z0-9][a-z0-9._-]*)\}\}", scene_text or ""):
            tag = match.group(0)
            if tag not in seen:
                seen.add(tag)
                references.append(self.resolve_library_reference(match.group(1)))
        try:
            payload = json.loads(scene_text)
        except (TypeError, json.JSONDecodeError):
            payload = None
        def visit(value):
            if isinstance(value, dict):
                asset_id = str(value.get("asset_id") or "").strip()
                reference_key = str(value.get("reference_key") or "").strip()
                if asset_id or reference_key:
                    reference = self.resolve_library_asset(asset_id) if asset_id else self.resolve_library_reference(reference_key)
                    if reference["tag"] not in seen:
                        seen.add(reference["tag"])
                        references.append(reference)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        if payload is not None:
            visit(payload)
        return references
