from __future__ import annotations

import argparse
import json
from pathlib import Path

from zet.services.config_service import ConfigService


def migrate_document(data: dict, path: Path) -> tuple[dict, bool]:
    if not isinstance(data, dict) or data.get("file_kind") != "scene":
        raise ValueError(f"Unsupported scene document: {path}")
    version = data.get("schema_version")
    if version not in {3, 4}:
        raise ValueError(f"Unsupported schema_version {version!r}: {path}")
    changed = version == 3 or "subscenes" not in data
    data["schema_version"] = 4
    data.setdefault("subscenes", [])
    if not isinstance(data["subscenes"], list):
        raise ValueError(f"subscenes must be an array: {path}")
    for element in data.get("scene_elements") or []:
        if not isinstance(element, dict):
            raise ValueError(f"scene_elements must contain objects: {path}")
        if "subscene_id" not in element:
            element["subscene_id"] = ""
            changed = True
    return data, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Zet Scene Builder documents from V3 to V4.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--apply", action="store_true", help="Write validated migrations; default is dry-run.")
    args = parser.parse_args()
    config = ConfigService.load(args.config)
    stories_path = Path(config.base_library_path) / "Stories"
    candidates: list[tuple[Path, dict]] = []
    for path in sorted(stories_path.rglob("*.scene.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Migration aborted: invalid JSON {path}: {exc}") from exc
        try:
            migrated, changed = migrate_document(data, path)
        except ValueError as exc:
            raise SystemExit(f"Migration aborted: {exc}") from exc
        if changed:
            candidates.append((path, migrated))
    print(f"Validated {len(list(stories_path.rglob('*.scene.json')))} scene files; {len(candidates)} require migration.")
    if not args.apply:
        print("Dry run only. Re-run with --apply to write changes.")
        return 0
    for path, data in candidates:
        temporary = path.with_name(f".{path.name}.v4.tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    print(f"Migrated {len(candidates)} scene files to V4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
