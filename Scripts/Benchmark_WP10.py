"""Benchmark incremental reconciliation at WP01 fixture scales."""

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


def run_wp10_benchmark(scales: tuple[int, ...] = (1, 10, 100)) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scale in scales:
        with tempfile.TemporaryDirectory(prefix=f"zet-wp10-{scale}x-") as temporary:
            root = Path(temporary)
            fixture = write_reliability_fixture(root / "authored-library", scale=scale)
            service = LibraryIndexService(
                ConfigService.load(fixture.config_path),
                index_root=root / "machine-state",
                project_root=PROJECT_ROOT,
            )
            service.reconcile()
            for state in ("unchanged", "one_changed"):
                if state == "one_changed":
                    scene = fixture.root / "Stories" / fixture.story_slug / f"{fixture.scene_slugs[0]}.scene.json"
                    value = json.loads(scene.read_text(encoding="utf-8"))
                    value["scene"]["name"] = "WP10 changed scene"
                    scene.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
                started = perf_counter()
                report = service.reconcile()
                duration_seconds = perf_counter() - started
                results.append(
                    {
                        **fixture.benchmark_metadata(
                            scale=scale, state=state, concurrent_activity="none"
                        ),
                        "reconciliation_seconds": round(duration_seconds, 6),
                        "changed_sources": len(report["changed_sources"]),
                        "parsed_sources": report["parsed_sources"],
                        "reused_sources": report["reused_sources"],
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
                "benchmarks": run_wp10_benchmark(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
