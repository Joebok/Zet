from pathlib import Path
from io import BytesIO
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from Local_Render_Adapters.stable_matrix_adapter import _render_size_for_references, _reference_image_bytes, ensure_prompt_terms, load_local_image_gen_overrides, render_preview


class StableMatrixAdapterTests(unittest.TestCase):
    def test_render_without_references_omits_init_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.md"
            prompt.write_text("Positive prompt", encoding="utf-8")
            image = BytesIO()
            Image.new("RGB", (1, 1), "white").save(image, format="PNG")

            with (
                patch("Local_Render_Adapters.stable_matrix_adapter.load_preset", return_value={"backend": "stable_matrix"}),
                patch(
                    "Local_Render_Adapters.stable_matrix_adapter._post_json",
                    return_value={"images": [__import__("base64").b64encode(image.getvalue()).decode()]},
                ) as post_json,
            ):
                render_preview(project_root=root, final_prompt_path=prompt, job_output_dir=root)

            self.assertNotIn("init_images", post_json.call_args.args[2])
            api_call = json.loads((root / "Stable_Matrix_API_Call.json").read_text(encoding="utf-8"))
            self.assertEqual("/sdapi/v1/txt2img", api_call["api_path"])
            self.assertNotIn("reference_count", api_call)
            self.assertNotIn("init_images", api_call["payload"])
            self.assertEqual(512, api_call["payload"]["width"])
            self.assertEqual(768, api_call["payload"]["height"])

    def test_render_with_references_still_uses_txt2img_and_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.md"
            prompt.write_text("Positive prompt", encoding="utf-8")
            reference = root / "reference.png"
            Image.new("RGB", (300, 600), "white").save(reference)
            template = root / "template.md"
            template.write_text(
                "<!-- ZET:BEGIN LOCAL_IMAGE_GEN_OVERRIDES -->\n"
                'orientation = "landscape"\n'
                "<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->\n",
                encoding="utf-8",
            )
            image = BytesIO()
            Image.new("RGB", (1, 1), "white").save(image, format="PNG")

            with (
                patch("Local_Render_Adapters.stable_matrix_adapter.load_preset", return_value={"backend": "stable_matrix"}),
                patch(
                    "Local_Render_Adapters.stable_matrix_adapter._post_json",
                    return_value={"images": [__import__("base64").b64encode(image.getvalue()).decode()]},
                ) as post_json,
            ):
                render_preview(
                    project_root=root,
                    final_prompt_path=prompt,
                    job_output_dir=root,
                    governing_template_path=template,
                    reference_files=[{"path": str(reference)}],
                )

            payload = post_json.call_args.args[2]
            self.assertNotIn("init_images", payload)
            api_call = json.loads((root / "Stable_Matrix_API_Call.json").read_text(encoding="utf-8"))
            self.assertEqual("/sdapi/v1/txt2img", api_call["api_path"])
            self.assertNotIn("reference_count", api_call)
            self.assertEqual(768, payload["width"])
            self.assertEqual(512, payload["height"])

    def test_render_size_uses_first_reference_aspect_with_512_short_side(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.png"
            Image.new("RGB", (300, 600), "white").save(first)

            self.assertEqual((512, 1024), _render_size_for_references([{"path": str(first)}], root, 512, 512))

    def test_reference_image_bytes_scales_into_render_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "wide.png"
            Image.new("RGB", (2000, 1000), "white").save(path)

            mime, image_bytes = _reference_image_bytes(path, 512, 1024)

            self.assertEqual("image/png", mime)
            with Image.open(BytesIO(image_bytes)) as image:
                self.assertEqual((512, 256), image.size)

    def test_load_local_image_gen_overrides_ignores_blank_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "template.md"
            path.write_text(
                "<!-- ZET:BEGIN LOCAL_IMAGE_GEN_OVERRIDES -->\n"
                'prompt = "exact prompt"\n'
                'negative_prompt = "exact negative"\n'
                'cfg_scale = 8.5\n'
                'orientation = "square"\n'
                'sd_model_checkpoint = "sd/model.safetensors"\n'
                'restore_faces = true\n'
                "<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->\n",
                encoding="utf-8",
            )

            self.assertEqual(
                {
                    "prompt": "exact prompt",
                    "negative_prompt": "exact negative",
                    "cfg_scale": 8.5,
                    "orientation": "square",
                    "sd_model_checkpoint": "sd/model.safetensors",
                    "restore_faces": True,
                },
                load_local_image_gen_overrides(path),
            )

    def test_load_local_image_gen_overrides_accepts_legacy_colon_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "template.md"
            path.write_text(
                "<!-- ZET:BEGIN LOCAL_IMAGE_GEN_OVERRIDES -->\n"
                "prompt:\n"
                "negative_prompt:denoising_strength:\n"
                "enable_hr: false\n"
                "orientation: landscape\n"
                "<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->\n",
                encoding="utf-8",
            )

            self.assertEqual(
                {"enable_hr": False, "orientation": "landscape"},
                load_local_image_gen_overrides(path),
            )

    def test_ensure_prompt_terms_appends_missing_terms(self) -> None:
        self.assertEqual(
            "portrait, sharp, painterly",
            ensure_prompt_terms("portrait, sharp", "sharp, painterly"),
        )

    def test_render_applies_globals_after_template_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config.toml").write_text(
                "[LocalRender]\nPositivePromptGlobals = \"masterpiece\"\nNegativePromptGlobals = \"blurry\"\n",
                encoding="utf-8",
            )
            template = root / "template.md"
            template.write_text(
                "<!-- ZET:BEGIN LOCAL_IMAGE_GEN_OVERRIDES -->\n"
                'prompt = "exact prompt"\n'
                'negative_prompt = "exact negative"\n'
                "<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->\n",
                encoding="utf-8",
            )
            prompt = root / "prompt.md"
            prompt.write_text("ignored", encoding="utf-8")
            image = BytesIO()
            Image.new("RGB", (1, 1), "white").save(image, format="PNG")

            with (
                patch("Local_Render_Adapters.stable_matrix_adapter.load_preset", return_value={"backend": "stable_matrix"}),
                patch(
                    "Local_Render_Adapters.stable_matrix_adapter._post_json",
                    return_value={"images": [__import__("base64").b64encode(image.getvalue()).decode()]},
                ) as post_json,
            ):
                render_preview(project_root=root, final_prompt_path=prompt, job_output_dir=root, governing_template_path=template)

            payload = post_json.call_args.args[2]
            self.assertEqual("exact prompt, masterpiece", payload["prompt"])
            self.assertEqual("exact negative, blurry", payload["negative_prompt"])

    def test_scene_preset_aspect_ratio_controls_payload_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.md"
            prompt.write_text("Positive prompt", encoding="utf-8")
            image = BytesIO()
            Image.new("RGB", (1, 1), "white").save(image, format="PNG")

            with (
                patch("Local_Render_Adapters.stable_matrix_adapter.load_preset", return_value={"backend": "stable_matrix", "aspect_ratio": "16:9"}),
                patch(
                    "Local_Render_Adapters.stable_matrix_adapter._post_json",
                    return_value={"images": [__import__("base64").b64encode(image.getvalue()).decode()]},
                ) as post_json,
            ):
                render_preview(project_root=root, final_prompt_path=prompt, job_output_dir=root, preset_name="scene-preview-sd15")

            payload = post_json.call_args.args[2]
            self.assertEqual((896, 512), (payload["width"], payload["height"]))

    def test_scene_aspect_ratio_argument_overrides_preset_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.md"
            prompt.write_text("Positive prompt", encoding="utf-8")
            image = BytesIO()
            Image.new("RGB", (1, 1), "white").save(image, format="PNG")

            with (
                patch("Local_Render_Adapters.stable_matrix_adapter.load_preset", return_value={"backend": "stable_matrix", "aspect_ratio": "4:5"}),
                patch(
                    "Local_Render_Adapters.stable_matrix_adapter._post_json",
                    return_value={"images": [__import__("base64").b64encode(image.getvalue()).decode()]},
                ) as post_json,
            ):
                render_preview(project_root=root, final_prompt_path=prompt, job_output_dir=root, aspect_ratio="16:9")

            payload = post_json.call_args.args[2]
            self.assertEqual((896, 512), (payload["width"], payload["height"]))


if __name__ == "__main__":
    unittest.main()
