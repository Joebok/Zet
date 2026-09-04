from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from Scripts.Run_Scene_Appearance_Jobs import compile_scene_appearance_job
from zet.models.asset import Asset
from zet.models.worker import WorkerContext
from zet.repositories.asset_repository import AssetRepository
from zet.services.config_service import ConfigService
from zet.services.path_service import PathService
from zet.services.scene_appearance_service import SceneAppearanceService, SceneAppearanceServiceError
from zet.services.turnaround_views import TURNAROUND_VIEW_ORDER
from zet.workers.scene_appearance_manifest_worker import run as resolve_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MORROW_TAG = "{{AUX:person:morrow:morrow-raven-form}}"
TUSK_TAG = "{{AUX:thing:utility-tusk:tusk-reference}}"


class SceneAppearancePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.library = self.root / "library"
        self.character_dir = self.library / "Characters" / "Tsaeytte" / "Adult"
        self.asset_dir = self.library / "Assets" / "Tsaeytte" / "Adult"
        self.pipeline_dir = self.library / "Pipelines" / "Tsaeytte" / "Adult"
        self.character_dir.mkdir(parents=True)
        self.asset_dir.mkdir(parents=True)
        self.pipeline_dir.mkdir(parents=True)
        self.root.joinpath("config.toml").write_text(
            "\n".join([
                "[BaseFolders]",
                f'BaseLibraryPath = "{self.library.as_posix()}"',
                'BaseCharacterPath = "Characters"',
                'BaseAssetPath = "Assets"',
                'BasePipelinePath = "Pipelines"',
                f'BaseAIQueuePath = "{(self.root / "Queue").as_posix()}"',
            ]),
            encoding="utf-8",
        )
        assets = []
        for asset_id, view in enumerate(TURNAROUND_VIEW_ORDER, start=1):
            filename = f"costume-{view}.png"
            self.asset_dir.joinpath(filename).write_bytes(b"image")
            assets.append({
                "asset_id": asset_id,
                "character": "Tsaeytte",
                "phase": "Adult",
                "pipeline": "Costume-Dressing",
                "body_view": view,
                "head_view": view,
                "costume": "Canonical Adventure Gear",
                "asset_state": "LOCKED",
                "pipeline_stage": "LOCKED",
                "actor": "HUMAN_AGENT",
                "final_image_output": filename,
            })
        self.character_dir.joinpath("Assets.json").write_text(
            json.dumps({"next_asset_id": 9, "assets": assets}, indent=2) + "\n",
            encoding="utf-8",
        )
        aux_dir = self.library / "AuxiliaryResources"
        aux_dir.mkdir(parents=True)
        morrow = aux_dir / "morrow.png"
        tusk = aux_dir / "tusk.png"
        morrow.write_bytes(b"image")
        tusk.write_bytes(b"image")
        aux_dir.joinpath("AuxiliaryResources.json").write_text(json.dumps({
            "resources": [
                {"category": "person", "resource_id": "morrow", "label": "Morrow", "images": [
                    {"image_id": "morrow-raven-form", "image_path": str(morrow)}
                ]},
                {"category": "thing", "resource_id": "utility-tusk", "label": "Utility Tusk", "images": [
                    {"image_id": "tusk-reference", "image_path": str(tusk)}
                ]},
            ]
        }, indent=2), encoding="utf-8")
        config = ConfigService.load(self.root / "config.toml")
        self.paths = PathService(config, self.root)
        self.repository = AssetRepository(self.paths)
        self.service = SceneAppearanceService(self.repository, self.paths)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _references() -> list[dict]:
        return [
            {"role": "scene_appearance_companion", "label": "Morrow raven form", "tag": MORROW_TAG},
            {"role": "scene_appearance_prop", "label": "Utility tusk", "tag": TUSK_TAG},
        ]

    def _create(self):
        return self.service.create(
            "Tsaeytte", "Adult", "hell-adventures", "Hell Adventures",
            "Canonical Adventure Gear",
            "Morrow is on the anatomical left shoulder; hold the tusk vertically in the anatomical right hand, "
            "with the pointed end resting on the ground and the broken thick base upward.",
            self._references(),
        )

    def test_create_is_atomic_and_seeds_exactly_eight_add_ref_assets(self) -> None:
        result = self._create()

        self.assertEqual(list(TURNAROUND_VIEW_ORDER), [asset.body_view for asset in result.assets])
        self.assertEqual({"ADD_REF"}, {asset.pipeline_stage for asset in result.assets})
        self.assertEqual({"hell-adventures"}, {asset.scene_appearance_id for asset in result.assets})
        self.assertTrue(Path(result.appearance.path).is_file())

        failing_path = self.paths.scene_appearance_definition_path("Tsaeytte", "Adult", "rollback-test")
        with patch.object(self.repository, "create_assets", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                self.service.create(
                    "Tsaeytte", "Adult", "rollback-test", "Rollback Test",
                    "Canonical Adventure Gear", "Arrangement.", self._references(),
                )
        self.assertFalse(failing_path.exists())

    def test_validation_and_render_affecting_update_reset_assets(self) -> None:
        result = self._create()
        changed = self.repository.get_asset("Tsaeytte", "Adult", result.assets[0].asset_id)
        changed.pipeline_stage = "LOCKED"
        changed.asset_state = "LOCKED"
        changed.reference_files = [{"role": "old"}]
        self.repository.save_asset(changed)

        updated = self.service.update(
            "Tsaeytte", "Adult", "hell-adventures", "Hell Adventures",
            "Canonical Adventure Gear", "Updated arrangement.", self._references(),
        )
        self.assertTrue(updated.render_changed)
        self.assertEqual({"ADD_REF"}, {asset.pipeline_stage for asset in updated.assets})
        self.assertTrue(all(not asset.reference_files for asset in updated.assets))
        with self.assertRaises(SceneAppearanceServiceError):
            self.service.create(
                "Tsaeytte", "Adult", "Bad ID", "Bad", "Canonical Adventure Gear",
                "Arrangement.", self._references(),
            )

    def test_manifest_resolves_exact_view_then_ordered_supporting_images(self) -> None:
        asset = self._create().assets[3]
        context = WorkerContext(
            pipeline_path=self.paths.pipeline_path(asset),
            candidate_image_path=self.paths.candidate_image_path(asset),
            locked_image_path=self.paths.locked_image_path(asset),
            character_path=self.paths.character_path(asset.character, asset.phase),
            character_asset_path=self.paths.character_asset_path(asset.character, asset.phase),
            config=self.paths.config,
            asset_repository=self.repository,
            path_service=self.paths,
        )

        result = resolve_manifest(asset, context)

        self.assertTrue(result.success, result.message)
        self.assertEqual(
            ["scene_appearance_source", "scene_appearance_companion", "scene_appearance_prop"],
            [item["role"] for item in result.reference_files or []],
        )
        self.assertEqual(asset.body_view, result.reference_files[0]["body_view"])

        source = self.repository.get_asset("Tsaeytte", "Adult", 4)
        source.asset_state = "IN_PROGRESS"
        source.pipeline_stage = "RENDER_REVIEW"
        self.repository.save_asset(source)
        missing = resolve_manifest(asset, context)
        self.assertFalse(missing.success)
        self.assertEqual("MISSING_COSTUME_DRESSING", missing.error_code)

    def test_compiler_keeps_prompt_short_and_records_provenance(self) -> None:
        asset = self._create().assets[0]
        definition_path = Path(asset.scene_appearance_definition_path)
        template_dir = self.root / "Config" / "Prompt_Templates"
        template_dir.mkdir(parents=True)
        for name in ("Prompt_Task_Bundles.json", "Prompt_View_Text.json", "Prompt_View_Aliases.json"):
            shutil.copyfile(PROJECT_ROOT / "Config" / name, self.root / "Config" / name)
        shutil.copyfile(PROJECT_ROOT / "Config" / "Prompt_Templates" / "scene_appearance_v1.md", template_dir / "scene_appearance_v1.md")
        refs = [
            {"role": "scene_appearance_source", "path": str(self.asset_dir / "costume-FRONT.png")},
            {"role": "scene_appearance_companion", "path": str(self.library / "AuxiliaryResources" / "morrow.png")},
            {"role": "scene_appearance_prop", "path": str(self.library / "AuxiliaryResources" / "tusk.png")},
        ]
        output = self.root / "compiled"

        result = compile_scene_appearance_job({
            "Job": "scene-front", "Task": "scene-appearance", "Character": "Tsaeytte",
            "Phase": "Adult", "Body View": "FRONT", "Scene Appearance ID": "hell-adventures",
            "Definition Path": str(definition_path), "Output Directory": str(output),
            "Expected Output": "front.png", "Reference Files": refs,
        }, self.root)

        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
        manifest = json.loads(Path(result["dependency_manifest"]).read_text(encoding="utf-8"))
        self.assertIn("anatomical left shoulder", prompt)
        self.assertIn("anatomical right hand", prompt)
        self.assertIn("pointed end", prompt)
        self.assertIn("not a narrative scene", prompt.lower())
        self.assertLess(len(prompt.split()), 350)
        self.assertEqual(
            ["scene_appearance_source", "scene_appearance_companion", "scene_appearance_prop"],
            manifest["required_reference_roles"],
        )
        self.assertTrue((output / "Image_Review.md").is_file())

    def test_legacy_asset_json_loads_without_scene_appearance_fields(self) -> None:
        asset = self.repository.get_asset("Tsaeytte", "Adult", 1)
        self.assertIsInstance(asset, Asset)
        self.assertIsNone(asset.scene_appearance_id)
        self.assertIsNone(asset.scene_appearance)


if __name__ == "__main__":
    unittest.main()
