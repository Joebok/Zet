import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.models.asset import Asset
from zet.models.worker import WorkerContext
from zet.repositories.asset_repository import AssetRepository
from zet.services.character_onboarding_service import CharacterOnboardingService, FOUNDATION_VIEWS
from zet.services.config_service import Config
from zet.services.local_head_image_service import LocalHeadImageService, VIEWS
from zet.services.path_service import PathService
from zet.services.reference_service import ReferenceService
from zet.workers import character_assembly_manifest_worker
from zet.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def config_for(root: Path) -> Config:
    return Config(
        base_library_path=str(root),
        base_character_path=str(root / "Characters"),
        base_asset_path=str(root / "Assets"),
        base_pipeline_path=str(root / "Pipelines"),
        base_ai_queue_path=str(root / "Queue"),
    )


class HeadImageCompilerTests(unittest.TestCase):
    def test_local_head_review_includes_background_gate_for_every_view(self) -> None:
        for view in VIEWS:
            with self.subTest(view=view):
                gates = LocalHeadImageService.review_gates(view)
                self.assertEqual("background", gates[0].key)
                self.assertIn("transparent background passes", gates[0].prompt)
                self.assertIn("Return TRUE only when the subject visibly blends", gates[0].prompt)

    def test_local_front_compiles_with_optional_source_and_keeps_traditional_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            base = {"Job": "local-front", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                    "Head View": "Front", "Template Path": str(template), "Reference Files": []}
            generated = compile_head_image_job({**base, "Output Directory": str(root / "text")}, PROJECT_ROOT,
                                               pipeline_mode="local")
            prompt = Path(generated["final_prompt"]).read_text(encoding="utf-8")
            manifest = json.loads(Path(generated["dependency_manifest"]).read_text(encoding="utf-8"))
            self.assertIn("No reference image is supplied", prompt)
            self.assertNotIn("# Render Task", prompt)
            self.assertEqual("generate", manifest["render_mode"])
            self.assertEqual([], manifest["resources"])
            self.assertEqual([], manifest["required_reference_roles"])

            source = root / "source.png"
            source.write_bytes(b"source")
            edited = compile_head_image_job({**base, "Output Directory": str(root / "guided"),
                                             "Reference Files": [{"role": "head_image_source", "path": str(source)}]},
                                            PROJECT_ROOT, pipeline_mode="local")
            edited_prompt = Path(edited["final_prompt"]).read_text(encoding="utf-8")
            edited_manifest = json.loads(Path(edited["dependency_manifest"]).read_text(encoding="utf-8"))
            self.assertIn("optional supplied identity reference", edited_prompt)
            self.assertEqual("edit", edited_manifest["render_mode"])
            self.assertEqual([str(source)], [item["path"] for item in edited_manifest["resources"]])

    def test_local_non_front_requires_selected_front_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(Exception, "require the selected FRONT anchor"):
                compile_head_image_job({
                    "Job": "local-profile", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                    "Head View": "Left Profile",
                    "Template Path": str(PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"),
                    "Output Directory": str(root / "output"), "Reference Files": [],
                }, PROJECT_ROOT, pipeline_mode="local")

    def test_local_head_workspace_starts_with_front_candidates_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1,
                                      "other_count": 1, "seeds": list(range(8))})

            self.assertEqual(8, len(run["views"]))
            self.assertEqual(8, run["candidate_count"])
            self.assertEqual("QUEUED", run["status"])
            self.assertEqual("", run["front_source"])
            prompt = Path(run["front_prompt_path"]).read_text(encoding="utf-8")
            self.assertIn("No reference image is supplied", prompt)
            self.assertEqual(1, len([item for item in run["candidates"] if item["view"] == "FRONT"]))

    def test_local_head_renders_view_before_gates_then_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2,
                                      "other_count": 1, "seeds": list(range(9))})
            candidates = [item for item in run["candidates"] if item["view"] == "FRONT"]
            candidate_ids = {item["candidate_id"] for item in candidates}
            events = []

            def queue(_run_id, candidate_id):
                events.append(("render", candidate_id))
                image_path = root / "renders" / f"{candidate_id}.png"
                service._update(run["run_id"], candidate_id, status="QUEUED", image_path=str(image_path))

            def wait(_run_id, candidate_id):
                events.append(("wait", candidate_id))
                candidate = next(item for item in service.detail(run["run_id"])["candidates"]
                                 if item["candidate_id"] == candidate_id)
                image_path = Path(candidate["image_path"])
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(b"image")
                service._update(run["run_id"], candidate_id, status="WAITING_FOR_GATES")
                return True

            def gates(_run_id, candidate_id):
                events.append(("gate", candidate_id))
                service._update(run["run_id"], candidate_id, status="WAITING_FOR_HUMAN_REVIEW")
                return True

            def rank(_run_id, view):
                events.append(("rank", view))
                return service.detail(run["run_id"])

            with patch.object(service, "queue_render_candidate", side_effect=queue), \
                    patch.object(service, "_wait_render", side_effect=wait), \
                    patch.object(service, "run_candidate_gates", side_effect=gates), \
                    patch.object(service, "rank_view", side_effect=rank):
                service.execute_run(run["run_id"], views={"FRONT"}, candidate_ids=candidate_ids)

            self.assertEqual([
                ("render", candidates[0]["candidate_id"]),
                ("render", candidates[1]["candidate_id"]),
                ("wait", candidates[0]["candidate_id"]),
                ("wait", candidates[1]["candidate_id"]),
                ("gate", candidates[0]["candidate_id"]),
                ("gate", candidates[1]["candidate_id"]),
                ("rank", "FRONT"),
            ], events)

    def test_local_head_ranking_closes_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2,
                                      "other_count": 1, "seeds": list(range(9))})
            candidates = [item for item in run["candidates"] if item["view"] == "FRONT"]
            for candidate in candidates:
                image_path = root / f"{candidate['candidate_id']}.png"
                image_path.write_bytes(candidate["candidate_id"].encode())
                service._update(run["run_id"], candidate["candidate_id"],
                                status="WAITING_FOR_HUMAN_REVIEW", image_path=str(image_path))

            temporary_paths = []

            def fake_codex(command, **_kwargs):
                schema_path = Path(command[command.index("--output-schema") + 1])
                output_path = Path(command[command.index("--output-last-message") + 1])
                temporary_paths.extend((schema_path, output_path))
                self.assertIn("ranking", json.loads(schema_path.read_text(encoding="utf-8"))["properties"])
                output_path.write_text(json.dumps({"ranking": [
                    {"candidate_id": item["candidate_id"], "reason": "Clear reference"} for item in candidates
                ]}), encoding="utf-8")
                return SimpleNamespace(returncode=0)

            with patch.object(service, "review_gates", return_value=[]), \
                    patch("zet.services.local_head_image_service.shutil.which", return_value="codex"), \
                    patch("zet.services.local_head_image_service.subprocess.run", side_effect=fake_codex):
                ranked = service.rank_view(run["run_id"], "FRONT")

            self.assertEqual("COMPLETE", ranked["rankings"]["FRONT"]["status"])
            self.assertTrue(temporary_paths)
            self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_standard_source_path_compiles_all_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            source = root / "source.png"
            source.write_bytes(b"image")
            for view in FOUNDATION_VIEWS:
                references = [{"role": "head_image_source", "path": str(source)}]
                with self.subTest(view=view):
                    result = compile_head_image_job({
                        "Job": f"head-{view}-source",
                        "Task": "head-image",
                        "Character": "Test",
                        "Phase": "Adult",
                        "Head View": view,
                        "Template Path": str(template),
                        "Output Directory": str(root / view / "source"),
                        "Reference Files": references,
                    }, PROJECT_ROOT)
                    prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                    self.assertIn("HEAD-IMAGE Adult CHARACTER REFERENCE", prompt)
                    self.assertNotIn("NECK FITMENT", prompt)
                    self.assertNotIn("simple, unobtrusive background", prompt.lower())
                    self.assertNotIn("{{", prompt)
                    self.assertNotIn("young-adult Tsaeytte", prompt)
                    self.assertNotIn("* Wrong age phase.", prompt)
                    manifest = json.loads(Path(result["dependency_manifest"]).read_text(encoding="utf-8"))
                    self.assertEqual(4, manifest["head_image_prompt_contract"]["version"])
                    self.assertEqual("deferred", manifest["head_image_prompt_contract"]["geometry_regularization"])
                    self.assertEqual([1], [item["image_index"] for item in manifest["resources"]])
                    self.assertEqual(["edit_base"], [item["prompt_role"] for item in manifest["resources"]])
                    self.assertEqual([str(source)], [item["path"] for item in manifest["resources"]])
                    self.assertEqual(2, manifest["prompt_schema_version"])
                    self.assertEqual("chatgpt_images_2_5_v1", manifest["engine_profile"])
                    self.assertEqual("edit", manifest["render_mode"])
                    if view == FOUNDATION_VIEWS[0]:
                        analysis = compile_head_image_job({
                            "Job": "head-analysis", "Task": "head-image", "Character": "Test",
                            "Phase": "Adult", "Head View": view, "Template Path": str(template),
                            "Output Directory": str(root / view / "analysis"), "Reference Files": references,
                        }, PROJECT_ROOT, prompt_variant="analysis")
                        analysis_text = Path(analysis["final_prompt"]).read_text(encoding="utf-8")
                        self.assertIn("# Review Specification", analysis_text)
                        self.assertIn("Image 1", analysis_text)
                        self.assertIn("HEAD-IMAGE Adult CHARACTER REFERENCE", analysis_text)
                        self.assertNotIn("# Render Task", analysis_text)
                        self.assertNotIn("<!-- ZET:", analysis_text)



    def test_rejects_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(Exception, "requires one head_image_source"):
                compile_head_image_job({
                    "Job": "missing",
                    "Task": "head-image",
                    "Character": "Test",
                    "Phase": "Adult",
                    "Head View": "Front",
                    "Template Path": str(PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"),
                    "Output Directory": str(root / "output"),
                    "Reference Files": [],
                }, PROJECT_ROOT)



class HeadImageReferenceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[PathService, AssetRepository, ReferenceService]:
        paths = PathService(config_for(root), PROJECT_ROOT)
        for phase in ("Adult", "Elder"):
            paths.character_path("Test", phase).mkdir(parents=True)
            paths.character_asset_path("Test", phase).mkdir(parents=True)
        adult_image = paths.character_asset_path("Test", "Adult") / "Head-Image_Front.png"
        adult_image.write_bytes(b"adult")
        (paths.character_path("Test", "Adult") / "Assets.json").write_text(json.dumps({
            "schema_version": 1,
            "next_asset_id": 2,
            "assets": [Asset(1, "Test", "Adult", "Head-Image", "Front", head_view="Front", asset_state="LOCKED", pipeline_stage="LOCKED", actor="HUMAN_AGENT", final_image_output=adult_image.name).__dict__],
        }), encoding="utf-8")
        elder_assets = [Asset(index + 1, "Test", "Elder", "Head-Image", view, head_view=view, final_image_output=f"Head-Image_{view}.png").__dict__ for index, view in enumerate(FOUNDATION_VIEWS)]
        (paths.character_path("Test", "Elder") / "Assets.json").write_text(json.dumps({"schema_version": 1, "next_asset_id": 9, "assets": elder_assets}), encoding="utf-8")
        repository = AssetRepository(paths)
        return paths, repository, ReferenceService(repository, paths)

    def _config_path(self, root: Path) -> Path:
        (root / "Queue").mkdir(exist_ok=True)
        path = root / "config.toml"
        path.write_text(f"""[BaseFolders]
BaseCharacterPath = "{(root / 'Characters').as_posix()}"
BaseAssetPath = "{(root / 'Assets').as_posix()}"
BasePipelinePath = "{(root / 'Pipelines').as_posix()}"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
""", encoding="utf-8")
        return path

    def test_local_head_image_page_and_shared_asset_lookup_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._fixture(root)
            client = TestClient(create_app(self._config_path(root)))

            page = client.get("/local-head-image")
            self.assertEqual(200, page.status_code)
            self.assertIn("Paste an image here", page.text)
            self.assertIn("Generate other views", page.text)
            self.assertIn("background:'Background'", page.text)
            assets = client.get("/api/local/assets", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(200, assets.status_code)
            self.assertEqual([], assets.json()["assets"])



    def test_manifest_api_lists_and_saves_optional_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._fixture(root)
            client = TestClient(create_app(self._config_path(root)))
            query = {"character": "Test", "phase": "Elder"}
            tasks = client.get("/api/head-image-manifest/tasks", params=query)
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(len(tasks.json()["tasks"]), 8)
            detail = client.get("/api/head-image-manifest/1", params=query)
            source_path = detail.json()["source_options"][0]["path"]
            saved = client.post("/api/head-image-manifest/1/source", params=query, json={"source_path": source_path, "apply_all": True})
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["selected_source"]["source_phase"], "Adult")
            remaining = client.get("/api/head-image-manifest/2", params=query)
            self.assertEqual(remaining.json()["reference_files"], [])


class HeadImageFoundationTests(unittest.TestCase):
    def test_new_foundation_contains_three_eight_view_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CharacterOnboardingService(PathService(config_for(Path(temp_dir)), PROJECT_ROOT), PROJECT_ROOT)
            assets = service._foundation_assets("Test", "Adult")
            self.assertEqual(len(assets), 24)
            self.assertEqual([item["pipeline"] for item in assets[8:16]], ["Head-Image"] * 8)



class DirectAssemblyHeadImageDefaultTests(unittest.TestCase):

    def test_manifest_defaults_to_same_view_locked_head_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character_path = root / "Characters" / "Test" / "Adult"
            asset_path = root / "Assets" / "Test" / "Adult"
            character_path.mkdir(parents=True)
            asset_path.mkdir(parents=True)
            body = asset_path / "Body-Reference_Front.png"
            head = asset_path / "Head-Image_Front.png"
            body.write_bytes(b"body")
            head.write_bytes(b"head")
            records = [
                Asset(1, "Test", "Adult", "Body-Reference", "Front", asset_state="LOCKED", pipeline_stage="LOCKED", actor="HUMAN_AGENT", final_image_output=body.name).__dict__,
                Asset(2, "Test", "Adult", "Head-Image", "Front", head_view="Front", asset_state="LOCKED", pipeline_stage="LOCKED", actor="HUMAN_AGENT", final_image_output=head.name).__dict__,
                Asset(3, "Test", "Adult", "Character-Assembly", "Front", head_view="Front", pipeline_stage="MANIFEST", final_image_output="Character-Assembly_Front_Front_Assembled.png").__dict__,
            ]
            (character_path / "Assets.json").write_text(json.dumps({"schema_version": 1, "next_asset_id": 4, "assets": records}), encoding="utf-8")
            context = WorkerContext(root / "pipeline", root / "candidate.png", root / "locked.png", character_path, asset_path)
            result = character_assembly_manifest_worker.run(Asset(**records[2]), context)
            self.assertTrue(result.success)
            saved = json.loads((character_path / "Assets.json").read_text(encoding="utf-8"))["assets"][2]
            self.assertEqual(saved["reference_files"], [])
            self.assertEqual([item["role"] for item in result.reference_files], ["body_reference", "head_image"])
            self.assertEqual(result.reference_files[1]["source_asset_id"], 2)
            other = asset_path / "Head-Image_Front_other.png"
            other.write_bytes(b"other head")
            records.append({**records[1], "asset_id": 4, "final_image_output": other.name})
            (character_path / "Assets.json").write_text(json.dumps({"assets": records}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Select a source reference"):
                character_assembly_manifest_worker.run(Asset(**records[2]), context)
            selected = Asset(**records[2])
            selected.reference_files = [{"role": "head_image", "source_asset_id": 4, "path": str(other)}]
            result = character_assembly_manifest_worker.run(selected, context)
            self.assertEqual(4, result.reference_files[1]["source_asset_id"])


if __name__ == "__main__":
    unittest.main()
