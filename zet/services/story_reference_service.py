from __future__ import annotations

import re

from zet.services.auxiliary_resource_tags import auxiliary_resource_image_for_tag, auxiliary_resource_tags_in_text


class StoryReferenceService:
    """Resolve persisted scene reference tags into render reference records."""

    def __init__(self, path_service, asset_repository, auxiliary_resource_repository, identity_key_repository, error_type):
        self.path_service = path_service
        self.asset_repository = asset_repository
        self.auxiliary_resource_repository = auxiliary_resource_repository
        self.identity_key_repository = identity_key_repository
        self.error_type = error_type

    def resolve_aux_reference(self, tag: str) -> dict:
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

    def resolve_asset_reference(self, tag: str, character: str, phase: str, asset_id: str) -> dict:
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
        }

    def resolve_scene_references(self, scene_text: str) -> list[dict]:
        references = []
        seen = set()
        pattern = r"\{\{ASSET:([^:}]+):([^:}]+):(\d+)(?::[^}]*)?\}\}|\{\{IDENTITY:([^:}]+):([^:}]+):([^:}]+)\}\}"
        for tag, _, _, _ in auxiliary_resource_tags_in_text(scene_text):
            if tag not in seen:
                seen.add(tag)
                references.append(self.resolve_aux_reference(tag))
        for match in re.finditer(pattern, scene_text or ""):
            tag = match.group(0)
            if tag in seen:
                continue
            seen.add(tag)
            if match.group(1):
                references.append(self.resolve_asset_reference(tag, match.group(1), match.group(2), match.group(3)))
            else:
                references.append(self.resolve_identity_reference(tag, match.group(4), match.group(5), match.group(6)))
        return references
