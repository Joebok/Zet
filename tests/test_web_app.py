import json
import base64
from tests.support.image_fixture import png_bytes
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from support.project_fixture import write_manual_render_ask, write_project_fixture
from zet.services.config_service import ConfigService
from zet.services.image_catalog_migration_service import ImageCatalogMigrationService
from zet.services.path_service import PathService
from zet.web.app import create_app


class WebAppTests(unittest.TestCase):
    def test_image_identity_button_starts_luna_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_fixture(Path(temp_dir))
            client = TestClient(create_app(config_path))
            self.assertIn('id="entity-library-generate-identity"', client.get("/").text)
            service = client.app.state.image_prompt_generation_service
            with patch.object(service, "start_identity", return_value={"job_id": "identity-job", "status": "RUNNING"}) as start:
                response = client.post("/api/entity-library/assets/image-1/generate-identity")
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual("identity-job", response.json()["job_id"])
            start.assert_called_once_with("image-1")

    def test_local_assets_can_start_and_check_library_wide_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            with TestClient(create_app(config_path)) as client:
                page = client.get("/")
                self.assertEqual(200, page.status_code)
                self.assertIn('id="local-run-all-remaining"', page.text)
                started = client.post("/api/local/run-all-remaining")
                self.assertEqual(200, started.status_code, started.text)
                campaign_id = started.json()["campaign_id"]
                deadline = time.monotonic() + 15
                status = client.get(f"/api/local/run-all-remaining/{campaign_id}")
                while status.json().get("status") not in {"COMPLETE", "FAILED"} and time.monotonic() < deadline:
                    time.sleep(0.05)
                    status = client.get(f"/api/local/run-all-remaining/{campaign_id}")
                self.assertEqual(200, status.status_code, status.text)
                self.assertEqual("COMPLETE", status.json()["status"])
                self.assertEqual(0, status.json()["images_remaining"])

    def test_gate_test_rig_and_gate_setup_apis(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            client = TestClient(create_app(config_path))
            page = client.get("/gate-test-rig")
            self.assertEqual(200, page.status_code)
            self.assertIn("/api/chat", page.text)
            self.assertIn("Run all current cases", page.text)
            self.assertIn("Add curated case", page.text)
            self.assertEqual([], client.get("/api/gate-test-rig/tests").json()["tests"])
            self.assertEqual(200, client.get("/gate-test-data").status_code)
            catalog = client.get("/api/local-gates/body-reference")
            self.assertEqual("Disabled", catalog.json()["statuses"]["orientation"])
            updated = client.put("/api/local-gates/head-image/gaze", json={"status": "Warning"})
            self.assertEqual(200, updated.status_code, updated.text)
            self.assertEqual("Warning", updated.json()["statuses"]["gaze"])
            case = client.post("/api/gate-test-data", json={
                "pipeline": "body-reference", "gate": "proportion", "view": "FRONT",
                "expected": "PASS", "image_data": base64.b64encode(png_bytes()).decode("ascii"),
            })
            self.assertEqual(200, case.status_code, case.text)
            case_id = case.json()["case_id"]
            image = client.get(f"/api/gate-test-data/body-reference/proportion/{case_id}/image/candidate")
            self.assertEqual(200, image.status_code)
            self.assertEqual(1, len(client.get("/api/gate-test-data?pipeline=body-reference&gate=proportion").json()["cases"]))
            self.assertEqual(200, client.delete(f"/api/gate-test-data/body-reference/proportion/{case_id}").status_code)

    def test_scene_appearance_api_creates_lists_updates_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            views = [
                "Front", "Front-Left-3-4", "Left-Profile", "Back-Left-3-4",
                "Back", "Back-Right-3-4", "Right-Profile", "Front-Right-3-4",
            ]
            asset_records = []
            asset_folder = root / "Assets" / "Test" / "Adult"
            for asset_id, view in enumerate(views, start=1):
                image_name = f"costume-{view}.png"
                asset_folder.joinpath(image_name).write_bytes(b"image")
                asset_records.append({
                    "asset_id": asset_id, "character": "Test", "phase": "Adult",
                    "pipeline": "Costume-Dressing", "body_view": view, "head_view": view,
                    "costume": "Adventure Gear", "asset_state": "LOCKED", "pipeline_stage": "LOCKED",
                    "actor": "HUMAN_AGENT", "final_image_output": image_name,
                })
            (root / "Characters" / "Test" / "Adult" / "Assets.json").write_text(
                json.dumps({"next_asset_id": 9, "assets": asset_records}, indent=2) + "\n",
                encoding="utf-8",
            )
            aux = root / "AuxiliaryResources"
            aux.mkdir()
            (aux / "morrow.png").write_bytes(b"image")
            (aux / "tusk.png").write_bytes(b"image")
            (aux / "AuxiliaryResources.json").write_text(json.dumps({"resources": [
                {"category": "person", "resource_id": "morrow", "label": "Morrow", "images": [
                    {"image_id": "raven", "image_path": str(aux / "morrow.png")}
                ]},
                {"category": "thing", "resource_id": "tusk", "label": "Tusk", "images": [
                    {"image_id": "reference", "image_path": str(aux / "tusk.png")}
                ]},
            ]}), encoding="utf-8")
            ImageCatalogMigrationService(PathService(ConfigService.load(config_path), root)).run()
            client = TestClient(create_app(config_path))
            body = {
                "appearance_id": "hell-adventures", "name": "Hell Adventures",
                "costume": "Adventure Gear", "instructions": "Morrow on left shoulder; tusk in right hand.",
                "supporting_references": [
                    {"role": "companion", "label": "Morrow", "tag": "{{AUX:person:morrow:raven}}"},
                    {"role": "prop", "label": "Tusk", "tag": "{{AUX:thing:tusk:reference}}"},
                ],
            }

            created = client.post("/api/scene-appearances", params={"character": "Test", "phase": "Adult"}, json=body)
            self.assertEqual(410, created.status_code, created.text)
            self.assertIn("retired", created.json()["detail"])
            listed = client.get("/api/scene-appearances", params={"character": "Test", "phase": "Adult"})
            self.assertEqual([], listed.json()["scene_appearances"])
            updated = client.put(
                "/api/scene-appearances/hell-adventures",
                params={"character": "Test", "phase": "Adult"}, json=body,
            )
            self.assertEqual(410, updated.status_code, updated.text)
            invalid = client.post(
                "/api/scene-appearances", params={"character": "Test", "phase": "Adult"},
                json={**body, "appearance_id": "Invalid ID"},
            )
            self.assertEqual(410, invalid.status_code)

    def test_image_catalog_import_replace_reference_set_and_delete_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            client = TestClient(create_app(config_path))

            created_set = client.post("/api/image-catalog/reference-sets", json={"label": "Props", "identity_text": "shared prop"})
            self.assertEqual(200, created_set.status_code, created_set.text)
            set_id = created_set.json()["reference_set"]["reference_set_id"]
            imported = client.post(
                "/api/image-catalog/imports",
                params={"label": "Lantern", "semantic_category": "Object", "reference_set_id": set_id},
                content=b"png image",
                headers={"content-type": "image/png"},
            )
            self.assertEqual(200, imported.status_code, imported.text)
            item = imported.json()["item"]
            self.assertTrue(item["is_managed"])
            self.assertEqual("imported", item["source_type"])
            self.assertEqual("shared prop", item["identity_text"])

            updated = client.patch(f"/api/image-catalog/{item['catalog_id']}", json={"label": "Blue Lantern", "reference_set_id": ""})
            self.assertEqual(200, updated.status_code, updated.text)
            self.assertEqual("Blue Lantern", updated.json()["item"]["managed_label"])
            replaced = client.put(
                f"/api/image-catalog/{item['catalog_id']}/content",
                content=b"jpeg image",
                headers={"content-type": "image/jpeg"},
            )
            self.assertEqual(200, replaced.status_code, replaced.text)
            self.assertTrue(replaced.json()["item"]["image_path"].endswith(".jpg"))
            deleted = client.delete(f"/api/image-catalog/{item['catalog_id']}")
            self.assertEqual(200, deleted.status_code, deleted.text)
            self.assertTrue(list((root / "ImageCatalog" / "_trash").glob("*.jpg")))

    def test_ai_controls_loads_recent_receipt_backed_harvests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            app = create_app(config_path, validate_catalog_on_create=False)
            lifecycle = app.state.zet_app.ai_proxy_service.ai_proxy_path_service.lifecycle
            lifecycle.write_receipt("Ask_Live", {
                "ask_id": "Ask_Live", "task_type": "prompt_condense", "asset_id": 1,
                "status": "SUCCESS", "harvested_at": "2026-08-25T12:00:00",
                "message": "Ask_Live harvested.",
            })
            lifecycle.write_receipt("Ask_Archived", {
                "ask_id": "Ask_Archived", "task_type": "prompt_condense", "asset_id": 1,
                "status": "BLOCKED", "harvested_at": "2026-08-24T12:00:00",
                "error_message": "MODEL_FAILURE: Ollama timed out.",
            })
            app.state.zet_app.library_index_service.rebuild(backfill_history=False)
            client = TestClient(app)
            with patch("zet.app.ZetApp.codex_jobs", return_value=[{
                "run_id": "20260922_120000_000001", "candidate_id": "c001",
                "character": "Test", "phase": "Adult", "view": "FRONT",
                "status": "PENDING", "details": "Waiting for candidate image",
            }]):
                response = client.get("/api/ai-controls")

            self.assertEqual(200, response.status_code)
            self.assertEqual("PENDING", response.json()["codex_jobs"][0]["status"])
            self.assertNotIn("recent_harvests", response.json())
            history = client.get("/api/ai-controls/recent-harvests", params={"limit": 2})
            self.assertEqual(200, history.status_code)
            recent = history.json()["items"]
            self.assertEqual(["Ask_Live", "Ask_Archived"], [item["ask_id"] for item in recent])
            self.assertEqual("prompt_condense", recent[0]["task_type"])
            self.assertEqual("MODEL_FAILURE: Ollama timed out.", recent[1]["details"])

    def test_restart_zet_api_uses_combined_process_operation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_fixture(Path(temp_dir))
            client = TestClient(create_app(config_path))

            with patch("zet.app.ZetApp.restart_zet", return_value=(1, 2)) as restart:
                response = client.post("/api/processes/restart-zet")

            self.assertEqual(200, response.status_code)
            self.assertEqual(1, response.json()["auto_harvest_stopped"])
            self.assertEqual(2, response.json()["dashboard_stopped"])
            restart.assert_called_once_with()

    def test_assets_api_serves_context_list_and_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_fixture(Path(temp_dir))
            client = TestClient(create_app(config_path))
            context = client.get("/api/context")
            self.assertEqual(context.status_code, 200)
            self.assertEqual(context.json()["default_character"], "Test")

            summary = client.get(
                "/api/workspace-summary",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(summary.status_code, 200)
            self.assertEqual(summary.json()["character"]["character"], "Test")
            self.assertEqual(summary.json()["character"]["phase"], "Adult")

            assets = client.get("/api/assets", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(assets.status_code, 200)
            self.assertEqual(assets.json()["assets"][0]["asset_id"], 1)
            self.assertIn("costume_or_expression", assets.json()["assets"][0])

            detail = client.get("/api/assets/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["asset"]["pipeline_stage"], "LOCKED")

    def test_asset_action_api_runs_current_worker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root, stage="MANIFEST", actor="PYTHON")
            client = TestClient(create_app(config_path))

            response = client.post("/api/assets/1/run-current-worker", params={"character": "Test", "phase": "Adult"})

            self.assertEqual(response.status_code, 400)
            self.assertIn("Traditional Body-Reference generation is retired", response.json()["detail"])

    def test_render_review_api_serves_tasks_detail_and_promotes_to_locked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root, stage="RENDER_REVIEW", actor="HUMAN_AGENT")
            (root / "Assets" / "Test" / "Adult" / "front.png").write_bytes(b"locked image")
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/render-review/tasks", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["items"], [])

            detail = client.get("/api/render-review/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertTrue(detail.json()["is_reviewable"])
            self.assertTrue(detail.json()["exists"]["candidate_image"])
            self.assertTrue(detail.json()["exists"]["locked_image"])
            self.assertTrue(detail.json()["candidate_image_path"].endswith("front.png"))
            self.assertTrue(detail.json()["locked_image_path"].endswith("front.png"))

            comment = client.post(
                "/api/render-review/1/comment",
                params={"character": "Test", "phase": "Adult"},
                json={"comment": "Good face, boots need checking."},
            )
            self.assertEqual(comment.status_code, 400)
            self.assertIn("Traditional Body-Reference generation is retired", comment.json()["detail"])

            unconfirmed = client.post(
                "/api/render-review/1/promote-to-locked",
                params={"character": "Test", "phase": "Adult"},
            )
            self.assertEqual(unconfirmed.status_code, 400)
            self.assertIn("Traditional Body-Reference generation is retired", unconfirmed.json()["detail"])

            promoted = client.post(
                "/api/render-review/1/promote-to-locked",
                params={"character": "Test", "phase": "Adult", "replace_existing": "true"},
            )
            self.assertEqual(promoted.status_code, 400)
            self.assertIn("Traditional Body-Reference generation is retired", promoted.json()["detail"])
            self.assertTrue((root / "Assets" / "Test" / "Adult" / "front.png").exists())

    def test_render_console_api_lists_task_detail_and_saves_image_answer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            ask_path = write_manual_render_ask(root)
            manifest_path = ask_path / "ask_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.update({"story_slug": "TestStory", "scene_slug": "Opening"})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            client = TestClient(create_app(config_path))

            tasks = client.get("/api/render-console/tasks")
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(tasks.json()["tasks"][0]["ask_id"], "Ask_Asset_1_RENDER_TEST")
            self.assertEqual(tasks.json()["tasks"][0]["display_label"], "TestStory / Opening")

            detail = client.get("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["prompt"], "manual render prompt\n")
            self.assertNotIn("gpt_helper_prompt", detail.json())
            self.assertEqual(
                client.post("/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/gpt-helper-prompt").status_code,
                404,
            )
            saved = client.post(
                "/api/render-console/tasks/Ask_Asset_1_RENDER_TEST/answer-image",
                params={
                    "render_comment": "First render has strong silhouette.",
                    "refinement_required": "true",
                    "additional_image_generations": "2",
                    "refinement_note": "Corrected hand placement.",
                },
                content=png_bytes(),
                headers={"content-type": "image/png"},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["status"], "SUCCESS")
            self.assertTrue((ask_path / "submission.json").exists())
            answer_path = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Asset_1_RENDER_TEST"
            self.assertTrue((answer_path / "front.png").exists())
            self.assertEqual(
                (answer_path / "Render_Review_Comment.md").read_text(encoding="utf-8").strip(),
                "First render has strong silhouette.",
            )
            manifest = json.loads((answer_path / "answer_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "SUCCESS")
            self.assertEqual(manifest["render_comment"], "First render has strong silhouette.")
            self.assertEqual(2, manifest["chatgpt_refinement"]["additional_image_generations"])
            metrics = client.get("/api/render-console/refinement-metrics")
            self.assertEqual(200, metrics.status_code)
            self.assertEqual(1, metrics.json()["classified_count"])
            self.assertEqual(1, metrics.json()["refined_count"])
            client.close()

    def test_render_console_uses_renamed_scene_and_subscene_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            story_dir = root / "Stories" / "Arcane-Tales"
            story_dir.mkdir(parents=True)
            (story_dir / "Arcane-Tales.md").write_text("Title: `[Arcane Tales]`\n", encoding="utf-8")
            (story_dir / "Into-the-Celestial-Sphere.md").write_text(
                "Scene: `[Wild Magic Surge]`\n", encoding="utf-8"
            )
            (story_dir / "Into-the-Celestial-Sphere.scene.json").write_text(json.dumps({
                "schema_version": 4,
                "file_kind": "scene",
                "scene": {"name": "Wild Magic Surge", "slug": "Into-the-Celestial-Sphere"},
                "subscenes": [{"id": "background", "name": "Celestial Backdrop", "enabled": True}],
            }), encoding="utf-8")
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Story_Background"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text(json.dumps({
                "version": 1,
                "ask_id": "Ask_Story_Background",
                "asset_id": None,
                "worker_type": "manual_chatgpt_render",
                "prompt_file": "Final_Image_Prompt.md",
                "expected_output": "background.png",
                "story_slug": "Arcane-Tales",
                "scene_slug": "Into-the-Celestial-Sphere",
                "render_target_id": "background",
            }), encoding="utf-8")
            (ask_path / "Final_Image_Prompt.md").write_text("scene prompt\n", encoding="utf-8")

            client = TestClient(create_app(config_path))
            response = client.get("/api/render-console/tasks")

            self.assertEqual(200, response.status_code, response.text)
            task = response.json()["tasks"][0]
            self.assertEqual("Arcane Tales / Wild Magic Surge", task["display_label"])
            self.assertEqual("Background subscene: Celestial Backdrop", task["display_subtext"])
            detail = client.get("/api/render-console/tasks/Ask_Story_Background").json()
            self.assertEqual("Wild Magic Surge", detail["task"]["scene_title"])
            client.close()

    def test_ir_scene_defaults_to_qwen_in_render_console_with_legacy_profile_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            with config_path.open("a", encoding="utf-8") as config:
                config.write('\n[LocalRender]\nBackend = "comfyui"\n'
                             '\n[ComfyUI]\nProfile = "comfyui-ipadapter-preview"\n'
                             'Checkpoint = "sdxl.safetensors"\n')
            workspace = root / "Scene_Workspace"
            workspace.mkdir()
            (workspace / "Scene_Render_IR.json").write_text(json.dumps({
                "canvas": {"aspect_ratio": "4:5"}, "scene": {"story_beat": "Tsaeytte enters the arch"},
                "image_inputs": [],
            }), encoding="utf-8")
            (workspace / "Local_Render_Prompt.md").write_text("old SDXL scene prompt\n", encoding="utf-8")
            ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Qwen_Default"
            ask_path.mkdir(parents=True)
            (ask_path / "ask_manifest.json").write_text(json.dumps({
                "version": 1, "ask_id": "Ask_Qwen_Default", "asset_id": None,
                "worker_type": "manual_chatgpt_render", "prompt_file": "Final_Image_Prompt.md",
                "expected_output": "scene.png", "story_slug": "FirstDay", "scene_slug": "Collision",
                "pipeline_path": str(workspace),
            }), encoding="utf-8")
            (ask_path / "Final_Image_Prompt.md").write_text("manual prompt\n", encoding="utf-8")

            client = TestClient(create_app(config_path))
            response = client.get("/api/render-console/tasks/Ask_Qwen_Default")

            self.assertEqual(200, response.status_code, response.text)
            local = response.json()["local_prompt"]
            self.assertEqual("comfyui-qwen-image-2-1-scene", local["default_local_profile"])
            self.assertEqual("comfyui-qwen-image-2-1-scene", local["configured_local_profile"])
            self.assertTrue(local["qwen_supports_local_test_render"])
            self.assertIn("Tsaeytte enters the arch", local["qwen_prompt"])
            with patch("zet.app.ZetApp.stage_scene_local_render_ask", return_value=root / "queued") as stage:
                queued = client.post("/api/render-console/tasks/Ask_Qwen_Default/local-test-render")
            self.assertEqual(200, queued.status_code, queued.text)
            self.assertEqual("comfyui-qwen-image-2-1-scene", stage.call_args.kwargs["render_profile"])
            with patch("zet.app.ZetApp.stage_scene_local_render_ask", return_value=root / "queued") as stage:
                queued = client.post("/api/render-console/tasks/Ask_Qwen_Default/local-test-render",
                                     json={"render_profile": "comfyui-qwen-image-2-1-scene"})
            self.assertEqual(200, queued.status_code, queued.text)
            self.assertEqual("comfyui-qwen-image-2-1-scene", stage.call_args.kwargs["render_profile"])
            client.close()

    def test_story_management_api_renames_reorders_and_moves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = write_project_fixture(root)
            for story_slug in ("Alpha", "Beta"):
                folder = root / "Stories" / story_slug
                folder.mkdir(parents=True)
                (folder / f"{story_slug}.md").write_text(f"Title: `[{story_slug}]`\n", encoding="utf-8")
                (folder / f"{story_slug}.story.json").write_text(
                    json.dumps({
                        "schema_version": 1,
                        "file_kind": "story_settings",
                        "story": {"slug": story_slug, "title": story_slug},
                        "scene_index": ["Opening"] if story_slug == "Alpha" else [],
                        "metadata": {},
                    }),
                    encoding="utf-8",
                )
            alpha = root / "Stories" / "Alpha"
            (alpha / "Opening.md").write_text("Scene: `[Opening]`\n", encoding="utf-8")
            (alpha / "Opening.scene.json").write_text(
                json.dumps({"schema_version": 4, "file_kind": "scene", "scene": {"slug": "Opening", "name": "Opening"}}),
                encoding="utf-8",
            )
            client = TestClient(create_app(config_path))

            response = client.put("/api/stories/order", json={"slugs": ["Beta", "Alpha"]})
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual(["Beta", "Alpha"], [item["slug"] for item in response.json()["stories"]])

            response = client.patch("/api/stories/Alpha", json={"title": "Renamed Alpha"})
            self.assertEqual(200, response.status_code)
            self.assertEqual("Renamed Alpha", response.json()["document"]["story"]["title"])

            response = client.put("/api/stories/Alpha/scenes/order", json={"slugs": ["Opening"]})
            self.assertEqual(200, response.status_code)
            self.assertEqual(["Opening"], [item["slug"] for item in response.json()["scenes"]])

            response = client.patch("/api/stories/Alpha/scenes/Opening", json={"title": "New Opening"})
            self.assertEqual(200, response.status_code)
            self.assertEqual("New Opening", response.json()["document"]["scene"]["title"])

            response = client.post(
                "/api/stories/Alpha/scenes/Opening/move",
                json={"target_story_slug": "Beta"},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual([], response.json()["source_scenes"])
            self.assertEqual(["Opening"], [item["slug"] for item in response.json()["target_scenes"]])


if __name__ == "__main__":
    unittest.main()
