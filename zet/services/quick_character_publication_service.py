"""Publish a complete quick character set using the existing library schema."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from PIL import Image

from zet.services.entity_library_service import EntityLibraryServiceError
from zet.services.quick_character_wizard_service import QuickCharacterWizardConflict


def publish_quick_character(app, session: dict, directory: Path) -> dict:
    library = app.entity_library_service
    sid, revision = session["session_id"], session["revision_id"]

    def stable_id(part: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"zet:quick-character:{sid}:{revision}:{part}"))

    set_id = stable_id("set")
    primary = session["references"][0]
    source_id = primary["asset_id"] or stable_id("source")
    source_links = []
    if primary["asset_id"]:
        try:
            source = library.get_asset(source_id)
        except EntityLibraryServiceError as exc:
            raise QuickCharacterWizardConflict("The primary library source is unavailable. Start a new wizard.") from exc
        if source["status"] == "archived" or source["checksum"] != primary["checksum"]:
            raise QuickCharacterWizardConflict("The primary library source changed. Start a new wizard from the current image.")
        if hashlib.sha256(Path(source["image_path"]).read_bytes()).hexdigest() != primary["checksum"]:
            raise QuickCharacterWizardConflict("The primary source image changed outside the library.")
        source_links = [link for link in source["entities"] if link["role"] in {"primary_subject", "depicted_subject"}]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assets = []
    if not primary["asset_id"]:
        assets.append({"asset_id": source_id, "label": session["name"] + " · Source",
                       "filename": primary["filename"], "view": "source", "prompt": "", "negative": ""})
    outputs = {}
    side = session["side"].upper()
    for view in ("FRONT", f"FRONT_{side}_3_4", f"{side}_PROFILE"):
        candidate_id = session["selected"][view]
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        if candidate["revision_id"] != revision or candidate["stale"] or candidate["status"] != "READY":
            raise QuickCharacterWizardConflict("All selected images must be reviewed and current.")
        asset_id = stable_id(view)
        outputs[view] = asset_id
        assets.append({"asset_id": asset_id, "label": session["name"] + " · " + view.replace("_3_4", " 3/4").replace("_", " ").title(),
                       "filename": candidate["filename"], "view": view.lower(), "prompt": candidate["prompt"],
                       "negative": "multiple characters, extra limbs, mirrored asymmetry, text, labels, collage",
                       "candidate": candidate})
    created_files = []
    try:
        library.images_root.mkdir(parents=True, exist_ok=True)
        for asset in assets:
            data = (directory / asset["filename"]).read_bytes()
            with Image.open(BytesIO(data)) as image:
                image.verify()
                mime_type = Image.MIME[image.format]
                extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image.format]
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
            path = library.images_root / (asset["asset_id"] + extension)
            checksum = hashlib.sha256(data).hexdigest()
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                    raise QuickCharacterWizardConflict("A saved wizard image differs from this selection.")
            else:
                path.write_bytes(data)
                created_files.append(path)
            asset.update(path=path, checksum=checksum, mime_type=mime_type, width=width, height=height)
        with library.repository.transaction() as connection:
            for asset in assets:
                aid, view = asset["asset_id"], asset["view"]
                connection.execute(
                    "INSERT OR IGNORE INTO assets(asset_id,label,checksum,file_name,mime_type,width,height,origin,origin_key,"
                    "status,notes,prompt,negative_prompt,derived_from_asset_id,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (aid, asset["label"], asset["checksum"], asset["path"].name, asset["mime_type"],
                     asset["width"], asset["height"], "import" if view == "source" else "imagegen",
                     f"quick-character:{sid}:{revision}:{view}", "approved", "", asset["prompt"], asset["negative"],
                     None if view == "source" else source_id, stamp, stamp))
                for link in source_links:
                    # SQLite composite keys permit repeated NULL variants.
                    existing = connection.execute(
                        "SELECT 1 FROM asset_entities WHERE asset_id=? AND entity_id=? AND variant_id IS ? AND role=?",
                        (aid, link["entity_id"], link["variant_id"], link["role"])).fetchone()
                    if not existing:
                        connection.execute("INSERT INTO asset_entities VALUES(?,?,?,?)",
                                           (aid, link["entity_id"], link["variant_id"], link["role"]))
                if view == "source":
                    continue
                for namespace, value in (("view", view), ("framing", session["framing"]), ("pipeline", "quick-character")):
                    facet_id = stable_id(f"facet:{namespace}:{value}")
                    connection.execute("INSERT OR IGNORE INTO facets VALUES(?,?,?,?)", (facet_id, namespace, value, 1))
                    actual = connection.execute("SELECT facet_id FROM facets WHERE namespace=? AND value=?", (namespace, value)).fetchone()[0]
                    connection.execute("INSERT OR IGNORE INTO asset_facets VALUES(?,?)", (aid, actual))
                details = {"session_id": sid, "revision_id": revision, "view": view,
                           "candidate_id": asset["candidate"]["candidate_id"],
                           "request_id": asset["candidate"]["request_id"],
                           "references": [{k: r[k] for k in ("asset_id", "checksum", "caption")} for r in session["references"]],
                           "description": session["description"], "proposals": session["proposals"]}
                connection.execute("INSERT OR IGNORE INTO provenance VALUES(?,?,?,?,?,?)",
                                   (stable_id(f"provenance:{view}"), aid, "generated_from", source_id, json.dumps(details), stamp))
                connection.execute("INSERT OR IGNORE INTO descriptors VALUES(?,?,?,?,?,?,?,?,?)",
                                   (stable_id(f"identity:{view}"), "asset", aid, "prompt_identity", session["identity"], 0, 1, stamp, stamp))
            connection.execute("INSERT OR IGNORE INTO reference_sets VALUES(?,?,?,?,?,?,?)",
                               (set_id, f"{session['name']} · Quick Character {sid[:8]}", "identity",
                                session["description"], source_links[0]["entity_id"] if len(source_links) == 1 else None, stamp, stamp))
            for order, (view, asset_id) in enumerate([("source", source_id), *outputs.items()]):
                connection.execute("INSERT OR IGNORE INTO reference_set_assets VALUES(?,?,?,?)", (set_id, asset_id, view.lower(), order))
    except Exception:
        for path in created_files:
            path.unlink(missing_ok=True)
        raise
    # If index refresh fails, a retry reuses the committed IDs and refreshes again.
    app.refresh_library_index()
    return {"set_id": set_id, "source_asset_id": source_id, "asset_ids": outputs,
            "tags": {view: f"{{{{LIB:ASSET:{aid}}}}}" for view, aid in outputs.items()}}
