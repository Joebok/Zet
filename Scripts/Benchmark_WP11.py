"""Benchmark fixed indexed pages against tenfold unrelated list growth."""

from __future__ import annotations

import json
import platform
import sys
import tempfile
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.repositories.library_index_repository import IndexSnapshot, LibraryIndexRepository
from zet.services.performance_instrumentation import collect


def row(number: int) -> dict:
    payload = {"catalog_id": f"item-{number:06d}", "label": f"Item {number:06d}"}
    return {
        "list_kind": "inventory", "item_key": payload["catalog_id"],
        "sort_key": payload["label"].casefold(), "character_name": "", "phase": "",
        "story_slug": "", "scene_slug": "", "source_key": "", "status": "ready",
        "source_type": "managed", "semantic_category": "Object", "costume": "",
        "pipeline": "", "subscene_id": "", "collections_text": "||",
        "keywords_text": "||", "search_text": payload["label"].casefold(), "is_base": 0,
        "payload_json": json.dumps(payload, separators=(",", ":")),
    }


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory(prefix="zet-wp11-") as temporary:
        root = Path(temporary)
        library = root / "library"
        library.mkdir()
        repository = LibraryIndexRepository(library, index_root=root / "machine-index")
        for scale, size in ((1, 500), (10, 5000)):
            generation = repository.begin_rebuild()
            repository.publish(
                generation,
                IndexSnapshot(list_items=tuple(row(number) for number in range(size))),
            )
            with collect(patch_path_reads=False) as instrumentation:
                started = perf_counter()
                page = repository.query_indexed_list("inventory", limit=50)
                elapsed = perf_counter() - started
            results.append({
                "scale": scale, "indexed_items": size, "page_items": len(page.items),
                "total": page.total, "query_seconds": round(elapsed, 6),
                "scene_loads": instrumentation.counts["scene_loads"],
                "render_compiles": instrumentation.counts["render_compiles"],
            })
    if any(item["page_items"] != 50 or item["scene_loads"] or item["render_compiles"] for item in results):
        raise SystemExit("WP11 bounded-work assertion failed")
    print(json.dumps({
        "runner": {"platform": platform.platform(), "python": sys.version.split()[0]},
        "benchmarks": results,
    }, indent=2))


if __name__ == "__main__":
    main()
