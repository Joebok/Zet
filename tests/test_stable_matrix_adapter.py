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

from Local_Render_Adapters.common import LocalRenderError
from Local_Render_Adapters.stable_matrix_adapter import _render_size_for_references, _reference_image_bytes, ensure_prompt_terms, render_preview


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

    def test_render_with_references_still_uses_txt2img(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "prompt.md"
            prompt.write_text("Positive prompt", encoding="utf-8")
            reference = root / "reference.png"
            Image.new("RGB", (300, 600), "white").save(reference)
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
                    reference_files=[{"path": str(reference)}],
                )

            payload = post_json.call_args.args[2]
            self.assertNotIn("init_images", payload)
            api_call = json.loads((root / "Stable_Matrix_API_Call.json").read_text(encoding="utf-8"))
            self.assertEqual("/sdapi/v1/txt2img", api_call["api_path"])
            self.assertNotIn("reference_count", api_call)
            self.assertEqual(512, payload["width"])
            self.assertEqual(768, payload["height"])







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



    def test_forge_couple_advanced_layout_sends_mappings_and_debug_base_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt = root / "Local_Render_Prompt.md"
            prompt.write_text("prompt: flat prompt\nnegative: bad\n", encoding="utf-8")
            image = BytesIO()
            Image.new("RGB", (1, 1), "white").save(image, format="PNG")
            mappings = [
                [0.0, 1.0, 0.0, 1.0, 0.65],
                [0.04, 0.47, 0.20, 0.98, 1.0],
                [0.53, 0.96, 0.20, 0.98, 1.08],
            ]
            layout = {
                "backend": "forge_couple_basic", "subject_count": 2,
                "prompt_lines": ["global", "Valindia", "Tsaeytte"],
                "mode": "Advanced", "disable_hr": True, "mappings": mappings,
            }
            with (
                patch("Local_Render_Adapters.stable_matrix_adapter.load_preset", return_value={"backend": "stable_matrix", "aspect_ratio": "4:5"}),
                patch("Local_Render_Adapters.stable_matrix_adapter._get_json", return_value={"txt2img": ["forge couple"]}),
                patch("Local_Render_Adapters.stable_matrix_adapter._post_json", return_value={"images": [__import__("base64").b64encode(image.getvalue()).decode()]}) as post_json,
            ):
                render_preview(project_root=root, final_prompt_path=prompt, job_output_dir=root, render_layout=layout)

            payload = post_json.call_args.args[2]
            self.assertEqual((640, 800, False), (payload["width"], payload["height"], payload["enable_hr"]))
            self.assertNotIn("denoising_strength", payload)
            self.assertEqual(
                [True, True, "Advanced", "", None, None, None, mappings, "{ }", False, True, None, None, None, None, None, None],
                payload["alwayson_scripts"]["forge couple"]["args"],
            )


if __name__ == "__main__":
    unittest.main()
