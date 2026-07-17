import json
import tempfile
import unittest
from pathlib import Path

from zet.app import ZetApp
from zet.services.pipeline_control_service import AutomationSettings


class PipelineControlServiceTests(unittest.TestCase):
    def test_save_automation_settings_updates_safe_config_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character_dir = root / "Characters" / "Test" / "Adult"
            character_dir.mkdir(parents=True)
            (root / "Assets").mkdir()
            (root / "Pipelines").mkdir()
            (root / "Queue").mkdir()
            (character_dir / "Assets.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "asset_id": 1,
                                "character": "Test",
                                "phase": "Adult",
                                "pipeline": "Body-Reference",
                                "body_view": "Front",
                                "head_view": None,
                                "costume": None,
                                "expression": None,
                                "asset_state": "IN_PROGRESS",
                                "pipeline_stage": "PROMPT",
                                "actor": "PYTHON",
                                "ai_state": None,
                                "final_image_output": "out.png",
                                "last_ai_update": None,
                                "error_code": None,
                                "error_message": None,
                                "updated_at": None,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (character_dir / "Pipelines.json").write_text(
                json.dumps(
                    {
                        "pipelines": {
                            "Body-Reference": {
                                "stages": ["PROMPT", "PROMPT_REVIEW"],
                                "actor_by_stage": {"PROMPT": "PYTHON", "PROMPT_REVIEW": "HUMAN_AGENT"},
                                "worker_by_stage": {"PROMPT": "zet.workers.body_reference_prompt_worker"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            config_path = root / "config.toml"
            config_path.write_text(
                f"""
[BaseFolders]
BaseCharacterPath = "{(root / 'Characters').as_posix()}"
BaseAssetPath = "{(root / 'Assets').as_posix()}"
BasePipelinePath = "{(root / 'Pipelines').as_posix()}"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"

[PromptCondense]
Enabled = false
Model = "old-model"
PromptFile = "old.md"

[LocalRender]
Preset = "old-preset"
LayoutBackend = "plain_txt2img"
Checkpoint = "old-checkpoint"

[AIHarvest]
AutoEnabled = false
IntervalSeconds = 60

[Render]
Backend = "local_image"
""".lstrip(),
                encoding="utf-8",
            )

            app = ZetApp.from_config(config_path)
            snapshot = app.pipeline_control_snapshot("Test", "Adult")
            self.assertEqual(snapshot.pipeline_rows[0].asset_count, 1)

            app.save_automation_settings(
                AutomationSettings(
                    local_render_preset="body-reference-preview",
                    local_render_positive_prompt_globals="masterpiece",
                    local_render_negative_prompt_globals="blurry",
                    local_render_use_forge_couple=True,
                    local_render_checkpoint="new-checkpoint",
                    ai_harvest_auto_enabled=True,
                    ai_harvest_interval_seconds=300,
                    render_backend="manual_chatgpt",
                )
            )

            reloaded = ZetApp.from_config(config_path).config
            self.assertEqual(reloaded.local_render_positive_prompt_globals, "masterpiece")
            self.assertEqual(reloaded.local_render_negative_prompt_globals, "blurry")
            self.assertEqual(reloaded.local_render_layout_backend, "forge_couple_basic")
            self.assertEqual(reloaded.local_render_checkpoint, "new-checkpoint")
            self.assertEqual(reloaded.ai_harvest_interval_seconds, 300)
            self.assertEqual(reloaded.render_backend, "manual_chatgpt")
            self.assertTrue(list(root.glob("config.backup.*.toml")))


if __name__ == "__main__":
    unittest.main()
