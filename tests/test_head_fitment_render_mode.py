import json
from pathlib import Path
import tempfile
import unittest

from zet.app import ZetApp


class HeadFitmentRenderModeTests(unittest.TestCase):
    def test_masked_local_mode_routes_render_to_python_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character = root / "Characters" / "Test" / "Elder"
            character.mkdir(parents=True)
            (root / "Assets").mkdir()
            (root / "Pipelines").mkdir()
            (root / "Queue").mkdir()
            (character / "Assets.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "next_asset_id": 2,
                    "assets": [{
                        "asset_id": 1,
                        "character": "Test",
                        "phase": "Elder",
                        "pipeline": "Head-Fitment",
                        "body_view": "Front",
                        "head_view": "Front",
                        "asset_state": "IN_PROGRESS",
                        "pipeline_stage": "PROMPT",
                        "actor": "PYTHON",
                        "final_image_output": "head.png",
                    }],
                }),
                encoding="utf-8",
            )
            (character / "Pipelines.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "pipelines": {
                        "Head-Fitment": {
                            "stages": ["PROMPT", "RENDER", "RENDER_REVIEW"],
                            "actor_by_stage": {"PROMPT": "PYTHON", "RENDER": "AI_AGENT", "RENDER_REVIEW": "HUMAN_AGENT"},
                            "worker_by_stage": {
                                "PROMPT": "zet.workers.head_fitment_prompt_worker",
                                "RENDER": "zet.workers.head_fitment_render_worker",
                                "RENDER_REVIEW": "zet.workers.noop_worker",
                            },
                        }
                    },
                }),
                encoding="utf-8",
            )
            config_path = root / "config.toml"
            config_path.write_text(
                f"""
[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"

[Render]
Backend = "manual_chatgpt"

[HeadFitment]
RenderMode = "masked_local"
""".lstrip(),
                encoding="utf-8",
            )
            asset = ZetApp.from_config(config_path).asset_service.move_next("Test", "Elder", 1)
            self.assertEqual("RENDER", asset.pipeline_stage)
            self.assertEqual("PYTHON", asset.actor)
            self.assertIsNone(asset.ai_state)
            self.assertFalse((root / "Queue" / "Manual_Render_Queue" / "Ask").exists())


if __name__ == "__main__":
    unittest.main()
