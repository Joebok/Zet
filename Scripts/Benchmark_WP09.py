"""Benchmark full machine-local index rebuilds at WP01 fixture scales."""

from __future__ import annotations

import json
import platform
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.support.reliability_fixture import write_reliability_fixture
from zet.services.config_service import ConfigService
from zet.services.library_index_service import LibraryIndexService


def run_wp09_benchmark(scales: tuple[int, ...] = (1, 10, 100)) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scale in scales:
        with tempfile.TemporaryDirectory(prefix=f"zet-wp09-{scale}x-") as temporary:
            root = Path(temporary)
            fixture = write_reliability_fixture(root / "authored-library", scale=scale)
            config = ConfigService.load(fixture.config_path)
            service = LibraryIndexService(config, index_root=root / "machine-state")
            for state in ("cold", "warm"):
                started = perf_counter()
                report = service.rebuild()
                rebuild_seconds = perf_counter() - started
                query_started = perf_counter()
                queried_scenes = 0
                cursor = None
                while True:
                    page = service.repository.query_scenes(
                        story_slug=fixture.story_slug, cursor=cursor, limit=500
                    )
                    queried_scenes += len(page.items)
                    cursor = page.next_cursor
                    if cursor is None:
                        break
                query_seconds = perf_counter() - query_started
                results.append(
                    {
                        **fixture.benchmark_metadata(scale=scale, state=state, concurrent_activity="none"),
                        "rebuild_seconds": round(rebuild_seconds, 6),
                        "query_seconds": round(query_seconds, 6),
                        "indexed_counts": report["counts"],
                        "queried_scenes": queried_scenes,
                        "temporary_index": True,
                    }
                )
    return results


def main() -> None:
    print(
        json.dumps(
            {
                "runner": {
                    "platform": platform.platform(),
                    "python": sys.version.split()[0],
                    "temporary_roots": True,
                },
                "benchmarks": run_wp09_benchmark(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
