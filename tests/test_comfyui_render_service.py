import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from zet.services.comfyui_render_service import (
    compile_ir_to_comfyui_workflow,
    compile_prompt_to_comfyui_workflow,
    run_comfyui_workflow,
)
from zet.services.local_render_types import LocalRenderError
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.scripts.render_comfyui_preview import main as render_comfyui_preview_main


class ComfyUIRenderServiceTests(unittest.TestCase):
    def _ir(self) -> dict:
        return {
            "schema_version": 3,
            "scene": {"slug": "At-the-Arch", "story_beat": "Two elves walk together."},
            "source": {},
            "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
            "composition": {"left_to_right": ["tsaeytte", "valindia"]},
            "style": {"art_style": "storybook fantasy illustration"},
            "environment": {"location": "academy archway", "lighting": "morning sunlight"},
            "elements": [
                {
                    "id": "tsaeytte",
                    "display_name": "Tsaeytte",
                    "element_type": "Character",
                    "resolved_source_sections": {"identity_preservation_core": "petite elf with short black hair"},
                },
                {
                    "id": "valindia",
                    "display_name": "Valindia",
                    "element_type": "Character",
                    "resolved_source_sections": {"identity_preservation_core": "tall elf with red and black hair"},
                },
            ],
            "placements": [
                {
                    "scene_element_id": "tsaeytte",
                    "position_within_cell": "left",
                    "depth": "foreground",
                    "pose": {"summary": "walking", "expression": "curious"},
                    "motion": {"state": "moving", "direction_screen": "toward camera"},
                },
                {
                    "scene_element_id": "valindia",
                    "position_within_cell": "right",
                    "depth": "foreground",
                    "pose": {"summary": "walking", "expression": "confident"},
                    "motion": {"state": "moving", "direction_screen": "toward camera"},
                },
            ],
            "props": [],
            "interactions": [],
            "custom_interactions": "",
            "dialogue": [{"text": "This must not enter the diffusion prompt."}],
            "references": [],
            "final_image_prompt_sections": {},
            "resolved_sources": {},
        }

    def _profile(self) -> dict:
        return {
            "backend": "comfyui",
            "short_side": 640,
            "max_long_side": 960,
            "steps": 28,
            "cfg": 7.0,
            "sampler_name": "dpmpp_2m",
            "scheduler": "karras",
            "seed": "random",
        }

    def test_compile_ir_builds_core_area_workflow(self) -> None:
        compilation = compile_ir_to_comfyui_workflow(
            self._ir(),
            self._profile(),
            checkpoint="model.safetensors",
            positive_prompt_globals="masterpiece",
            negative_prompt_globals="EasyNegative",
            seed=123,
        )

        classes = [node["class_type"] for node in compilation.workflow.values()]
        self.assertEqual(2, classes.count("ConditioningSetArea"))
        self.assertIn("CheckpointLoaderSimple", classes)
        self.assertIn("KSampler", classes)
        self.assertEqual((960, 544), (compilation.width, compilation.height))
        self.assertEqual(123, compilation.seed)
        self.assertIn("masterpiece", compilation.prompts["global"])
        self.assertIn("EasyNegative", compilation.prompts["negative"])
        self.assertNotIn("This must not enter", json.dumps(compilation.prompts))
        checkpoint_node = next(node for node in compilation.workflow.values() if node["class_type"] == "CheckpointLoaderSimple")
        self.assertEqual("model.safetensors", checkpoint_node["inputs"]["ckpt_name"])

    def test_compile_prompt_builds_plain_core_workflow(self) -> None:
        compilation = compile_prompt_to_comfyui_workflow(
            "one character",
            "blurry",
            self._profile(),
            checkpoint="model.safetensors",
            seed=7,
            aspect_ratio="4:5",
        )

        classes = [node["class_type"] for node in compilation.workflow.values()]
        self.assertNotIn("ConditioningSetArea", classes)
        self.assertEqual((640, 800), (compilation.width, compilation.height))

    def test_compile_rejects_invalid_ir(self) -> None:
        ir = self._ir()
        ir["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            compile_ir_to_comfyui_workflow(ir, self._profile(), checkpoint="model.safetensors")

    def test_run_submits_polls_and_safely_downloads_images(self) -> None:
        submitted = {"prompt_id": "prompt-1"}
        history = {
            "prompt-1": {
                "status": {"status_str": "success"},
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "../unsafe.png", "subfolder": "Zet", "type": "output"},
                        ]
                    }
                },
            }
        }
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch(
                "zet.services.comfyui_render_service._request_json",
                side_effect=[submitted, history],
            ),
            patch("zet.services.comfyui_render_service._request_bytes", return_value=b"png"),
        ):
            result = run_comfyui_workflow(
                {"1": {"class_type": "Test", "inputs": {}}},
                server_url="http://127.0.0.1:8188",
                output_dir=Path(temp_dir),
                poll_seconds=0,
                timeout_seconds=1,
            )

            self.assertEqual("prompt-1", result.prompt_id)
            self.assertEqual(Path(temp_dir) / "unsafe.png", result.image_paths[0])
            self.assertEqual(b"png", result.image_paths[0].read_bytes())

    def test_run_reports_validation_error(self) -> None:
        with patch(
            "zet.services.comfyui_render_service._request_json",
            return_value={"node_errors": {"1": "bad checkpoint"}},
        ):
            with self.assertRaisesRegex(LocalRenderError, "validation failed"):
                run_comfyui_workflow(
                    {},
                    server_url="http://127.0.0.1:8188",
                    output_dir=Path("."),
                )

    def test_run_reports_execution_error(self) -> None:
        with patch(
            "zet.services.comfyui_render_service._request_json",
            side_effect=[
                {"prompt_id": "prompt-1"},
                {"prompt-1": {"status": {"status_str": "error", "messages": ["failed"]}}},
            ],
        ):
            with self.assertRaisesRegex(LocalRenderError, "execution failed"):
                run_comfyui_workflow(
                    {},
                    server_url="http://127.0.0.1:8188",
                    output_dir=Path("."),
                    poll_seconds=0,
                    timeout_seconds=1,
                )

    def test_run_times_out(self) -> None:
        with patch(
            "zet.services.comfyui_render_service._request_json",
            return_value={"prompt_id": "prompt-1"},
        ):
            with self.assertRaisesRegex(LocalRenderError, "timed out"):
                run_comfyui_workflow(
                    {},
                    server_url="http://127.0.0.1:8188",
                    output_dir=Path("."),
                    timeout_seconds=0,
                )

    def test_checkpoint_discovery_reads_comfyui_loader_choices(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [["one.safetensors", "two.safetensors"]]}}
            }
        }).encode()
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_path = Path(temp_dir) / "profiles.json"
            profiles_path.write_text(
                json.dumps({"comfyui-core-preview": {"backend": "comfyui"}}),
                encoding="utf-8",
            )
            with patch("zet.services.local_render_backend_service.urlopen", return_value=response):
                checkpoints = LocalRenderBackendService(profiles_path).list_checkpoints(
                    "comfyui-core-preview",
                    backend="comfyui",
                    server_url="http://127.0.0.1:8188",
                )

        self.assertEqual(["one.safetensors", "two.safetensors"], [item["title"] for item in checkpoints])

    def test_cli_compile_only_writes_workflow_beside_ir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Config").mkdir()
            (root / "Config" / "Local_Render_Presets.json").write_text(
                json.dumps({"comfyui-core-preview": self._profile()}),
                encoding="utf-8",
            )
            config_path = root / "config.toml"
            config_path.write_text(
                """
[BaseFolders]
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "Queue"

[ComfyUI]
Profile = "comfyui-core-preview"
Checkpoint = "model.safetensors"
""".lstrip(),
                encoding="utf-8",
            )
            ir_path = root / "Scene_Render_IR.json"
            ir_path.write_text(json.dumps(self._ir()), encoding="utf-8")

            exit_code = render_comfyui_preview_main([
                str(ir_path),
                "--config",
                str(config_path),
                "--seed",
                "42",
                "--compile-only",
            ])

            self.assertEqual(0, exit_code)
            workflow = json.loads((root / "ComfyUI_Workflow_API.json").read_text(encoding="utf-8"))
            sampler = next(node for node in workflow.values() if node["class_type"] == "KSampler")
            self.assertEqual(42, sampler["inputs"]["seed"])


if __name__ == "__main__":
    unittest.main()
