from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.support.project_fixture import write_project_fixture
from tests.support.image_fixture import png_bytes
from fastapi.testclient import TestClient
from zet.web.app import create_app
from zet.services.atomic_file_service import write_json_atomic
from zet.services.config_service import ConfigService
from zet.services.manual_render_publication_service import (
    ManualRenderPublicationConflict,
    ManualRenderPublicationService,
)
from zet.services.workflow_storage import snapshot_manual_ask, subject_key, task_state_path


class ManualRenderPublicationReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = write_project_fixture(self.root)
        self.config = ConfigService.load(self.config_path)
        self.service = ManualRenderPublicationService(self.config)

    def bundle(self, ask_id: str, *, story: bool = False) -> tuple[Path, Path, dict]:
        ready = self.root / "Queue" / "Manual_Render_Queue" / "Ask" / ask_id
        staging = ready.with_name(f".{ask_id}.staging")
        staging.mkdir(parents=True)
        manifest = {
            "ask_id": ask_id,
            "worker_type": "manual_chatgpt_render",
            "prompt_file": "Final_Image_Prompt.md",
            "expected_output": "scene.png",
            "reference_files": [],
            "image_inputs": [],
        }
        if story:
            pipeline = self.root / "Stories" / "Story" / "Scenes" / "Scene" / "Render"
            manifest.update(
                story_slug="Story",
                scene_slug="Scene",
                render_target_id="main",
                pipeline_path=str(pipeline),
                render_input_hash="current-inputs",
                ollama_attempt_id=f"attempt-{ask_id}",
            )
        (staging / "Final_Image_Prompt.md").write_text("render prompt\n", encoding="utf-8")
        manifest = snapshot_manual_ask(staging, ready, manifest, Path)
        return staging, ready, manifest

    def test_publication_records_intent_updates_active_and_supersedes_only_after_ready(self) -> None:
        old_staging, old_ready, old_manifest = self.bundle("Ask_Old")
        self.service.publish(old_staging, old_ready, publication_subject=subject_key(old_manifest))
        new_staging, new_ready, new_manifest = self.bundle("Ask_New")
        active_path = self.root / "pipeline" / "Active_Render.json"
        active = {
            "ask_id": "Ask_New",
            "attempt_id": "new",
            "render_input_hash": "current-inputs",
            "render_bundle_hash": new_manifest["render_bundle_hash"],
            "ask_path": str(new_ready),
        }
        published = self.service.publish(
            new_staging,
            new_ready,
            active_render_path=active_path,
            active_render=active,
            publication_subject=subject_key(new_manifest),
        )
        self.assertEqual(new_ready, published)
        self.assertTrue(new_ready.is_dir())
        self.assertEqual(active, json.loads(active_path.read_text(encoding="utf-8")))
        self.assertTrue(task_state_path(self.root / "Queue", "Superseded", "Ask_Old").is_file())
        intent = json.loads(self.service.intent_path("Ask_New").read_text(encoding="utf-8"))
        self.assertEqual("COMMITTED", intent["status"])

    def test_sharing_errors_and_timeout_preserve_complete_staging_for_recovery(self) -> None:
        for error_code in (5, 32, 33):
            with self.subTest(error_code=error_code):
                staging, ready, _ = self.bundle(f"Ask_WinError_{error_code}")
                error = OSError(error_code, "sharing violation")
                error.winerror = error_code
                with patch("zet.services.manual_render_publication_service.replace_with_retry", side_effect=error):
                    with self.assertRaises(OSError):
                        self.service.publish(staging, ready)
                self.assertTrue(staging.is_dir())
                self.assertFalse(ready.exists())
                inspection = next(item for item in self.service.inspect() if item["ask_id"] == ready.name)
                self.assertEqual("recoverable", inspection["status"])
                self.service.recover(ready.name)
                self.assertTrue(ready.is_dir())

        staging, ready, _ = self.bundle("Ask_Timeout")
        with patch("zet.services.manual_render_publication_service.replace_with_retry", side_effect=TimeoutError("deadline")):
            with self.assertRaises(TimeoutError):
                self.service.publish(staging, ready)
        self.assertTrue(staging.is_dir())
        self.service.recover(ready.name)
        self.assertTrue(ready.is_dir())

    def test_conflicting_destination_and_newer_active_are_preserved(self) -> None:
        staging, ready, _ = self.bundle("Ask_Conflict")
        ready.mkdir(parents=True)
        write_json_atomic(
            ready / "ask_manifest.json",
            {"ask_id": "Ask_Other", "worker_type": "manual_chatgpt_render"},
        )
        with self.assertRaises(ManualRenderPublicationConflict):
            self.service.publish(staging, ready)
        self.assertTrue(staging.is_dir())
        self.assertEqual("Ask_Other", json.loads((ready / "ask_manifest.json").read_text())["ask_id"])

        staging, ready, manifest = self.bundle("Ask_Newer_Active", story=True)
        active_path = self.root / "pipeline" / "Active_Render.json"
        write_json_atomic(active_path, {"ask_id": "Ask_Old"})
        with patch("zet.services.manual_render_publication_service.replace_with_retry", side_effect=TimeoutError("deadline")):
            with self.assertRaises(TimeoutError):
                self.service.publish(
                    staging,
                    ready,
                    active_render_path=active_path,
                    active_render={"ask_id": ready.name, "render_bundle_hash": manifest["render_bundle_hash"]},
                    publication_subject=subject_key(manifest),
                )
        write_json_atomic(active_path, {"ask_id": "Ask_Newest"})
        with self.assertRaises(ManualRenderPublicationConflict):
            self.service.recover(ready.name)
        self.assertTrue(staging.is_dir())
        self.assertEqual("Ask_Newest", json.loads(active_path.read_text())["ask_id"])

    def test_duplicate_recovery_is_idempotent_and_hash_or_dependency_changes_block(self) -> None:
        staging, ready, manifest = self.bundle("Ask_Duplicate")
        self.service.publish(staging, ready)
        self.assertEqual(ready, self.service.recover(ready.name))
        self.assertEqual(1, len(self.service.inspect()))

        staging, ready, _ = self.bundle("Ask_Changed")
        with patch("zet.services.manual_render_publication_service.replace_with_retry", side_effect=TimeoutError("deadline")):
            with self.assertRaises(TimeoutError):
                self.service.publish(staging, ready)
        (staging / "Final_Image_Prompt.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "match"):
            self.service.recover(ready.name)
        self.assertTrue(staging.is_dir())

        staging, ready, _ = self.bundle("Ask_Stale_Dependencies", story=True)
        with patch("zet.services.manual_render_publication_service.replace_with_retry", side_effect=TimeoutError("deadline")):
            with self.assertRaises(TimeoutError):
                self.service.publish(staging, ready)
        with self.assertRaisesRegex(RuntimeError, "dependencies changed"):
            self.service.recover(ready.name, dependency_validator=lambda _: False)
        self.assertTrue(staging.is_dir())
        self.assertFalse(ready.exists())

    def test_crash_after_bundle_rename_or_during_superseding_recovers_without_duplication(self) -> None:
        old_staging, old_ready, old_manifest = self.bundle("Ask_Boundary_Old")
        self.service.publish(old_staging, old_ready, publication_subject=subject_key(old_manifest))
        new_staging, new_ready, new_manifest = self.bundle("Ask_Boundary_Active")
        active_path = self.root / "pipeline" / "Active_Render.json"
        active = {"ask_id": new_ready.name, "render_bundle_hash": new_manifest["render_bundle_hash"]}

        original_write = write_json_atomic

        def fail_active(path: Path, payload: dict, *args, **kwargs):
            if path == active_path:
                raise OSError("crash while recording active render")
            return original_write(path, payload, *args, **kwargs)

        with patch("zet.services.manual_render_publication_service.write_json_atomic", side_effect=fail_active):
            with self.assertRaisesRegex(OSError, "active render"):
                self.service.publish(
                    new_staging,
                    new_ready,
                    active_render_path=active_path,
                    active_render=active,
                    publication_subject=subject_key(new_manifest),
                )
        self.assertTrue(new_ready.is_dir())
        self.assertFalse(task_state_path(self.root / "Queue", "Superseded", old_ready.name).is_file())
        self.service.recover(new_ready.name)
        self.assertTrue(task_state_path(self.root / "Queue", "Superseded", old_ready.name).is_file())

        another_staging, another_ready, another_manifest = self.bundle("Ask_Boundary_Supersede")

        def fail_supersede(*args, **kwargs):
            raise OSError("crash while superseding")

        with patch("zet.services.manual_render_publication_service.supersede_task", side_effect=fail_supersede):
            with self.assertRaisesRegex(OSError, "superseding"):
                self.service.publish(
                    another_staging,
                    another_ready,
                    publication_subject=subject_key(another_manifest),
                )
        self.assertTrue(another_ready.is_dir())
        self.service.recover(another_ready.name)
        self.assertTrue(another_ready.is_dir())

    def test_zetapp_and_dashboard_expose_inspect_and_recover(self) -> None:
        staging, ready, _ = self.bundle("Ask_Dashboard")
        client = TestClient(create_app(self.config_path))
        publication = client.get("/api/render-console/publications")
        self.assertEqual(200, publication.status_code)
        item = next(row for row in publication.json()["publications"] if row["ask_id"] == "Ask_Dashboard")
        self.assertTrue(item["recoverable"])
        recovered = client.post("/api/render-console/publications/Ask_Dashboard/recover")
        self.assertEqual(200, recovered.status_code, recovered.text)
        self.assertTrue(ready.is_dir())
        self.assertFalse(staging.exists())


if __name__ == "__main__":
    unittest.main()
