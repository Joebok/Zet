import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.models.asset import Asset
from zet.models.worker import WorkerContext
from zet.repositories.asset_repository import AssetRepository
from zet.services.character_onboarding_service import CharacterOnboardingService, FOUNDATION_VIEWS
from zet.services.config_service import Config
from zet.services.path_service import PathService
from zet.services.reference_service import ReferenceService
from zet.workers import head_fitment_manifest_worker
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
    def test_compiles_with_and_without_optional_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            source = root / "source.png"
            source.write_bytes(b"image")
            for view in FOUNDATION_VIEWS:
                for suffix, references in (("none", []), ("source", [{"role": "head_image_source", "path": str(source)}])):
                    with self.subTest(view=view, source=bool(references)):
                        result = compile_head_image_job({
                            "Job": f"head-{view}-{suffix}",
                            "Task": "head-image",
                            "Character": "Test",
                            "Phase": "Adult",
                            "Head View": view,
                            "Template Path": str(template),
                            "Output Directory": str(root / view / suffix),
                            "Reference Files": references,
                        }, PROJECT_ROOT)
                        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                        self.assertIn("HEAD-IMAGE CHARACTER REFERENCE", prompt)
                        self.assertNotIn("NECK FITMENT", prompt)
                        self.assertNotIn("transparent background", prompt.lower())
                        self.assertIn("source image is attached" if references else "No source image is supplied", prompt)

    def test_source_reference_instructions_follow_attachment_notice_only_when_source_is_attached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "Character.md"
            template_text = (
                PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            ).read_text(encoding="utf-8")
            template.write_text(
                template_text.replace(
                    "<!-- ZET:BEGIN HEAD_IMAGE_REFERENCE_INSTRUCTIONS -->\n\n<!-- ZET:END HEAD_IMAGE_REFERENCE_INSTRUCTIONS -->",
                    "<!-- ZET:BEGIN HEAD_IMAGE_REFERENCE_INSTRUCTIONS -->\n\nInterpret this source as identity evidence.\n\n<!-- ZET:END HEAD_IMAGE_REFERENCE_INSTRUCTIONS -->",
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
            self.assertLess(prompt.index("rotate the result into the requested target view."), prompt.index("Interpret this source as identity evidence."))
            self.assertLess(prompt.index("Interpret this source as identity evidence."), prompt.index("Create one reusable head reference image."))

            without_source = compile_head_image_job({
                **base_job,
                "Output Directory": str(root / "without-source"),
                "Reference Files": [],
            }, PROJECT_ROOT)
            prompt = Path(without_source["final_prompt"]).read_text(encoding="utf-8")
            self.assertNotIn("Interpret this source as identity evidence.", prompt)

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
    def test_new_foundation_contains_four_eight_view_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CharacterOnboardingService(PathService(config_for(Path(temp_dir)), PROJECT_ROOT), PROJECT_ROOT)
            assets = service._foundation_assets("Test", "Adult")
            self.assertEqual(len(assets), 32)
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


class HeadFitmentHeadImageDefaultTests(unittest.TestCase):
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
                (3, "Head-Fitment", "Front"),
                (4, "Head-Fitment", "Left"),
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
                Asset(5, "Test", "Adult", "Head-Fitment", "Front", head_view="Front").__dict__,
                Asset(6, "Test", "Adult", "Character-Assembly", "Front", head_view="Front").__dict__,
            ])
            (character_path / "Assets.json").write_text(
                json.dumps({"schema_version": 1, "next_asset_id": 7, "assets": records}),
                encoding="utf-8",
            )
            service = ReferenceService(AssetRepository(paths), paths)

            fitment = service.head_fitment_context("Test", "Adult", 5)
            self.assertEqual([item["asset_id"] for item in fitment["body_reference_options"]], [1])
            assembly = service.character_assembly_context("Test", "Adult", 6)
            self.assertEqual([item["asset_id"] for item in assembly["body_reference_options"]], [1])
            self.assertEqual([item["asset_id"] for item in assembly["head_fitment_options"]], [3])

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
                Asset(3, "Test", "Adult", "Head-Fitment", "Front", head_view="Front", pipeline_stage="MANIFEST", final_image_output="Head-Fitment_Front_Front.png").__dict__,
            ]
            (character_path / "Assets.json").write_text(json.dumps({"schema_version": 1, "next_asset_id": 4, "assets": records}), encoding="utf-8")
            context = WorkerContext(root / "pipeline", root / "candidate.png", root / "locked.png", character_path, asset_path)
            result = head_fitment_manifest_worker.run(Asset(**records[2]), context)
            self.assertTrue(result.success)
            saved = json.loads((character_path / "Assets.json").read_text(encoding="utf-8"))["assets"][2]
            self.assertEqual([item["role"] for item in saved["reference_files"]], ["body_reference", "head_image"])
            self.assertEqual(saved["reference_files"][1]["source_asset_id"], 2)


if __name__ == "__main__":
    unittest.main()
