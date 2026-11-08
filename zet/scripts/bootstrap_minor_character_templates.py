"""Preview and apply a name-and-source-only Minor Character bootstrap."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from uuid import NAMESPACE_URL, uuid5

from zet.scripts.reconcile_inventory_locks import confined, fingerprint
from zet.services.minor_character_templates import MinorCharacterTemplates, matches_seed, seed
from zet.services.workflow_storage import file_lock, validate_image


def _source(record, path):
    if record["workflow_version"] == 2:
        source = record.get("source") or {}
        archive = path.with_name("session.legacy-v1.json")
        original = json.loads(archive.read_bytes()) if archive.is_file() else {}
        _, original_id = _primary(original)
        return source.get("file"), original_id
    return _primary(record)


def _primary(record):
    item = next((row for row in record.get("references", [])
                 if row.get("reference_id") == record.get("primary_reference_id")), {})
    return item.get("filename"), item.get("asset_id")


def _available(root, asset, digest=None):
    if asset["status"] == "archived" or asset["lock_owner"]:
        return False
    try:
        path = confined(root, root / "images" / asset["file_name"])
        validate_image(path.read_bytes())
        return fingerprint(path) == asset["checksum"] and (digest is None or digest == asset["checksum"])
    except (OSError, ValueError):
        return False


def preview(root, choices=None):
    choices = choices or {}
    with closing(sqlite3.connect((root / "catalog.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        assets = {row["asset_id"]: dict(row) for row in db.execute("SELECT * FROM assets")}
    rows = []
    for path in sorted(root.glob("_state/QuickCharacterWizard/*/session.json")):
        path = confined(root, path)
        record = json.loads(path.read_bytes())
        if record.get("workflow_version") not in (1, 2) or record.get("deleted_at") or record.get("status") == "ABANDONED":
            continue
        old_id = path.parent.name
        sid = uuid5(NAMESPACE_URL, f"zet-minor-template:{old_id}").hex
        destination = MinorCharacterTemplates(root).path(sid)
        row = {"legacy_id": old_id, "record_hash": fingerprint(path), "name": record["name"],
               "character_id": sid, "template": destination.relative_to(root).as_posix(),
               "asset_id": "", "matches": [], "blockers": []}
        rows.append(row)
        if path.with_suffix(".inventory-journal").exists():
            row["blockers"].append("Pending Inventory publication.")
        candidates = record.get("candidates", []) + [
            item for board in record.get("boards", {}).values() for item in board["candidates"].values()]
        active = {"QUEUING", "SUBMITTING", "QUEUED", "RUNNING", "REVIEWING"}
        if record.get("job", {}).get("status") in active or any(
                item.get("status") in active for item in candidates) or any(
                board.get(key, {}).get("status") in active
                for board in record.get("boards", {}).values() for key in ("text_job", "luna_review")):
            row["blockers"].append("Pending legacy AI work.")
        if any(asset["lock_path"] and asset["lock_owner"] and
               json.loads(asset["lock_owner"])[:2] == ["minor", old_id] for asset in assets.values()):
            row["blockers"].append("Active legacy Inventory locks. Resolve them before cutover.")
        digest = None
        relative, original_id = _source(record, path)
        if relative:
            try:
                source = confined(root, path.parent / relative)
                if not source.is_relative_to(path.parent):
                    raise ValueError("Invalid saved source path.")
                validate_image(source.read_bytes())
                digest = fingerprint(source)
            except (OSError, ValueError):
                pass
        row["source_hash"] = digest
        matches = [asset for asset in assets.values()
                   if digest and asset["checksum"] == digest and _available(root, asset, digest)]
        row["matches"] = sorted([{"asset_id": asset["asset_id"], "label": asset["label"]} for asset in matches],
                                key=lambda item: item["asset_id"])
        if old_id in choices:
            selected = assets.get(choices[old_id])
            if selected and _available(root, selected):
                row["asset_id"] = selected["asset_id"]
        elif original_id in {asset["asset_id"] for asset in matches}:
            row["asset_id"] = original_id
        elif len(matches) == 1:
            row["asset_id"] = matches[0]["asset_id"]
        elif root.name.casefold() == "moonsea" and record["name"] == "Galen":
            dedicated = [asset for asset in matches if asset["label"] == "Galen · Source"]
            if len(dedicated) == 1:
                row["asset_id"] = dedicated[0]["asset_id"]
        if not row["asset_id"]:
            row["blockers"].append("Choose an eligible Inventory asset for this source.")
        else:
            row["asset_checksum"] = assets[row["asset_id"]]["checksum"]
            if destination.exists() and not matches_seed(destination.read_text(encoding="utf-8-sig"), row["name"], row["asset_id"]):
                row["blockers"].append("Destination template already contains different data.")
    names = [row["name"].casefold() for row in rows]
    for row in rows:
        if names.count(row["name"].casefold()) > 1:
            row["blockers"].append("Duplicate active Minor Character name.")
    return {"universe": str(root), "choices": choices, "characters": rows}


def apply(root, approved):
    store = MinorCharacterTemplates(root)
    with file_lock(store.root / ".bootstrap.lock"):
        if approved != preview(root, approved["choices"]) or any(row["blockers"] for row in approved["characters"]):
            raise ValueError("The preview changed or has blockers. Review a fresh preview.")
        for row in approved["characters"]:
            if not store.path(row["character_id"]).exists():
                store.write(row["character_id"], seed(row["name"], row["asset_id"]))
    return len(approved["characters"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("universe", type=Path)
    parser.add_argument("--choices", type=Path, help="JSON mapping of legacy IDs to reviewed Inventory IDs")
    parser.add_argument("--apply-reviewed", type=Path)
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args()
    root = args.universe.resolve(strict=True)
    if args.apply_reviewed:
        if not args.writers_stopped:
            parser.error("--apply-reviewed requires --writers-stopped")
        print(apply(root, json.loads(args.apply_reviewed.read_text(encoding="utf-8-sig"))))
    else:
        choices = json.loads(args.choices.read_text(encoding="utf-8-sig")) if args.choices else None
        print(json.dumps(preview(root, choices), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
