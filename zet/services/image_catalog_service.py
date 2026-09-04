from __future__ import annotations

import hashlib
import json
import re
import shutil
from uuid import uuid4
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from zet.models.image_catalog import ImageCatalogItem
from zet.services.ai_proxy_path_service import AIProxyPathService


SEMANTIC_CATEGORIES = {"Person", "Place", "Object", "Composite/Scene"}
SECTION_MODES = {"inherit", "override", "not_applicable"}
BASE_PIPELINES = {"Body-Reference", "Head-Image", "Character-Assembly"}


class ImageCatalogServiceError(Exception):
    """Report image-catalog validation and workflow failures."""


class ImageCatalogReferenceConflict(ImageCatalogServiceError):
    """Report a managed image that is still referenced by active library files."""

    def __init__(self, references: list[str]):
        self.references = references
        super().__init__(f"Image is referenced by {len(references)} active file(s).")


class ImageCatalogService:
    """Discover selectable images and overlay logical organization metadata."""

    TASK_TYPE = "image_catalog_description"
    PROMPT_FILE = "OLLAMA_PROMPT.md"
    RESULT_FILE = "IMAGE_DESCRIPTION.json"

    def __init__(
        self,
        config,
        path_service,
        repository,
        asset_repository,
        identity_key_repository,
        turnaround_repository,
        story_service,
    ):
        self.config = config
        self.path_service = path_service
        self.repository = repository
        self.asset_repository = asset_repository
        self.identity_key_repository = identity_key_repository
        self.turnaround_repository = turnaround_repository
        self.story_service = story_service
        self.ai_paths = AIProxyPathService(config)

    @staticmethod
    def _catalog_id(source_key: str) -> str:
        return "img_" + hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "item"

    @staticmethod
    def _extract_section(path: Path, section: str) -> str:
        if not path.is_file():
            return ""
        match = re.search(
            rf"<!-- ZET:BEGIN {re.escape(section)} -->\s*(.*?)\s*<!-- ZET:END {re.escape(section)} -->",
            path.read_text(encoding="utf-8"),
            re.DOTALL,
        )
        return str(match.group(1)).strip() if match else ""

    def _canonical_character_sections(self, character: str, phase: str, costume: str = "") -> tuple[str, str]:
        identity = self._extract_section(
            self.path_service.character_template_path(character, phase), "SCENE_CHARACTER_IDENTITY"
        )
        costume_text = ""
        if costume:
            costume_text = self._extract_section(
                self.path_service.costume_template_path(character, phase, costume), "SCENE_COSTUME_IDENTITY"
            )
        return identity, costume_text

    def _base_record(self, source_key: str, **values) -> dict:
        return {
            "catalog_id": self._catalog_id(source_key),
            "source_key": source_key,
            "source_type": "",
            "tag": "",
            "label": "",
            "image_path": "",
            "thumbnail_path": "",
            "mime_type": "",
            "semantic_category": "Composite/Scene",
            "character": "",
            "phase": "",
            "costume": "",
            "pipeline": "",
            "view": "",
            "story_slug": "",
            "scene_slug": "",
            "subscene_id": "",
            "is_base_pipeline": False,
            "candidate_pending": False,
            "image_review_key": "",
            "is_managed": False,
            "managed_label": "",
            "reference_set_id": "",
            "reference_set_label": "",
            "default_reference_roles": [],
            "created_at": "",
            "updated_at": "",
            "inherited_identity": "",
            "inherited_costume": "",
            "costume_applicable": False,
            **values,
        }

    def _discover_managed(self, payload: dict) -> list[dict]:
        rows = []
        reference_sets = payload.get("reference_sets", {})
        for record in payload.get("managed_images", {}).values():
            if not isinstance(record, dict):
                continue
            image_path = self.path_service.resolve_path(str(record.get("image_path") or ""))
            if not image_path.is_file():
                continue
            set_id = str(record.get("reference_set_id") or "")
            reference_set = reference_sets.get(set_id, {}) if set_id else {}
            managed_label = str(record.get("label") or record.get("catalog_id") or "Imported image")
            set_label = str(reference_set.get("label") or "")
            display_label = f"{set_label} - {managed_label}" if set_label else managed_label
            category = str(record.get("semantic_category") or "Object")
            rows.append(self._base_record(
                str(record.get("source_key") or f"import:{record.get('catalog_id')}"),
                catalog_id=str(record.get("catalog_id") or ""),
                source_type="imported",
                tag=str(record.get("tag") or ""),
                label=display_label,
                managed_label=managed_label,
                image_path=str(image_path),
                thumbnail_path=str(image_path),
                mime_type=str(record.get("mime_type") or record.get("content_type") or ""),
                semantic_category=category,
                pipeline="Imported Reference",
                inherited_identity=str(reference_set.get("identity_text") or ""),
                inherited_costume=str(reference_set.get("costume_text") or ""),
                costume_applicable=category == "Person",
                is_managed=True,
                reference_set_id=set_id,
                reference_set_label=set_label,
                created_at=str(record.get("created_at") or ""),
                updated_at=str(record.get("updated_at") or ""),
            ))
        return rows

    def _character_phases(self):
        root = Path(self.path_service.config.base_character_path)
        if not root.exists():
            return
        for character_dir in sorted(item for item in root.iterdir() if item.is_dir() and not item.name.startswith("_")):
            for phase_dir in sorted(item for item in character_dir.iterdir() if item.is_dir() and not item.name.startswith("_")):
                yield character_dir.name, phase_dir.name

    def _discover_character_images(self) -> list[dict]:
        rows = []
        for character, phase in self._character_phases() or []:
            try:
                assets = self.asset_repository.list_assets(character, phase)
            except Exception:
                assets = []
            for asset in assets:
                if asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
                    continue
                image_path = self.path_service.locked_image_path(asset)
                if not image_path.is_file():
                    continue
                identity, costume_text = self._canonical_character_sections(character, phase, asset.costume or "")
                tag_parts = [self.story_service._asset_reference_pipeline_code(asset.pipeline), asset.body_view]
                if asset.pipeline == "Costume-Dressing" and asset.costume:
                    tag_parts.append(asset.costume)
                if asset.pipeline == "Scene-Appearance" and asset.scene_appearance:
                    tag_parts.extend([asset.scene_appearance, asset.costume or ""])
                if asset.pipeline == "Expression" and asset.expression:
                    tag_parts.append(asset.expression)
                tag = f"{{{{ASSET:{character}:{phase}:{asset.asset_id}:{' | '.join(part for part in tag_parts if part)}}}}}"
                source_key = f"asset:{character}:{phase}:{asset.asset_id}"
                label = " | ".join(
                    part for part in [character, phase, asset.pipeline, asset.scene_appearance or "", asset.costume or "", asset.body_view]
                    if part
                )
                if asset.pipeline == "Scene-Appearance":
                    label = " | ".join(part for part in [
                        character,
                        phase,
                        " / ".join(filter(None, ["Scene Appearance", asset.scene_appearance or "", asset.costume or "", asset.body_view])),
                    ] if part)
                rows.append(self._base_record(
                    source_key,
                    source_type="pipeline",
                    tag=tag,
                    label=label,
                    image_path=str(image_path),
                    thumbnail_path=str(image_path),
                    semantic_category="Person",
                    character=character,
                    phase=phase,
                    costume=asset.costume or "",
                    pipeline=asset.pipeline,
                    view=asset.body_view or "",
                    is_base_pipeline=asset.pipeline in BASE_PIPELINES,
                    inherited_identity=identity,
                    inherited_costume=costume_text,
                    costume_applicable=bool(asset.costume),
                    default_reference_roles=["internal arrangement"] if asset.pipeline == "Scene-Appearance" else [],
                ))
            try:
                identity_keys = self.identity_key_repository.list_identity_keys(character, phase)
            except Exception:
                identity_keys = []
            for key in identity_keys:
                image_path = self.path_service.resolve_path(key.image_path)
                if not image_path.is_file():
                    continue
                identity, costume_text = self._canonical_character_sections(character, phase, key.source_costume or "")
                source_key = f"identity:{character}:{phase}:{key.identity_key_id}"
                rows.append(self._base_record(
                    source_key,
                    source_type="identity-key",
                    tag=f"{{{{IDENTITY:{character}:{phase}:{key.identity_key_id}}}}}",
                    label=key.label,
                    image_path=str(image_path),
                    thumbnail_path=str(image_path),
                    semantic_category="Person",
                    character=character,
                    phase=phase,
                    costume=key.source_costume or "",
                    pipeline="Identity Key",
                    view=key.source_body_view or "",
                    inherited_identity=identity,
                    inherited_costume=costume_text,
                    costume_applicable=bool(key.source_costume),
                ))
            try:
                sheets = self.turnaround_repository.list_sheets(character, phase)
            except Exception:
                sheets = []
            for sheet in sheets:
                image_path = self.path_service.resolve_path(str(sheet.locked_image_path or ""))
                if sheet.sheet_type != "full" or not sheet.source_asset_ids or not image_path.is_file():
                    continue
                identity, costume_text = self._canonical_character_sections(character, phase, sheet.costume or "")
                detail = [self.story_service._asset_reference_pipeline_code(sheet.source_pipeline), "Turnaround"]
                if sheet.costume:
                    detail.append(sheet.costume)
                if sheet.scene_appearance:
                    detail = [self.story_service._asset_reference_pipeline_code(sheet.source_pipeline), "Turnaround", sheet.scene_appearance, sheet.costume or ""]
                source_key = f"turnaround:{character}:{phase}:{sheet.turnaround_id}"
                rows.append(self._base_record(
                    source_key,
                    source_type="turnaround",
                    tag=f"{{{{ASSET:{character}:{phase}:{sheet.source_asset_ids[0]}:{' | '.join(detail)}}}}}",
                    label=sheet.label or sheet.turnaround_id,
                    image_path=str(image_path),
                    thumbnail_path=str(image_path),
                    semantic_category="Person",
                    character=character,
                    phase=phase,
                    costume=sheet.costume or "",
                    pipeline="Turnaround",
                    inherited_identity=identity,
                    inherited_costume=costume_text,
                    costume_applicable=bool(sheet.costume),
                    default_reference_roles=["internal arrangement"] if sheet.source_pipeline == "Scene-Appearance" else [],
                ))
        return rows

    def _discover_scenes(self) -> list[dict]:
        rows = []
        for story in self.story_service.list_stories():
            for scene in self.story_service.list_scenes(story.slug):
                image_path = self.story_service.scene_image_path(story.slug, scene.slug)
                if image_path.is_file():
                    source_key = f"scene:{story.slug}:{scene.slug}:main"
                    rows.append(self._base_record(
                        source_key,
                        source_type="scene",
                        tag=f"{{{{SCENE:{story.slug}:{scene.slug}}}}}",
                        label=f"{story.title} - {scene.title}",
                        image_path=str(image_path),
                        thumbnail_path=str(image_path),
                        semantic_category="Composite/Scene",
                        pipeline="Rendered Scene",
                        story_slug=story.slug,
                        scene_slug=scene.slug,
                        candidate_pending=self.path_service.scene_candidate_image_path(story.slug, scene.slug).is_file(),
                        image_review_key=f"scene:{story.slug}:{scene.slug}",
                    ))
                document = self.story_service.load_scene_builder_data(story.slug, scene.slug)
                elements = {str(item.get("id") or ""): item for item in document.data.get("scene_elements") or [] if isinstance(item, dict)}
                for definition in document.data.get("subscenes") or []:
                    target_id = str(definition.get("id") or "")
                    image_path = self.path_service.scene_subscene_locked_path(story.slug, scene.slug, target_id)
                    if not target_id or not image_path.is_file():
                        continue
                    if definition.get("kind") == "element":
                        composition = (definition.get("setup") or {}).get("composition") or {}
                    else:
                        composition = definition.get("prompt_overrides") or {}
                    composition_identity = str(composition.get("composition_notes") or "").strip()
                    inherited_identity = composition_identity
                    inherited_costume = ""
                    category = "Composite/Scene"
                    costume_applicable = False
                    if definition.get("kind") == "element":
                        anchor = elements.get(str(definition.get("anchor_element_id") or ""), {})
                        sections = self.story_service._canonical_element_source_sections(anchor)
                        if sections:
                            inherited_identity = str(sections.get("identity_preservation_core") or composition_identity)
                            inherited_costume = str(sections.get("identity_preservation_costume") or "")
                            category = {"Character": "Person", "Person": "Person", "Place": "Place", "Object": "Object"}.get(str(anchor.get("resource_type") or ""), "Composite/Scene")
                            costume_applicable = category == "Person"
                    source_key = f"scene:{story.slug}:{scene.slug}:{target_id}"
                    rows.append(self._base_record(
                        source_key,
                        source_type="subscene",
                        tag=self.story_service.scene_render_target_service.image_tag(story.slug, scene.slug, target_id),
                        label=f"{story.title} - {scene.title} - {definition.get('name') or target_id}",
                        image_path=str(image_path),
                        thumbnail_path=str(image_path),
                        semantic_category=category,
                        pipeline="Rendered Scene Subscene",
                        story_slug=story.slug,
                        scene_slug=scene.slug,
                        subscene_id=target_id,
                        candidate_pending=self.path_service.scene_subscene_candidate_path(story.slug, scene.slug, target_id).is_file(),
                        image_review_key=f"scene:{story.slug}:{scene.slug}:{target_id}",
                        inherited_identity=inherited_identity,
                        inherited_costume=inherited_costume,
                        costume_applicable=costume_applicable,
                    ))
        return rows

    def _pending_ids(self) -> set[str]:
        result = set()
        for path in self.ai_paths.task_paths("ask", "answer", "running"):
            manifest_path = path / "ask_manifest.json"
            if not manifest_path.exists() or (path / "harvest_manifest.json").exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if manifest.get("task_type") == self.TASK_TYPE:
                result.add(str(manifest.get("catalog_id") or ""))
        return result

    def _draft(self, catalog_id: str) -> dict:
        path = self.path_service.image_catalog_drafts_path() / f"{catalog_id}.json"
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def _materialize(self, source: dict, payload: dict, pending_ids: set[str]) -> ImageCatalogItem:
        metadata = payload.get("items", {}).get(source["source_key"], {})
        if metadata.get("catalog_id"):
            source = {**source, "catalog_id": str(metadata["catalog_id"])}
        sections = metadata.get("sections", {}) if isinstance(metadata.get("sections"), dict) else {}
        identity_meta = sections.get("identity", {}) if isinstance(sections.get("identity"), dict) else {}
        costume_meta = sections.get("costume", {}) if isinstance(sections.get("costume"), dict) else {}
        identity_mode = str(identity_meta.get("mode") or "inherit")
        costume_mode = str(costume_meta.get("mode") or ("inherit" if source["costume_applicable"] else "not_applicable"))
        if costume_mode == "inherit" and not source["costume_applicable"]:
            costume_mode = "not_applicable"
        identity_text = str(identity_meta.get("approved_text") or "") if identity_mode == "override" else str(source["inherited_identity"] or "")
        costume_text = str(costume_meta.get("approved_text") or "") if costume_mode == "override" else str(source["inherited_costume"] or "")
        draft = self._draft(source["catalog_id"])
        semantic_category = str(metadata.get("semantic_category") or source["semantic_category"])
        identity_status = "approved" if identity_mode == "override" and identity_text else "inherited" if identity_text else "missing"
        if costume_mode == "not_applicable":
            costume_status = "not_applicable"
        else:
            costume_status = "approved" if costume_mode == "override" and costume_text else "inherited" if costume_text else "missing"
        if source["catalog_id"] in pending_ids:
            description_status = "ai_queued"
        elif draft:
            description_status = "ai_review_required"
        elif identity_status == "missing" or costume_status == "missing":
            description_status = "missing"
        elif "approved" in {identity_status, costume_status}:
            description_status = "approved"
        else:
            description_status = "inherited"
        collections_by_id = {item.get("id"): item.get("label") for item in payload.get("collections", []) if isinstance(item, dict)}
        keywords_by_id = {item.get("id"): item.get("label") for item in payload.get("keywords", []) if isinstance(item, dict)}
        values = {key: value for key, value in source.items() if key not in {"semantic_category", "inherited_identity", "inherited_costume", "costume_applicable"}}
        return ImageCatalogItem(
            **values,
            semantic_category=str(metadata.get("semantic_category") or source["semantic_category"]),
            collections=[collections_by_id[item] for item in metadata.get("collection_ids", []) if item in collections_by_id],
            keywords=[keywords_by_id[item] for item in metadata.get("keyword_ids", []) if item in keywords_by_id],
            identity_text=identity_text,
            costume_text=costume_text,
            identity_status=identity_status,
            costume_status=costume_status,
            description_status=description_status,
            identity_mode=identity_mode,
            costume_mode=costume_mode,
            ai_draft_identity=str(draft.get("identity_preservation_scene") or ""),
            ai_draft_costume=(
                str(draft.get("identity_preservation_costume_scene") or "")
                if semantic_category == "Person"
                else ""
            ),
        )

    def list_items(self, **filters) -> list[ImageCatalogItem]:
        payload = self.repository.load()
        pending_ids = self._pending_ids()
        sources = [*self._discover_managed(payload), *self._discover_character_images(), *self._discover_scenes()]
        items = [self._materialize(source, payload, pending_ids) for source in sources]
        include_base = bool(filters.get("include_base", True))
        text_filter = str(filters.get("q") or "").strip().lower()
        result = []
        for item in items:
            if item.is_base_pipeline and not include_base:
                continue
            if filters.get("source_type") and item.source_type != filters["source_type"]:
                continue
            if filters.get("semantic_category") and item.semantic_category != filters["semantic_category"]:
                continue
            for field in ("character", "phase", "costume", "pipeline", "story_slug", "scene_slug", "subscene_id"):
                if filters.get(field) and str(getattr(item, field)).lower() != str(filters[field]).lower():
                    break
            else:
                if filters.get("collection") and filters["collection"] not in item.collections:
                    continue
                if filters.get("keyword") and filters["keyword"] not in item.keywords:
                    continue
                if filters.get("status") == "needs_identity" and item.identity_status != "missing":
                    continue
                if filters.get("status") == "needs_costume" and item.costume_status != "missing":
                    continue
                if filters.get("status") == "ready" and (
                    item.identity_status == "missing" or item.costume_status == "missing"
                ):
                    continue
                if filters.get("status") and filters["status"] not in {"needs_identity", "needs_costume", "ready"} and item.description_status != filters["status"]:
                    continue
                haystack = " ".join(str(value) for value in [item.tag, item.label, item.source_type, item.semantic_category, item.character, item.phase, item.costume, item.pipeline, item.view, item.story_slug, item.scene_slug, item.subscene_id, *item.collections, *item.keywords]).lower()
                if text_filter and not all(term in haystack for term in text_filter.split()):
                    continue
                result.append(item)
        return sorted(result, key=lambda item: (item.semantic_category.lower(), item.label.lower(), item.catalog_id))

    def get_item(self, catalog_id: str) -> ImageCatalogItem:
        item = next((item for item in self.list_items(include_base=True) if item.catalog_id == catalog_id), None)
        if item is None:
            raise ImageCatalogServiceError(f"Image catalog item {catalog_id} not found.")
        return item

    def item_for_tag(self, tag: str) -> ImageCatalogItem | None:
        return next((item for item in self.list_items(include_base=True) if item.tag == str(tag or "").strip()), None)

    def update_item(self, catalog_id: str, changes: dict) -> ImageCatalogItem:
        item = self.get_item(catalog_id)
        payload = self.repository.load()
        managed = payload.get("managed_images", {}).get(catalog_id)
        if "label" in changes or "reference_set_id" in changes:
            if not managed:
                raise ImageCatalogServiceError("Only imported images can change their label or reference set.")
            if "label" in changes:
                label = str(changes.get("label") or "").strip()
                if not label:
                    raise ImageCatalogServiceError("Image label is required.")
                managed["label"] = label
            if "reference_set_id" in changes:
                set_id = str(changes.get("reference_set_id") or "").strip()
                if set_id and set_id not in payload.get("reference_sets", {}):
                    raise ImageCatalogServiceError("Reference set not found.")
                managed["reference_set_id"] = set_id
            managed["updated_at"] = datetime.now().isoformat(timespec="seconds")
        metadata = dict(payload["items"].get(item.source_key, {}))
        category = changes.get("semantic_category")
        if category is not None:
            if category not in SEMANTIC_CATEGORIES:
                raise ImageCatalogServiceError("Invalid semantic category.")
            metadata["semantic_category"] = category
            if managed:
                managed["semantic_category"] = category
        for key in ("collection_ids", "keyword_ids"):
            if key in changes:
                vocabulary = "collections" if key == "collection_ids" else "keywords"
                valid_ids = {entry.get("id") for entry in payload.get(vocabulary, []) if isinstance(entry, dict)}
                requested = {str(value) for value in changes[key] if str(value)}
                if not requested <= valid_ids:
                    raise ImageCatalogServiceError(f"Unknown {vocabulary} selection.")
                metadata[key] = sorted(requested)
        sections = dict(metadata.get("sections") or {})
        for name in ("identity", "costume"):
            if name not in changes:
                continue
            current = dict(sections.get(name) or {})
            section_changes = changes[name] if isinstance(changes[name], dict) else {}
            mode = str(section_changes.get("mode") or current.get("mode") or "inherit")
            if mode not in SECTION_MODES or name == "identity" and mode == "not_applicable":
                raise ImageCatalogServiceError(f"Invalid {name} section mode.")
            current["mode"] = mode
            if "approved_text" in section_changes:
                current["approved_text"] = str(section_changes.get("approved_text") or "").strip()
                current["provenance"] = str(section_changes.get("provenance") or "manual")
            sections[name] = current
        metadata["sections"] = sections
        metadata["catalog_id"] = item.catalog_id
        metadata["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload["items"][item.source_key] = metadata
        self.repository.save(payload)
        return self.get_item(catalog_id)

    @staticmethod
    def _content_extension(content_type: str) -> str:
        normalized = str(content_type or "").split(";", 1)[0].strip().lower()
        extensions = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
        if normalized not in extensions:
            raise ImageCatalogServiceError("Image must be PNG, JPEG, WebP, or GIF.")
        return extensions[normalized]

    def _validate_reference_set(self, payload: dict, reference_set_id: str) -> str:
        set_id = str(reference_set_id or "").strip()
        if set_id and set_id not in payload.get("reference_sets", {}):
            raise ImageCatalogServiceError("Reference set not found.")
        return set_id

    def import_image(self, label: str, semantic_category: str, reference_set_id: str, image_bytes: bytes, content_type: str) -> ImageCatalogItem:
        cleaned_label = str(label or "").strip()
        if not cleaned_label:
            raise ImageCatalogServiceError("Image label is required.")
        if semantic_category not in SEMANTIC_CATEGORIES:
            raise ImageCatalogServiceError("Invalid semantic category.")
        if not image_bytes:
            raise ImageCatalogServiceError("Image content is required.")
        extension = self._content_extension(content_type)
        payload = self.repository.load()
        set_id = self._validate_reference_set(payload, reference_set_id)
        catalog_id = "img_" + uuid4().hex[:20]
        source_key = f"import:{catalog_id}"
        image_dir = self.path_service.image_catalog_images_path()
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{catalog_id}{extension}"
        image_path.write_bytes(image_bytes)
        now = datetime.now().isoformat(timespec="seconds")
        payload["managed_images"][catalog_id] = {
            "catalog_id": catalog_id,
            "source_key": source_key,
            "label": cleaned_label,
            "image_path": str(image_path),
            "mime_type": str(content_type).split(";", 1)[0].strip().lower(),
            "tag": f"{{{{IMAGE:{catalog_id}}}}}",
            "semantic_category": semantic_category,
            "reference_set_id": set_id,
            "created_at": now,
            "updated_at": now,
        }
        self.repository.save(payload)
        return self.get_item(catalog_id)

    def _trash_file(self, path: Path, catalog_id: str) -> None:
        if not path.is_file():
            return
        trash = self.path_service.image_catalog_trash_path()
        trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        shutil.move(str(path), str(trash / f"{catalog_id}_{stamp}{path.suffix.lower()}"))

    def replace_image_content(self, catalog_id: str, image_bytes: bytes, content_type: str) -> ImageCatalogItem:
        if not image_bytes:
            raise ImageCatalogServiceError("Image content is required.")
        extension = self._content_extension(content_type)
        payload = self.repository.load()
        record = payload.get("managed_images", {}).get(catalog_id)
        if not record:
            raise ImageCatalogServiceError("Only imported images can be replaced.")
        old_path = self.path_service.resolve_path(str(record.get("image_path") or ""))
        target_dir = old_path.parent if old_path.parent.exists() else self.path_service.image_catalog_images_path()
        target_dir.mkdir(parents=True, exist_ok=True)
        self._trash_file(old_path, catalog_id)
        new_path = target_dir / f"{catalog_id}{extension}"
        new_path.write_bytes(image_bytes)
        record["image_path"] = str(new_path)
        record["mime_type"] = str(content_type).split(";", 1)[0].strip().lower()
        record.pop("content_type", None)
        record["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.repository.save(payload)
        return self.get_item(catalog_id)

    def reference_locations(self, catalog_id: str) -> list[str]:
        item = self.get_item(catalog_id)
        roots = [
            Path(self.config.base_library_path) / name
            for name in ("Stories", "Characters", "Assets", "Pipelines")
        ]
        matches = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or "_backup" in path.parts or path.suffix.lower() not in {".json", ".md", ".toml", ".txt"}:
                    continue
                try:
                    if item.tag in path.read_text(encoding="utf-8", errors="ignore"):
                        matches.append(str(path))
                except OSError:
                    continue
        return sorted(set(matches))

    def delete_image(self, catalog_id: str, force: bool = False) -> dict:
        item = self.get_item(catalog_id)
        if not item.is_managed:
            raise ImageCatalogServiceError("Only imported images can be deleted.")
        if catalog_id in self._pending_ids():
            raise ImageCatalogServiceError("Image cannot be deleted while an AI description is pending.")
        references = self.reference_locations(catalog_id)
        if references and not force:
            raise ImageCatalogReferenceConflict(references)
        payload = self.repository.load()
        record = payload["managed_images"].pop(catalog_id)
        payload["items"].pop(item.source_key, None)
        self._trash_file(self.path_service.resolve_path(str(record.get("image_path") or "")), catalog_id)
        draft = self.path_service.image_catalog_drafts_path() / f"{catalog_id}.json"
        if draft.exists():
            draft.unlink()
        self.repository.save(payload)
        return {"catalog_id": catalog_id, "references": references}

    def list_reference_sets(self) -> list[dict]:
        payload = self.repository.load()
        counts = {key: 0 for key in payload.get("reference_sets", {})}
        for image in payload.get("managed_images", {}).values():
            set_id = str(image.get("reference_set_id") or "")
            if set_id in counts:
                counts[set_id] += 1
        return sorted(
            [{**record, "image_count": counts.get(set_id, 0)} for set_id, record in payload.get("reference_sets", {}).items()],
            key=lambda record: (str(record.get("label") or "").lower(), str(record.get("reference_set_id") or "")),
        )

    def save_reference_set(self, data: dict, reference_set_id: str = "") -> dict:
        payload = self.repository.load()
        label = str(data.get("label") or "").strip()
        if not label:
            raise ImageCatalogServiceError("Reference set label is required.")
        set_id = str(reference_set_id or "").strip()
        if set_id and set_id not in payload["reference_sets"]:
            raise ImageCatalogServiceError("Reference set not found.")
        if not set_id:
            base = self._slug(label)
            set_id = base
            index = 2
            while set_id in payload["reference_sets"]:
                set_id = f"{base}-{index}"
                index += 1
        current = dict(payload["reference_sets"].get(set_id) or {})
        now = datetime.now().isoformat(timespec="seconds")
        current.update({
            "reference_set_id": set_id,
            "label": label,
            "identity_text": str(data.get("identity_text") or "").strip(),
            "costume_text": str(data.get("costume_text") or "").strip(),
            "created_at": current.get("created_at") or now,
            "updated_at": now,
        })
        legacy_category = str(data.get("legacy_category") or current.get("legacy_category") or "").strip().lower()
        if legacy_category:
            if legacy_category not in {"person", "place", "thing"}:
                raise ImageCatalogServiceError("Reference set category must be person, place, or thing.")
            current["legacy_category"] = legacy_category
        payload["reference_sets"][set_id] = current
        self.repository.save(payload)
        return next(item for item in self.list_reference_sets() if item["reference_set_id"] == set_id)

    def delete_reference_set(self, reference_set_id: str) -> None:
        payload = self.repository.load()
        if reference_set_id not in payload.get("reference_sets", {}):
            raise ImageCatalogServiceError("Reference set not found.")
        if any(str(item.get("reference_set_id") or "") == reference_set_id for item in payload.get("managed_images", {}).values()):
            raise ImageCatalogServiceError("Reference set must be empty before it can be deleted.")
        del payload["reference_sets"][reference_set_id]
        self.repository.save(payload)

    def managed_item_for_tag(self, tag: str) -> ImageCatalogItem | None:
        cleaned = str(tag or "").strip()
        return next((item for item in self.list_items(include_base=True) if item.is_managed and item.tag == cleaned), None)

    def reference_set_sections(self, reference_set_id: str) -> dict:
        record = self.repository.load().get("reference_sets", {}).get(str(reference_set_id or ""), {})
        if not record:
            return {}
        return {
            "identity_preservation_core": str(record.get("identity_text") or ""),
            "identity_preservation_costume": str(record.get("costume_text") or ""),
            "identity_source": str(self.path_service.image_catalog_inventory_path()),
            "costume_source": str(self.path_service.image_catalog_inventory_path()),
        }

    def bulk_update(self, catalog_ids: list[str], changes: dict) -> list[ImageCatalogItem]:
        unique_ids = list(dict.fromkeys(catalog_ids))
        if "reference_set_id" in changes and any(not self.get_item(catalog_id).is_managed for catalog_id in unique_ids):
            raise ImageCatalogServiceError("Reference sets can only be assigned to imported images.")
        return [self.update_item(catalog_id, changes) for catalog_id in unique_ids]

    def _vocabulary(self, name: str) -> list[dict]:
        return [dict(item) for item in self.repository.load().get(name, []) if isinstance(item, dict)]

    def list_organization(self) -> dict:
        payload = self.repository.load()
        items = list(payload.get("items", {}).values())
        for name, membership in (("collections", "collection_ids"), ("keywords", "keyword_ids")):
            counts = {entry.get("id"): 0 for entry in payload.get(name, []) if isinstance(entry, dict)}
            for metadata in items:
                for entry_id in metadata.get(membership, []):
                    if entry_id in counts:
                        counts[entry_id] += 1
            for entry in payload.get(name, []):
                entry["usage_count"] = counts.get(entry.get("id"), 0)
        return {"collections": payload.get("collections", []), "keywords": payload.get("keywords", [])}

    def save_vocabulary(self, kind: str, label: str, entry_id: str = "") -> dict:
        if kind not in {"collections", "keywords"}:
            raise ImageCatalogServiceError("Invalid organization kind.")
        cleaned = str(label or "").strip()
        if not cleaned:
            raise ImageCatalogServiceError("Organization label is required.")
        payload = self.repository.load()
        target_id = entry_id or self._slug(cleaned)
        if not entry_id and any(item.get("id") == target_id for item in payload[kind]):
            raise ImageCatalogServiceError(f"{cleaned} already exists.")
        found = False
        for item in payload[kind]:
            if item.get("id") == target_id:
                item["label"] = cleaned
                found = True
        if not found:
            payload[kind].append({"id": target_id, "label": cleaned})
        payload[kind].sort(key=lambda item: str(item.get("label") or "").lower())
        self.repository.save(payload)
        return self.list_organization()

    def delete_vocabulary(self, kind: str, entry_id: str, merge_into: str = "") -> dict:
        if kind not in {"collections", "keywords"}:
            raise ImageCatalogServiceError("Invalid organization kind.")
        payload = self.repository.load()
        if merge_into and merge_into not in {item.get("id") for item in payload[kind]}:
            raise ImageCatalogServiceError("Merge target not found.")
        membership = "collection_ids" if kind == "collections" else "keyword_ids"
        payload[kind] = [item for item in payload[kind] if item.get("id") != entry_id]
        for metadata in payload["items"].values():
            values = [value for value in metadata.get(membership, []) if value != entry_id]
            if merge_into and merge_into not in values:
                values.append(merge_into)
            metadata[membership] = sorted(values)
        self.repository.save(payload)
        return self.list_organization()

    def queue_description(self, catalog_id: str) -> ImageCatalogItem:
        item = self.get_item(catalog_id)
        if item.description_status == "ai_queued":
            return item
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        ask_id = f"Ask_ImageCatalog_{catalog_id}_{stamp}"
        ask_path = self.ai_paths.file_proxy_client.create_staging(ask_id)
        suffix = Path(item.image_path).suffix or ".png"
        image_name = f"source{suffix.lower()}"
        shutil.copy2(item.image_path, ask_path / image_name)
        if item.semantic_category == "Person":
            prompt = f"""Analyze the supplied image as a reusable visual reference in the semantic category {item.semantic_category}.
Return concise, literal compiler text in both JSON fields.

IDENTITY_PRESERVATION_SCENE is required and must not be blank. Describe only stable physical identity: apparent age, build, face, skin, hair, eyes, species, proportions, and distinctive non-clothing features. Exclude clothing, armor, jewelry, carried objects, pose, expression, framing, camera, lighting, and background.

IDENTITY_PRESERVATION_COSTUME_SCENE describes only visible clothing, armor, footwear, jewelry, worn accessories, their colors/materials, and costume silhouette. Exclude face, body, build, skin, hair, eyes, species, pose, and carried objects. For a Person this field is required and must not be blank; describe every visible worn item.

Do not move physical identity details into the costume field."""
            schema = {
                "type": "object",
                "properties": {
                    "identity_preservation_scene": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Required stable visual identity only; never clothing, pose, or carried objects.",
                    },
                    "identity_preservation_costume_scene": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Visible clothing and worn accessories only; never physical identity or carried objects.",
                    },
                },
                "required": ["identity_preservation_scene", "identity_preservation_costume_scene"],
            }
        else:
            prompt = f"""Analyze the supplied image as a reusable visual reference in the semantic category {item.semantic_category}.
Return concise, literal compiler text in the JSON field.

IDENTITY_PRESERVATION_SCENE is required and must not be blank. Describe the stable defining visual features of the image subject. Exclude transient details such as pose, expression, framing, camera, lighting, and background.

Return only the requested JSON field."""
            schema = {
                "type": "object",
                "properties": {
                    "identity_preservation_scene": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Required stable defining visual features only; never transient scene details.",
                    },
                },
                "required": ["identity_preservation_scene"],
            }
        manifest = {
            "version": 1,
            "ask_id": ask_id,
            "asset_id": None,
            "character": "",
            "phase": "",
            "pipeline": "ImageCatalog",
            "pipeline_stage": "DESCRIPTION",
            "ollama_attempt_id": f"{stamp}_IMAGE_DESCRIPTION",
            "worker_type": "ollama_generate",
            "ollama_model": self.config.ai_image_description_model,
            "prompt_file": self.PROMPT_FILE,
            "expected_output": self.RESULT_FILE,
            "task_type": self.TASK_TYPE,
            "auxiliary": True,
            "manual": False,
            "target_output_file": f"{catalog_id}.json",
            "target_output_dir": str(self.path_service.image_catalog_drafts_path().resolve()),
            "catalog_id": catalog_id,
            "image_files": [image_name],
            "response_schema": schema,
        }
        (ask_path / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (ask_path / self.PROMPT_FILE).write_text(prompt + "\n", encoding="utf-8")
        self.ai_paths.file_proxy_client.publish(ask_path, ask_id, "ollama_generate")
        return self.get_item(catalog_id)

    def approve_draft(self, catalog_id: str, identity_text: str, costume_text: str, costume_not_applicable: bool = False) -> ImageCatalogItem:
        if not str(identity_text or "").strip():
            raise ImageCatalogServiceError("Identity description is required before approval.")
        if not costume_not_applicable and not str(costume_text or "").strip():
            raise ImageCatalogServiceError("Costume description is required before approval, or mark it not applicable.")
        changes = {
            "identity": {"mode": "override", "approved_text": identity_text, "provenance": "ai_reviewed"},
            "costume": {"mode": "not_applicable"} if costume_not_applicable else {"mode": "override", "approved_text": costume_text, "provenance": "ai_reviewed"},
        }
        self.update_item(catalog_id, changes)
        self.reject_draft(catalog_id)
        return self.get_item(catalog_id)

    def reject_draft(self, catalog_id: str) -> ImageCatalogItem:
        item = self.get_item(catalog_id)
        path = self.path_service.image_catalog_drafts_path() / f"{catalog_id}.json"
        if path.exists():
            path.unlink()
        return self.get_item(item.catalog_id)

    def payload(self, item: ImageCatalogItem) -> dict:
        return asdict(item)

    def rebind_source_prefix(self, old_prefix: str, new_prefix: str = "") -> None:
        """Move or retire catalog overlays when source services move or delete records."""
        payload = self.repository.load()
        changed = False
        for source_key in list(payload["items"]):
            if not source_key.startswith(old_prefix):
                continue
            metadata = payload["items"].pop(source_key)
            if new_prefix:
                payload["items"][new_prefix + source_key[len(old_prefix):]] = metadata
            changed = True
        if changed:
            self.repository.save(payload)
