from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import call, patch

from zet.services.local_image_review_service import LocalImageReviewService


class LocalImageReviewServiceTests(unittest.TestCase):
    def test_list_images_includes_qwen_prompt_and_model_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            render_dir = Path(temp_dir) / "Local_Test_Renders"
            render_dir.mkdir()
            (render_dir / "scene.png").write_bytes(b"png")
            (render_dir / "scene.json").write_text(json.dumps({
                "prompt": "A new scene using <image1> as reference.",
                "render_profile": "comfyui-qwen-image-2-1-scene",
                "checkpoint": "qwen_image_2.1_int8_convrot.safetensors",
                "image_generation": "comfyui",
            }), encoding="utf-8")
            task = SimpleNamespace(asset_id=None, manifest={"pipeline_path": temp_dir})

            images = LocalImageReviewService(SimpleNamespace()).list_images(task)

        self.assertEqual(1, len(images))
        self.assertIn("<image1>", images[0]["prompt"])
        self.assertEqual("qwen_image_2.1_int8_convrot.safetensors", images[0]["checkpoint"])

    def test_queue_images_for_all_checkpoints_refreshes_and_queues_each_model(self) -> None:
        app = SimpleNamespace(
            config=SimpleNamespace(
                local_render_backend="comfyui",
                comfyui_profile="portrait",
                comfyui_server_url="http://comfy.test",
            ),
            config_path=Path("config.toml"),
        )
        service = LocalImageReviewService(app)
        task = object()
        with (
            patch(
                "zet.services.local_image_review_service.LocalRenderBackendService.list_checkpoints",
                return_value=[{"title": "one.safetensors"}, {"title": "two.safetensors"}],
            ) as list_checkpoints,
            patch.object(
                service,
                "queue_images",
                side_effect=[
                    [{"ask_path": "one-1", "seed": 1}, {"ask_path": "one-2", "seed": 2}],
                    [{"ask_path": "two-1", "seed": 3}, {"ask_path": "two-2", "seed": 4}],
                ],
            ) as queue_images,
        ):
            queued, checkpoint_count = service.queue_images_for_all_checkpoints(task, 2)

        list_checkpoints.assert_called_once_with(
            "portrait",
            backend="comfyui",
            server_url="http://comfy.test",
        )
        self.assertEqual(
            [call(task, 2, checkpoint="one.safetensors"), call(task, 2, checkpoint="two.safetensors")],
            queue_images.call_args_list,
        )
        self.assertEqual(2, checkpoint_count)
        self.assertEqual(
            ["one.safetensors", "one.safetensors", "two.safetensors", "two.safetensors"],
            [item["checkpoint"] for item in queued],
        )


if __name__ == "__main__":
    unittest.main()
