import re
from datetime import datetime
from pathlib import Path

from zet.models.auxiliary_resource import AuxiliaryResource
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.services.path_service import PathService


VALID_AUXILIARY_CATEGORIES = {"person", "place", "thing"}


class AuxiliaryResourceServiceError(Exception):
    """Report auxiliary resource validation or storage failures."""


class AuxiliaryResourceService:
    """Manage global auxiliary scene reference resources."""

    def __init__(self, repository: AuxiliaryResourceRepository, path_service: PathService):
        self.repository = repository
        self.path_service = path_service

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _category(self, value: str) -> str:
        category = str(value or "").strip().lower()
        if category not in VALID_AUXILIARY_CATEGORIES:
            raise AuxiliaryResourceServiceError("Auxiliary resource category must be person, place, or thing.")
        return category

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "resource"

    def _extension_for_content_type(self, content_type: str) -> str:
        normalized = str(content_type or "").split(";", 1)[0].strip().lower()
        if normalized in {"image/jpeg", "image/jpg"}:
            return ".jpg"
        if normalized == "image/webp":
            return ".webp"
        if normalized == "image/gif":
            return ".gif"
        return ".png"

    def _tag(self, category: str, resource_id: str, image_id: str) -> str:
        return f"{{{{AUX:{category}:{resource_id}:{image_id}}}}}"

    def _unique_resource_id(self, label: str) -> str:
        base = self._slug(label)
        existing = {resource.resource_id for resource in self.repository.list_resources()}
        if base not in existing:
            return base
        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _unique_image_id(self, resource: AuxiliaryResource, label: str, original_id: str = "") -> str:
        base = self._slug(label)
        existing = {str(image.get("image_id") or "") for image in resource.images if str(image.get("image_id") or "") != original_id}
        if base not in existing:
            return base
        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _template_text(self, label: str, category: str) -> str:
        source = self.path_service.auxiliary_resource_template_source_path()
        if not source.exists():
            raise AuxiliaryResourceServiceError(f"Auxiliary resource template not found: {source}")
        text = source.read_text(encoding="utf-8")
        text = re.sub(r"(?im)^Resource_Name:\s*`[^`]*`", f"Resource_Name: `{label}`", text)
        text = re.sub(r"(?im)^Resource_Category:\s*`[^`]*`", f"Resource_Category: `{category}`", text)
        if "Resource_Name:" not in text:
            text = f"Resource_Name: `{label}`\nResource_Category: `{category}`\n\n{text}"
        return text.rstrip() + "\n"

    def _resource_paths(self, resource_id: str) -> tuple[Path, Path]:
        folder = self.path_service.auxiliary_resource_folder_path(resource_id)
        return folder, folder / f"{resource_id}_Template.md"

    def list_resources(self, category: str) -> list[AuxiliaryResource]:
        normalized = self._category(category)
        return sorted(
            [resource for resource in self.repository.list_resources() if resource.category == normalized],
            key=lambda item: (item.label.lower(), item.resource_id),
        )

    def create_resource(self, category: str, label: str) -> AuxiliaryResource:
        normalized = self._category(category)
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise AuxiliaryResourceServiceError("Auxiliary resource label is required.")
        resource_id = self._unique_resource_id(cleaned_label)
        folder, template_path = self._resource_paths(resource_id)
        folder.mkdir(parents=True, exist_ok=False)
        template_path.write_text(self._template_text(cleaned_label, normalized), encoding="utf-8")
        now = self._timestamp()
        resource = AuxiliaryResource(
            resource_id=resource_id,
            category=normalized,
            label=cleaned_label,
            resource_path=str(folder),
            template_path=str(template_path),
            images=[],
            tag="",
            image_path="",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_resource(resource)
        return resource

    def update_resource(self, resource_id: str, label: str) -> AuxiliaryResource:
        resource = self.repository.get_resource(resource_id)
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise AuxiliaryResourceServiceError("Auxiliary resource label is required.")
        resource.label = cleaned_label
        folder, template_path = self._resource_paths(resource.resource_id)
        folder.mkdir(parents=True, exist_ok=True)
        if not template_path.exists():
            template_path.write_text(self._template_text(cleaned_label, resource.category), encoding="utf-8")
        resource.resource_path = str(folder)
        resource.template_path = str(template_path)
        resource.updated_at = self._timestamp()
        self.repository.save_resource(resource)
        return resource

    def save_image(
        self,
        resource_id: str,
        image_label: str,
        image_bytes: bytes,
        content_type: str,
        original_image_id: str = "",
    ) -> AuxiliaryResource:
        resource = self.repository.get_resource(resource_id)
        cleaned_label = str(image_label or "").strip()
        if not cleaned_label:
            raise AuxiliaryResourceServiceError("Image label is required.")
        image_id = self._unique_image_id(resource, cleaned_label, original_image_id)
        folder, _ = self._resource_paths(resource.resource_id)
        folder.mkdir(parents=True, exist_ok=True)
        existing = next((image for image in resource.images if image.get("image_id") == original_image_id), None) if original_image_id else None
        extension = self._extension_for_content_type(content_type) if image_bytes else Path(existing.get("image_path", "")).suffix if existing else ".png"
        image_path = folder / f"{image_id}{extension}"
        if existing:
            old_path = Path(existing.get("image_path", ""))
            if old_path.exists() and old_path != image_path:
                old_path.rename(image_path)
        if image_bytes:
            image_path.write_bytes(image_bytes)
        if not image_path.exists():
            raise AuxiliaryResourceServiceError("Auxiliary resource image is required.")
        now = self._timestamp()
        image_record = {
            "image_id": image_id,
            "label": cleaned_label,
            "tag": self._tag(resource.category, resource.resource_id, image_id),
            "image_path": str(image_path),
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }
        resource.images = [image for image in resource.images if image.get("image_id") != original_image_id]
        resource.images.append(image_record)
        resource.images.sort(key=lambda item: (str(item.get("label") or "").lower(), str(item.get("image_id") or "")))
        first = resource.images[0] if resource.images else {}
        resource.tag = str(first.get("tag") or "")
        resource.image_path = str(first.get("image_path") or "")
        resource.updated_at = now
        self.repository.save_resource(resource)
        return resource
