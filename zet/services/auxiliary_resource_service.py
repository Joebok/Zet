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
        """Initialize the service with repository and path helpers."""
        self.repository = repository
        self.path_service = path_service

    def _timestamp(self) -> str:
        """Return the current timestamp for persisted resource rows."""
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _category(self, value: str) -> str:
        """Normalize and validate an auxiliary resource category."""
        category = str(value or "").strip().lower()
        if category not in VALID_AUXILIARY_CATEGORIES:
            raise AuxiliaryResourceServiceError("Auxiliary resource category must be person, place, or thing.")
        return category

    def _slug(self, value: str) -> str:
        """Normalize a label into a stable resource id segment."""
        return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "resource"

    def _extension_for_content_type(self, content_type: str) -> str:
        """Return a safe image extension for an uploaded content type."""
        normalized = str(content_type or "").split(";", 1)[0].strip().lower()
        if normalized in {"image/jpeg", "image/jpg"}:
            return ".jpg"
        if normalized == "image/webp":
            return ".webp"
        if normalized == "image/gif":
            return ".gif"
        return ".png"

    def _tag(self, category: str, resource_id: str) -> str:
        """Return the compiler-facing tag for a resource."""
        return f"{{{{AUX:{category}:{resource_id}}}}}"

    def _unique_resource_id(self, category: str, label: str) -> str:
        """Build a unique resource id within the category."""
        base = self._slug(label)
        existing = {resource.resource_id for resource in self.repository.list_resources() if resource.category == category}
        if base not in existing:
            return base
        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _write_image(self, category: str, resource_id: str, image_bytes: bytes, content_type: str) -> Path:
        """Write uploaded resource image bytes to the global image folder."""
        if not image_bytes:
            raise AuxiliaryResourceServiceError("Auxiliary resource image is required.")
        extension = self._extension_for_content_type(content_type)
        image_path = self.path_service.auxiliary_resource_image_path(category, resource_id, extension)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
        return image_path

    def list_resources(self, category: str) -> list[AuxiliaryResource]:
        """List resources filtered by one category."""
        normalized = self._category(category)
        return sorted(
            [resource for resource in self.repository.list_resources() if resource.category == normalized],
            key=lambda item: (item.label.lower(), item.resource_id),
        )

    def create_resource(self, category: str, label: str, image_bytes: bytes, content_type: str) -> AuxiliaryResource:
        """Create one auxiliary resource with an uploaded image."""
        normalized = self._category(category)
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise AuxiliaryResourceServiceError("Auxiliary resource label is required.")
        resource_id = self._unique_resource_id(normalized, cleaned_label)
        image_path = self._write_image(normalized, resource_id, image_bytes, content_type)
        now = self._timestamp()
        resource = AuxiliaryResource(
            resource_id=resource_id,
            category=normalized,
            label=cleaned_label,
            tag=self._tag(normalized, resource_id),
            image_path=str(image_path),
            created_at=now,
            updated_at=now,
        )
        self.repository.save_resource(resource)
        return resource

    def update_resource(
        self,
        resource_id: str,
        label: str,
        image_bytes: bytes | None = None,
        content_type: str = "",
    ) -> AuxiliaryResource:
        """Update an auxiliary resource label and optionally replace its image."""
        resource = self.repository.get_resource(resource_id)
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise AuxiliaryResourceServiceError("Auxiliary resource label is required.")
        image_path = self.path_service.resolve_path(resource.image_path)
        if image_bytes is not None:
            image_path = self._write_image(resource.category, resource.resource_id, image_bytes, content_type)
        resource.label = cleaned_label
        resource.image_path = str(image_path)
        resource.updated_at = self._timestamp()
        self.repository.save_resource(resource)
        return resource
