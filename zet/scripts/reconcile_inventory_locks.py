"""Preview and apply an offline, universe-scoped Inventory lock reconciliation."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService
from zet.services.library_reference_service import write_library_json
from zet.services.workflow_storage import file_lock
from zet.services.atomic_file_service import write_json_atomic


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confined(root, path):
    path = path.resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Path is outside the selected universe: {path}")
    return path


def preview(root):
    catalog = root / "catalog.sqlite3"
    with closing(sqlite3.connect(catalog.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = {r["asset_id"]: dict(r) for r in db.execute("SELECT * FROM assets")}
        references = {}
        for table in ("asset_usages", "logical_references", "reference_set_assets"):
            for row in db.execute(f"SELECT * FROM {table}"):
                if row["asset_id"]:
                    references.setdefault(row["asset_id"], []).append({"table": table, **dict(row)})

    records, bindings, moves, unlocks = {}, [], [], []
    by_owner = {row["lock_owner"]: row for row in rows.values() if row.get("lock_owner")}
    claimed = set()

    def load(path):
        confined(root, path)
        if path.with_suffix(".inventory-journal").exists():
            raise ValueError(f"Recover the pending workflow journal first: {path}")
        data = path.read_bytes()
        records[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    def bind(path, parts, candidate, source, label, prompt, asset_id, origin, **classification):
        owner = EntityLibraryService.lock_owner(*parts)
        row = by_owner.get(owner) or rows.get(asset_id)
        if asset_id and not row:
            raise ValueError(f"Missing catalog ID {asset_id} in {path}")
        source = confined(root, source)
        digest = fingerprint(source)
        if row:
            asset_id = row["asset_id"]
            if asset_id in claimed or row.get("lock_owner") not in (None, owner) or row["checksum"] != digest:
                raise ValueError(f"Cannot prove lock ownership for {asset_id} in {path}")
            claimed.add(asset_id)
        relative = source.relative_to(root).as_posix()
        if row and row.get("lock_candidate") == candidate and row.get("lock_path") == relative:
            return
        bindings.append(dict(record=path.relative_to(root).as_posix(), owner=owner, candidate=candidate,
                             source=relative, checksum=digest, asset_id=asset_id or "", label=label,
                             prompt=prompt or "", origin=origin, classification=classification))

    for path in sorted(root.glob("_state/CharacterAssetContainers/*/*/*/*/container.json")):
        data = load(path)
        if data.get("_pending_publication_id") or any(path.parent.glob("publications/*.json")):
            raise ValueError(f"Recover pending character publication first: {path}")
        scope = data["scope"]
        for view, board in data["boards"].items():
            locked = [cid for cid, candidate in board["candidates"].items() if candidate.get("locked")]
            if not locked:
                continue
            if locked != [board["selected_id"]] or locked[0] not in board["slots"]:
                raise ValueError(f"Invalid locked board: {path} ({view})")
            item = board["candidates"][locked[0]]
            source = root / (item.get("locked_image_path") or item["image_path"])
            bind(path, ("character", data["container_id"], view), locked[0], source,
                 " · ".join(filter(None, (scope["character"], scope["phase"], scope["costume"],
                                           scope["pipeline"], view))), item.get("prompt"),
                 item.get("inventory_asset_id"), "pipeline",
                 **{key: scope[key] for key in ("character", "phase", "costume")}, view=view)

    for path in sorted(root.glob("_state/QuickCharacterWizard/*/session.json")):
        data = load(path)
        if data.get("workflow_version") == 2:
            for view, board in data["boards"].items():
                locked = [item for item in board["candidates"].values() if item.get("locked")]
                if not locked:
                    continue
                if len(locked) != 1 or locked[0]["id"] != board["selected_id"] or board["selected_id"] not in board["slots"]:
                    raise ValueError(f"Invalid Minor Character board: {path} ({view})")
                item = locked[0]
                bind(path, ("minor", data["session_id"], view), item["id"], path.parent / item["image_path"],
                     f"{data['name']} · {view}", item["prompt"], item.get("inventory_asset_id"), "imagegen")
            continue
        if data.get("workflow_version") != 1 or data.get("deleted_at") or data.get("status") == "ABANDONED":
            continue
        final = data.get("final_locked") or {}
        draft = data.get("locked") or {}
        for view, lock in sorted({**draft, **final}.items()):
            cid = lock["candidate_id"]
            matches = [c for c in data["candidates"] if c["candidate_id"] == cid and c["view"] == view]
            if len(matches) != 1:
                raise ValueError(f"Cannot locate Minor Character lock: {path} ({view})")
            candidate = matches[0]
            if view in final and view in draft:
                unlocks.append(dict(record=path.relative_to(root).as_posix(), view=view,
                                    candidate=draft[view]["candidate_id"]))
            source = path.parent / (lock.get("snapshot") or candidate["filename"])
            if lock.get("asset_id"):
                row = rows[lock["asset_id"]]
                if row.get("lock_path"):
                    source = root / row["lock_path"]
                elif not row.get("lock_owner"):
                    source = root / "images" / row["file_name"]
            bind(path, ("minor", data["session_id"], view), cid, source, f"{data['name']} · {view}",
                 candidate.get("prompt"), lock.get("asset_id"), "imagegen")

    for story_path in sorted(root.glob("NarrativeStories/*/story.json")):
        story = load(story_path)
        for scene_id in story["scene_ids"]:
            scene_path = confined(root, story_path.parent / scene_id / "scene.json")
            scene = load(scene_path)
            for target_id in scene["target_ids"]:
                path = confined(root, scene_path.parent / target_id / "target.json")
                target = load(path)
                locked = [cid for cid, c in target["candidates"].items() if c.get("locked")]
                if not locked:
                    continue
                if locked != [target["selected_id"]] or locked[0] not in target["slots"]:
                    raise ValueError(f"Invalid locked Narrative target: {path}")
                item = target["candidates"][locked[0]]
                source = path.parent / (item.get("scene_text_final", {}).get("image") or item["image"])
                bind(path, ("narrative", story_path.parent.name, scene_id, target_id), locked[0],
                     source, target["title"], item.get("prompt"), item.get("published_asset_id"), "narrative")

    for path in sorted(root.glob("Characters/*/*/IdentityKeys.json")):
        for item in load(path)["identity_keys"]:
            key = hashlib.sha256(json.dumps([item["character"], item["phase"], item["identity_key_id"]]).encode()).hexdigest()
            key = f"identity-key.{key}"
            matching = [r for r in rows.values() if r["origin_key"] == key and r["status"] == "approved"]
            if matching:
                row = matching[0]
                source = root / (row.get("lock_path") or f"images/{row['file_name']}")
                bind(path, ("identity", key), item["identity_key_id"], source,
                     row["label"], row["prompt"], row["asset_id"], "pipeline")

    active_paths = {entry["source"] for entry in bindings}
    active_paths.update(row["lock_path"] for row in rows.values() if row.get("lock_path"))
    for asset_id, row in sorted(rows.items()):
        key = row.get("origin_key") or ""
        managed = (row["origin"] == "pipeline" and key.casefold().startswith("local:")
                   or row["origin"] == "narrative" and key.startswith("narrative:")
                   or row["origin"] == "imagegen" and key.startswith("minor-character:"))
        if not managed or asset_id in claimed or row.get("lock_owner"):
            continue
        name = row["file_name"]
        if name != Path(name).name:
            raise ValueError(f"Invalid managed filename: {name}")
        source = confined(root, root / "images" / name)
        destination = confined(root, root / "OrphanedImages" / name)
        if source.relative_to(root).as_posix() in active_paths:
            raise ValueError(f"An orphan and a current lock share a managed file: {source}")
        if destination.exists():
            raise ValueError(f"Orphan destination already exists: {destination}")
        moves.append(dict(asset_id=asset_id, label=row["label"], source=source.relative_to(root).as_posix(),
                          destination=destination.relative_to(root).as_posix(),
                          checksum=fingerprint(source) if source.is_file() else None,
                          references=references.get(asset_id, [])))
    return dict(universe=str(root), records=records, bindings=bindings, unlocks=unlocks, moves=moves)


def apply(root, approved):
    """Writers must be stopped. The reviewed manifest also serves as the recovery plan."""
    catalog = root / "catalog.sqlite3"
    journal = root / "_state" / "inventory-reconciliation.json"
    with file_lock(journal.with_suffix(".lock")):
        if journal.exists():
            state = json.loads(journal.read_text(encoding="utf-8"))
            if state["manifest"] != approved:
                raise ValueError("Resume with the original reviewed manifest.")
        else:
            if preview(root) != approved:
                raise ValueError("The library changed. Generate a fresh preview.")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            backup = root / "backups" / f"inventory-reconciliation-{stamp}"
            backup.mkdir(parents=True)
            with closing(sqlite3.connect(catalog.as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(backup / "catalog.sqlite3")) as saved:
                    original.backup(saved)
                    if saved.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("Catalog backup failed verification.")
            affected = {item["record"] for item in approved["bindings"] + approved["unlocks"]}
            for relative in sorted(affected):
                destination = backup / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / relative, destination)
                if fingerprint(destination) != approved["records"][relative]:
                    raise ValueError(f"Record changed while backing it up: {relative}")
            state = {"manifest": approved, "backup": str(backup), "completed": []}
            write_json_atomic(journal, state)

        def step(key, action):
            if key not in state["completed"]:
                action()
                state["completed"].append(key)
                write_json_atomic(journal, state)

        repository = EntityLibraryRepository(catalog)
        repository.initialize()
        library = EntityLibraryService(SimpleNamespace(config=SimpleNamespace(base_library_path=root),
                                                        entity_library_images_path=lambda: root / "images"),
                                       repository)

        def bind(item):
            source = confined(root, root / item["source"])
            if fingerprint(source) != item["checksum"]:
                raise ValueError(f"Locked image changed: {source}")
            path = confined(root, root / item["record"])
            record = json.loads(path.read_text(encoding="utf-8"))
            parts = json.loads(item["owner"])
            cid = item["candidate"]
            asset = library.bind_workflow_lock(item["owner"], cid, source, label=item["label"],
                prompt=item["prompt"], origin=item["origin"], existing_id=item["asset_id"], **item["classification"])
            if parts[0] == "character":
                candidate = record["boards"][parts[2]]["candidates"][cid]
                candidate.update(inventory_asset_id=asset["asset_id"], locked_image_path=str(source),
                                 image_sha256=item["checksum"])
                write_json_atomic(path, record)
            elif parts[0] == "minor":
                view = parts[2]
                if record.get("workflow_version") == 2:
                    record["boards"][view]["candidates"][cid]["inventory_asset_id"] = asset["asset_id"]
                    write_json_atomic(path, record)
                    return
                lock = record.get("final_locked", {}).get(view) or record["locked"][view]
                lock["asset_id"] = asset["asset_id"]
                # A historical private snapshot remains the workflow-owned image.
                write_library_json(path, record, root)
            elif parts[0] == "narrative":
                record["candidates"][cid]["published_asset_id"] = asset["asset_id"]
                write_library_json(path, record, root)

        def unlock(item):
            path = confined(root, root / item["record"])
            record = json.loads(path.read_text(encoding="utf-8"))
            current = record["locked"].get(item["view"])
            if current:
                if current["candidate_id"] != item["candidate"]:
                    raise ValueError(f"Minor Character lock changed: {path}")
                del record["locked"][item["view"]]
                write_library_json(path, record, root)

        def move(item):
            source = confined(root, root / item["source"])
            destination = confined(root, root / item["destination"])
            if item["checksum"]:
                if source.exists():
                    if destination.exists() or fingerprint(source) != item["checksum"]:
                        raise ValueError(f"Orphan source or destination changed: {source}")
                elif not destination.is_file() or fingerprint(destination) != item["checksum"]:
                    raise ValueError(f"Cannot locate the reviewed orphan: {source}")
            elif source.exists() or destination.exists():
                raise ValueError(f"Orphan file appeared after review: {source}")
            asset_id = item["asset_id"]
            with repository.transaction() as db:
                db.execute("""UPDATE assets SET status='archived',lock_owner=?,lock_path=NULL,lock_candidate=NULL
                              WHERE asset_id=?""", (library.lock_owner("orphan", asset_id), asset_id))
                library._deactivate_asset_references(db, [asset_id], datetime.now(timezone.utc).isoformat())
            if source.exists():
                destination.parent.mkdir(exist_ok=True)
                source.rename(destination)

        for item in approved["bindings"]:
            step(item["owner"], lambda: bind(item))
        for item in approved["unlocks"]:
            step(f"unlock:{item['record']}:{item['view']}", lambda: unlock(item))
        for item in approved["moves"]:
            step(f"move:{item['asset_id']}", lambda: move(item))
        write_json_atomic(Path(state["backup"]) / "reconciliation.json", state)
        journal.unlink()
        return state["backup"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("universe", type=Path)
    parser.add_argument("--apply-reviewed", type=Path, help="Apply the exact reviewed JSON manifest.")
    parser.add_argument("--writers-stopped", action="store_true", help="Confirm Zet and library writers are stopped.")
    args = parser.parse_args()
    root = args.universe.resolve(strict=True)
    if args.apply_reviewed:
        if not args.writers_stopped:
            parser.error("--apply-reviewed requires --writers-stopped")
        manifest = json.loads(args.apply_reviewed.read_text(encoding="utf-8-sig"))
        print(apply(root, manifest))
    else:
        print(json.dumps(preview(root), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
