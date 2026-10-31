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

    def add(raw: str | Path, base: Path) -> None:
        path = Path(raw)
        path = (path if path.is_absolute() else base / path).resolve()
        if not path.is_relative_to(source):
            raise ValueError(f"Image path is outside the source library: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Eligible image is missing: {path}")
        images.add(path)

    for catalog in source.rglob("catalog.sqlite3"):
        root = catalog.parent
        with closing(sqlite3.connect(catalog.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            for asset_id, file_name in db.execute("SELECT asset_id, file_name FROM assets"):
                name = Path(file_name).name
                if name != file_name or not name:
                    raise ValueError(f"Invalid inventory filename in {catalog}")
                add(root / "images" / (f"{asset_id}{name}" if name.startswith(".") else name), root)

    for path in source.rglob("local_assets.json"):
        if "LocalAssets" not in path.parts:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        universe = path.parents[4]
        for asset in record.get("assets", {}).values():
            if asset.get("render_mode") == "final" and asset.get("locked"):
                add(asset["locked_image_path"], universe)

    for path in source.rglob("session.json"):
        if path.parent.parent.name != "QuickCharacterWizard":
            continue
        session = json.loads(path.read_text(encoding="utf-8"))
        if session.get("deleted_at"):
            continue
        for lock in (session.get("final_locked") or {}).values():
            if lock.get("snapshot"):
                add(lock["snapshot"], path.parent)
            # Published Final locks are included by the authoritative catalog.

    for path in source.rglob("target.json"):
        if "NarrativeStories" not in path.parts:
            continue
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
