import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zet.services.config_service import ConfigService


class ConfigServiceTests(unittest.TestCase):
    def test_platform_override_applies_only_matching_platform(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """
[BaseFolders]
BaseCharacterPath = "_Lib/Characters/"
BaseAssetPath = "_Lib/Assets/"
BasePipelinePath = "_Lib/Pipelines/"
BaseAIQueuePath = "_Lib/AI_Queue/"

[BaseFoldersByPlatform.Windows]
BaseAIQueuePath = "C:/Users/Joe/Library/CloudStorage/Dropbox/AI_Queue/"

[BaseFoldersByPlatform.Darwin]
BaseAIQueuePath = "/Users/joe/Library/CloudStorage/Dropbox/AI_Queue/"

[AIHarvest]
AutoEnabled = true
IntervalSeconds = 300

[Render]
Backend = "manual_chatgpt"
""".lstrip(),
                encoding="utf-8",
            )

            with patch.object(ConfigService, "_platform_name", return_value="Darwin"):
                config = ConfigService.load(config_path)

            self.assertEqual(config.base_ai_queue_path, "/Users/joe/Library/CloudStorage/Dropbox/AI_Queue/")
            self.assertEqual(config.base_character_path, "_Lib/Characters/")
            self.assertTrue(config.ai_harvest_auto_enabled)
            self.assertEqual(config.ai_harvest_interval_seconds, 300)
            self.assertEqual(config.render_backend, "manual_chatgpt")
            self.assertEqual(config.local_render_layout_backend, "forge_couple_basic")
            self.assertEqual(config.zine_print_scale, 0.978)
            self.assertEqual(config.zine_page_margin, 4)

    def test_backend_specific_render_config_is_independent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """
[BaseFolders]
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "Queue"

[LocalRender]
Backend = "comfyui"

[StableMatrix]
Profile = "scene-preview-sd15"
Checkpoint = "stable.safetensors"
PositivePromptGlobals = "stable positive"
NegativePromptGlobals = "stable negative"

[ComfyUI]
Profile = "comfyui-core-preview"
ServerURL = "http://127.0.0.1:8188"
Checkpoint = "comfy.safetensors"
PositivePromptGlobals = "comfy positive"
NegativePromptGlobals = "comfy negative"
PollSeconds = 0.5
TimeoutSeconds = 120
""".lstrip(),
                encoding="utf-8",
            )

            config = ConfigService.load(config_path)

            self.assertEqual("comfyui", config.local_render_backend)
            self.assertEqual("stable.safetensors", config.local_render_checkpoint)
            self.assertEqual("stable positive", config.local_render_positive_prompt_globals)
            self.assertEqual("comfy.safetensors", config.comfyui_checkpoint)
            self.assertEqual("comfy positive", config.comfyui_positive_prompt_globals)
            self.assertEqual(0.5, config.comfyui_poll_seconds)
            self.assertEqual(120, config.comfyui_timeout_seconds)


if __name__ == "__main__":
    unittest.main()
