from __future__ import annotations

import re

from zet.services.auxiliary_resource_tags import auxiliary_resource_image_for_tag, auxiliary_resource_tags_in_text


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
        )
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
            elif match.group(4):
                references.append(self.resolve_identity_reference(tag, match.group(4), match.group(5), match.group(6)))
            else:
                references.append(self.resolve_scene_reference(tag, match.group(7), match.group(8)))
        return references
