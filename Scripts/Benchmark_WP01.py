"""Run the isolated WP01 fixture benchmark at 1x, 10x, and 100x scale."""

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

from fastapi.testclient import TestClient

from tests.support.reliability_fixture import write_reliability_fixture
from zet.render_console.queue import RenderConsoleQueue
from zet.services.performance_instrumentation import PerformanceInstrumentation, collect
from zet.services.scene_render_compiler import compile_scene_render_ir
from zet.web.app import create_app
from zet.app import ZetApp


DEFAULT_PROMPT_SECTIONS = {
    "anatomical_requirements": "# Anatomical Requirements\nfixture",
    "avoid": "# Avoid\nfixture",
    "high_risk_elements": "# High-Risk Elements\nfixture",
    "final_verification": "# Final Verification\nfixture",
}


def _exercise(fixture, app: ZetApp, queue: RenderConsoleQueue) -> None:
    app.list_scenes(fixture.story_slug)
    app.load_scene(fixture.story_slug, fixture.scene_slugs[0])
    app.image_catalog_service.list_items(include_base=True)
    queue.list_tasks()
    app.ai_proxy_service.recent_harvests()
    builder = app.story_service.load_scene_builder_data(fixture.story_slug, fixture.scene_slugs[0])
    settings_path = app.story_service.get_story_settings_path_from_story_md(
        app.story_service.path_service.story_file_path(fixture.story_slug)
    )
    compile_scene_render_ir(
        builder.data,
        app.story_service.load_story_settings(settings_path),
        default_prompt_sections=DEFAULT_PROMPT_SECTIONS,
    )


def run_wp01_benchmark(scales: tuple[int, ...] = (1, 10, 100)) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scale in scales:
        with tempfile.TemporaryDirectory(prefix=f"zet-wp01-{scale}x-") as temp_dir:
            fixture = write_reliability_fixture(Path(temp_dir), scale=scale)
            app = None
            queue = None
            for state in ("cold", "warm"):
                metrics = PerformanceInstrumentation()
                with collect(metrics):
                    started = perf_counter()
                    if app is None:
                        app = ZetApp.from_config(fixture.config_path)
                        queue = RenderConsoleQueue(app.config)
                    _exercise(fixture, app, queue)
                    duration_seconds = perf_counter() - started
                    client = TestClient(create_app(fixture.config_path, performance=metrics))
                    endpoint_response = client.get("/api/stories")
                    endpoint_response.raise_for_status()

                results.append(
                    {
                        **fixture.benchmark_metadata(
                            scale=scale, state=state, concurrent_activity="none"
                        ),
                        "duration_seconds": round(duration_seconds, 6),
                        "endpoint_status": endpoint_response.status_code,
                        "instrumentation": metrics.snapshot(),
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
                "benchmarks": run_wp01_benchmark(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
