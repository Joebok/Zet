import re
import shutil
from datetime import datetime
import hashlib
import mimetypes
from pathlib import Path

from zet.models.auxiliary_resource import AuxiliaryResource
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.services.auxiliary_resource_tags import auxiliary_resource_tag
from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService
from zet.services.path_service import PathService


AUXILIARY_RESOURCE_CATEGORIES = [
    {"value": "person", "label": "Person", "resource_type": "Person"},
    {"value": "place", "label": "Place", "resource_type": "Place"},
    {"value": "thing", "label": "Thing", "resource_type": "Object"},
]
VALID_AUXILIARY_CATEGORIES = {item["value"] for item in AUXILIARY_RESOURCE_CATEGORIES}


class AuxiliaryResourceServiceError(Exception):
    """Report auxiliary resource validation or storage failures."""


class AuxiliaryResourceService:
    """Manage global auxiliary scene reference resources."""

    def __init__(self, repository: AuxiliaryResourceRepository, path_service: PathService):
        self.repository = repository
        self.path_service = path_service
        catalog_repository = EntityLibraryRepository(path_service.entity_library_database_path())
        catalog_repository.initialize()
        self.entity_library = EntityLibraryService(path_service, catalog_repository)

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
        return auxiliary_resource_tag(category, resource_id, image_id)

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

    def _entity_and_set(self, category: str, resource_id: str, label: str) -> tuple[str, str]:
        entity_type = {"person": "person", "place": "location", "thing": "prop"}[category]
        entity = next((item for item in self.entity_library.list_entities(entity_type)
                       if item["name"].casefold() == label.casefold()), None)
        if entity is None:
            entity = self.entity_library.create_entity({"name": label, "entity_type": entity_type})
        set_name = f"Auxiliary: {category}/{resource_id}"
        reference_set = next((item for item in self.entity_library.list_sets() if item["name"] == set_name), None)
        if reference_set is None:
            reference_set = self.entity_library.create_set({"name": set_name, "set_type": "legacy_auxiliary",
                                                             "description": label, "entity_id": entity["entity_id"]})
        return entity["entity_id"], reference_set["set_id"]

    def list_resources(self, category: str) -> list[AuxiliaryResource]:
        normalized = self._category(category)
        return sorted(
            [resource for resource in self.repository.list_resources() if resource.category == normalized],
            key=lambda item: (item.label.lower(), item.resource_id),
        )

    def migrate_legacy_images(self, original_library_root: str | Path) -> dict[str, int]:
        """Register moved auxiliary image files in the universe catalog and retain their tags."""
        original_root = Path(original_library_root).expanduser().resolve()
        imported = 0
        unresolved = 0
        for resource in self.repository.list_resources():
            entity_id, set_id = self._entity_and_set(resource.category, resource.resource_id, resource.label)
            changed = False
            for image in resource.images:
                tag = str(image.get("tag") or self._tag(resource.category, resource.resource_id, str(image.get("image_id") or "")))
                source = Path(str(image.get("image_path") or ""))
                try:
                    relative = source.resolve().relative_to(original_root)
                    source = self.path_service.library_path("_state", *relative.parts)
                except (OSError, ValueError):
                    pass
                if not source.is_file():
                    unresolved += 1
                    continue
                data = source.read_bytes()
                checksum = hashlib.sha256(data).hexdigest()
                mime_type = mimetypes.guess_type(source.name)[0] or "image/png"
                asset = self.entity_library.import_asset(
                    str(image.get("label") or resource.label), mime_type, data,
                    notes=str(resource.notes or ""), entity_ids=[entity_id], set_ids=[set_id],
                    origin="legacy_auxiliary", origin_key=f"auxiliary:{tag}:{checksum}",
                )
                self.entity_library.register_legacy_reference(tag, asset["asset_id"])
                image["image_path"] = asset["image_path"]
                image["tag"] = tag
                changed = True
                imported += 1
            old_folder = Path(str(resource.resource_path or ""))
            try:
                resource.resource_path = str(self.path_service.library_path("_state", *old_folder.resolve().relative_to(original_root).parts))
                changed = True
            except (OSError, ValueError):
                pass
            old_template = Path(str(resource.template_path or ""))
            try:
                resource.template_path = str(self.path_service.library_path("_state", *old_template.resolve().relative_to(original_root).parts))
                changed = True
            except (OSError, ValueError):
                pass
            if changed:
                first = resource.images[0] if resource.images else {}
                resource.image_path = str(first.get("image_path") or "")
                resource.tag = str(first.get("tag") or "")
                self.repository.save_resource(resource)
        return {"imported": imported, "unresolved": unresolved}

    def create_resource(self, category: str, label: str) -> AuxiliaryResource:
        normalized = self._category(category)
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise AuxiliaryResourceServiceError("Auxiliary resource label is required.")
        resource_id = self._unique_resource_id(cleaned_label)
        self._entity_and_set(normalized, resource_id, cleaned_label)
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

    def delete_resource(self, resource_id: str) -> AuxiliaryResource:
        resource = self.repository.get_resource(resource_id)
        folder, _ = self._resource_paths(resource.resource_id)
        templates_root = self.path_service.library_path("_state", "ResourceTemplates")
        if not resource.resource_id or folder.resolve().parent != templates_root.resolve():
            raise AuxiliaryResourceServiceError("Auxiliary resource folder is invalid.")
        if folder.exists():
            shutil.rmtree(folder)
        self.repository.delete_resource(resource.resource_id)
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
        folder, _ = self._resource_paths(resource.resource_id)
        folder.mkdir(parents=True, exist_ok=True)
        existing = next((image for image in resource.images if image.get("image_id") == original_image_id), None) if original_image_id else None
        image_id = str(existing.get("image_id")) if existing else self._unique_image_id(resource, cleaned_label)
        extension = self._extension_for_content_type(content_type) if image_bytes else Path(existing.get("image_path", "")).suffix if existing else ".png"
        image_path = folder / f"{image_id}{extension}"
        if not image_bytes and existing:
            old_path = Path(existing.get("image_path", ""))
            if old_path.is_file():
                image_bytes = old_path.read_bytes()
        if not image_bytes:
            raise AuxiliaryResourceServiceError("Auxiliary resource image is required.")
        entity_id, set_id = self._entity_and_set(resource.category, resource.resource_id, resource.label)
        mime_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}.get(extension.lower(), "image/png")
        tag = self._tag(resource.category, resource.resource_id, image_id)
        import hashlib
        checksum = hashlib.sha256(image_bytes).hexdigest()
        catalog_asset = self.entity_library.import_asset(
            cleaned_label, mime_type, image_bytes,
            notes=str(resource.notes or ""), entity_ids=[entity_id], set_ids=[set_id],
            origin="legacy_auxiliary", origin_key=f"auxiliary:{tag}:{checksum}",
        )
        self.entity_library.register_legacy_reference(tag, catalog_asset["asset_id"])
        image_path = Path(catalog_asset["image_path"])
        now = self._timestamp()
        image_record = {
            "image_id": image_id,
            "label": cleaned_label,
            "tag": tag,
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
