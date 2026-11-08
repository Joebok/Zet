"""Preview or apply a reviewed offline Minor Character collection migration."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.scripts.reconcile_inventory_locks import confined, fingerprint
from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.entity_library_service import EntityLibraryService
from zet.services.minor_character_service import VIEWS, empty_collection
from zet.services.minor_character_workflow_service import MinorCharacterWorkflow
from zet.services.workflow_storage import file_lock, validate_image


def _valid_id(value):
    return isinstance(value, str) and len(value) == 32 and all(char in "0123456789abcdef" for char in value)


def _checked_image(root, path, checksum=None):
    path = confined(root, path)
    validate_image(path.read_bytes())
    digest = fingerprint(path)
    if checksum and checksum != digest:
        raise ValueError("Image checksum does not match its saved record.")
    return {"path": path.relative_to(root).as_posix(), "sha256": digest}


def preview(root):
    with closing(sqlite3.connect((root / "catalog.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = {row["asset_id"]: dict(row) for row in db.execute("SELECT * FROM assets")}
    owners = {row["lock_owner"]: row for row in rows.values() if row["lock_owner"]}
    collections = []
    for path in sorted(root.glob("_state/QuickCharacterWizard/*/session.json")):
        path = confined(root, path)
        old = json.loads(path.read_bytes())
        if old.get("workflow_version") != 1 or old.get("deleted_at") or old.get("status") == "ABANDONED":
            continue
        sid = path.parent.name
        plan = {"sid": sid, "name": old["name"], "record": path.relative_to(root).as_posix(),
                "sha256": fingerprint(path), "source": None, "locks": {}, "deactivate": [],
                "issues": [], "blockers": []}
        collections.append(plan)
        if not _valid_id(sid) or sid != old.get("session_id"):
            plan["blockers"].append("Record and collection ownership disagree.")
        if path.with_suffix(".inventory-journal").exists():
            plan["blockers"].append("Pending Inventory publication.")
        working = MinorCharacterWorkflow._working_ids(old)
        if old.get("job", {}).get("status") in {"QUEUING", "QUEUED", "RUNNING"} or any(
                item["status"] in {"QUEUING", "QUEUED", "RUNNING", "REVIEWING"}
                for item in old["candidates"] if item["candidate_id"] in working):
            plan["blockers"].append("Pending legacy AI work.")
        primary = next((item for item in old["references"]
                        if item["reference_id"] == old.get("primary_reference_id")), None)
        try:
            if primary is None:
                raise ValueError("No primary source image is recorded.")
            plan["source"] = {**_checked_image(root, path.parent / primary["filename"], primary.get("checksum")),
                              "label": primary.get("caption") or "Original character reference"}
        except (OSError, ValueError) as exc:
            plan["issues"].append(str(exc))
        for view in VIEWS:
            final = old.get("final_locked", {}).get(view)
            draft = old.get("locked", {}).get(view)
            owner = EntityLibraryService.lock_owner("minor", sid, view)
            alias = owners.get(owner)
            try:
                if not final:
                    if alias and alias["lock_path"]:
                        if not draft or alias["lock_candidate"] != draft["candidate_id"]:
                            raise ValueError("Active Inventory alias does not match the Draft lock.")
                        plan["deactivate"].append({"owner": owner, "alias": alias})
                    continue
                cid = final["candidate_id"]
                if not _valid_id(cid) or cid not in old["final_boards"][view]["slots"]:
                    raise ValueError("Final lock is outside its board.")
                matches = [item for item in old["candidates"] if item["candidate_id"] == cid and item["view"] == view]
                if len(matches) != 1:
                    raise ValueError("Could not identify the Final candidate uniquely.")
                item = matches[0]
                if item.get("render_mode") != "final" or not isinstance(item.get("prompt"), str):
                    raise ValueError("Final quality or submitted prompt could not be verified.")
                asset_id = final.get("asset_id") or ""
                row = rows[asset_id] if asset_id else alias
                if row and (row["lock_owner"] not in (None, owner) or (alias and alias["asset_id"] != row["asset_id"])
                            or (row["lock_path"] and row["lock_candidate"] != cid)):
                    raise ValueError("Inventory ownership disagrees with the Final lock.")
                source = path.parent / (final.get("snapshot") or item["filename"])
                if row and row["lock_path"]:
                    source = root / row["lock_path"]
                elif row and not row["lock_owner"]:
                    source = root / "images" / row["file_name"]
                plan["locks"][view] = {"candidate": cid, "prompt": item["prompt"], "owner": owner,
                    "image": _checked_image(root, source, row["checksum"] if row else None),
                    "asset_id": row["asset_id"] if row else "", "alias": row}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                plan["blockers"].append(f"{view}: {exc}")
    return {"universe": str(root), "collections": collections}


def apply(root, approved):
    """Resume with the same manifest after an interruption and before restarting writers."""
    journal = root / "_state" / "minor-collection-migration.json"
    catalog = root / "catalog.sqlite3"
    with file_lock(journal.with_suffix(".lock")):
        if journal.exists():
            state = json.loads(journal.read_bytes())
            if state["manifest"] != approved:
                raise ValueError("Resume with the original reviewed migration manifest.")
        else:
            if approved != preview(root) or any(row["blockers"] for row in approved["collections"]):
                raise ValueError("The preview changed or contains blockers. Review a fresh preview.")
            backup = root / "backups" / f"minor-collections-{uuid4().hex}"
            backup.mkdir(parents=True)
            with closing(sqlite3.connect(catalog.as_uri() + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(backup / catalog.name)) as destination:
                    source.backup(destination)
            for row in approved["collections"]:
                original = confined(root, root / row["record"])
                write_bytes_atomic(backup / row["sid"] / "session.json", original.read_bytes())
            state = {"manifest": approved, "backup": str(backup), "done": []}
            write_json_atomic(journal, state)
        repository = EntityLibraryRepository(catalog)
        library = EntityLibraryService(SimpleNamespace(config=SimpleNamespace(base_library_path=root),
            entity_library_images_path=lambda: root / "images"), repository)
        for row in approved["collections"]:
            if row["sid"] not in state["done"]:
                _migrate(root, library, row)
                state["done"].append(row["sid"])
                write_json_atomic(journal, state)
        write_json_atomic(Path(state["backup"]) / "migration.json", state)
        journal.unlink()
        return state["backup"]


def _migrate(root, library, row):
    sid = row["sid"]
    path = confined(root, root / row["record"])
    archive = path.with_name("session.legacy-v1.json")
    original = json.loads(path.read_bytes())
    if original.get("workflow_version") == 2 and archive.is_file() and fingerprint(archive) == row["sha256"]:
        return
    if fingerprint(path) != row["sha256"] or path.with_suffix(".inventory-journal").exists():
        raise ValueError(f"Legacy session changed after review: {path}")
    if archive.exists() and fingerprint(archive) != row["sha256"]:
        raise ValueError(f"An unrelated archive already exists: {archive}")
    write_bytes_atomic(archive, path.read_bytes())
    value = empty_collection(sid, row["name"])

    def copy(evidence, key):
        source = confined(root, root / evidence["path"])
        contents = source.read_bytes()
        from hashlib import sha256
        if sha256(contents).hexdigest() != evidence["sha256"]:
            raise ValueError(f"Reviewed source changed: {source}")
        relative = f"collection-import/{key}{source.suffix}"
        write_bytes_atomic(path.parent / relative, contents)
        return relative

    if row["source"]:
        source = row["source"]
        value["source"] = {"file": copy(source, "source"), "label": source["label"]}
    for view, lock in row["locks"].items():
        cid = lock["candidate"]
        if not _valid_id(cid):
            raise ValueError("Invalid legacy candidate ID.")
        image = copy(lock["image"], cid)
        asset = library.bind_workflow_lock(lock["owner"], cid, path.parent / image, origin="imagegen",
            label=f"{row['name']} · {VIEWS[view]}", prompt=lock["prompt"], existing_id=lock["asset_id"])
        board = value["boards"][view]
        board["slots"][0] = board["selected_id"] = cid
        board["prompt"] = lock["prompt"]
        board["candidates"][cid] = {"id": cid, "candidate_id": cid, "slot": 1,
            "status": "COMPLETE", "render_mode": "final", "locked": True, "image": True,
            "image_path": image, "prompt": lock["prompt"], "inventory_asset_id": asset["asset_id"]}
    library.unbind_workflow_locks([item["owner"] for item in row["deactivate"]])
    write_json_atomic(path, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("universe", type=Path)
    parser.add_argument("--apply-reviewed", type=Path)
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    root = args.universe.resolve(strict=True)
    if args.apply_reviewed:
        if not args.writers_stopped:
            parser.error("--apply-reviewed requires --writers-stopped")
        print(apply(root, json.loads(args.apply_reviewed.read_text(encoding="utf-8-sig"))))
    else:
        print(json.dumps(preview(root), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
