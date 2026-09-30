from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import hashlib
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
        return self.images_root / f"{asset_id}{Path(file_name).suffix.lower()}"

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
        for item in self.pipeline_provider():
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
                continue
            data = source_path.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            versioned_key = f"{origin_key}:{checksum}"
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
                    entity_id = entity[0] if entity else str(uuid4())
                    if not entity:
                        connection.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?)", (entity_id, entity_name, entity_type, "", "active", stamp, stamp))
                    variant_id = None
                    if entity_type == "character" and phase:
                        variant = connection.execute("SELECT variant_id FROM variants WHERE entity_id=? AND lower(name)=lower(?) AND variant_type='life_stage'", (entity_id, phase)).fetchone()
                        variant_id = variant[0] if variant else str(uuid4())
                        if not variant:
                            connection.execute("INSERT INTO variants VALUES(?,?,?,?,?,?,?)", (variant_id, entity_id, phase, "life_stage", "", stamp, stamp))
                    connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (asset_id, entity_id, variant_id, role))
                connection.execute(
                    "INSERT INTO provenance(provenance_id,asset_id,relation_type,details_json,created_at) VALUES(?,?,?,?,?)",
                    (str(uuid4()), asset_id, "locked_pipeline_source", json.dumps({"tag": origin_key, "label": item.label}), stamp),
                )
            self._pipeline_signatures[origin_key] = signature

    def list_assets(self, **filters) -> list[dict]:
        self._sync_pipeline_assets()
        rows = self.repository.fetchall("SELECT * FROM assets ORDER BY created_at DESC, asset_id")
        output = []
        for row in rows:
            asset_id = row["asset_id"]
            path = self._image_path(asset_id, row["file_name"])
            if not path.is_file():
                continue
            entities = self.repository.fetchall(
                "SELECT e.entity_id,e.name,e.entity_type,ae.role,ae.variant_id,v.name AS variant_name FROM asset_entities ae JOIN entities e ON e.entity_id=ae.entity_id LEFT JOIN variants v ON v.variant_id=ae.variant_id WHERE ae.asset_id=? ORDER BY e.name",
                (asset_id,),
            )
            sets = self.repository.fetchall(
                "SELECT s.set_id,s.name,sa.role,sa.sort_order FROM reference_set_assets sa JOIN reference_sets s ON s.set_id=sa.set_id WHERE sa.asset_id=? ORDER BY sa.sort_order,s.name",
                (asset_id,),
            )
            facets = self.repository.fetchall(
                "SELECT f.namespace,f.value FROM asset_facets af JOIN facets f ON f.facet_id=af.facet_id WHERE af.asset_id=? ORDER BY f.namespace,f.value",
                (asset_id,),
            )
            tags = [item["tag"] for item in self.repository.fetchall("SELECT tag FROM asset_tags WHERE asset_id=? ORDER BY tag", (asset_id,))]
            logical = self.repository.fetchone("SELECT reference_key,label,set_id FROM logical_references WHERE asset_id=? AND status='active' ORDER BY reference_key LIMIT 1", (asset_id,))
            item = {**row, "image_path": str(path), "thumbnail_path": str(path), "entities": entities, "sets": sets, "facets": facets, "tags": tags, "logical_reference": logical}
            descriptor_ready = self.repository.fetchone(
                "SELECT 1 FROM descriptors d WHERE d.enabled=1 AND d.descriptor_type IN ('prompt_identity','prompt_object','prompt_background','human_description') AND ((d.owner_type='asset' AND d.owner_id=?) OR (d.owner_type='entity' AND d.owner_id IN (SELECT entity_id FROM asset_entities WHERE asset_id=?)) OR (d.owner_type='variant' AND d.owner_id IN (SELECT variant_id FROM asset_entities WHERE asset_id=?)) OR (d.owner_type='set' AND d.owner_id IN (SELECT set_id FROM reference_set_assets WHERE asset_id=?))) LIMIT 1",
                (asset_id, asset_id, asset_id, asset_id),
            )
            item["descriptor_ready"] = bool(descriptor_ready)
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
            query = str(filters.get("q") or "").casefold().split()
            haystack = " ".join([row["file_name"], row["origin"], row["notes"], *[value["name"] for value in entities], *[value["name"] for value in sets], *tags, *[f'{value["namespace"]}:{value["value"]}' for value in facets]]).casefold()
            if query and not all(term in haystack for term in query):
                continue
            output.append(self._json(item))
        return output

    def get_asset(self, asset_id: str) -> dict:
        item = next((row for row in self.list_assets() if row["asset_id"] == asset_id), None)
        if item is None:
            raise EntityLibraryServiceError(f"Image asset not found: {asset_id}")
        item["descriptors"] = self.repository.fetchall(
            "SELECT * FROM descriptors WHERE owner_type='asset' AND owner_id=? ORDER BY priority,descriptor_type", (asset_id,)
        )
        item["provenance"] = self.repository.fetchall("SELECT * FROM provenance WHERE asset_id=? ORDER BY created_at", (asset_id,))
        item["usages"] = self.usage_for_asset(asset_id)
        return item

    def import_asset(self, label: str, mime_type: str, data: bytes, *, notes: str = "", entity_ids: list[str] | None = None, set_ids: list[str] | None = None, origin: str = "import", origin_key: str | None = None) -> dict:
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
                    "INSERT INTO assets(asset_id,label,checksum,file_name,mime_type,width,height,origin,origin_key,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (asset_id, label, checksum, path.name, mime_type, width, height, origin, origin_key, "approved", notes.strip(), stamp, stamp),
                )
                self._link_assets(connection, asset_id, entity_ids or [], set_ids or [])
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.get_asset(asset_id)

    def register_locked_pipeline_image(self, source: Path, *, label: str, pipeline: str, character: str, phase: str, checksum: str) -> dict:
        """Publish one verified local candidate into permanent ID-addressed storage."""
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != checksum:
            raise EntityLibraryServiceError("The selected image changed before it could be locked.")
        import mimetypes
        mime_type = mimetypes.guess_type(source.name)[0] or "image/png"
        key = f"local:{pipeline}:{character}:{phase}:{checksum}"
        asset = self.import_asset(label, mime_type, data, origin="pipeline", origin_key=key, notes="Locked local pipeline image")
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
    def _link_assets(connection, asset_id: str, entity_ids: list[str], set_ids: list[str]) -> None:
        for entity_id in entity_ids:
            connection.execute("INSERT OR IGNORE INTO asset_entities(asset_id,entity_id,role) VALUES(?,?,?)", (asset_id, entity_id, "depicted_subject"))
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
        return self.get_asset(created["asset_id"])

    def set_asset_status(self, asset_id: str, status: str) -> dict:
        if status not in ASSET_STATUSES:
            raise EntityLibraryServiceError("Invalid image status.")
        with self.repository.transaction() as connection:
            cursor = connection.execute("UPDATE assets SET status=?,updated_at=? WHERE asset_id=?", (status, _now(), asset_id))
            if not cursor.rowcount:
                raise EntityLibraryServiceError(f"Image asset not found: {asset_id}")
        return self.get_asset(asset_id)

    def update_asset(self, asset_id: str, data: dict) -> dict:
        current = self.get_asset(asset_id)
        stamp = _now()
        requested_status = str(data.get("status", current["status"]) or "").strip()
        if current["status"] == "approved" and requested_status != "approved":
            usages = self.usage_for_asset(asset_id)
            references = self.repository.fetchall("SELECT reference_key FROM logical_references WHERE asset_id=? AND status='active'", (asset_id,))
            if usages or references:
                raise EntityLibraryServiceError("Resolve current consumers and preferred references before changing this image from approved status.")
        with self.repository.transaction() as connection:
            label = str(data.get("label", current["label"]) or "").strip()
            notes = str(data.get("notes", current["notes"]) or "").strip()
            status = requested_status
            if not label:
                raise EntityLibraryServiceError("Image label is required.")
            if status not in ASSET_STATUSES:
                raise EntityLibraryServiceError("Invalid image status.")
            connection.execute("UPDATE assets SET label=?,notes=?,status=?,rating=?,updated_at=? WHERE asset_id=?", (label, notes, status, data.get("rating", current["rating"]), stamp, asset_id))
            if "entity_links" in data:
                connection.execute("DELETE FROM asset_entities WHERE asset_id=?", (asset_id,))
                for link in data.get("entity_links") or []:
                    role = str(link.get("role") or "depicted_subject")
                    if role not in ASSET_ROLES:
                        raise EntityLibraryServiceError(f"Invalid asset relationship role: {role}")
                    connection.execute("INSERT INTO asset_entities(asset_id,entity_id,variant_id,role) VALUES(?,?,?,?)", (asset_id, link["entity_id"], link.get("variant_id") or None, role))
            if "set_ids" in data:
                connection.execute("DELETE FROM reference_set_assets WHERE asset_id=?", (asset_id,))
                for order, set_id in enumerate(data.get("set_ids") or []):
                    connection.execute("INSERT INTO reference_set_assets(set_id,asset_id,role,sort_order) VALUES(?,?,?,?)", (set_id, asset_id, "member", order))
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
        usages = self.usage_for_asset(asset_id)
        references = self.repository.fetchall("SELECT reference_key FROM logical_references WHERE asset_id=? AND status='active'", (asset_id,))
        if usages or references:
            raise EntityLibraryServiceError(
                f"Image has {len(usages)} current consumer(s) and {len(references)} active logical reference(s); update those references first."
            )
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
            return self.repository.fetchall("SELECT * FROM entities WHERE entity_type=? ORDER BY name COLLATE NOCASE", (entity_type,))
        return self.repository.fetchall("SELECT * FROM entities ORDER BY name COLLATE NOCASE")

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
            return self.repository.fetchall("SELECT * FROM variants WHERE entity_id=? ORDER BY name COLLATE NOCASE", (entity_id,))
        return self.repository.fetchall("SELECT * FROM variants ORDER BY name COLLATE NOCASE")

    def create_relation(self, data: dict) -> dict:
        source, target = self._require(data.get("source_entity_id"), "Source entity"), self._require(data.get("target_entity_id"), "Target entity")
        relation = str(data.get("relation_type") or "").strip()
        if relation not in RELATION_TYPES:
            raise EntityLibraryServiceError("Invalid entity relationship type.")
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO entity_relations VALUES(?,?,?,?)", (source, target, relation, str(data.get("notes") or "").strip()))
        return {"source_entity_id": source, "target_entity_id": target, "relation_type": relation}

    def create_set(self, data: dict) -> dict:
        name = self._require(data.get("name"), "Reference set name")
        set_id, stamp = str(uuid4()), _now()
        with self.repository.transaction() as connection:
            connection.execute("INSERT INTO reference_sets VALUES(?,?,?,?,?,?,?)", (set_id, name, str(data.get("set_type") or "general"), str(data.get("description") or "").strip(), data.get("entity_id") or None, stamp, stamp))
            for order, asset_id in enumerate(data.get("asset_ids") or []):
                connection.execute("INSERT INTO reference_set_assets(set_id,asset_id,role,sort_order) VALUES(?,?,?,?)", (set_id, asset_id, "member", order))
        return self.get_set(set_id)

    def get_set(self, set_id: str) -> dict:
        item = self.repository.fetchone("SELECT * FROM reference_sets WHERE set_id=?", (set_id,))
        if not item:
            raise EntityLibraryServiceError(f"Reference set not found: {set_id}")
        item["assets"] = self.repository.fetchall("SELECT a.asset_id,a.file_name,a.status,sa.role,sa.sort_order FROM reference_set_assets sa JOIN assets a ON a.asset_id=sa.asset_id WHERE sa.set_id=? ORDER BY sa.sort_order", (set_id,))
        item["descriptors"] = self.repository.fetchall("SELECT * FROM descriptors WHERE owner_type='set' AND owner_id=? ORDER BY priority", (set_id,))
        return item

    def list_sets(self) -> list[dict]:
        self._sync_pipeline_assets()
        return [self.get_set(item["set_id"]) for item in self.repository.fetchall("SELECT set_id FROM reference_sets ORDER BY name COLLATE NOCASE")]

    def add_set_asset(self, set_id: str, asset_id: str, role: str = "member", sort_order: int = 0) -> dict:
        with self.repository.transaction() as connection:
            connection.execute("INSERT OR REPLACE INTO reference_set_assets VALUES(?,?,?,?)", (set_id, asset_id, role, int(sort_order)))
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
        return self.repository.fetchall("SELECT namespace,value,controlled,count(*) AS usage_count FROM facets f JOIN asset_facets af ON af.facet_id=f.facet_id GROUP BY namespace,value,controlled ORDER BY namespace,value")

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

