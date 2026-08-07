from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository
from zet.services.config_service import Config
from zet.services.head_fitment_edit_service import (
    HeadFitmentEditService,
    MASK_EDIT,
    MASK_PROTECT,
    MASK_REMOVE,
    compile_head_fitment_inpaint_workflow,
)
from zet.services.path_service import PathService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class HeadFitmentEditServiceTests(unittest.TestCase):
    def _fixture(self, root: Path):
        characters = root / "Characters"
        assets = root / "Assets"
        pipelines = root / "Pipelines"
        queue = root / "Queue"
        phase = characters / "Test" / "Elder"
        asset_dir = assets / "Test" / "Elder"
        phase.mkdir(parents=True)
        asset_dir.mkdir(parents=True)
        pipelines.mkdir()
        queue.mkdir()
        head_path = asset_dir / "Head-Image_Front.png"
        body_path = asset_dir / "Body-Reference_Front.png"
        head = Image.new("RGB", (64, 80), (220, 210, 190))
        draw = ImageDraw.Draw(head)
        draw.ellipse((8, 3, 56, 60), fill=(90, 70, 55))
        draw.rectangle((26, 52, 38, 78), fill=(130, 95, 75))
        head.save(head_path)
        body = Image.new("RGB", (64, 96), (210, 210, 210))
        draw = ImageDraw.Draw(body)
        draw.ellipse((18, 3, 46, 35), fill=(110, 100, 90))
        draw.polygon([(27, 30), (37, 30), (43, 70), (21, 70)], fill=(110, 100, 90))
        body.save(body_path)
        asset = Asset(
            1,
            "Test",
            "Elder",
            "Head-Fitment",
            "Front",
            head_view="Front",
            pipeline_stage="MANIFEST",
            final_image_output="Head-Fitment_Front_Front.png",
            reference_files=[
                {"role": "body_reference", "path": str(body_path)},
                {"role": "head_image", "path": str(head_path)},
            ],
        )
        (phase / "Assets.json").write_text(
            json.dumps({"schema_version": 1, "next_asset_id": 2, "assets": [asset.__dict__]}),
            encoding="utf-8",
        )
        config = Config(
            base_library_path=str(root),
            base_character_path=str(characters),
            base_asset_path=str(assets),
            base_pipeline_path=str(pipelines),
            base_ai_queue_path=str(queue),
            head_fitment_render_mode="masked_local",
            head_fitment_masked_local_checkpoint="test-checkpoint",
        )
        paths = PathService(config, PROJECT_ROOT)
        repository = AssetRepository(paths)
        return HeadFitmentEditService(repository, paths), repository.get_asset("Test", "Elder", 1), head_path

    def test_mask_is_persisted_confirmed_and_invalidated_by_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, asset, head_path = self._fixture(Path(temp_dir))
            context = service.initialize("Test", "Elder", 1)
            self.assertTrue(context["mask_exists"])
            self.assertFalse(context["confirmed"])
            with Image.open(context["mask_path"]) as image:
                self.assertTrue(set(np.unique(np.array(image))).issubset({MASK_REMOVE, MASK_EDIT, MASK_PROTECT}))
                buffer = BytesIO()
                image.save(buffer, "PNG")
            confirmed = service.save_mask("Test", "Elder", 1, buffer.getvalue())
            self.assertTrue(confirmed["confirmed"])
            self.assertTrue(confirmed["current"])
            head_path.write_bytes(head_path.read_bytes() + b"changed")
            self.assertFalse(service.context("Test", "Elder", 1)["current"])

    def test_render_restores_protected_pixels_and_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, asset, head_path = self._fixture(Path(temp_dir))
            context = service.initialize("Test", "Elder", 1)
            mask = np.full((80, 64), MASK_REMOVE, np.uint8)
            mask[:52, 8:56] = MASK_PROTECT
            mask[52:72, 24:40] = MASK_EDIT
            buffer = BytesIO()
            Image.fromarray(mask, "L").save(buffer, "PNG")
            service.save_mask("Test", "Elder", 1, buffer.getvalue())

            requirements = {
                "schema_version": 1,
                "backend": "comfyui",
                "server_url": "http://test",
                "preset": "head-fitment-inpaint",
                "required_nodes": [],
                "missing_nodes": [],
                "models": [{"kind": "checkpoint", "required": True, "configured": "test-checkpoint", "available": True, "resolved": {"name": "test-checkpoint"}}],
                "not_required": ["ControlNet"],
            }

            def response(_workflow, *, output_dir, **_kwargs):
                raw = output_dir / "raw-test.png"
                Image.new("RGB", (64, 80), (255, 0, 0)).save(raw)
                return SimpleNamespace(image_paths=[raw], prompt_id="prompt-1")

            output_path = service.path_service.pipeline_path(asset) / asset.final_image_output
            with patch.object(service, "model_requirements", return_value=requirements), patch(
                "zet.services.head_fitment_edit_service.run_comfyui_workflow", side_effect=response
            ):
                service.render(asset, "fit only the neck", output_path)

            with Image.open(head_path) as source, Image.open(output_path) as result:
                source_pixel = source.convert("RGBA").getpixel((20, 20))
                self.assertEqual(source_pixel, result.getpixel((20, 20)))
                self.assertEqual(0, result.getpixel((2, 75))[3])
                self.assertEqual((255, 0, 0), result.getpixel((32, 65))[:3])
            self.assertTrue(service.paths(asset).model_requirements.exists())

    def test_comfyui_inpaint_workflow_uses_core_nodes(self) -> None:
        workflow = compile_head_fitment_inpaint_workflow(
            init_input="init.png", mask_input="mask.png", checkpoint="model.safetensors",
            prompt="neck", negative_prompt="face", steps=24, cfg=6.0,
            sampler_name="dpmpp_2m", scheduler="karras", denoise=0.22,
            grow_mask_by=6, seed=7, output_prefix="Zet/Test",
        )
        self.assertEqual("VAEEncodeForInpaint", workflow["7"]["class_type"])
        self.assertEqual(0.22, workflow["8"]["inputs"]["denoise"])
        self.assertEqual("red", workflow["4"]["inputs"]["channel"])

    def test_generated_mask_auto_confirms_and_preserves_confirmed_current_mask(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _, _ = self._fixture(Path(temp_dir))
            generated = Path(temp_dir) / "generated.png"
            mask = np.full((80, 64), MASK_REMOVE, np.uint8)
            mask[:55, 8:56] = MASK_PROTECT
            mask[55:74, 22:42] = MASK_EDIT
            Image.fromarray(mask, "L").save(generated)
            report = {
                "confidence_score": 0.95,
                "validation_failures": [],
                "components": {"semantic_agreement": 0.95},
                "geometry": {"center_x": 32},
            }

            installed = service.install_generated_mask(
                "Test", "Elder", 1, generated, report,
                source_ask_id="ask-1", auto_confirm=True, threshold=0.90,
            )

            self.assertTrue(installed["confirmed"])
            self.assertTrue(installed["auto_confirmed"])
            self.assertEqual(installed["source_ask_id"], "ask-1")
            generated.write_bytes(b"not-an-image")
            preserved = service.install_generated_mask(
                "Test", "Elder", 1, generated, report,
                source_ask_id="ask-2", auto_confirm=True, threshold=0.90,
            )
            self.assertEqual(preserved["generation_install"], "preserved_confirmed")

    def test_reject_archives_artifacts_and_marks_mask_unconfirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, asset, _ = self._fixture(Path(temp_dir))
            context = service.initialize("Test", "Elder", 1)
            with Image.open(context["mask_path"]) as image:
                buffer = BytesIO()
                image.save(buffer, "PNG")
            service.save_mask("Test", "Elder", 1, buffer.getvalue())

            rejected = service.reject_mask("Test", "Elder", 1, "profile corridor was anterior")

            self.assertFalse(rejected["confirmed"])
            self.assertEqual("profile corridor was anterior", rejected["rejection_history"][-1]["reason"])
            archives = list((service.paths(asset).diagnostics / "rejected").iterdir())
            self.assertEqual(1, len(archives))
            self.assertTrue((archives[0] / "Head_Fitment_Edit_Mask.png").is_file())
            self.assertTrue((archives[0] / "rejection.json").is_file())


if __name__ == "__main__":
    unittest.main()
