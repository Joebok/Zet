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

[RenderConsole]
Host = "0.0.0.0"
Port = 8090
RequireToken = true
Token = "test-token"
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
            self.assertEqual(config.render_console_host, "0.0.0.0")
            self.assertEqual(config.render_console_port, 8090)
            self.assertTrue(config.render_console_require_token)
            self.assertEqual(config.render_console_token, "test-token")


if __name__ == "__main__":
    unittest.main()
