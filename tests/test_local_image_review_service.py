from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import call, patch

from zet.services.local_image_review_service import LocalImageReviewService


class LocalImageReviewServiceTests(unittest.TestCase):
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
