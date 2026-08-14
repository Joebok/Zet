import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.models.asset import Asset
from zet.models.worker import WorkerContext
from zet.repositories.asset_repository import AssetRepository
from zet.services.character_onboarding_service import CharacterOnboardingService, FOUNDATION_VIEWS
from zet.services.config_service import Config
from zet.services.path_service import PathService
from zet.services.reference_service import ReferenceService
from zet.workers import character_assembly_manifest_worker
from zet.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ELDER_LIBRARY_ROOT = PROJECT_ROOT.parent / "Zet_Library"


def config_for(root: Path) -> Config:
    return Config(
        base_library_path=str(root),
        base_character_path=str(root / "Characters"),
        base_asset_path=str(root / "Assets"),
        base_pipeline_path=str(root / "Pipelines"),
        base_ai_queue_path=str(root / "Queue"),
    )


class HeadImageCompilerTests(unittest.TestCase):
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
                    self.assertEqual(references, manifest["resources"])

    def test_standard_source_sections_are_rendered_in_canonical_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "Character.md"
            template_text = (
                PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            ).read_text(encoding="utf-8")
            template.write_text(
                template_text.replace(
                    "<!-- ZET:BEGIN HEAD_IMAGE_SOURCE_INSTRUCTIONS -->",
                    "<!-- ZET:BEGIN HEAD_IMAGE_SOURCE_INSTRUCTIONS -->\nInterpret this source as identity evidence.",
                    1,
                ),
                encoding="utf-8",
            )
            source = root / "source.png"
            source.write_bytes(b"image")
            base_job = {
                "Job": "reference-instructions",
                "Task": "head-image",
                "Character": "Test",
                "Phase": "Adult",
                "Head View": "Front",
                "Template Path": str(template),
            }

            with_source = compile_head_image_job({
                **base_job,
                "Output Directory": str(root / "with-source"),
                "Reference Files": [{"role": "head_image_source", "path": str(source)}],
            }, PROJECT_ROOT)
            prompt = Path(with_source["final_prompt"]).read_text(encoding="utf-8")
            ordered = [
                "Interpret this source as identity evidence.",
                "[Technical head and face description.]",
                "Front view head notes:",
                "[Technical hair description.]",
                "Front view hair notes:",
                "Source-image contract:",
                "Render one clear image of the character's head",
            ]
            self.assertEqual(sorted(prompt.index(value) for value in ordered), [prompt.index(value) for value in ordered])

    def test_transform_path_suppresses_all_standard_source_head_and_hair_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"image")
            template = root / "Character.md"
            text = (PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md").read_text(encoding="utf-8")
            text = text.replace(
                "<!-- ZET:BEGIN HEAD_IMAGE_TRANSFORM_INSTRUCTIONS -->",
                "<!-- ZET:BEGIN HEAD_IMAGE_TRANSFORM_INSTRUCTIONS -->\nTRANSFORM PATH ONLY",
                1,
            )
            template.write_text(text, encoding="utf-8")
            result = compile_head_image_job({
                "Job": "transform",
                "Task": "head-image",
                "Character": "Test",
                "Phase": "Elder",
                "Head View": "Front",
                "Template Path": str(template),
                "Output Directory": str(root / "output"),
                "Reference Files": [{"role": "head_image_source", "path": str(source)}],
            }, PROJECT_ROOT)
            prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
            self.assertIn("TRANSFORM PATH ONLY", prompt)
            for excluded in (
                "[Technical head and face description.]",
                "Front view head notes:",
                "[Technical hair description.]",
                "Front view hair notes:",
                "Source-image contract:",
                "Render one clear image of the character's head",
            ):
                self.assertNotIn(excluded, prompt)

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

    def test_rejects_multiple_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"image")
            job = {
                "Job": "multiple",
                "Task": "head-image",
                "Character": "Test",
                "Phase": "Adult",
                "Head View": "Front",
                "Template Path": str(PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"),
                "Output Directory": str(root / "output"),
                "Reference Files": [{"role": "head_image_source", "path": str(source)}] * 2,
            }
            with self.assertRaisesRegex(Exception, "at most one"):
                compile_head_image_job(job, PROJECT_ROOT)


@unittest.skipUnless(
    (ELDER_LIBRARY_ROOT / "Characters" / "Tsaeytte" / "Elder" / "Character.md").is_file(),
    "The checked-out Zet_Library Elder regression artifacts are unavailable.",
)
class ElderPromptRegressionTests(unittest.TestCase):
    def test_review_prompt_changes_are_confined_to_requested_view_section(self) -> None:
        review_root = PROJECT_ROOT / "Docs" / "Template_Schema_Review"
        for name in ("Front", "Front-Left-3-4", "Left-Profile", "Back-Right-3-4"):
            with self.subTest(view=name):
                before = (review_root / "before" / "prompts" / "Head-Image" / f"{name}.md").read_text(encoding="utf-8")
                after = (review_root / "after" / "prompts" / "Head-Image" / f"{name}.md").read_text(encoding="utf-8")
                before_prefix, before_view = before.split("## Requested view", 1)
                after_prefix, after_view = after.split("## Requested view", 1)
                self.assertEqual(before_prefix, after_prefix)
                self.assertEqual(
                    before_view.split("## Rendering Style", 1)[1],
                    after_view.split("## Rendering Style", 1)[1],
                )

    def test_current_compilers_emit_canonical_elder_prompts_for_all_views(self) -> None:
        template = ELDER_LIBRARY_ROOT / "Characters" / "Tsaeytte" / "Elder" / "Character.md"
        pipeline_root = ELDER_LIBRARY_ROOT / "Pipelines" / "Tsaeytte" / "Elder"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            for task, compiler in (
                ("Head-Image", compile_head_image_job),
                ("Character-Assembly", compile_character_assembly_job),
            ):
                prompt_paths = sorted((pipeline_root / task).rglob("Final_Image_Prompt.md"))
                self.assertEqual(8, len(prompt_paths), task)
                for index, expected_path in enumerate(prompt_paths):
                    manifest = json.loads(
                        (expected_path.parent / "dependency_manifest.json").read_text(encoding="utf-8")
                    )
                    job = {
                        "Job": manifest["job_id"],
                        "Task": manifest["task"],
                        "Character": manifest["character"],
                        "Phase": manifest["phase"],
                        "Template Path": str(template),
                        "Output Directory": str(output_root / task / str(index)),
                        "Reference Files": manifest["resources"],
                    }
                    if task == "Head-Image":
                        job["Head View"] = manifest["view_token"]
                    else:
                        job.update({
                            "Body View": manifest["body_view_token"],
                            "Head View": manifest["head_view_token"],
                            "Assembly Style Mode": manifest["assembly_style_mode"],
                        })
                    result = compiler(job, PROJECT_ROOT)
                    actual = Path(result["final_prompt"]).read_text(encoding="utf-8")
                    self.assertNotIn("{{", actual, str(expected_path))
                    view_token = manifest.get("view_token") or manifest["body_view_token"]
                    self.assertIn(view_token.replace("_", " ").split()[0], actual.upper())
                    if task == "Head-Image":
                        self.assertNotIn("BODY PROPORTIONS", actual)
                        self.assertNotIn("FITMENT CLOTHING", actual)


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

    def test_cross_phase_source_is_saved_to_one_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, repository, service = self._fixture(Path(temp_dir))
            context = service.head_image_context("Test", "Elder", 1)
            self.assertEqual(len(context["source_options"]), 1)
            source_path = context["source_options"][0]["path"]
            updated = service.save_head_image_source("Test", "Elder", 1, source_path)
            self.assertEqual(updated.reference_files[0]["role"], "head_image_source")
            self.assertEqual(updated.reference_files[0]["source_phase"], "Adult")
            self.assertTrue(all(not asset.reference_files for asset in repository.list_assets("Test", "Elder")[1:]))

    def test_upload_uses_head_image_source_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, _, service = self._fixture(Path(temp_dir))
            path = service.upload_head_image_source("Test", "Elder", "source.png", b"image")
            self.assertEqual(path.parent.name, "Head_Image_Sources")
            self.assertTrue(path.is_file())

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

    def test_add_missing_head_images_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = PathService(config_for(root), PROJECT_ROOT)
            phase = paths.character_path("Test", "Adult")
            phase.mkdir(parents=True)
            (phase / "Assets.json").write_text('{"schema_version": 1, "next_asset_id": 1, "assets": []}\n', encoding="utf-8")
            (phase / "Pipelines.json").write_text(json.dumps({"schema_version": 1, "pipelines": {"Body-Reference": {"stages": [], "actor_by_stage": {}, "worker_by_stage": {}}}}), encoding="utf-8")
            service = CharacterOnboardingService(paths, PROJECT_ROOT)
            self.assertEqual(len(service.add_missing_head_image_foundation("Test", "Adult")), 8)
            self.assertEqual(service.add_missing_head_image_foundation("Test", "Adult"), [])


class DirectAssemblyHeadImageDefaultTests(unittest.TestCase):
    def test_manifest_reference_options_match_asset_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = PathService(config_for(root), PROJECT_ROOT)
            character_path = paths.character_path("Test", "Adult")
            asset_path = Path(paths.config.base_asset_path) / "Test" / "Adult"
            character_path.mkdir(parents=True)
            asset_path.mkdir(parents=True)
            records = []
            for asset_id, pipeline, view in (
                (1, "Body-Reference", "Front"),
                (2, "Body-Reference", "Left"),
                (3, "Head-Image", "Front"),
                (4, "Head-Image", "Left"),
            ):
                output = f"{pipeline}_{view}.png"
                (asset_path / output).write_bytes(b"image")
                records.append(Asset(
                    asset_id,
                    "Test",
                    "Adult",
                    pipeline,
                    view,
                    head_view=view,
                    asset_state="LOCKED",
                    pipeline_stage="LOCKED",
                    actor="HUMAN_AGENT",
                    final_image_output=output,
                ).__dict__)
            records.extend([
                Asset(5, "Test", "Adult", "Character-Assembly", "Front", head_view="Front").__dict__,
            ])
            (character_path / "Assets.json").write_text(
                json.dumps({"schema_version": 2, "next_asset_id": 6, "reserved_asset_ids": [], "assets": records}),
                encoding="utf-8",
            )
            service = ReferenceService(AssetRepository(paths), paths)

            assembly = service.character_assembly_context("Test", "Adult", 5)
            self.assertEqual([item["asset_id"] for item in assembly["body_reference_options"]], [1])
            self.assertEqual([item["asset_id"] for item in assembly["head_image_options"]], [3])

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
            self.assertEqual([item["role"] for item in saved["reference_files"]], ["body_reference", "head_image"])
            self.assertEqual(saved["reference_files"][1]["source_asset_id"], 2)


if __name__ == "__main__":
    unittest.main()
