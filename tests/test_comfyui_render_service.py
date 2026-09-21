import json
from tests.support.image_fixture import png_bytes
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from zet.services.comfyui_render_service import (
    ComfyUIRunResult,
    _upload_comfyui_input,
    compile_ir_to_comfyui_workflow,
    compile_prompt_to_comfyui_workflow,
    run_comfyui_workflow,
)
from zet.services.local_render_types import LocalRenderError
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.scripts.render_comfyui_preview import main as render_comfyui_preview_main
from Scripts.Local_Render_Adapters.comfyui_adapter import render_preview


class ComfyUIRenderServiceTests(unittest.TestCase):
    def _ir(self) -> dict:
        return {
            "schema_version": 4,
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
        self.assertEqual("core_txt2img_prompt_only", compilation.workflow_kind)

    def test_compile_prompt_builds_img2img_controlnet_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init = root / "init.png"
            pose = root / "pose.png"
            init.write_bytes(b"init")
            pose.write_bytes(b"pose")
            profile = self._profile() | {
                "prompt_workflow_kind": "img2img_controlnet_prompt_only",
                "control_preprocessor": "dwpose",
                "controlnet_model": "openpose.safetensors",
                "denoise": 0.55,
                "control_strength": 0.8,
                "control_start": 0.0,
                "control_end": 0.85,
            }

            compilation = compile_prompt_to_comfyui_workflow(
                "one character", "blurry", profile,
                checkpoint="model.safetensors", seed=9,
                reference_files=[
                    {"role": "prompt_evolution_init", "path": str(init)},
                    {"role": "prompt_evolution_pose", "path": str(pose)},
                ],
                available_node_types={
                    "LoadImage", "DWPreprocessor", "ControlNetLoader", "ControlNetApplyAdvanced",
                },
            )

        classes = [node["class_type"] for node in compilation.workflow.values()]
        self.assertIn("VAEEncode", classes)
        self.assertIn("DWPreprocessor", classes)
        self.assertIn("ControlNetApplyAdvanced", classes)
        sampler = next(node for node in compilation.workflow.values() if node["class_type"] == "KSampler")
        self.assertEqual(0.55, sampler["inputs"]["denoise"])
        control = next(node for node in compilation.workflow.values() if node["class_type"] == "ControlNetApplyAdvanced")
        self.assertEqual(0.8, control["inputs"]["strength"])
        self.assertEqual("img2img_controlnet_prompt_only", compilation.workflow_kind)
        self.assertEqual(2, len(compilation.debug["references_used"]))

    def test_compile_prompt_builds_ipadapter_controlnet_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.png"
            pose = Path(temp_dir) / "pose.png"
            reference.write_bytes(b"reference")
            pose.write_bytes(b"pose")
            profile = self._profile() | {
                "prompt_workflow_kind": "ipadapter_controlnet_prompt_only",
                "ipadapter_model": "ipadapter.safetensors",
                "clip_vision_model": "clip.safetensors",
                "character_reference_weight": 0.65,
                "control_preprocessor": "dwpose",
                "controlnet_model": "openpose.safetensors",
            }

            compilation = compile_prompt_to_comfyui_workflow(
                "one character", "blurry", profile,
                checkpoint="model.safetensors", seed=9,
                reference_files=[
                    {"role": "prompt_evolution_appearance", "path": str(reference)},
                    {"role": "prompt_evolution_pose", "path": str(pose)},
                ],
                available_node_types={
                    "LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced",
                    "DWPreprocessor", "ControlNetLoader", "ControlNetApplyAdvanced",
                },
            )

        classes = [node["class_type"] for node in compilation.workflow.values()]
        self.assertIn("IPAdapterAdvanced", classes)
        self.assertIn("ControlNetApplyAdvanced", classes)
        adapter = next(node for node in compilation.workflow.values() if node["class_type"] == "IPAdapterAdvanced")
        sampler = next(node for node in compilation.workflow.values() if node["class_type"] == "KSampler")
        self.assertEqual(0.65, adapter["inputs"]["weight"])
        self.assertEqual(adapter["inputs"]["model"], ["1", 0])
        self.assertEqual(sampler["inputs"]["model"], ["7", 0])
        self.assertEqual("ipadapter_controlnet_prompt_only", compilation.workflow_kind)
        self.assertEqual(2, len(compilation.debug["references_used"]))

    def test_controlnet_prompt_fails_when_required_node_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pose = Path(temp_dir) / "pose.png"
            pose.write_bytes(b"pose")
            with self.assertRaisesRegex(LocalRenderError, "DWPreprocessor"):
                compile_prompt_to_comfyui_workflow(
                    "one character", "blurry",
                    self._profile() | {
                        "prompt_workflow_kind": "controlnet_prompt_only",
                        "control_preprocessor": "dwpose",
                        "controlnet_model": "openpose.safetensors",
                    },
                    checkpoint="model.safetensors",
                    reference_files=[{"role": "prompt_evolution_pose", "path": str(pose)}],
                    available_node_types={"LoadImage", "ControlNetLoader", "ControlNetApplyAdvanced"},
                )

    def test_prompt_only_uses_core_compiler_with_enhanced_scene_profile(self) -> None:
        compilation = compile_prompt_to_comfyui_workflow(
            "one character",
            "blurry",
            {**self._profile(), "workflow_kind": "ipadapter_scene_preview"},
            checkpoint="model.safetensors",
            seed=7,
        )

        self.assertEqual("core_txt2img_prompt_only", compilation.workflow_kind)

    def test_single_character_layout_uses_nearly_full_canvas(self) -> None:
        ir = self._ir()
        ir["elements"] = ir["elements"][:1]
        ir["placements"] = ir["placements"][:1]
        ir["composition"]["left_to_right"] = ["tsaeytte"]

        compilation = compile_ir_to_comfyui_workflow(
            ir,
            self._profile(),
            checkpoint="model.safetensors",
            seed=1,
        )

        region = compilation.debug["layout_plan"]["regions"][0]
        self.assertGreaterEqual(region["w"], 0.85)
        self.assertGreaterEqual(region["h"], 0.9)

    def test_four_character_layout_separates_shared_lanes_and_depths(self) -> None:
        ir = self._ir()
        ir["placements"][1]["depth"] = "background"
        for index, (element_id, position, depth) in enumerate(
            (("kaeldor", "left", "foreground"), ("student", "left", "midground")),
            start=2,
        ):
            ir["elements"].append({
                "id": element_id,
                "display_name": element_id.title(),
                "element_type": "Character",
                "resolved_source_sections": {
                    "identity_preservation_core": "athletic young elf man with blond hair"
                },
            })
            ir["placements"].append({
                "scene_element_id": element_id,
                "position_within_cell": position,
                "depth": depth,
                "pose": {"summary": "walking", "expression": "calm"},
                "motion": {"state": "moving", "direction_screen": "toward camera"},
            })
        ir["composition"] = {
            "left_to_right": ["kaeldor", "student", "tsaeytte", "valindia"],
            "focal_point": "student",
        }

        compilation = compile_ir_to_comfyui_workflow(
            ir,
            self._profile(),
            checkpoint="model.safetensors",
            seed=1,
        )

        regions = compilation.debug["layout_plan"]["regions"]
        self.assertEqual(4, len(regions))
        self.assertEqual(4, len({(item["x"], item["y"]) for item in regions}))
        focal = next(item for item in regions if item["element_id"] == "student")
        self.assertTrue(focal["is_focal"])
        self.assertGreater(focal["conditioning_strength"], 1.08)
        self.assertLess(
            next(item for item in regions if item["depth"] == "background")["h"],
            next(item for item in regions if item["depth"] == "foreground")["h"],
        )

    def test_scene_prompts_resolve_gaze_and_remove_toward_camera_conflicts(self) -> None:
        ir = self._ir()
        ir["placements"][0]["pose"]["gaze_target_element_id"] = "valindia"
        ir["elements"][0]["resolved_source_sections"]["identity_preservation_core"] = (
            "petite adolescent elf girl with short black hair"
        )

        compilation = compile_ir_to_comfyui_workflow(
            ir,
            self._profile(),
            checkpoint="model.safetensors",
            negative_prompt_globals="front-facing body, EasyNegative",
            seed=1,
        )

        prompt = next(
            item["prompt"]
            for item in compilation.prompts["region_records"]
            if item["element_id"] == "tsaeytte"
        )
        self.assertIn("looking toward Valindia", prompt)
        self.assertIn("curious expression", prompt)
        self.assertNotIn("subject opposite", prompt)
        self.assertNotIn("adult elf woman", prompt)
        self.assertNotIn("front-facing body", compilation.prompts["negative"])
        self.assertNotIn("looking at viewer", compilation.prompts["negative"])
        self.assertIn("EasyNegative", compilation.prompts["negative"])

    def test_ipadapter_profile_fails_clearly_when_nodes_are_missing(self) -> None:
        profile = {**self._profile(), "workflow_kind": "ipadapter_scene_preview"}
        with self.assertRaisesRegex(LocalRenderError, "requires unavailable nodes"):
            compile_ir_to_comfyui_workflow(
                self._ir(),
                profile,
                checkpoint="model.safetensors",
                available_node_types=set(),
            )

    def test_ipadapter_profile_fails_clearly_when_references_are_missing(self) -> None:
        profile = {
            **self._profile(),
            "workflow_kind": "ipadapter_scene_preview",
            "ipadapter_model": "ipadapter.safetensors",
            "clip_vision_model": "clip.safetensors",
        }
        nodes = {"LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced"}
        with self.assertRaisesRegex(LocalRenderError, "requires at least one resolved reference"):
            compile_ir_to_comfyui_workflow(
                self._ir(),
                profile,
                checkpoint="model.safetensors",
                available_node_types=nodes,
            )

    def test_ipadapter_preset_uses_tuned_defaults(self) -> None:
        presets = json.loads(
            (Path(__file__).resolve().parents[1] / "Config" / "Local_Render_Presets.json").read_text(
                encoding="utf-8"
            )
        )
        profile = presets["comfyui-ipadapter-preview"]

        self.assertEqual(0.40, profile["character_reference_weight"])
        self.assertEqual(0.20, profile["backdrop_reference_weight"])
        self.assertEqual(0.75, profile["character_reference_end_at"])
        self.assertEqual(0.55, profile["backdrop_reference_end_at"])
        self.assertEqual("linear", profile["ipadapter_weight_type"])
        self.assertEqual("average", profile["ipadapter_combine_embeds"])
        self.assertEqual("V only", profile["ipadapter_embeds_scaling"])

    def test_ipadapter_profile_applies_configured_settings_and_modified_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.png"
            reference.write_bytes(b"png")
            backdrop = Path(temp_dir) / "backdrop.png"
            backdrop.write_bytes(b"png")
            ir = self._ir()
            ir["elements"].append({
                "id": "archway",
                "display_name": "Archway",
                "element_type": "Backdrop",
                "resolved_source_sections": {},
            })
            ir["references"] = [
                {"tag": "{{REF}}", "applies_to_element_id": "tsaeytte"},
                {"tag": "{{BACKDROP}}", "applies_to_element_id": "archway"},
            ]
            ir["resolved_sources"] = {
                "references": [
                    {"tag": "{{REF}}", "path": str(reference)},
                    {"tag": "{{BACKDROP}}", "path": str(backdrop)},
                ],
            }
            profile = {
                **self._profile(),
                "workflow_kind": "ipadapter_scene_preview",
                "ipadapter_model": "ipadapter.safetensors",
                "clip_vision_model": "clip.safetensors",
                "character_reference_weight": 0.31,
                "character_reference_end_at": 0.62,
                "backdrop_reference_weight": 0.17,
                "backdrop_reference_end_at": 0.48,
                "ipadapter_weight_type": "linear",
                "ipadapter_combine_embeds": "average",
                "ipadapter_embeds_scaling": "V only",
            }
            nodes = {"LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced"}
            compilation = compile_ir_to_comfyui_workflow(
                ir,
                profile,
                checkpoint="model.safetensors",
                available_node_types=nodes,
            )

        reference_record = compilation.debug["references_used"][0]
        self.assertRegex(reference_record["comfyui_input_name"], r"^Zet/[0-9a-f]{12}/reference\.png$")
        load_image = next(
            node for node in compilation.workflow.values() if node["class_type"] == "LoadImage"
        )
        self.assertEqual(reference_record["comfyui_input_name"], load_image["inputs"]["image"])
        adapters = [
            (node_id, node)
            for node_id, node in compilation.workflow.items()
            if node["class_type"] == "IPAdapterAdvanced"
        ]
        self.assertEqual(2, len(adapters))
        adapter_id, adapter = adapters[0]
        self.assertEqual(0.31, adapter["inputs"]["weight"])
        self.assertEqual(0.0, adapter["inputs"]["start_at"])
        self.assertEqual(0.62, adapter["inputs"]["end_at"])
        self.assertEqual("linear", adapter["inputs"]["weight_type"])
        self.assertEqual("average", adapter["inputs"]["combine_embeds"])
        self.assertEqual("V only", adapter["inputs"]["embeds_scaling"])
        backdrop_adapter_id, backdrop_adapter = adapters[1]
        self.assertEqual([adapter_id, 0], backdrop_adapter["inputs"]["model"])
        self.assertEqual(0.17, backdrop_adapter["inputs"]["weight"])
        self.assertEqual(0.48, backdrop_adapter["inputs"]["end_at"])
        sampler = next(
            node for node in compilation.workflow.values() if node["class_type"] == "KSampler"
        )
        self.assertEqual([backdrop_adapter_id, 0], sampler["inputs"]["model"])
        self.assertEqual(
            {
                "reference_element_id": "tsaeytte",
                "staged_reference_file": reference_record["comfyui_input_name"],
                "weight": 0.31,
                "start_at": 0.0,
                "end_at": 0.62,
                "weight_type": "linear",
                "combine_embeds": "average",
                "embeds_scaling": "V only",
            },
            compilation.debug["ipadapter_applications"][0],
        )
        self.assertEqual("archway", compilation.debug["ipadapter_applications"][1]["reference_element_id"])
        self.assertEqual(0.17, compilation.debug["ipadapter_applications"][1]["weight"])
        self.assertEqual(0.48, compilation.debug["ipadapter_applications"][1]["end_at"])

    def test_default_negative_prompt_omits_generic_view_direction_terms(self) -> None:
        ir = self._ir()
        for placement in ir["placements"]:
            placement["motion"]["direction_screen"] = ""
        compilation = compile_ir_to_comfyui_workflow(
            ir,
            self._profile(),
            checkpoint="model.safetensors",
        )

        self.assertNotIn("front-facing body", compilation.prompts["negative"])
        self.assertNotIn("looking at viewer", compilation.prompts["negative"])

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
            patch("zet.services.comfyui_render_service._request_bytes", return_value=png_bytes()),
            patch("zet.services.comfyui_render_service._upload_comfyui_input") as upload,
        ):
            reference_files = [{"path": "reference.png", "comfyui_input_name": "Zet/hash/reference.png"}]
            result = run_comfyui_workflow(
                {"1": {"class_type": "Test", "inputs": {}}},
                server_url="http://127.0.0.1:8188",
                output_dir=Path(temp_dir),
                reference_files=reference_files,
                poll_seconds=0,
                timeout_seconds=1,
            )

            upload.assert_called_once_with("http://127.0.0.1:8188", reference_files[0])
            self.assertEqual("prompt-1", result.prompt_id)
            self.assertEqual(Path(temp_dir), result.image_paths[0].parent)
            self.assertTrue(result.image_paths[0].name.endswith("_1_unsafe.png"))
            self.assertEqual(png_bytes(), result.image_paths[0].read_bytes())

    def test_upload_stages_reference_in_requested_subfolder(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "name": "reference.png",
            "subfolder": "Zet/hash",
            "type": "input",
        }).encode()
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "reference.png"
            source.write_bytes(b"png-data")
            with patch("zet.services.comfyui_render_service.urlopen", return_value=response) as request:
                _upload_comfyui_input(
                    "http://127.0.0.1:8188",
                    {"path": str(source), "comfyui_input_name": "Zet/hash/reference.png"},
                )

        uploaded_request = request.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8188/upload/image", uploaded_request.full_url)
        self.assertIn(b'name="subfolder"\r\n\r\nZet/hash', uploaded_request.data)
        self.assertIn(b'filename="reference.png"', uploaded_request.data)
        self.assertIn(b"png-data", uploaded_request.data)

    def test_proxy_adapter_passes_compiled_references_to_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Config").mkdir()
            (root / "Config" / "Local_Render_Presets.json").write_text(json.dumps({
                "comfyui-ipadapter-preview": {
                    **self._profile(),
                    "workflow_kind": "ipadapter_scene_preview",
                    "ipadapter_model": "ipadapter.safetensors",
                    "clip_vision_model": "clip.safetensors",
                    "character_reference_weight": 0.37,
                    "character_reference_end_at": 0.66,
                    "ipadapter_weight_type": "linear",
                    "ipadapter_combine_embeds": "average",
                    "ipadapter_embeds_scaling": "V only",
                },
            }), encoding="utf-8")
            (root / "config.toml").write_text(
                '[ComfyUI]\nCheckpoint = "model.safetensors"\n',
                encoding="utf-8",
            )
            reference = root / "reference.png"
            reference.write_bytes(b"png")
            ir = self._ir()
            ir["references"] = [{"tag": "{{REF}}", "applies_to_element_id": "tsaeytte"}]
            ir["resolved_sources"] = {
                "references": [{"tag": "{{REF}}", "path": str(reference)}],
            }
            ir_path = root / "Scene_Render_IR.json"
            ir_path.write_text(json.dumps(ir), encoding="utf-8")
            prompt_path = root / "prompt.md"
            prompt_path.write_text("prompt", encoding="utf-8")
            output_image = root / "output.png"
            output_image.write_bytes(b"png")
            run_result = ComfyUIRunResult("prompt-1", [output_image], {}, {})
            nodes = {"LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced"}
            with (
                patch(
                    "Scripts.Local_Render_Adapters.comfyui_adapter.list_comfyui_node_types",
                    return_value=nodes,
                ),
                patch(
                    "Scripts.Local_Render_Adapters.comfyui_adapter.run_comfyui_workflow",
                    return_value=run_result,
                ) as run,
            ):
                result = render_preview(
                    project_root=root,
                    final_prompt_path=prompt_path,
                    job_output_dir=root / "job",
                    profile_name="comfyui-ipadapter-preview",
                    scene_render_ir_path=ir_path,
                )
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(
                {
                    "reference_element_id": "tsaeytte",
                    "staged_reference_file": run.call_args.kwargs["reference_files"][0]["comfyui_input_name"],
                    "weight": 0.37,
                    "start_at": 0.0,
                    "end_at": 0.66,
                    "weight_type": "linear",
                    "combine_embeds": "average",
                    "embeds_scaling": "V only",
                },
                metadata["ipadapter_applications"][0],
            )

        references = run.call_args.kwargs["reference_files"]
        self.assertEqual(str(reference), references[0]["path"])
        self.assertRegex(references[0]["comfyui_input_name"], r"^Zet/[0-9a-f]{12}/reference\.png$")

    def test_proxy_adapter_applies_single_character_render_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Config").mkdir()
            profile = json.loads(
                (Path(__file__).resolve().parents[1] / "Config" / "Local_Render_Presets.json").read_text(
                    encoding="utf-8"
                )
            )["image-recipe-lab-ipadapter-controlnet-sdxl"]
            (root / "Config" / "Local_Render_Presets.json").write_text(json.dumps({"lab": profile}), encoding="utf-8")
            (root / "config.toml").write_text('[ComfyUI]\nCheckpoint = "model.safetensors"\n', encoding="utf-8")
            prompt = root / "Prompt.md"
            prompt.write_text("Prompt: full body\nNegative: cropped\n", encoding="utf-8")
            appearance = root / "appearance.png"
            pose = root / "pose.png"
            appearance.write_bytes(b"appearance")
            pose.write_bytes(b"pose")
            output = root / "output.png"
            output.write_bytes(b"output")
            nodes = {
                "LoadImage", "CLIPVisionLoader", "IPAdapterModelLoader", "IPAdapterAdvanced",
                "DWPreprocessor", "ControlNetLoader", "ControlNetApplyAdvanced",
            }
            with (
                patch("Scripts.Local_Render_Adapters.comfyui_adapter.list_comfyui_node_types", return_value=nodes),
                patch(
                    "Scripts.Local_Render_Adapters.comfyui_adapter.run_comfyui_workflow",
                    return_value=ComfyUIRunResult("prompt-1", [output], {}, {}),
                ) as run,
            ):
                render_preview(
                    project_root=root,
                    final_prompt_path=prompt,
                    job_output_dir=root / "job",
                    profile_name="lab",
                    reference_files=[
                        {"role": "prompt_evolution_appearance", "path": str(appearance)},
                        {"role": "prompt_evolution_pose", "path": str(pose)},
                    ],
                    render_overrides={"width": 900, "height": 1300, "character_reference_weight": 0.45},
                )

            workflow = run.call_args.args[0]
            latent = next(node for node in workflow.values() if node["class_type"] == "EmptyLatentImage")
            adapter = next(node for node in workflow.values() if node["class_type"] == "IPAdapterAdvanced")
            self.assertEqual((896, 1296), (latent["inputs"]["width"], latent["inputs"]["height"]))
            self.assertEqual(0.45, adapter["inputs"]["weight"])

    def test_run_reports_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "zet.services.comfyui_render_service._request_json",
            return_value={"node_errors": {"1": "bad checkpoint"}},
        ):
            with self.assertRaisesRegex(LocalRenderError, "validation failed"):
                run_comfyui_workflow(
                    {},
                    server_url="http://127.0.0.1:8188",
                    output_dir=Path(temp_dir),
                )

    def test_modern_reference_adapters_compile_native_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            appearance, pose = root / "appearance.png", root / "pose.png"
            appearance.write_bytes(b"appearance")
            pose.write_bytes(b"pose")
            references = [
                {"role": "prompt_evolution_appearance", "path": str(appearance)},
                {"role": "prompt_evolution_pose", "path": str(pose)},
            ]
            common_nodes = {
                "UNETLoader", "CLIPLoader", "VAELoader", "LoadImage", "KSampler", "VAEDecode", "SaveImage",
            }
            flux = compile_prompt_to_comfyui_workflow(
                "character", "bad anatomy",
                {"prompt_workflow_kind": "flux2_reference_prompt_only", "width": 832, "height": 1216,
                 "text_encoder": "qwen_3_4b.safetensors", "vae": "flux2-vae.safetensors", "cfg": 3.5},
                checkpoint="flux2-klein-4b.safetensors", seed=11, reference_files=references,
                available_node_types=common_nodes | {
                    "ReferenceLatent", "EmptyFlux2LatentImage", "CLIPTextEncode", "VAEEncode", "FluxGuidance",
                },
            )
            qwen = compile_prompt_to_comfyui_workflow(
                "character", "bad anatomy",
                {"prompt_workflow_kind": "qwen_image_edit_prompt_only", "width": 832, "height": 1216,
                 "text_encoder": "qwen_2.5_vl.safetensors", "vae": "qwen_image_vae.safetensors", "cfg": 1},
                checkpoint="qwen_image_edit_2511.safetensors", seed=12, reference_files=references,
                available_node_types=common_nodes | {"TextEncodeQwenImageEditPlus", "EmptySD3LatentImage"},
            )

        self.assertEqual("flux2_reference_prompt_only", flux.workflow_kind)
        self.assertEqual(2, sum(node["class_type"] == "ReferenceLatent" for node in flux.workflow.values()))
        self.assertEqual("qwen_image_edit_prompt_only", qwen.workflow_kind)
        qwen_encode = next(node for node in qwen.workflow.values() if node["class_type"] == "TextEncodeQwenImageEditPlus" and "image1" in node["inputs"])
        self.assertIn("image2", qwen_encode["inputs"])

    def test_qwen_21_scene_uses_all_references_and_independent_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ir = self._ir()
            ir["render_mode"] = "composite"
            ir["dialogue"] = [{"speaker_element_id": "tsaeytte", "text": "Come with me"}]
            ir["image_inputs"] = []
            for index in range(1, 6):
                source = Path(temp_dir) / f"ref{index}.png"
                source.write_bytes(b"reference")
                ir["image_inputs"].append({"index": index, "role": "subject_reference", "path": str(source),
                                           "label": f"Character {index}", "applies_to": f"Character {index}",
                                           "preserve": ["identity"]})
            profile = {"workflow_kind": "qwen_image_21_scene_preview", "pixel_budget": 1048576,
                       "text_encoder": "qwen3vl_8b_int8_convrot.safetensors",
                       "vae": "qwen_image_2.1_vae_bf16.safetensors", "steps": 40}
            nodes = {"UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21",
                     "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage", "LoadImage"}
            compilation = compile_ir_to_comfyui_workflow(ir, profile, checkpoint="qwen_image_2.1_int8_convrot.safetensors",
                                                         seed=7, available_node_types=nodes)
            workflow = compilation.workflow
            self.assertEqual(5, len(compilation.debug["references_used"]))
            self.assertEqual(["<image1>", "<image2>", "<image3>", "<image4>", "<image5>"],
                             [f"<image{i}>" for i in range(1, 6) if f"<image{i}>" in compilation.prompts["global"]])
            self.assertIn('"Come with me"', compilation.prompts["global"])
            self.assertEqual((1376, 768), (compilation.width, compilation.height))
            self.assertEqual(["5", 0], workflow["6"]["inputs"]["latent_image"])
            self.assertEqual(5, sum(node["class_type"] == "LoadImage" for node in workflow.values()))
            self.assertEqual("", workflow["4"]["inputs"]["negative_prompt"])
            self.assertEqual(1.0, workflow["6"]["inputs"]["cfg"])
            manual_refs = [{"image_index": index, "path": ir["image_inputs"][index - 1]["path"]}
                           for index in range(5, 0, -1)]
            ordered = compile_ir_to_comfyui_workflow(
                ir, profile, checkpoint="qwen_image_2.1_int8_convrot.safetensors", seed=7,
                available_node_types=nodes, reference_files=manual_refs)
            self.assertEqual([1, 2, 3, 4, 5],
                             [item["image_index"] for item in ordered.debug["references_used"]])
            with self.assertRaisesRegex(LocalRenderError, "do not match the scene IR image slots"):
                compile_ir_to_comfyui_workflow(
                    ir, profile, checkpoint="qwen_image_2.1_int8_convrot.safetensors", seed=7,
                    available_node_types=nodes, reference_files=manual_refs[:-1])
            self.assertEqual("A revised scene.", compile_ir_to_comfyui_workflow(
                ir, profile, checkpoint="qwen_image_2.1_int8_convrot.safetensors", seed=7,
                available_node_types=nodes, scene_prompt_override="A revised scene.").prompts["global"])
            ir["image_inputs"][2]["path"] = str(Path(temp_dir) / "missing.png")
            with self.assertRaisesRegex(LocalRenderError, "reference 3 is missing"):
                compile_ir_to_comfyui_workflow(ir, profile, checkpoint="qwen_image_2.1_int8_convrot.safetensors",
                                              seed=7, available_node_types=nodes)
            ir["image_inputs"] = ir["image_inputs"] * 3
            with self.assertRaisesRegex(LocalRenderError, "at most ten"):
                compile_ir_to_comfyui_workflow(ir, profile, checkpoint="qwen_image_2.1_int8_convrot.safetensors",
                                              seed=7, available_node_types=nodes)

    def test_run_reports_execution_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
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
                    output_dir=Path(temp_dir),
                    poll_seconds=0,
                    timeout_seconds=1,
                )

    def test_run_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "zet.services.comfyui_render_service._request_json",
            return_value={"prompt_id": "prompt-1"},
        ):
            with self.assertRaisesRegex(LocalRenderError, "timed out"):
                run_comfyui_workflow(
                    {},
                    server_url="http://127.0.0.1:8188",
                    output_dir=Path(temp_dir),
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

    def test_qwen_model_discovery_reads_diffusion_loader_choices(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "UNETLoader": {"input": {"required": {"unet_name": [["qwen_image_2.1_int8_convrot.safetensors"]]}}}
        }).encode()
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_path = Path(temp_dir) / "profiles.json"
            profiles_path.write_text(
                json.dumps({"comfyui-qwen-image-2-1-scene": {"backend": "comfyui", "model_family": "qwen-image-2.1"}}),
                encoding="utf-8",
            )
            with patch("zet.services.local_render_backend_service.urlopen", return_value=response) as request:
                models = LocalRenderBackendService(profiles_path).list_checkpoints(
                    "comfyui-qwen-image-2-1-scene", backend="comfyui", server_url="http://127.0.0.1:8188",
                )

        self.assertEqual(["qwen_image_2.1_int8_convrot.safetensors"], [item["title"] for item in models])
        self.assertEqual("http://127.0.0.1:8188/object_info/UNETLoader", request.call_args.args[0].full_url)

    def test_comfyui_options_discovers_controlnet_and_sampler_choices(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["model.safetensors"]]}}},
            "ControlNetLoader": {"input": {"required": {"control_net_name": [["pose.safetensors"]]}}},
            "KSampler": {"input": {"required": {
                "sampler_name": [["dpmpp_2m"]], "scheduler": [["karras"]],
            }}},
            "UNETLoader": {"input": {"required": {"unet_name": [["flux2-klein-4b.safetensors"]]}}},
            "CLIPLoader": {"input": {"required": {"clip_name": [["qwen_3_4b.safetensors"]]}}},
            "VAELoader": {"input": {"required": {"vae_name": [["flux2-vae.safetensors"]]}}},
            "DWPreprocessor": {"input": {"required": {}}},
        }).encode()
        with patch("zet.services.local_render_backend_service.urlopen", return_value=response):
            options = LocalRenderBackendService("missing.json").comfyui_options("http://127.0.0.1:8188")

        self.assertEqual(["pose.safetensors"], options["controlnet_models"])
        self.assertEqual(["dpmpp_2m"], options["samplers"])
        self.assertEqual(["flux2-klein-4b.safetensors"], options["diffusion_models"])
        self.assertEqual(["qwen_3_4b.safetensors"], options["text_encoders"])
        self.assertEqual(["flux2-vae.safetensors"], options["vaes"])
        self.assertIn("DWPreprocessor", options["node_types"])

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
            debug = json.loads((root / "ComfyUI_Compilation_Debug.json").read_text(encoding="utf-8"))
            pose = json.loads((root / "ComfyUI_Pose_Layout_Control.json").read_text(encoding="utf-8"))
            self.assertEqual("core_txt2img_scene_preview", debug["workflow_kind"])
            self.assertEqual(42, debug["seed"])
            self.assertEqual("scene_layout_control", pose["kind"])


if __name__ == "__main__":
    unittest.main()
