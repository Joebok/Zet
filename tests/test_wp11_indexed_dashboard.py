from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from support.project_fixture import write_project_fixture
from zet.repositories.library_index_repository import (
    IndexSnapshot,
    LibraryIndexError,
    LibraryIndexRepository,
)
from zet.services.config_service import ConfigService
from zet.services.library_index_service import LibraryIndexService
from zet.web.app import create_app


def indexed_row(number: int) -> dict:
    payload = {"catalog_id": f"item-{number:03d}", "label": f"Item {number:03d}"}
    return {
        "list_kind": "inventory",
        "item_key": payload["catalog_id"],
        "sort_key": payload["label"].casefold(),
        "character_name": "",
        "phase": "",
        "story_slug": "",
        "scene_slug": "",
        "source_key": "",
        "status": "ready",
        "source_type": "managed",
        "semantic_category": "Object",
        "costume": "",
        "pipeline": "",
        "subscene_id": "",
        "collections_text": "||",
        "keywords_text": "||",
        "search_text": payload["label"].casefold(),
        "is_base": 0,
        "payload_json": json.dumps(payload),
    }


class WP11IndexedDashboardTests(unittest.TestCase):
    def test_pages_are_ordered_bounded_and_generation_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "library"
            library.mkdir()
            repository = LibraryIndexRepository(library, index_root=root / "index")
            generation = repository.begin_rebuild()
            repository.publish(generation, IndexSnapshot(list_items=tuple(
                indexed_row(number) for number in range(260, 0, -1)
            )))

            first = repository.query_indexed_list("inventory", limit=50)
            second = repository.query_indexed_list(
                "inventory", cursor=first.next_cursor, limit=200
            )
            self.assertEqual(260, first.total)
            self.assertEqual(50, len(first.items))
            self.assertEqual("item-001", first.items[0]["catalog_id"])
            self.assertEqual(200, len(second.items))
            self.assertEqual(generation, first.generation)
            self.assertEqual("ready", first.freshness["state"])
            with self.assertRaisesRegex(LibraryIndexError, "between 1 and 200"):
                repository.query_indexed_list("inventory", limit=201)

            next_generation = repository.begin_rebuild()
            repository.publish(next_generation, IndexSnapshot(list_items=(indexed_row(1),)))
            with self.assertRaisesRegex(LibraryIndexError, "stale cursor"):
                repository.query_indexed_list("inventory", cursor=first.next_cursor)

    def test_dashboard_apis_use_only_indexed_list_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = write_project_fixture(
                Path(temporary), stage="RENDER_REVIEW", actor="HUMAN_AGENT"
            )
            client = TestClient(create_app(config_path))
            zet_app = client.app.state.zet_app
            with (
                patch.object(zet_app.image_catalog_service, "list_items", side_effect=AssertionError("scan")),
                patch.object(zet_app.production_work_summary_service, "summary", side_effect=AssertionError("scan")),
                patch.object(zet_app.ai_proxy_service, "recent_harvests", side_effect=AssertionError("archive")),
                patch.object(zet_app.scene_candidate_import_service, "list_candidates", side_effect=AssertionError("parse")),
            ):
                responses = [
                    client.get("/api/image-catalog"),
                    client.get("/api/render-review/tasks", params={"character": "Test", "phase": "Adult"}),
                    client.get("/api/scene-candidates", params={"source_key": "missing"}),
                    client.get("/api/ai-controls/recent-harvests"),
                ]
                summary = client.get("/api/production-work-summary", params={
                    "workspace": "character", "character": "Test", "phase": "Adult",
                })

            for response in responses:
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual(
                    {"items", "total", "next_cursor", "generation", "freshness"},
                    set(response.json()),
                )
            self.assertEqual(200, summary.status_code)
            self.assertEqual(
                responses[1].json()["total"], summary.json()["current"]["image_review_waiting"]
            )
            self.assertEqual(responses[1].json()["generation"], summary.json()["generation"])
            self.assertEqual(422, client.get("/api/image-catalog", params={"limit": 201}).status_code)

    def test_history_backfill_is_explicit_resumable_and_does_not_scan_on_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = write_project_fixture(root)
            archive = root / "Queue" / "Zet_File_Proxy_State" / "Archive" / "Harvested" / "2026-09-01"
            for number in (1, 2, 3):
                folder = archive / f"Ask_{number}"
                folder.mkdir(parents=True)
                (folder / "ask_manifest.json").write_text(json.dumps({
                    "ask_id": f"Ask_{number}", "task_type": "prompt_condense",
                }), encoding="utf-8")
                (folder / "answer_manifest.json").write_text(json.dumps({
                    "ask_id": f"Ask_{number}", "status": "SUCCESS",
                }), encoding="utf-8")
                (folder / "harvest_manifest.json").write_text(json.dumps({
                    "harvested_at": f"2026-09-0{number}T12:00:00",
                }), encoding="utf-8")
            service = LibraryIndexService(
                ConfigService.load(config_path), index_root=root / "machine-index",
                project_root=root,
            )
            service.reconcile()
            self.assertEqual(0, service.repository.query_job_history(harvested_only=True).total)

            first = service.backfill_history(batch_size=1)
            second = service.backfill_history(batch_size=1)
            cursor_page = service.repository.query_job_history(harvested_only=True, limit=1)
            third = service.backfill_history(batch_size=1)
            self.assertFalse(first["complete"])
            self.assertFalse(second["complete"])
            self.assertTrue(third["complete"])
            self.assertEqual(3, service.repository.query_job_history(harvested_only=True).total)
            self.assertNotEqual(first["cursor"], second["cursor"])
            with self.assertRaisesRegex(LibraryIndexError, "stale cursor"):
                service.repository.query_job_history(
                    harvested_only=True, cursor=cursor_page.next_cursor, limit=1
                )

            with patch.object(
                service.queue_paths, "harvested_archive_root", side_effect=AssertionError("archive scan")
            ):
                page = service.repository.query_job_history(harvested_only=True, limit=1)
            self.assertEqual(1, len(page.items))

    def test_fixed_page_work_is_independent_of_unrelated_index_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "library"
            library.mkdir()
            repository = LibraryIndexRepository(library, index_root=root / "index")
            for size in (20, 200):
                generation = repository.begin_rebuild()
                repository.publish(generation, IndexSnapshot(list_items=tuple(
                    indexed_row(number) for number in range(size)
                )))
                page = repository.query_indexed_list("inventory", limit=10)
                self.assertEqual(10, len(page.items))
                self.assertIsNotNone(page.next_cursor)


if __name__ == "__main__":
    unittest.main()
