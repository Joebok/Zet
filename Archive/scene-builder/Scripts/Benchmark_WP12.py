"""Rehearse catalog migration and verify WP12 scale acceptance on isolated copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.support.reliability_fixture import ReliabilityFixture, write_reliability_fixture
from zet.repositories.image_catalog_repository import ImageCatalogRepository
from zet.services.config_service import ConfigService
from zet.services.image_catalog_migration_service import (
    ImageCatalogMigrationInterrupted,
    ImageCatalogMigrationService,
)
from zet.services.library_index_service import LibraryIndexService
from zet.services.path_service import PathService
from zet.services.performance_instrumentation import collect
from zet.services.scene_render_compiler import compile_scene_render_ir, final_image_prompt_text
from zet.services.summary_cache import SummaryCache

DEFAULT_PROMPT_SECTIONS = {
    "anatomical_requirements": "# Anatomical Requirements\nfixture",
    "avoid": "# Avoid\nfixture",
    "high_risk_elements": "# High-Risk Elements\nfixture",
    "final_verification": "# Final Verification\nfixture",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _p95(values: list[float]) -> float:
    return sorted(values)[int(0.95 * len(values)) - 1]


def _add_first_day_tasks(fixture: ReliabilityFixture) -> None:
    """Give every one of the eight base scenes an isolated active task association."""
    queue = fixture.root / "Queue" / "Manual_Render_Queue" / "Ask"
    template = json.loads((queue / "WP01_ACTIVE_001" / "ask_manifest.json").read_text(encoding="utf-8"))
    for number, scene_slug in enumerate(fixture.scene_slugs[:8], start=1):
        ask_id = f"WP12_FIRST_DAY_{number:03d}"
        folder = queue / ask_id
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {**template, "ask_id": ask_id, "scene_slug": scene_slug}
        (folder / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (folder / "Final_Image_Prompt.md").write_text(
            f"deterministic First Day prompt for {scene_slug}\n", encoding="utf-8"
        )


def _compiled_prompt_hashes(fixture: ReliabilityFixture) -> dict[str, str]:
    story_root = fixture.root / "Stories" / fixture.story_slug
    story = json.loads((story_root / f"{fixture.story_slug}.story.json").read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for scene_slug in fixture.scene_slugs[:8]:
        scene = json.loads((story_root / f"{scene_slug}.scene.json").read_text(encoding="utf-8"))
        prompt = final_image_prompt_text(
            compile_scene_render_ir(scene, story, default_prompt_sections=DEFAULT_PROMPT_SECTIONS)
        )
        result[scene_slug] = _sha256(prompt.encode("utf-8"))
    return result


def _rehearsal_snapshot(fixture: ReliabilityFixture, paths: PathService) -> dict[str, Any]:
    catalog = ImageCatalogRepository(paths).load()
    queue = fixture.root / "Queue" / "Manual_Render_Queue"
    tasks = []
    for manifest_path in sorted(queue.rglob("ask_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("story_slug") == fixture.story_slug:
            tasks.append((str(manifest.get("ask_id")), str(manifest.get("scene_slug")), str(manifest.get("render_target_id"))))
    associations = {}
    for scene_slug in fixture.scene_slugs[:8]:
        pipeline = fixture.root / "Pipelines" / "Stories" / fixture.story_slug / scene_slug
        associations[scene_slug] = {
            "main_candidate": (pipeline / "Candidate" / f"{scene_slug}.png").is_file(),
            "background_candidate": (pipeline / "Subscenes" / "background" / "Candidate" / "background.png").is_file(),
            "tasks": sorted(task for task in tasks if task[1] == scene_slug),
        }
    image_hashes = {}
    for catalog_id, record in catalog["managed_images"].items():
        image_hashes[catalog_id] = _sha256(paths.resolve_path(record["image_path"]).read_bytes())
    return {
        "entity_counts": {
            "stories": len(list((fixture.root / "Stories").glob("*/*.story.json"))),
            "scenes": len(list((fixture.root / "Stories").glob("*/*.scene.json"))),
            "catalog_records": len(catalog["managed_images"]),
            "reference_sets": len(catalog["reference_sets"]),
            "tasks": len(tasks),
        },
        "references": sorted(
            (catalog_id, str(record.get("reference_set_id") or ""))
            for catalog_id, record in catalog["managed_images"].items()
        ),
        "overrides": {
            key: value.get("sections", {}) for key, value in sorted(catalog["items"].items())
        },
        "image_hashes": image_hashes,
        "prompt_hashes": _compiled_prompt_hashes(fixture),
        "associations": associations,
    }


def _make_catalog_legacy(paths: PathService) -> None:
    repository = ImageCatalogRepository(paths)
    payload = repository.load()
    payload["schema_version"] = 2
    root = paths.image_catalog_root()
    for folder in (root / "Records", root / "ReferenceSets"):
        if folder.exists():
            shutil.rmtree(folder)
    organization = root / "Organization.json"
    if organization.exists():
        organization.unlink()
    paths.image_catalog_inventory_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_migration_rehearsal(root: Path) -> dict[str, Any]:
    fixture = write_reliability_fixture(root / "library", scale=1)
    _add_first_day_tasks(fixture)
    config = ConfigService.load(fixture.config_path)
    paths = PathService(config, PROJECT_ROOT)
    catalog_repository = ImageCatalogRepository(paths)
    catalog = catalog_repository.load()
    metadata = catalog["items"]["wp01:identity:001"]
    metadata["sections"]["identity"] = {
        "mode": "override",
        "approved_text": "  exact WP12 identity override\nsecond line  ",
        "provenance": "wp12-rehearsal",
    }
    metadata["sections"]["costume"] = {
        "mode": "override",
        "approved_text": "exact WP12 costume override",
        "provenance": "wp12-rehearsal",
    }
    catalog_repository.save(catalog)
    before = _rehearsal_snapshot(fixture, paths)
    _make_catalog_legacy(paths)
    migration = ImageCatalogMigrationService(paths)
    dry_run = migration.run(dry_run=True).to_dict()
    interrupted = False
    try:
        migration.run(interrupt_after=1)
    except ImageCatalogMigrationInterrupted:
        interrupted = True
    migrated = migration.run().to_dict()
    after = _rehearsal_snapshot(fixture, paths)
    rebuilt = LibraryIndexService(config, index_root=root / "machine-index", project_root=PROJECT_ROOT).rebuild()
    return {
        "dry_run": dry_run,
        "interrupted_checkpoint_resumed": interrupted,
        "migration": migrated,
        "comparison_equal": before == after,
        "comparison": {"before": before, "after": after},
        "index_counts": rebuilt["counts"],
        "backup_exists": Path(migrated["backup_path"]).is_file(),
    }


def _review_rows(fixture: ReliabilityFixture) -> tuple[dict, ...]:
    rows = []
    for scene_slug in fixture.scene_slugs:
        for target in ("main", "background"):
            payload = {"story_slug": fixture.story_slug, "scene_slug": scene_slug, "render_target_id": target}
            key = f"scene:{fixture.story_slug}:{scene_slug}:{target}"
            rows.append({
                "list_kind": "image_review_scene", "item_key": key, "sort_key": key,
                "character_name": "", "phase": "", "story_slug": fixture.story_slug,
                "scene_slug": scene_slug, "source_key": "", "status": "waiting",
                "source_type": "scene", "semantic_category": "", "costume": "",
                "pipeline": "", "subscene_id": target, "collections_text": "||",
                "keywords_text": "||", "search_text": key.casefold(), "is_base": 0,
                "payload_json": json.dumps(payload, separators=(",", ":")),
            })
    return tuple(rows)


def _single_flight(factory) -> int:
    active = 0
    maximum = 0
    lock = threading.Lock()
    SummaryCache.clear()

    def measured() -> dict:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        sleep(0.02)
        with lock:
            active -= 1
        return {"ok": True}

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: factory(measured), range(2)))
    return maximum


def _verify_rebuild_recovery(service: LibraryIndexService, fixture: ReliabilityFixture) -> dict[str, Any]:
    """Interrupt publication while proving readers retain the last complete generation."""
    expected = service.repository.query_scenes(story_slug=fixture.story_slug, limit=50).items
    generation = service.repository.begin_rebuild()
    snapshot = service.snapshot()
    entered = threading.Event()
    release = threading.Event()

    def cancel_before_activation() -> None:
        entered.set()
        release.wait(timeout=5)
        raise RuntimeError("WP12 simulated rebuild cancellation")

    def publish() -> None:
        service.repository.publish(generation, snapshot, before_activate=cancel_before_activation)

    interrupted = False
    navigation_seconds = 5.0
    with ThreadPoolExecutor(max_workers=2) as executor:
        publication = executor.submit(publish)
        if not entered.wait(timeout=5):
            release.set()
            raise RuntimeError("Rebuild did not reach its cancellable publication boundary.")
        started = perf_counter()
        navigation = executor.submit(
            service.repository.query_scenes, story_slug=fixture.story_slug, limit=50
        )
        try:
            during = navigation.result(timeout=2).items
            navigation_seconds = perf_counter() - started
        finally:
            release.set()
        try:
            publication.result()
        except RuntimeError as exc:
            interrupted = "simulated rebuild cancellation" in str(exc)
    resumed = service.rebuild(backfill_history=False)
    return {
        "interrupted": interrupted,
        "navigation_retained_generation": during == expected,
        "navigation_seconds": round(navigation_seconds, 6),
        "resumed": resumed["state"] == "ready",
    }


def run_scale_acceptance(root: Path, scale: int, *, runs: int = 30) -> dict[str, Any]:
    fixture = write_reliability_fixture(root / f"library-{scale}x", scale=scale)
    _add_first_day_tasks(fixture)
    config = ConfigService.load(fixture.config_path)
    service = LibraryIndexService(config, index_root=root / f"index-{scale}x", project_root=PROJECT_ROOT)
    service.list_items_provider = lambda: _review_rows(fixture)
    started = perf_counter()
    rebuild = service.rebuild(backfill_history=False)
    cold_rebuild_seconds = perf_counter() - started

    navigation: list[float] = []
    reviews: list[float] = []
    with collect(patch_path_reads=False) as metrics:
        for _ in range(runs):
            started = perf_counter()
            scene_page = service.repository.query_scenes(story_slug=fixture.story_slug, limit=50)
            navigation.append(perf_counter() - started)
            started = perf_counter()
            review_page = service.repository.query_indexed_list(
                "image_review_scene", story_slug=fixture.story_slug, limit=50
            )
            reviews.append(perf_counter() - started)

    reconcile_active = 0
    reconcile_maximum = 0
    reconcile_lock = threading.Lock()
    original_snapshot = service.snapshot

    def measured_snapshot(*args, **kwargs):
        nonlocal reconcile_active, reconcile_maximum
        with reconcile_lock:
            reconcile_active += 1
            reconcile_maximum = max(reconcile_maximum, reconcile_active)
        try:
            sleep(0.01)
            return original_snapshot(*args, **kwargs)
        finally:
            with reconcile_lock:
                reconcile_active -= 1

    service.snapshot = measured_snapshot  # type: ignore[method-assign]
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _: service.reconcile(), range(2)))
    service.snapshot = original_snapshot  # type: ignore[method-assign]

    summary_maximum = _single_flight(
        lambda measured: SummaryCache.get_or_compute(("wp12", scale), measured)
    )
    rebuild_recovery = _verify_rebuild_recovery(service, fixture)
    navigation_p95 = _p95(navigation)
    review_p95 = _p95(reviews)
    return {
        **fixture.benchmark_metadata(scale=scale, state="warm", concurrent_activity="simultaneous reconciliation"),
        "runs": runs,
        "cold_rebuild_seconds": round(cold_rebuild_seconds, 6),
        "navigation_p95_seconds": round(navigation_p95, 6),
        "review_listing_p95_seconds": round(review_p95, 6),
        "navigation_page_items": len(scene_page.items),
        "review_page_items": len(review_page.items),
        "review_total": review_page.total,
        "archive_traversals": metrics.counts["archive_traversals"],
        "reconciliation_maximum_active": reconcile_maximum,
        "summary_maximum_active": summary_maximum,
        "rebuild_recovery": rebuild_recovery,
        "index_counts": rebuild["counts"],
        "pass": navigation_p95 < 2 and review_p95 < 3 and len(review_page.items) <= 50
        and metrics.counts["archive_traversals"] == 0 and reconcile_maximum == 1 and summary_maximum == 1
        and rebuild_recovery["interrupted"] and rebuild_recovery["navigation_retained_generation"]
        and rebuild_recovery["navigation_seconds"] < 2 and rebuild_recovery["resumed"],
    }


def run_wp12_benchmark(*, scales: tuple[int, ...] = (1, 10, 100), runs: int = 30) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zet-wp12-") as temporary:
        root = Path(temporary)
        migration = run_migration_rehearsal(root / "migration")
        scales_report = [run_scale_acceptance(root, scale, runs=runs) for scale in scales]
    passed = migration["comparison_equal"] and migration["interrupted_checkpoint_resumed"] \
        and migration["backup_exists"] and all(item["pass"] for item in scales_report)
    return {
        "runner": {"platform": platform.platform(), "python": sys.version.split()[0], "temporary_roots": True},
        "requirements": {"navigation_p95_seconds": 2, "review_listing_p95_seconds": 3, "runs": runs},
        "migration_rehearsal": migration,
        "scale_acceptance": scales_report,
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the JSON evidence to this path.")
    parser.add_argument("--runs", type=int, default=30)
    args = parser.parse_args(argv)
    report = run_wp12_benchmark(runs=args.runs)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
