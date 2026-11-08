"""Enumerate images eligible for the selective library copy."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys


def eligible_images(source: Path) -> list[Path]:
    source = source.resolve(strict=True)
    images: set[Path] = set()
    # Accept a universe root or a container with immediate universe folders.
    # Archived catalogs/workflow snapshots are not authoritative live metadata.
    universes = [source, *(path for path in source.iterdir()
                           if path.is_dir() and (path / "universe.json").is_file())]

    def add(raw: str | Path, base: Path) -> None:
        path = Path(raw)
        path = (path if path.is_absolute() else base / path).resolve()
        if not path.is_relative_to(source):
            raise ValueError(f"Image path is outside the source library: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Eligible image is missing: {path}")
        images.add(path)

    for catalog in (root / "catalog.sqlite3" for root in universes):
        if not catalog.is_file():
            continue
        root = catalog.parent
        with closing(sqlite3.connect(catalog.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(assets)")}
            symbolic = "lock_owner" in columns
            fields = "asset_id,file_name,lock_owner,lock_path" if symbolic else "asset_id,file_name,NULL,NULL"
            for asset_id, file_name, owner, lock_path in db.execute(f"SELECT {fields} FROM assets"):
                if owner:
                    if lock_path:
                        add(lock_path, root)
                    continue
                name = Path(file_name).name
                if name != file_name or not name:
                    raise ValueError(f"Invalid inventory filename in {catalog}")
                add(root / "images" / (f"{asset_id}{name}" if name.startswith(".") else name), root)

    for path in (path for root in universes
                 for path in (root / "_state" / "LocalAssets").glob("*/*/local_assets.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        universe = path.parents[4]
        if (universe / "_state" / "CharacterAssetContainers").is_dir():
            continue
        for asset in record.get("assets", {}).values():
            if asset.get("render_mode") == "final" and asset.get("locked"):
                add(asset["locked_image_path"], universe)

    for path in (path for root in universes
                 for path in (root / "_state" / "QuickCharacterWizard").glob("*/session.json")):
        session = json.loads(path.read_text(encoding="utf-8"))
        if session.get("deleted_at"):
            continue
        for lock in (session.get("final_locked") or {}).values():
            if lock.get("snapshot"):
                add(lock["snapshot"], path.parent)
            # Published Final locks are included by the authoritative catalog.

    for path in (path for root in universes
                 for path in (root / "NarrativeStories").glob("*/*/*/target.json")):
        target = json.loads(path.read_text(encoding="utf-8"))
        for candidate in (target.get("candidates") or {}).values():
            if candidate.get("render_mode", "draft") == "final" and candidate.get("locked"):
                final = candidate.get("scene_text_final") or {}
                add(final.get("image") or candidate["image"], path.parent)
    return sorted(images)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps([str(path) for path in eligible_images(args.source)]))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f"Cannot enumerate eligible backup images: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
