from pathlib import Path
from io import BytesIO
import sys
import tempfile
import unittest

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from Local_Render_Adapters.stable_matrix_adapter import _render_size_for_references, _reference_image_bytes, load_local_image_gen_overrides


class StableMatrixAdapterTests(unittest.TestCase):
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
                "prompt: exact prompt\n"
                "negative_prompt: exact negative\n"
                "steps:\n"
                "cfg_scale: 8.5\n"
                "sd_model_checkpoint: sd/model.safetensors\n"
                "restore_faces: true\n"
                "<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->\n",
                encoding="utf-8",
            )

            self.assertEqual(
                {
                    "prompt": "exact prompt",
                    "negative_prompt": "exact negative",
                    "cfg_scale": "8.5",
                    "sd_model_checkpoint": "sd/model.safetensors",
                    "restore_faces": "true",
                },
                load_local_image_gen_overrides(path),
            )


if __name__ == "__main__":
    unittest.main()
