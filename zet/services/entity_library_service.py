from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from zet.repositories.entity_library_repository import EntityLibraryRepository


ENTITY_TYPES = {
    "character", "person", "creature", "group", "location", "structure", "prop", "costume", "symbol"
}
VARIANT_TYPES = {"life_stage", "form", "state", "version"}
DESCRIPTOR_TYPES = {
    "human_description", "prompt_identity", "prompt_costume", "prompt_object", "prompt_background",
    "negative_guidance", "selection_notes",
}
ASSET_STATUSES = {"draft", "approved", "obsolete", "archived"}
RELATION_TYPES = {"part_of", "variant_of", "associated_with"}
ASSET_ROLES = {"primary_subject", "depicted_subject", "worn_costume", "held_prop", "location", "backdrop", "source"}
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


class EntityLibraryServiceError(Exception):
    """Report entity-library validation or lookup failures."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EntityLibraryService:
    """Manage library assets and the typed metadata that describes them."""

    def __init__(self, path_service, repository: EntityLibraryRepository):
        self.path_service = path_service
        self.repository = repository
        self.images_root = path_service.entity_library_images_path()
        self.pipeline_provider = None
        self._pipeline_signatures: dict[str, tuple[int, int]] = {}

    @staticmethod
    def _require(value: str, label: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise EntityLibraryServiceError(f"{label} is required.")
        return value

    @staticmethod
    def _dimensions(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
        if mime_type == "image/png" and len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if mime_type == "image/gif" and len(data) >= 10 and data[:3] == b"GIF":
            return struct.unpack("<HH", data[6:10])
        if mime_type == "image/jpeg" and data[:2] == b"\xff\xd8":
            index = 2
            while index + 9 < len(data):
                if data[index] != 0xFF:
                    index += 1
                    continue
                marker = data[index + 1]
                index += 2
                if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                    continue
                if index + 2 > len(data):
                    break
                segment_length = int.from_bytes(data[index:index + 2], "big")
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and index + 7 <= len(data):
                    return int.from_bytes(data[index + 5:index + 7], "big"), int.from_bytes(data[index + 3:index + 5], "big")
                if segment_length < 2:
                    break
                index += segment_length
        return None, None

    def _image_path(self, asset_id: str, file_name: str) -> Path:
        basename = Path(file_name).name
        return self.images_root / (f"{asset_id}{basename}" if basename.startswith(".") else basename)

    @staticmethod
    def _json(row: dict) -> dict:
        for key in ("width", "height", "rating"):
            if row.get(key) is None:
                continue
            row[key] = int(row[key])
        return row

    def _sync_pipeline_assets(self) -> None:
        if not callable(self.pipeline_provider):
            return
        items = self.pipeline_provider()
        active_origin_keys = set()
        for item in items:
            source_type = str(getattr(item, "source_type", ""))
            source_path = Path(str(getattr(item, "image_path", "")))
            if source_type == "local-pipeline" and source_path.is_file():
                checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
                origin_key = (f"local:{getattr(item, 'pipeline', '')}:{getattr(item, 'character', '')}:"
                              f"{getattr(item, 'phase', '')}:")
                legacy_origin_key = origin_key + checksum
                if str(getattr(item, "pipeline", "")).casefold() == "costume-dressing":
                    origin_key += f"{str(getattr(item, 'costume', '')).casefold()}:{str(getattr(item, 'view', '')).upper()}:"
                active_origin_keys.update((legacy_origin_key, origin_key + checksum))
        for item in items:
            if (
                getattr(item, "source_type", "") != "pipeline"
                or not getattr(item, "available", True)
                or getattr(item, "candidate_pending", False)
                or getattr(item, "asset_state", "LOCKED") != "LOCKED"
            ):
                continue
            source_path = Path(item.image_path)
            if not source_path.is_file():
                continue
            origin_key = str(item.tag)
            stat = source_path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if self._pipeline_signatures.get(origin_key) == signature:
                cached = self.repository.fetchall(
                    "SELECT origin_key FROM assets WHERE origin='pipeline' AND substr(origin_key,1,length(?)+1)=?||':'",
                    (origin_key, origin_key),
                )
                active_origin_keys.update(row["origin_key"] for row in cached)
                continue
            data = source_path.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            versioned_key = f"{origin_key}:{checksum}"
            active_origin_keys.add(versioned_key)
            current = self.repository.fetchone("SELECT asset_id FROM assets WHERE origin_key = ?", (versioned_key,))
            if current:
                self._pipeline_signatures[origin_key] = signature
                continue
            mime_type = str(item.mime_type or "image/png").lower()
            extension = IMAGE_TYPES.get(mime_type, source_path.suffix.lower() or ".png")
            asset_id = str(uuid4())
            width, height = self._dimensions(data, mime_type)
            target = self._image_path(asset_id, extension)
            self.images_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
            stamp = _now()
            with self.repository.transaction() as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO assets(asset_id, label, checksum, file_name, mime_type, width, height, origin, origin_key, status, notes, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (asset_id, str(item.label), checksum, target.name, mime_type, width, height, "pipeline", versioned_key, "approved", "Locked pipeline asset", stamp, stamp),
                )
                character = str(getattr(item, "character", "") or "").strip()
                phase = str(getattr(item, "phase", "") or "").strip()
                for entity_name, entity_type, role in ((character, "character", "primary_subject"), (str(getattr(item, "costume", "") or "").strip(), "costume", "worn_costume")):
                    if not entity_name:
                        continue
                    entity = connection.execute("SELECT entity_id FROM entities WHERE lower(name)=lower(?) AND entity_type=?", (entity_name, entity_type)).fetchone()
                    if not entity:
                        entity = connection.execute("SELECT entity_id FROM entity_name_aliases WHERE lower(name)=lower(?) AND entity_type=?", (entity_name, entity_type)).fetchone()
                    entity_id = entity[0] if entity else str(uuid4())
                    if not entity:
                        connection.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?)", (entity_id, entity_name, entity_type, "", "active", stamp, stamp))
                    variant_id = None
                    if entity_type == "character" and phase:
                        variant = connection.execute("SELECT variant_id FROM variants WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'", (entity_id, phase)).fetchone()
                        if not variant:
                            variant = connection.execute("SELECT variant_id FROM variant_name_aliases WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'", (entity_id, phase)).fetchone()
                        variant_id = variant[0] if variant else str(uuid4())
                        if not variant:
                            connection.execute("INSERT INTO variants VALUES(?,?,?,?,?,?,?)", (variant_id, entity_id, phase, "life_stage", "", stamp, stamp))
                    connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (asset_id, entity_id, variant_id, role))
                connection.execute(
                    "INSERT INTO provenance(provenance_id,asset_id,relation_type,details_json,created_at) VALUES(?,?,?,?,?)",
                    (str(uuid4()), asset_id, "locked_pipeline_source", json.dumps({"tag": origin_key, "label": item.label}), stamp),
                )
            self._pipeline_signatures[origin_key] = signature
        if active_origin_keys:
            placeholders = ",".join("?" for _ in active_origin_keys)
            with self.repository.transaction() as connection:
                connection.execute(
                    f"UPDATE assets SET status='archived',updated_at=? "
                    f"WHERE origin='pipeline' AND status<>'archived' AND origin_key NOT IN ({placeholders})",
                    (_now(), *sorted(active_origin_keys)),
                )
        else:
            with self.repository.transaction() as connection:
                connection.execute(
                    "UPDATE assets SET status='archived',updated_at=? WHERE origin='pipeline' AND status<>'archived'",
                    (_now(),),
                )

    def list_assets(self, **filters) -> list[dict]:
        self._sync_pipeline_assets()
        include_archived = bool(filters.pop("include_archived", False))
        hide_obsolete = bool(filters.pop("hide_obsolete", False))
        rows = self.repository.fetchall("SELECT * FROM assets ORDER BY created_at DESC, asset_id")
        if not rows:
            return []
        asset_ids = tuple(row["asset_id"] for row in rows)
        placeholders = ",".join("?" for _ in asset_ids)
        entities_by_asset: dict[str, list[dict]] = {}
        for item in self.repository.fetchall(
            f"SELECT ae.asset_id,e.entity_id,e.name,e.entity_type,ae.role,ae.variant_id,v.name AS variant_name "
            f"FROM asset_entities ae JOIN entities e ON e.entity_id=ae.entity_id "
            f"LEFT JOIN variants v ON v.variant_id=ae.variant_id WHERE ae.asset_id IN ({placeholders}) ORDER BY e.name",
            asset_ids,
        ):
            entities_by_asset.setdefault(item["asset_id"], []).append(item)
        sets_by_asset: dict[str, list[dict]] = {}
        for item in self.repository.fetchall(
            f"SELECT sa.asset_id,s.set_id,s.name,sa.role,sa.sort_order FROM reference_set_assets sa "
            f"JOIN reference_sets s ON s.set_id=sa.set_id WHERE sa.asset_id IN ({placeholders}) "
            f"ORDER BY sa.sort_order,s.name",
            asset_ids,
        ):
            sets_by_asset.setdefault(item["asset_id"], []).append(item)
        facets_by_asset: dict[str, list[dict]] = {}
        for item in self.repository.fetchall(
            f"SELECT af.asset_id,f.namespace,f.value FROM asset_facets af "
            f"JOIN facets f ON f.facet_id=af.facet_id WHERE af.asset_id IN ({placeholders}) "
            f"ORDER BY f.namespace,f.value",
            asset_ids,
        ):
            facets_by_asset.setdefault(item["asset_id"], []).append(item)
        tags_by_asset: dict[str, list[str]] = {}
        for item in self.repository.fetchall(
            f"SELECT asset_id,tag FROM asset_tags WHERE asset_id IN ({placeholders}) ORDER BY tag",
            asset_ids,
        ):
            tags_by_asset.setdefault(item["asset_id"], []).append(item["tag"])
        references_by_asset: dict[str, list[dict]] = {}
        for item in self.repository.fetchall(
            f"SELECT reference_key,label,set_id,status,asset_id FROM logical_references "
            f"WHERE asset_id IN ({placeholders}) ORDER BY reference_key",
            asset_ids,
        ):
            references_by_asset.setdefault(item["asset_id"], []).append({
                key: item[key] for key in ("reference_key", "label", "set_id", "status")
            })
        descriptor_assets = {
            item["asset_id"]
            for item in self.repository.fetchall(
                f"SELECT DISTINCT a.asset_id FROM assets a JOIN descriptors d ON d.enabled=1 "
                f"AND d.descriptor_type IN ('prompt_identity','prompt_object','prompt_background','human_description') "
                f"LEFT JOIN asset_entities ae ON ae.asset_id=a.asset_id "
                f"LEFT JOIN reference_set_assets rsa ON rsa.asset_id=a.asset_id "
                f"WHERE a.asset_id IN ({placeholders}) AND ((d.owner_type='asset' AND d.owner_id=a.asset_id) "
                f"OR (d.owner_type='entity' AND d.owner_id=ae.entity_id) "
                f"OR (d.owner_type='variant' AND d.owner_id=ae.variant_id) "
                f"OR (d.owner_type='set' AND d.owner_id=rsa.set_id))",
                asset_ids,
            )
        }
        output = []
        query = str(filters.get("q") or "").casefold().split()
        for row in rows:
            asset_id = row["asset_id"]
            path = self._image_path(asset_id, row["file_name"])
            if not path.is_file():
                continue
            entities = entities_by_asset.get(asset_id, [])
            sets = sets_by_asset.get(asset_id, [])
            facets = facets_by_asset.get(asset_id, [])
            tags = tags_by_asset.get(asset_id, [])
            logical_references = references_by_asset.get(asset_id, [])
            logical = next((reference for reference in logical_references if reference["status"] == "active"), None)
            if row["status"] != "approved":
                logical = None
            item = {**row, "image_path": str(path), "thumbnail_path": str(path), "entities": entities, "sets": sets, "facets": facets, "tags": tags, "logical_reference": logical, "logical_references": logical_references}
            item["descriptor_ready"] = asset_id in descriptor_assets
            if row["status"] == "archived" and filters.get("status") != "archived" and not include_archived:
                continue
            if row["status"] == "obsolete" and filters.get("status") != "obsolete" and hide_obsolete:
                continue
            if filters.get("status") and row["status"] != filters["status"]:
                continue
            if filters.get("origin") and row["origin"] != filters["origin"]:
                continue
            if filters.get("entity_id") and not any(value["entity_id"] == filters["entity_id"] for value in entities):
                continue
            if filters.get("entity_type") and not any(value["entity_type"] == filters["entity_type"] for value in entities):
                continue
            if filters.get("variant_id") and not any(value["variant_id"] == filters["variant_id"] for value in entities):
                continue
            if filters.get("set_id") and not any(value["set_id"] == filters["set_id"] for value in sets):
                continue
            if filters.get("facet_namespace") and not any(value["namespace"] == filters["facet_namespace"] for value in facets):
                continue
            if filters.get("facet_value") and not any(value["value"] == filters["facet_value"] for value in facets):
                continue
            haystack = " ".join([row["label"], row["file_name"], row["origin"], row["notes"], logical["reference_key"] if logical else "", *[value["name"] for value in entities], *[value["variant_name"] or "" for value in entities], *[value["name"] for value in sets], *tags, *[f'{value["namespace"]}:{value["value"]}' for value in facets]]).casefold()
            if query and not all(term in haystack for term in query):
                continue
            output.append(self._json(item))
        return output

    def image_binding(self, asset_id: str) -> dict:
        """Resolve an already chosen image without inventory scans or prompt metadata."""
        item = self.repository.fetchone("SELECT asset_id,label,file_name FROM assets WHERE asset_id=?", (asset_id,))
        if item is None:
            raise EntityLibraryServiceError(f"Image asset not found: {asset_id}")
        path = self._image_path(asset_id, item["file_name"])
        if not path.is_file():
            raise EntityLibraryServiceError(f"Reference image is unavailable: {asset_id}")
        return {**item, "image_path": str(path)}

    def get_asset(self, asset_id: str) -> dict:
        item = next((row for row in self.list_assets(include_archived=True) if row["asset_id"] == asset_id), None)
        if item is None:
            raise EntityLibraryServiceError(f"Image asset not found: {asset_id}")
        item["descriptors"] = self.repository.fetchall(
            "SELECT * FROM descriptors WHERE owner_type='asset' AND owner_id=? ORDER BY priority,descriptor_type", (asset_id,)
        )
        item["provenance"] = self.repository.fetchall("SELECT * FROM provenance WHERE asset_id=? ORDER BY created_at", (asset_id,))
        item["usages"] = self.usage_for_asset(asset_id)
        return item

    def import_asset(self, label: str, mime_type: str, data: bytes, *, notes: str = "", prompt: str = "", negative_prompt: str = "", entity_ids: list[str] | None = None, set_ids: list[str] | None = None, origin: str = "import", origin_key: str | None = None, entity_role: str = "depicted_subject", provenance_details: dict | None = None) -> dict:
        label = self._require(label, "Image label")
        mime_type = str(mime_type or "").split(";")[0].strip().lower()
        if mime_type not in IMAGE_TYPES or not data:
            raise EntityLibraryServiceError("Choose a non-empty PNG, JPEG, WEBP, or GIF image.")
        checksum = hashlib.sha256(data).hexdigest()
        if origin_key:
            existing = self.repository.fetchone("SELECT asset_id FROM assets WHERE origin_key=?", (origin_key,))
            if existing:
                return self.get_asset(existing["asset_id"])
        asset_id = str(uuid4())
        stamp = _now()
        extension = IMAGE_TYPES[mime_type]
        path = self._image_path(asset_id, extension)
        self.images_root.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        width, height = self._dimensions(data, mime_type)
        try:
            with self.repository.transaction() as connection:
                connection.execute(
                    "INSERT INTO assets(asset_id,label,checksum,file_name,mime_type,width,height,origin,origin_key,status,notes,prompt,negative_prompt,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (asset_id, label, checksum, path.name, mime_type, width, height, origin, origin_key, "approved", notes.strip(), str(prompt or "").strip(), str(negative_prompt or "").strip(), stamp, stamp),
                )
                self._link_assets(connection, asset_id, entity_ids or [], set_ids or [], entity_role=entity_role)
                if provenance_details is not None:
                    connection.execute(
                        "INSERT INTO provenance(provenance_id,asset_id,relation_type,details_json,created_at) VALUES(?,?,?,?,?)",
                        (str(uuid4()), asset_id, "generated_from", json.dumps(provenance_details), stamp),
                    )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.get_asset(asset_id)

    def import_generated_image(self, label: str, mime_type: str, data: bytes, *, entity_id: str, reference_role: str, provenance: str, prompt: str = "", negative_prompt: str = "") -> dict:
        """Import a generated image with its entity, reference role, and provenance atomically."""
        entity_id = self._require(entity_id, "Entity")
        reference_role = self._require(reference_role, "Reference role")
        if reference_role not in ASSET_ROLES:
            raise EntityLibraryServiceError(f"Invalid reference role: {reference_role}")
        if not self.repository.fetchone("SELECT entity_id FROM entities WHERE entity_id=?", (entity_id,)):
            raise EntityLibraryServiceError(f"Entity not found: {entity_id}")
        mime_type = str(mime_type or "").split(";")[0].strip().lower()
        if mime_type not in IMAGE_TYPES or not data:
            raise EntityLibraryServiceError("Choose a non-empty PNG, JPEG, WEBP, or GIF image.")
        checksum = hashlib.sha256(data).hexdigest()
        origin_key = f"imagegen:{checksum}"
        existing = self.repository.fetchone("SELECT asset_id FROM assets WHERE origin='imagegen' AND checksum=?", (checksum,))
        if existing:
            return {"asset": self.get_asset(existing["asset_id"]), "duplicate": True}
        asset = self.import_asset(
            label, mime_type, data, origin="imagegen", origin_key=origin_key,
            entity_ids=[entity_id], entity_role=reference_role,
            prompt=prompt, negative_prompt=negative_prompt,
            provenance_details={"source": "local_image_generation", "details": str(provenance or "").strip()},
        )
        return {"asset": asset, "duplicate": False}

    def register_locked_pipeline_image(self, source: Path, *, label: str, pipeline: str, character: str, phase: str, checksum: str,
                                       costume: str = "", view: str = "", reference_key: str = "") -> dict:
        """Publish one verified local candidate into permanent ID-addressed storage."""
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != checksum:
            raise EntityLibraryServiceError("The selected image changed before it could be locked.")
        import mimetypes
        mime_type = mimetypes.guess_type(source.name)[0] or "image/png"
        key = f"local:{pipeline}:{character}:{phase}:"
        if str(pipeline).casefold() == "costume-dressing":
            key += f"{str(costume).casefold()}:{str(view).upper()}:"
        key += checksum
        asset = self.import_asset(label, mime_type, data, origin="pipeline", origin_key=key, notes="Locked local pipeline image")
        if str(pipeline).casefold() == "costume-dressing" and costume and view:
            return self.classify_costume_image(asset["asset_id"], character=character, phase=phase,
                                                costume=costume, view=view, reference_key=reference_key)
        return asset

    @staticmethod
    def logical_costume_reference_key(character: str, phase: str, costume: str, view: str) -> str:
        def part(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")
        return ".".join((part(character), part(phase), "costume-dressing", part(costume), part(view)))

    def classify_costume_image(self, asset_id: str, *, character: str, phase: str, costume: str, view: str,
                               reference_key: str = "", preserve_active_reference: bool = False) -> dict:
        """Classify a locked costume image and point its stable reference at it."""
        costume = str(costume or "").replace("_", " ").strip()
        view = str(view or "").replace("_", " ").strip()
        label = " · ".join(value for value in (character, phase, costume, view.title()) if value)
        stamp = _now()
        with self.repository.transaction() as connection:
            asset = connection.execute("SELECT asset_id,label FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
            if not asset:
                raise EntityLibraryServiceError(f"Image asset not found: {asset_id}")
            names = ((character, "character", "primary_subject"), (costume, "costume", "worn_costume"))
            variant_id = None
            for name, entity_type, role in names:
                if not name:
                    continue
                entity = connection.execute("SELECT entity_id FROM entities WHERE lower(name)=lower(?) AND entity_type=?", (name, entity_type)).fetchone()
                entity_id = entity["entity_id"] if entity else str(uuid4())
                if not entity:
                    connection.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?)", (entity_id, name, entity_type, "", "active", stamp, stamp))
                if entity_type == "character":
                    variant = connection.execute("SELECT variant_id FROM variants WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'", (entity_id, phase)).fetchone()
                    variant_id = variant["variant_id"] if variant else str(uuid4())
                    if not variant:
                        connection.execute("INSERT INTO variants VALUES(?,?,?,?,?,?,?)", (variant_id, entity_id, phase, "life_stage", "", stamp, stamp))
                connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (asset_id, entity_id, variant_id if entity_type == "character" else None, role))
            for namespace, value in (("pipeline", "costume-dressing"), ("view", view)):
                if not value:
                    continue
                facet = connection.execute("SELECT facet_id FROM facets WHERE namespace=? AND lower(value)=lower(?)", (namespace, value)).fetchone()
                facet_id = facet["facet_id"] if facet else str(uuid4())
                if not facet:
                    connection.execute("INSERT INTO facets VALUES(?,?,?,?)", (facet_id, namespace, value, 1))
                connection.execute("INSERT OR IGNORE INTO asset_facets(asset_id,facet_id) VALUES(?,?)", (asset_id, facet_id))
            if asset["label"] != label:
                connection.execute("UPDATE assets SET label=?,updated_at=? WHERE asset_id=?", (label, stamp, asset_id))
        key = reference_key or self.logical_costume_reference_key(character, phase, costume, view)
        current_reference = self.repository.fetchone("SELECT label,asset_id,status FROM logical_references WHERE reference_key=?", (key,))
        if not current_reference:
            self.save_logical_reference({"reference_key": key, "label": label, "asset_id": asset_id})
        elif not preserve_active_reference and (
            current_reference["label"] != label
            or current_reference["asset_id"] != asset_id
            or current_reference["status"] != "active"
        ):
            self.save_logical_reference({"reference_key": key, "label": label, "asset_id": asset_id})
        return self.get_asset(asset_id)

    def backfill_costume_references(self, *, dry_run: bool = True) -> dict:
        """Classify current costume locks and migrate scene tags that name an exact slot."""
        root = Path(self.path_service.config.base_library_path)
        slots: dict[tuple[str, str, str, str], dict] = {}
        assets = scenes = 0
        for store_path in (root / "_state" / "LocalAssets").glob("*/*/local_assets.json"):
            character, phase = store_path.parent.parent.name, store_path.parent.name
            try:
                data = json.loads(store_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for local_key, record in (data.get("assets") or {}).items():
                if (str(record.get("pipeline") or "").casefold() != "costume-dressing"
                        or not record.get("locked") or record.get("stale")):
                    continue
                costume, view = str(record.get("qualifier") or ""), str(record.get("view") or "")
                asset_id = str(record.get("entity_library_asset_id") or "")
                if not costume or not view or not asset_id:
                    continue
                slot = (character.casefold(), phase.casefold(), costume.replace("_", " ").casefold(), view.replace("_", " ").casefold())
                key = str(record.get("reference_key") or self.logical_costume_reference_key(character, phase, costume, view))
                slots[slot] = {"character": character, "phase": phase, "costume": costume, "view": view,
                               "asset_id": asset_id, "reference_key": key, "store_path": store_path,
                               "local_key": local_key, "record": record}
                if not dry_run:
                    self.classify_costume_image(asset_id, character=character, phase=phase, costume=costume,
                                                view=view, reference_key=key, preserve_active_reference=True)
                    if record.get("reference_key") != key:
                        from zet.services.atomic_file_service import write_json_atomic
                        record["reference_key"] = key
                        write_json_atomic(store_path, data)
                assets += 1

        def target_for(tag: str, asset_id: str = "") -> dict | None:
            if asset_id:
                matches = [slot for slot in slots.values() if slot["asset_id"] == asset_id]
                return matches[0] if len(matches) == 1 else None
            raw = tag.strip().removeprefix("{{").removesuffix("}}")
            parts = raw.split(":")
            if len(parts) >= 4 and parts[0] == "LOCAL":
                local_key = ":".join(parts[3:]).casefold()
                return next((slot for slot in slots.values() if slot["local_key"].casefold() == local_key
                             and slot["character"].casefold() == parts[1].casefold()
                             and slot["phase"].casefold() == parts[2].casefold()), None)
            if len(parts) == 5 and parts[0] == "ASSET":
                character, phase = parts[1], parts[2]
                descriptors = [part.strip() for part in parts[4].split("|")]
                if len(descriptors) < 3 or "costume" not in descriptors[0].casefold():
                    return None
                view_token = re.sub(r"[^a-z0-9]+", "", descriptors[1].casefold())
                matches = [slot for slot in slots.values()
                           if slot["character"].casefold() == character.casefold()
                           and slot["phase"].casefold() == phase.casefold()
                           and slot["costume"].replace("_", " ").casefold() == descriptors[2].replace("_", " ").casefold()
                           and re.sub(r"[^a-z0-9]+", "", slot["view"].casefold()) == view_token]
                return matches[0] if len(matches) == 1 else None
            return None

        changed = []
        for scene_path in (root / "Stories").glob("*/*.scene.json"):
            try:
                document = json.loads(scene_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            updated = copy.deepcopy(document)
            count = 0
            for element in updated.get("scene_elements", []):
                for reference in element.get("reference_images", []):
                    tag = str(reference.get("tag") or "")
                    target = target_for(tag, str(reference.get("asset_id") or "")) if tag or reference.get("asset_id") else None
                    if not target:
                        continue
                    if element.get("character") and str(element["character"]).casefold() != target["character"].casefold():
                        continue
                    if element.get("phase") and str(element["phase"]).casefold() != target["phase"].casefold():
                        continue
                    if element.get("costume") and str(element["costume"]).replace("_", " ").casefold() != target["costume"].replace("_", " ").casefold():
                        continue
                    reference.pop("tag", None)
                    reference.pop("asset_id", None)
                    reference["reference_key"] = target["reference_key"]
                    count += 1
            if count:
                changed.append((scene_path, updated, count))
                scenes += count
        if not dry_run:
            for path, document, _ in changed:
                backup_dir = path.parent / "_backup"
                backup_dir.mkdir(exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                shutil.copy2(path, backup_dir / f"{path.stem}.{stamp}.json")
                from zet.services.atomic_file_service import write_json_atomic
                write_json_atomic(path, document)
        return {"dry_run": dry_run, "costume_images": assets, "scene_references": scenes,
                "scenes_changed": len(changed)}
        stamp = _now()
        with self.repository.transaction() as connection:
            entity = connection.execute("SELECT entity_id FROM entities WHERE lower(name)=lower(?) AND entity_type='character'", (character,)).fetchone()
            entity_id = entity["entity_id"] if entity else str(uuid4())
            if not entity:
                connection.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?)", (entity_id, character, "character", "", "active", stamp, stamp))
            variant = connection.execute("SELECT variant_id FROM variants WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'", (entity_id, phase)).fetchone()
            variant_id = variant["variant_id"] if variant else str(uuid4())
            if not variant:
                connection.execute("INSERT INTO variants VALUES(?,?,?,?,?,?,?)", (variant_id, entity_id, phase, "life_stage", "", stamp, stamp))
            connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (asset["asset_id"], entity_id, variant_id, "primary_subject"))
        return asset

    @staticmethod
    def _link_assets(connection, asset_id: str, entity_ids: list[str], set_ids: list[str], *, entity_role: str = "depicted_subject") -> None:
        for entity_id in entity_ids:
            connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,role) VALUES(?,?,?)", (asset_id, entity_id, entity_role))
        for order, set_id in enumerate(set_ids):
            connection.execute("INSERT OR IGNORE INTO reference_set_assets(set_id,asset_id,role,sort_order) VALUES(?,?,?,?)", (set_id, asset_id, "member", order))

    def replace_asset(self, asset_id: str, mime_type: str, data: bytes) -> dict:
        original = self.get_asset(asset_id)
        created = self.import_asset(original["label"], mime_type, data, notes=f"Replacement for {asset_id}")
        if created["asset_id"] == asset_id:
            return created
        stamp = _now()
        with self.repository.transaction() as connection:
            connection.execute("UPDATE assets SET replacement_for_asset_id=? WHERE asset_id=?", (asset_id, created["asset_id"]))
            direct_usages = connection.execute("SELECT 1 FROM asset_usages WHERE asset_id=? AND status='current' LIMIT 1", (asset_id,)).fetchone()
            if not direct_usages:
                connection.execute("UPDATE assets SET status='obsolete',updated_at=? WHERE asset_id=?", (stamp, asset_id))
            connection.execute("INSERT INTO provenance(provenance_id,asset_id,relation_type,source_asset_id,created_at) VALUES(?,?,?,?,?)", (str(uuid4()), created["asset_id"], "replacement_for", asset_id, stamp))
            connection.execute("UPDATE logical_references SET asset_id=?,updated_at=? WHERE asset_id=?", (created["asset_id"], stamp, asset_id))
            for entity in original["entities"]:
                connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (created["asset_id"], entity["entity_id"], entity["variant_id"], entity["role"]))
            for member in original["sets"]:
                connection.execute("INSERT OR IGNORE INTO reference_set_assets(set_id,asset_id,role,sort_order) VALUES(?,?,?,?)", (member["set_id"], created["asset_id"], member["role"], member["sort_order"]))
            connection.execute("INSERT OR IGNORE INTO asset_facets(asset_id,facet_id) SELECT ?,facet_id FROM asset_facets WHERE asset_id=?", (created["asset_id"], asset_id))
            connection.execute("INSERT OR IGNORE INTO asset_tags(asset_id,tag) SELECT ?,tag FROM asset_tags WHERE asset_id=?", (created["asset_id"], asset_id))
        return self.get_asset(created["asset_id"])

    def apply_generated_image(self, asset_id: str, expected_checksum: str, mime_type: str, data: bytes,
                              prompt: str, negative_prompt: str, request_id: str, result_index: int) -> dict:
        asset = self.get_asset(asset_id)
        prior = self.repository.fetchone(
            "SELECT details_json FROM provenance WHERE asset_id=? AND relation_type='image_generation_update' ORDER BY created_at DESC LIMIT 1",
            (asset_id,),
        )
        if prior:
            try:
                applied = json.loads(prior["details_json"])
                if applied.get("request_id") == request_id and applied.get("result_index") == result_index:
                    return asset
            except (TypeError, json.JSONDecodeError):
                pass
        if asset["origin"] == "pipeline" or asset["status"] == "archived":
            raise EntityLibraryServiceError("Only available, non-pipeline images can be modified.")
        if asset["checksum"] != expected_checksum:
            raise EntityLibraryServiceError("The source image changed. Reopen Image Generation from the current image.")
        try:
            if hashlib.sha256(Path(asset["image_path"]).read_bytes()).hexdigest() != expected_checksum:
                raise EntityLibraryServiceError("The source image changed. Reopen Image Generation from the current image.")
        except OSError as exc:
            raise EntityLibraryServiceError("The source image is unavailable. Reopen Image Generation from the current image.") from exc
        mime_type = str(mime_type or "").split(";", 1)[0].strip().lower()
        if not data or mime_type not in IMAGE_TYPES:
            raise EntityLibraryServiceError("Choose a valid generated image.")
        checksum = hashlib.sha256(data).hexdigest()
        width, height = self._dimensions(data, mime_type)
        revision = f"{asset_id}_{checksum}{IMAGE_TYPES[mime_type]}"
        staged = self.images_root / revision
        self.images_root.mkdir(parents=True, exist_ok=True)
        if not staged.is_file() or hashlib.sha256(staged.read_bytes()).hexdigest() != checksum:
            temporary = staged.with_name(staged.name + "." + uuid4().hex + ".tmp")
            try:
                temporary.write_bytes(data)
                temporary.replace(staged)
            finally:
                temporary.unlink(missing_ok=True)
        stamp = _now()
        try:
            with self.repository.transaction() as connection:
                current = connection.execute(
                    "SELECT checksum,file_name,origin,origin_key,status FROM assets WHERE asset_id=?", (asset_id,)
                ).fetchone()
                if not current or current["status"] == "archived" or current["origin"] == "pipeline":
                    raise EntityLibraryServiceError("This image can no longer be modified.")
                if current["checksum"] != expected_checksum:
                    raise EntityLibraryServiceError("The source image changed. Reopen Image Generation from the current image.")
                current_path = self._image_path(asset_id, current["file_name"])
                try:
                    current_checksum = hashlib.sha256(current_path.read_bytes()).hexdigest()
                except OSError as exc:
                    raise EntityLibraryServiceError("The source image is unavailable. Reopen Image Generation from the current image.") from exc
                if current_checksum != expected_checksum:
                    raise EntityLibraryServiceError("The source image changed. Reopen Image Generation from the current image.")
                details = {"request_id": request_id, "result_index": result_index,
                           "previous_file": current["file_name"], "previous_checksum": current["checksum"]}
                connection.execute(
                    "UPDATE assets SET checksum=?,file_name=?,mime_type=?,width=?,height=?,prompt=?,negative_prompt=?,origin_key=CASE WHEN origin_key LIKE 'imagegen:%' THEN NULL ELSE origin_key END,updated_at=? WHERE asset_id=?",
                    (checksum, revision, mime_type, width, height, prompt.strip(), negative_prompt.strip(), stamp, asset_id),
                )
                connection.execute(
                    "INSERT INTO provenance(provenance_id,asset_id,relation_type,details_json,created_at) VALUES(?,?,?,?,?)",
                    (str(uuid4()), asset_id, "image_generation_update", json.dumps(details), stamp),
                )
        except Exception:
            referenced = self.repository.fetchone(
                "SELECT 1 AS found FROM assets WHERE asset_id=? AND file_name=?", (asset_id, revision)
            )
            if not referenced:
                staged.unlink(missing_ok=True)
            raise
        return self.get_asset(asset_id)

    def set_asset_status(self, asset_id: str, status: str) -> dict:
        if status not in ASSET_STATUSES:
            raise EntityLibraryServiceError("Invalid image status.")
        if status == "archived":
            usages = self.usage_for_asset(asset_id)
            if usages:
                raise EntityLibraryServiceError(
                    f"Image has {len(usages)} current consumer(s); update those consumers before archiving it."
                )
        with self.repository.transaction() as connection:
            if status == "archived":
                connection.execute(
                    "UPDATE logical_references SET status='inactive',updated_at=? WHERE asset_id=? AND status='active'",
                    (_now(), asset_id),
                )
            cursor = connection.execute("UPDATE assets SET status=?,updated_at=? WHERE asset_id=?", (status, _now(), asset_id))
            if not cursor.rowcount:
                raise EntityLibraryServiceError(f"Image asset not found: {asset_id}")
        return self.get_asset(asset_id)

    def update_asset(self, asset_id: str, data: dict) -> dict:
        current = self.get_asset(asset_id)
        stamp = _now()
        requested_status = str(data.get("status", current["status"]) or "").strip()
        if current["status"] == "approved" and requested_status not in {"approved", "archived"}:
            usages = self.usage_for_asset(asset_id)
            references = self.repository.fetchall("SELECT reference_key FROM logical_references WHERE asset_id=? AND status='active'", (asset_id,))
            if usages or references:
                raise EntityLibraryServiceError("Resolve current consumers and preferred references before changing this image from approved status.")
        if requested_status == "archived":
            usages = self.usage_for_asset(asset_id)
            if usages:
                raise EntityLibraryServiceError(
                    f"Image has {len(usages)} current consumer(s); update those consumers before archiving it."
                )
        with self.repository.transaction() as connection:
            label = str(data.get("label", current["label"]) or "").strip()
            notes = str(data.get("notes", current["notes"]) or "").strip()
            status = requested_status
            if not label:
                raise EntityLibraryServiceError("Image label is required.")
            if status not in ASSET_STATUSES:
                raise EntityLibraryServiceError("Invalid image status.")
            if status == "archived":
                connection.execute(
                    "UPDATE logical_references SET status='inactive',updated_at=? WHERE asset_id=? AND status='active'",
                    (stamp, asset_id),
                )
            connection.execute("UPDATE assets SET label=?,notes=?,status=?,rating=?,prompt=?,negative_prompt=?,updated_at=? WHERE asset_id=?",
                               (label, notes, status, data.get("rating", current["rating"]),
                                str(data.get("prompt", current.get("prompt", "")) or "").strip(),
                                str(data.get("negative_prompt", current.get("negative_prompt", "")) or "").strip(),
                                stamp, asset_id))
            if "entity_links" in data:
                existing_links = {(item["entity_id"], item["role"]): item for item in current["entities"]}
                connection.execute("DELETE FROM asset_entities WHERE asset_id=?", (asset_id,))
                for link in data.get("entity_links") or []:
                    if isinstance(link, str):
                        link = {"entity_id": link}
                    previous = next((value for (entity_id, _), value in existing_links.items() if entity_id == link.get("entity_id")), {})
                    role = str(link.get("role") or previous.get("role") or "depicted_subject")
                    if role not in ASSET_ROLES:
                        raise EntityLibraryServiceError(f"Invalid asset relationship role: {role}")
                    connection.execute("INSERT INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (asset_id, link["entity_id"], link.get("variant_id") or previous.get("variant_id") or None, role))
            if "set_ids" in data:
                existing_sets = {item["set_id"]: item for item in current["sets"]}
                connection.execute("DELETE FROM reference_set_assets WHERE asset_id=?", (asset_id,))
                for order, set_id in enumerate(data.get("set_ids") or []):
                    previous = existing_sets.get(set_id, {})
                    connection.execute("INSERT INTO reference_set_assets(set_id,asset_id,role,sort_order) VALUES(?,?,?,?)", (set_id, asset_id, previous.get("role", "member"), previous.get("sort_order", order)))
            if "facets" in data:
                connection.execute("DELETE FROM asset_facets WHERE asset_id=?", (asset_id,))
                for facet in data.get("facets") or []:
                    namespace = self._require(facet.get("namespace"), "Facet namespace")
                    value = self._require(facet.get("value"), "Facet value")
                    found = connection.execute("SELECT facet_id FROM facets WHERE namespace=? AND value=?", (namespace, value)).fetchone()
                    facet_id = found[0] if found else str(uuid4())
                    if not found:
                        connection.execute("INSERT INTO facets VALUES(?,?,?,?)", (facet_id, namespace, value, int(bool(facet.get("controlled", True)))))
                    connection.execute("INSERT INTO asset_facets VALUES(?,?)", (asset_id, facet_id))
            if "tags" in data:
                connection.execute("DELETE FROM asset_tags WHERE asset_id=?", (asset_id,))
                for tag in sorted({str(value).strip() for value in data.get("tags") or [] if str(value).strip()}):
                    connection.execute("INSERT INTO asset_tags VALUES(?,?)", (asset_id, tag))
        return self.get_asset(asset_id)

    def delete_asset(self, asset_id: str) -> dict:
        return self.set_asset_status(asset_id, "archived")

    def create_entity(self, data: dict) -> dict:
        name = self._require(data.get("name"), "Entity name")
        entity_type = str(data.get("entity_type") or "").strip()
        if entity_type not in ENTITY_TYPES:
            raise EntityLibraryServiceError("Invalid entity type.")
        entity_id, stamp = str(uuid4()), _now()
        with self.repository.transaction() as connection:
            connection.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?)", (entity_id, name, entity_type, str(data.get("description") or "").strip(), "active", stamp, stamp))
        return self.repository.fetchone("SELECT * FROM entities WHERE entity_id=?", (entity_id,)) or {}

    def list_entities(self, entity_type: str = "") -> list[dict]:
        self._sync_pipeline_assets()
        if entity_type:
            rows = self.repository.fetchall("SELECT * FROM entities WHERE entity_type=? ORDER BY name COLLATE NOCASE", (entity_type,))
        else:
            rows = self.repository.fetchall("SELECT * FROM entities ORDER BY name COLLATE NOCASE")
        for row in rows:
            row["image_count"] = self.repository.fetchone("SELECT count(DISTINCT asset_id) AS n FROM asset_entities WHERE entity_id=?", (row["entity_id"],))["n"]
            row["variant_count"] = self.repository.fetchone("SELECT count(*) AS n FROM variants WHERE entity_id=?", (row["entity_id"],))["n"]
            row["descriptors"] = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type='entity' AND owner_id=? ORDER BY descriptor_type", (row["entity_id"],))
        return rows

    def update_entity(self, entity_id: str, data: dict) -> dict:
        current = self.repository.fetchone("SELECT * FROM entities WHERE entity_id=?", (entity_id,))
        if not current:
            raise EntityLibraryServiceError(f"Entity not found: {entity_id}")
        name = self._require(data.get("name", current["name"]), "Entity name")
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR IGNORE INTO entity_name_aliases VALUES(?,?,?)", (current["name"], current["entity_type"], entity_id))
            connection.execute("UPDATE entities SET name=?,description=?,updated_at=? WHERE entity_id=?", (name, str(data.get("description", current["description"]) or "").strip(), _now(), entity_id))
        return self.repository.fetchone("SELECT * FROM entities WHERE entity_id=?", (entity_id,)) or {}

    def delete_entity(self, entity_id: str) -> dict:
        current = self.repository.fetchone("SELECT * FROM entities WHERE entity_id=?", (entity_id,))
        if not current:
            raise EntityLibraryServiceError(f"Entity not found: {entity_id}")
        dependencies = self.repository.fetchall("SELECT 'image' AS kind,count(DISTINCT asset_id) AS n FROM asset_entities WHERE entity_id=? UNION ALL SELECT 'variant',count(*) FROM variants WHERE entity_id=? UNION ALL SELECT 'relationship',count(*) FROM entity_relations WHERE source_entity_id=? OR target_entity_id=?", (entity_id, entity_id, entity_id, entity_id))
        used = [f"{row['n']} {row['kind']}(s)" for row in dependencies if row["n"]]
        if used:
            raise EntityLibraryServiceError("Entity is still in use: " + ", ".join(used))
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM descriptors WHERE owner_type='entity' AND owner_id=?", (entity_id,))
            connection.execute("DELETE FROM entities WHERE entity_id=?", (entity_id,))
        return {"entity_id": entity_id, "name": current["name"]}

    def create_variant(self, entity_id: str, data: dict) -> dict:
        name = self._require(data.get("name"), "Variant name")
        variant_type = str(data.get("variant_type") or "").strip()
        if variant_type not in VARIANT_TYPES:
            raise EntityLibraryServiceError("Invalid variant type.")
        variant_id, stamp = str(uuid4()), _now()
        with self.repository.transaction() as connection:
            connection.execute("INSERT INTO variants VALUES(?,?,?,?,?,?,?)", (variant_id, entity_id, name, variant_type, str(data.get("description") or "").strip(), stamp, stamp))
        return self.repository.fetchone("SELECT * FROM variants WHERE variant_id=?", (variant_id,)) or {}

    def list_variants(self, entity_id: str = "") -> list[dict]:
        self._sync_pipeline_assets()
        if entity_id:
            rows = self.repository.fetchall("SELECT v.*,e.name AS entity_name FROM variants v JOIN entities e USING(entity_id) WHERE entity_id=? ORDER BY name COLLATE NOCASE", (entity_id,))
        else:
            rows = self.repository.fetchall("SELECT v.*,e.name AS entity_name FROM variants v JOIN entities e USING(entity_id) ORDER BY e.name COLLATE NOCASE,v.name COLLATE NOCASE")
        for row in rows:
            row["image_count"] = self.repository.fetchone("SELECT count(DISTINCT asset_id) AS n FROM asset_entities WHERE variant_id=?", (row["variant_id"],))["n"]
            row["descriptors"] = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type='variant' AND owner_id=? ORDER BY descriptor_type", (row["variant_id"],))
        return rows

    def update_variant(self, variant_id: str, data: dict) -> dict:
        current = self.repository.fetchone("SELECT * FROM variants WHERE variant_id=?", (variant_id,))
        if not current:
            raise EntityLibraryServiceError(f"Variant not found: {variant_id}")
        name = self._require(data.get("name", current["name"]), "Variant name")
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR IGNORE INTO variant_name_aliases VALUES(?,?,?,?)", (current["entity_id"], current["name"], current["variant_type"], variant_id))
            connection.execute("UPDATE variants SET name=?,description=?,updated_at=? WHERE variant_id=?", (name, str(data.get("description", current["description"]) or "").strip(), _now(), variant_id))
        return self.repository.fetchone("SELECT * FROM variants WHERE variant_id=?", (variant_id,)) or {}

    def delete_variant(self, variant_id: str) -> dict:
        current = self.repository.fetchone("SELECT * FROM variants WHERE variant_id=?", (variant_id,))
        if not current:
            raise EntityLibraryServiceError(f"Variant not found: {variant_id}")
        count = self.repository.fetchone("SELECT count(DISTINCT asset_id) AS n FROM asset_entities WHERE variant_id=?", (variant_id,))["n"]
        if count:
            raise EntityLibraryServiceError(f"Variant is still assigned to {count} image(s).")
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM descriptors WHERE owner_type='variant' AND owner_id=?", (variant_id,))
            connection.execute("DELETE FROM variants WHERE variant_id=?", (variant_id,))
        return {"variant_id": variant_id, "name": current["name"]}

    def create_relation(self, data: dict) -> dict:
        source, target = self._require(data.get("source_entity_id"), "Source entity"), self._require(data.get("target_entity_id"), "Target entity")
        relation = str(data.get("relation_type") or "").strip()
        if relation not in RELATION_TYPES:
            raise EntityLibraryServiceError("Invalid entity relationship type.")
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO entity_relations VALUES(?,?,?,?)", (source, target, relation, str(data.get("notes") or "").strip()))
        return {"source_entity_id": source, "target_entity_id": target, "relation_type": relation}

    def list_relations(self, entity_id: str) -> list[dict]:
        return self.repository.fetchall(
            "SELECT r.*,s.name AS source_name,t.name AS target_name FROM entity_relations r JOIN entities s ON s.entity_id=r.source_entity_id JOIN entities t ON t.entity_id=r.target_entity_id WHERE source_entity_id=? OR target_entity_id=? ORDER BY relation_type,source_name,target_name",
            (entity_id, entity_id),
        )

    def delete_relation(self, source_entity_id: str, target_entity_id: str, relation_type: str) -> dict:
        with self.repository.transaction() as connection:
            cursor = connection.execute("DELETE FROM entity_relations WHERE source_entity_id=? AND target_entity_id=? AND relation_type=?", (source_entity_id, target_entity_id, relation_type))
            if not cursor.rowcount:
                raise EntityLibraryServiceError("Entity relationship not found.")
        return {"source_entity_id": source_entity_id, "target_entity_id": target_entity_id, "relation_type": relation_type}

    def create_set(self, data: dict) -> dict:
        name = self._require(data.get("name"), "Reference set name")
        set_id, stamp = str(uuid4()), _now()
        with self.repository.transaction() as connection:
            connection.execute("INSERT INTO reference_sets VALUES(?,?,?,?,?,?,?)", (set_id, name, str(data.get("set_type") or "general"), str(data.get("description") or "").strip(), data.get("entity_id") or None, stamp, stamp))
            for order, asset_id in enumerate(data.get("asset_ids") or []):
                connection.execute("INSERT INTO reference_set_assets(set_id,asset_id,role,sort_order) VALUES(?,?,?,?)", (set_id, asset_id, "member", order))
        return self.get_set(set_id)

    def update_set(self, set_id: str, data: dict) -> dict:
        name = self._require(data.get("name"), "Reference set name")
        current = self.repository.fetchone("SELECT * FROM reference_sets WHERE set_id=?", (set_id,))
        if not current:
            raise EntityLibraryServiceError(f"Reference set not found: {set_id}")
        stamp = _now()
        with self.repository.transaction() as connection:
            cursor = connection.execute(
                "UPDATE reference_sets SET name=?,set_type=?,description=?,entity_id=?,updated_at=? WHERE set_id=?",
                (name, str(data.get("set_type", current["set_type"]) or "general").strip() or "general",
                 str(data.get("description", current["description"]) or "").strip(),
                 data.get("entity_id", current["entity_id"]) or None, stamp, set_id),
            )
            if not cursor.rowcount:
                raise EntityLibraryServiceError(f"Reference set not found: {set_id}")
        return self.get_set(set_id)

    def delete_set(self, set_id: str) -> dict:
        """Remove a set and its descriptors while preserving its member images."""
        reference_set = self.get_set(set_id)
        references = self.repository.fetchall("SELECT reference_key FROM logical_references WHERE set_id=? AND status='active'", (set_id,))
        if references:
            raise EntityLibraryServiceError("Reference set is used by active logical references: " + ", ".join(item["reference_key"] for item in references))
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM descriptors WHERE owner_type='set' AND owner_id=?", (set_id,))
            connection.execute("DELETE FROM reference_sets WHERE set_id=?", (set_id,))
        return {"set_id": set_id, "name": reference_set["name"], "image_count": len(reference_set["assets"])}

    def get_set(self, set_id: str) -> dict:
        item = self.repository.fetchone("SELECT * FROM reference_sets WHERE set_id=?", (set_id,))
        if not item:
            raise EntityLibraryServiceError(f"Reference set not found: {set_id}")
        item["assets"] = self.repository.fetchall("SELECT a.asset_id,a.file_name,a.label,a.status,sa.role,sa.sort_order FROM reference_set_assets sa JOIN assets a ON a.asset_id=sa.asset_id WHERE sa.set_id=? ORDER BY sa.sort_order", (set_id,))
        item["image_count"] = len(item["assets"])
        item["descriptors"] = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type='set' AND owner_id=? ORDER BY priority", (set_id,))
        return item

    def list_sets(self) -> list[dict]:
        self._sync_pipeline_assets()
        return [self.get_set(item["set_id"]) for item in self.repository.fetchall("SELECT set_id FROM reference_sets ORDER BY name COLLATE NOCASE")]

    def add_set_asset(self, set_id: str, asset_id: str, role: str = "member", sort_order: int = 0) -> dict:
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO reference_set_assets VALUES(?,?,?,?)", (set_id, asset_id, role, int(sort_order)))
        return self.get_set(set_id)

    def remove_set_asset(self, set_id: str, asset_id: str) -> dict:
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM reference_set_assets WHERE set_id=? AND asset_id=?", (set_id, asset_id))
        return self.get_set(set_id)

    def save_descriptor(self, data: dict) -> dict:
        owner_type = str(data.get("owner_type") or "").strip()
        owner_id = self._require(data.get("owner_id"), "Descriptor owner")
        descriptor_type = str(data.get("descriptor_type") or "").strip()
        text = str(data.get("text") or "").strip()
        if owner_type not in {"entity", "variant", "set", "asset"} or descriptor_type not in DESCRIPTOR_TYPES:
            raise EntityLibraryServiceError("Invalid descriptor owner or type.")
        existing = self.repository.fetchone("SELECT descriptor_id FROM descriptors WHERE owner_type=? AND owner_id=? AND descriptor_type=?", (owner_type, owner_id, descriptor_type))
        descriptor_id, stamp = (existing["descriptor_id"] if existing else str(uuid4())), _now()
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO descriptors VALUES(?,?,?,?,?,?,?,?,?)", (descriptor_id, owner_type, owner_id, descriptor_type, text, int(data.get("priority") or 0), int(bool(data.get("enabled", True))), stamp, stamp))
        return self.repository.fetchone("SELECT * FROM descriptors WHERE descriptor_id=?", (descriptor_id,)) or {}

    def save_facets(self, asset_id: str, facets: list[dict]) -> list[dict]:
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM asset_facets WHERE asset_id=?", (asset_id,))
            for item in facets:
                namespace, value = self._require(item.get("namespace"), "Facet namespace"), self._require(item.get("value"), "Facet value")
                facet = connection.execute("SELECT facet_id FROM facets WHERE namespace=? AND value=?", (namespace, value)).fetchone()
                facet_id = facet[0] if facet else str(uuid4())
                if not facet:
                    connection.execute("INSERT INTO facets VALUES(?,?,?,?)", (facet_id, namespace, value, int(bool(item.get("controlled", True)))))
                connection.execute("INSERT INTO asset_facets VALUES(?,?)", (asset_id, facet_id))
        return self.repository.fetchall("SELECT f.namespace,f.value FROM asset_facets af JOIN facets f ON f.facet_id=af.facet_id WHERE af.asset_id=? ORDER BY namespace,value", (asset_id,))

    def list_facets(self) -> list[dict]:
        self._sync_pipeline_assets()
        return self.repository.fetchall("SELECT f.facet_id,f.namespace,f.value,f.controlled,count(DISTINCT af.asset_id) AS usage_count FROM facets f LEFT JOIN asset_facets af ON af.facet_id=f.facet_id GROUP BY f.facet_id,f.namespace,f.value,f.controlled ORDER BY namespace,value")

    def create_facet(self, data: dict) -> dict:
        namespace = self._require(data.get("namespace"), "Facet namespace")
        value = self._require(data.get("value"), "Facet value")
        facet_id = str(uuid4())
        with self.repository.transaction() as connection:
            connection.execute("INSERT INTO facets VALUES(?,?,?,?)", (facet_id, namespace, value, int(bool(data.get("controlled", True)))))
        return self.repository.fetchone("SELECT * FROM facets WHERE facet_id=?", (facet_id,)) or {}

    def update_facet(self, facet_id: str, data: dict) -> dict:
        current = self.repository.fetchone("SELECT * FROM facets WHERE facet_id=?", (facet_id,))
        if not current:
            raise EntityLibraryServiceError(f"Facet not found: {facet_id}")
        value = self._require(data.get("value", current["value"]), "Facet value")
        with self.repository.transaction() as connection:
            connection.execute("UPDATE facets SET value=? WHERE facet_id=?", (value, facet_id))
        return self.repository.fetchone("SELECT * FROM facets WHERE facet_id=?", (facet_id,)) or {}

    def delete_facet(self, facet_id: str) -> dict:
        current = self.repository.fetchone("SELECT * FROM facets WHERE facet_id=?", (facet_id,))
        if not current:
            raise EntityLibraryServiceError(f"Facet not found: {facet_id}")
        count = self.repository.fetchone("SELECT count(*) AS n FROM asset_facets WHERE facet_id=?", (facet_id,))["n"]
        if count:
            raise EntityLibraryServiceError(f"Facet is still assigned to {count} image(s).")
        with self.repository.transaction() as connection:
            connection.execute("DELETE FROM facets WHERE facet_id=?", (facet_id,))
        return {"facet_id": facet_id, "namespace": current["namespace"], "value": current["value"]}

    def _merge_snapshot(self, kind: str, source_id: str, target_id: str) -> tuple[dict, list[dict]]:
        tables = {"entity": ("entities", "entity_id"), "variant": ("variants", "variant_id"), "set": ("reference_sets", "set_id"), "facet": ("facets", "facet_id")}
        if kind not in tables:
            raise EntityLibraryServiceError("Unknown organization type.")
        table, key = tables[kind]
        source = self.repository.fetchone(f"SELECT * FROM {table} WHERE {key}=?", (source_id,))
        target = self.repository.fetchone(f"SELECT * FROM {table} WHERE {key}=?", (target_id,))
        if not source or not target or source_id == target_id:
            raise EntityLibraryServiceError("Choose two different existing records to merge.")
        if kind == "entity" and source["entity_type"] != target["entity_type"]:
            raise EntityLibraryServiceError("Entities must have the same type to merge.")
        if kind == "variant" and (source["entity_id"] != target["entity_id"] or source["variant_type"] != target["variant_type"]):
            raise EntityLibraryServiceError("Variants must have the same owner and type to merge.")
        if kind == "facet" and source["namespace"] != target["namespace"]:
            raise EntityLibraryServiceError("Facets must have the same namespace to merge.")
        state = {"kind": kind, "source": source, "target": target}
        conflicts = []
        shared_fields = {"entity": ("description",), "variant": ("description",), "set": ("set_type", "description", "entity_id"), "facet": ()}[kind]
        for field in shared_fields:
            if source.get(field) and target.get(field) and source[field] != target[field]:
                conflicts.append({"key": f"{kind}:{field}", "label": field.replace("_", " "), "source": source[field], "target": target[field]})
        owner_type = {"entity": "entity", "variant": "variant", "set": "set"}.get(kind)
        if owner_type:
            state["source_descriptors"] = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type=? AND owner_id=? ORDER BY descriptor_type", (owner_type, source_id))
            state["target_descriptors"] = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type=? AND owner_id=? ORDER BY descriptor_type", (owner_type, target_id))
            target_descriptors = {item["descriptor_type"]: item for item in state["target_descriptors"]}
            for descriptor in state["source_descriptors"]:
                other = target_descriptors.get(descriptor["descriptor_type"])
                if other and descriptor["text"] != other["text"]:
                    conflicts.append({"key": f"descriptor:{descriptor['descriptor_type']}", "label": f"{descriptor['descriptor_type']} descriptor", "source": descriptor["text"], "target": other["text"]})
        if kind == "entity":
            state["source_name_aliases"] = self.repository.fetchall("SELECT name,entity_type,entity_id FROM entity_name_aliases WHERE entity_id=? ORDER BY name", (source_id,))
            state["target_name_aliases"] = self.repository.fetchall("SELECT name,entity_type,entity_id FROM entity_name_aliases WHERE entity_id=? ORDER BY name", (target_id,))
            state["source_assets"] = self.repository.fetchall("SELECT * FROM asset_entities WHERE entity_id=? ORDER BY asset_id,role", (source_id,))
            state["target_assets"] = self.repository.fetchall("SELECT * FROM asset_entities WHERE entity_id=? ORDER BY asset_id,role", (target_id,))
            state["source_relations"] = self.repository.fetchall("SELECT * FROM entity_relations WHERE source_entity_id=? OR target_entity_id=? ORDER BY source_entity_id,target_entity_id,relation_type", (source_id, source_id))
            state["target_relations"] = self.repository.fetchall("SELECT * FROM entity_relations WHERE source_entity_id=? OR target_entity_id=? ORDER BY source_entity_id,target_entity_id,relation_type", (target_id, target_id))
            state["source_variants"] = self.repository.fetchall("SELECT * FROM variants WHERE entity_id=? ORDER BY name", (source_id,))
            state["target_variants"] = self.repository.fetchall("SELECT * FROM variants WHERE entity_id=? ORDER BY name", (target_id,))
            target_variants = {(item["name"].casefold(), item["variant_type"]): item for item in state["target_variants"]}
            for variant in state["source_variants"]:
                other = target_variants.get((variant["name"].casefold(), variant["variant_type"]))
                if other and variant["description"] and other["description"] and variant["description"] != other["description"]:
                    conflicts.append({"key": f"variant:{variant['variant_id']}:description", "label": f"{variant['name']} description", "source": variant["description"], "target": other["description"]})
                if other:
                    source_descriptors = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type='variant' AND owner_id=? ORDER BY descriptor_type", (variant["variant_id"],))
                    target_descriptors = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type='variant' AND owner_id=? ORDER BY descriptor_type", (other["variant_id"],))
                    state.setdefault("variant_descriptors", {})[variant["variant_id"]] = {"source": source_descriptors, "target": target_descriptors}
                    for descriptor in source_descriptors:
                        target_descriptor = next((item for item in target_descriptors if item["descriptor_type"] == descriptor["descriptor_type"]), None)
                        if target_descriptor and descriptor["text"] != target_descriptor["text"]:
                            conflicts.append({"key": f"variant_descriptor:{variant['variant_id']}:{descriptor['descriptor_type']}", "label": f"{variant['name']} · {descriptor['descriptor_type']} descriptor", "source": descriptor["text"], "target": target_descriptor["text"]})
        if kind == "set":
            state["source_members"] = self.repository.fetchall("SELECT * FROM reference_set_assets WHERE set_id=? ORDER BY sort_order,asset_id", (source_id,))
            state["target_members"] = self.repository.fetchall("SELECT * FROM reference_set_assets WHERE set_id=? ORDER BY sort_order,asset_id", (target_id,))
            target_members = {item["asset_id"]: item for item in state["target_members"]}
            for member in state["source_members"]:
                other = target_members.get(member["asset_id"])
                if other and other["role"] != member["role"]:
                    asset = self.repository.fetchone("SELECT label,file_name FROM assets WHERE asset_id=?", (member["asset_id"],)) or {}
                    conflicts.append({"key": f"member:{member['asset_id']}:role", "label": f"{asset.get('label') or asset.get('file_name') or member['asset_id']} membership role", "source": member["role"], "target": other["role"]})
            state["source_references"] = self.repository.fetchall("SELECT reference_key,set_id,status FROM logical_references WHERE set_id=? ORDER BY reference_key", (source_id,))
        if kind == "variant":
            state["source_assets"] = self.repository.fetchall("SELECT * FROM asset_entities WHERE variant_id=? ORDER BY asset_id,role", (source_id,))
        if kind == "facet":
            state["source_assets"] = self.repository.fetchall("SELECT asset_id FROM asset_facets WHERE facet_id=? ORDER BY asset_id", (source_id,))
            state["target_assets"] = self.repository.fetchall("SELECT asset_id FROM asset_facets WHERE facet_id=? ORDER BY asset_id", (target_id,))
        state["conflicts"] = conflicts
        return state, conflicts

    def preview_merge(self, kind: str, source_id: str, target_id: str) -> dict:
        state, conflicts = self._merge_snapshot(kind, source_id, target_id)
        token = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        counts = {
            "entity": len({item["asset_id"] for item in state.get("source_assets", [])}),
            "variant": len({item["asset_id"] for item in state.get("source_assets", [])}),
            "set": len(state.get("source_members", [])),
            "facet": len({item["asset_id"] for item in state.get("source_assets", [])}),
        }
        return {"kind": kind, "source": state["source"], "target": state["target"], "image_count": counts[kind], "conflicts": conflicts, "token": token}

    def merge_records(self, kind: str, source_id: str, target_id: str, token: str, resolutions: dict | None = None) -> dict:
        state, conflicts = self._merge_snapshot(kind, source_id, target_id)
        current_token = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        if not token or token != current_token:
            raise EntityLibraryServiceError("Records changed after preview. Review the merge preview again.")
        resolutions = resolutions or {}
        missing = [item["key"] for item in conflicts if resolutions.get(item["key"]) not in {"source", "target"}]
        if missing:
            raise EntityLibraryServiceError("Choose source or target for each conflict: " + ", ".join(missing))
        source, target = state["source"], state["target"]
        stamp = _now()
        with self.repository.transaction() as connection:
            locked_state, _ = self._merge_snapshot(kind, source_id, target_id)
            locked_token = hashlib.sha256(json.dumps(locked_state, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            if locked_token != token:
                raise EntityLibraryServiceError("Records changed after preview. Review the merge preview again.")
            if kind == "entity" and source.get("description") and target.get("description") and source["description"] != target["description"] and resolutions.get("entity:description") == "source":
                connection.execute("UPDATE entities SET description=?,updated_at=? WHERE entity_id=?", (source["description"], stamp, target_id))
            if kind == "variant" and source.get("description") and target.get("description") and source["description"] != target["description"] and resolutions.get("variant:description") == "source":
                connection.execute("UPDATE variants SET description=?,updated_at=? WHERE variant_id=?", (source["description"], stamp, target_id))
            for conflict in conflicts:
                if conflict["key"].startswith("descriptor:") and resolutions[conflict["key"]] == "source":
                    descriptor_type = conflict["key"].split(":", 1)[1]
                    connection.execute("UPDATE descriptors SET text=?,enabled=?,priority=?,updated_at=? WHERE owner_type=? AND owner_id=? AND descriptor_type=?", (conflict["source"], next(d["enabled"] for d in state["source_descriptors"] if d["descriptor_type"] == descriptor_type), next(d["priority"] for d in state["source_descriptors"] if d["descriptor_type"] == descriptor_type), stamp, {"entity":"entity","variant":"variant","set":"set"}[kind], target_id, descriptor_type))
            for descriptor in state.get("source_descriptors", []):
                other = next((d for d in state.get("target_descriptors", []) if d["descriptor_type"] == descriptor["descriptor_type"]), None)
                if not other:
                    connection.execute("UPDATE descriptors SET owner_id=?,updated_at=? WHERE descriptor_id=?", (target_id, stamp, descriptor["descriptor_id"]))
                else:
                    connection.execute("DELETE FROM descriptors WHERE descriptor_id=?", (descriptor["descriptor_id"],))
            if kind == "entity":
                # Preserve old pipeline names and every image/variant reference while redirecting organization links.
                connection.execute("INSERT OR IGNORE INTO entity_name_aliases SELECT name,entity_type,? FROM entity_name_aliases WHERE entity_id=?", (target_id, source_id))
                connection.execute("INSERT OR IGNORE INTO entity_name_aliases VALUES(?,?,?)", (source["name"], source["entity_type"], target_id))
                connection.execute("INSERT OR IGNORE INTO entity_name_aliases VALUES(?,?,?)", (target["name"], target["entity_type"], target_id))
                for variant in state["source_variants"]:
                    other = next((v for v in state["target_variants"] if v["name"].casefold() == variant["name"].casefold() and v["variant_type"] == variant["variant_type"]), None)
                    variant_aliases = self.repository.fetchall("SELECT name,variant_type FROM variant_name_aliases WHERE variant_id=? ORDER BY name", (variant["variant_id"],))
                    if other:
                        variant_target = other["variant_id"]
                        if variant["description"] and (not other["description"] or resolutions.get(f"variant:{variant['variant_id']}:description") == "source"):
                            connection.execute("UPDATE variants SET description=? WHERE variant_id=?", (variant["description"], variant_target))
                        connection.execute("UPDATE asset_entities SET variant_id=? WHERE variant_id=?", (variant_target, variant["variant_id"]))
                        for descriptor in state.get("variant_descriptors", {}).get(variant["variant_id"], {}).get("source", []):
                            target_descriptor = next((item for item in state["variant_descriptors"][variant["variant_id"]]["target"] if item["descriptor_type"] == descriptor["descriptor_type"]), None)
                            if target_descriptor and resolutions.get(f"variant_descriptor:{variant['variant_id']}:{descriptor['descriptor_type']}") == "source":
                                connection.execute("UPDATE descriptors SET text=?,enabled=?,priority=?,updated_at=? WHERE descriptor_id=?", (descriptor["text"], descriptor["enabled"], descriptor["priority"], stamp, target_descriptor["descriptor_id"]))
                        connection.execute("INSERT OR IGNORE INTO descriptors(descriptor_id,owner_type,owner_id,descriptor_type,text,priority,enabled,created_at,updated_at) SELECT lower(hex(randomblob(16))),'variant',?,descriptor_type,text,priority,enabled,created_at,updated_at FROM descriptors WHERE owner_type='variant' AND owner_id=? AND descriptor_type NOT IN (SELECT descriptor_type FROM descriptors WHERE owner_type='variant' AND owner_id=?)", (variant_target, variant["variant_id"], variant_target))
                        for alias in [*variant_aliases, {"name": variant["name"], "variant_type": variant["variant_type"]}]:
                            connection.execute("INSERT OR REPLACE INTO variant_name_aliases VALUES(?,?,?,?)", (target_id, alias["name"], alias["variant_type"], variant_target))
                        connection.execute("DELETE FROM variants WHERE variant_id=?", (variant["variant_id"],))
                    else:
                        connection.execute("UPDATE variants SET entity_id=?,updated_at=? WHERE variant_id=?", (target_id, stamp, variant["variant_id"]))
                        for alias in [*variant_aliases, {"name": variant["name"], "variant_type": variant["variant_type"]}]:
                            connection.execute("INSERT OR REPLACE INTO variant_name_aliases VALUES(?,?,?,?)", (target_id, alias["name"], alias["variant_type"], variant["variant_id"]))
                        connection.execute("DELETE FROM variant_name_aliases WHERE entity_id=? AND variant_id=?", (source_id, variant["variant_id"]))
                for link in state["source_assets"]:
                    current_link = connection.execute("SELECT variant_id FROM asset_entities WHERE asset_id=? AND entity_id=? AND role=?", (link["asset_id"], source_id, link["role"])).fetchone()
                    if not current_link:
                        continue
                    duplicate = connection.execute("SELECT 1 FROM asset_entities WHERE asset_id=? AND entity_id=? AND role=? AND variant_id IS ?", (link["asset_id"], target_id, link["role"], current_link["variant_id"])).fetchone()
                    if duplicate:
                        connection.execute("DELETE FROM asset_entities WHERE asset_id=? AND entity_id=? AND role=? AND variant_id IS ?", (link["asset_id"], source_id, link["role"], current_link["variant_id"]))
                    else:
                        connection.execute("UPDATE asset_entities SET entity_id=? WHERE asset_id=? AND entity_id=? AND role=? AND variant_id IS ?", (target_id, link["asset_id"], source_id, link["role"], current_link["variant_id"]))
                connection.execute("INSERT OR IGNORE INTO entity_relations(source_entity_id,target_entity_id,relation_type,notes) SELECT ?,target_entity_id,relation_type,notes FROM entity_relations WHERE source_entity_id=? AND target_entity_id<>?", (target_id, source_id, target_id))
                connection.execute("INSERT OR IGNORE INTO entity_relations(source_entity_id,target_entity_id,relation_type,notes) SELECT source_entity_id,?,relation_type,notes FROM entity_relations WHERE target_entity_id=? AND source_entity_id<>?", (target_id, source_id, target_id))
                connection.execute("DELETE FROM entity_relations WHERE source_entity_id=? OR target_entity_id=?", (source_id, source_id))
                connection.execute("DELETE FROM entities WHERE entity_id=?", (source_id,))
            elif kind == "variant":
                connection.execute("INSERT OR IGNORE INTO variant_name_aliases SELECT entity_id,name,variant_type,? FROM variant_name_aliases WHERE variant_id=?", (target_id, source_id))
                connection.execute("INSERT OR REPLACE INTO variant_name_aliases VALUES(?,?,?,?)", (source["entity_id"], source["name"], source["variant_type"], target_id))
                connection.execute("UPDATE asset_entities SET variant_id=? WHERE variant_id=?", (target_id, source_id))
                connection.execute("DELETE FROM variants WHERE variant_id=?", (source_id,))
            elif kind == "set":
                for conflict in conflicts:
                    if conflict["key"].startswith("member:") and resolutions[conflict["key"]] == "source":
                        asset_id = conflict["key"].split(":")[1]
                        connection.execute("UPDATE reference_set_assets SET role=? WHERE set_id=? AND asset_id=?", (conflict["source"], target_id, asset_id))
                max_order = max((item["sort_order"] for item in state["target_members"]), default=-1)
                for member in state["source_members"]:
                    existing_member = next((item for item in state["target_members"] if item["asset_id"] == member["asset_id"]), None)
                    if existing_member:
                        connection.execute("DELETE FROM reference_set_assets WHERE set_id=? AND asset_id=?", (source_id, member["asset_id"]))
                    else:
                        connection.execute("UPDATE reference_set_assets SET set_id=?,sort_order=? WHERE set_id=? AND asset_id=?", (target_id, max_order + member["sort_order"] + 1, source_id, member["asset_id"]))
                connection.execute("UPDATE logical_references SET set_id=? WHERE set_id=?", (target_id, source_id))
                connection.execute("UPDATE reference_sets SET set_type=?,description=?,entity_id=?,updated_at=? WHERE set_id=?", tuple(source[field] if resolutions.get(f"set:{field}") == "source" else target[field] for field in ("set_type", "description", "entity_id")) + (stamp, target_id))
                connection.execute("DELETE FROM reference_sets WHERE set_id=?", (source_id,))
            else:
                connection.execute("INSERT OR IGNORE INTO asset_facets SELECT asset_id,? FROM asset_facets WHERE facet_id=?", (target_id, source_id))
                connection.execute("DELETE FROM facets WHERE facet_id=?", (source_id,))
        return {"kind": kind, "source_id": source_id, "target_id": target_id}

    def save_logical_reference(self, data: dict, reference_key: str = "") -> dict:
        key = self._require(reference_key or data.get("reference_key"), "Logical reference key")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", key):
            raise EntityLibraryServiceError("Logical reference keys use lowercase letters, numbers, dots, underscores, and hyphens.")
        label = self._require(data.get("label") or key, "Logical reference label")
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO logical_references VALUES(?,?,?,?,?,?)", (key, label, data.get("asset_id") or None, data.get("set_id") or None, str(data.get("status") or "active"), _now()))
        return self.repository.fetchone("SELECT * FROM logical_references WHERE reference_key=?", (key,)) or {}

    def list_logical_references(self) -> list[dict]:
        return self.repository.fetchall("SELECT lr.*,a.file_name,a.status AS asset_status FROM logical_references lr LEFT JOIN assets a ON a.asset_id=lr.asset_id ORDER BY reference_key")

    def resolve_reference(self, reference_key: str) -> dict:
        row = self.repository.fetchone("SELECT asset_id,status,set_id FROM logical_references WHERE reference_key=?", (reference_key,))
        if not row or row["status"] != "active" or not row["asset_id"]:
            raise EntityLibraryServiceError(f"Logical image reference is missing or inactive: {reference_key}")
        asset = self.get_asset(row["asset_id"])
        if asset["status"] != "approved":
            raise EntityLibraryServiceError(f"Logical image reference resolves to an ineligible image: {reference_key}")
        asset["reference_set_id"] = row["set_id"] or ""
        return asset

    def register_legacy_reference(self, reference_tag: str, asset_id: str) -> None:
        """Keep a historical AUX tag pointing at its catalog image."""
        self.get_asset(asset_id)
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO legacy_image_references VALUES(?,?,?)", (reference_tag, asset_id, _now()))

    def resolve_legacy_reference(self, reference_tag: str) -> dict:
        row = self.repository.fetchone("SELECT asset_id FROM legacy_image_references WHERE reference_tag=?", (reference_tag,))
        if not row:
            raise EntityLibraryServiceError(f"Legacy image reference is missing: {reference_tag}")
        return self.get_asset(row["asset_id"])

    def effective_descriptors(self, asset_id: str, set_id: str = "") -> list[dict]:
        asset = self.get_asset(asset_id)
        owners = [("entity", item["entity_id"]) for item in asset["entities"]]
        owners.extend(("variant", item["variant_id"]) for item in asset["entities"] if item["variant_id"])
        if set_id:
            owners.append(("set", set_id))
        owners.append(("asset", asset_id))
        resolved = {}
        for owner_type, owner_id in owners:
            for descriptor in self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type=? AND owner_id=? AND enabled=1 ORDER BY priority", (owner_type, owner_id)):
                resolved[descriptor["descriptor_type"]] = descriptor
        return list(resolved.values())

    def usage_for_asset(self, asset_id: str) -> list[dict]:
        return self.repository.fetchall(
            "SELECT DISTINCT u.* FROM asset_usages u LEFT JOIN logical_references lr ON lr.reference_key=u.reference_key WHERE (u.asset_id=? OR lr.asset_id=?) AND u.status='current' ORDER BY u.consumer_type,u.consumer_id,u.locator",
            (asset_id, asset_id),
        )

    def search_picker(self, **filters) -> list[dict]:
        return [item for item in self.list_assets(**filters) if item["status"] == "approved"]

    def refresh_usages(self, library_root: str | Path) -> dict:
        """Rebuild usage records from authored scene JSON and template references."""
        root = Path(library_root).resolve()
        observations = []
        missing = []
        for path in sorted(root.rglob("*.scene.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            consumer_id = path.relative_to(root).as_posix()
            def visit(value, locator=""):
                if isinstance(value, dict):
                    direct = str(value.get("asset_id") or "").strip()
                    logical = str(value.get("reference_key") or "").strip()
                    if direct or logical:
                        observations.append((direct or None, logical or None, "scene", consumer_id, locator or "$"))
                    for key, child in value.items():
                        visit(child, f"{locator}.{key}" if locator else str(key))
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        visit(child, f"{locator}[{index}]")
            visit(data)
        template_paths = list((root / "Characters").rglob("*.md")) + list((root / "CostumePrompt").rglob("*.md"))
        for path in sorted(template_paths):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            consumer_id = path.relative_to(root).as_posix()
            for match in re.finditer(r"\{\{LIB:ASSET:([0-9a-fA-F-]{36})\}\}", text):
                observations.append((match.group(1), None, "template", consumer_id, f"offset:{match.start()}"))
            for match in re.finditer(r"\{\{LIB:REF:([a-z0-9][a-z0-9._-]*)\}\}", text):
                observations.append((None, match.group(1), "template", consumer_id, f"offset:{match.start()}"))
        stamp = _now()
        current = []
        with self.repository.transaction() as connection:
            connection.execute("UPDATE asset_usages SET status='stale'")
            for asset_id, reference_key, consumer_type, consumer_id, locator in observations:
                if asset_id:
                    exists = connection.execute("SELECT 1 FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
                else:
                    exists = connection.execute("SELECT 1 FROM logical_references WHERE reference_key=?", (reference_key,)).fetchone()
                if not exists:
                    missing.append({"asset_id": asset_id, "reference_key": reference_key, "consumer_id": consumer_id, "locator": locator})
                    continue
                usage_id = hashlib.sha256("|".join((asset_id or "", reference_key or "", consumer_id, locator)).encode()).hexdigest()
                connection.execute(
                    "INSERT INTO asset_usages(usage_id,asset_id,reference_key,consumer_type,consumer_id,locator,last_seen,status) VALUES(?,?,?,?,?,?,?,'current') ON CONFLICT(usage_id) DO UPDATE SET last_seen=excluded.last_seen,status='current'",
                    (usage_id, asset_id, reference_key, consumer_type, consumer_id, locator, stamp),
                )
                current.append(usage_id)
        stale_count = self.repository.fetchone("SELECT count(*) AS count FROM asset_usages WHERE status='stale'") or {"count": 0}
        return {"current": len(current), "missing": missing, "stale": int(stale_count["count"])}

