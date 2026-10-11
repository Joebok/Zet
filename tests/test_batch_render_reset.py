import json
import tempfile
import unittest
from pathlib import Path

from zet.app import ZetApp


def asset_record(asset_id: int, pipeline: str, stage: str, state: str = "IN_PROGRESS") -> dict:
    return {
        "asset_id": asset_id,
        "character": "Test",
        "phase": "Adult",
        "pipeline": pipeline,
        "body_view": "Front",
        "head_view": None,
        "costume": None,
        "expression": None,
        "asset_state": state,
        "pipeline_stage": stage,
        "actor": "HUMAN_AGENT",
        "ai_state": None,
        "final_image_output": f"asset_{asset_id}.png",
        "last_ai_update": None,
        "error_code": None,
        "error_message": None,
        "updated_at": None,
    }


class BatchRenderResetTests(unittest.TestCase):
    def test_reset_pipeline_assets_to_render_stages_fresh_asks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character_dir = root / "Characters" / "Test" / "Adult"
            prompt_dir = character_dir / "Body_Reference" / "Front"
            prompt_dir.mkdir(parents=True)
            (root / "Assets" / "Test" / "Adult").mkdir(parents=True)
            (root / "Pipelines").mkdir()
            (root / "Queue").mkdir()
            (prompt_dir / "Final_Image_Prompt.md").write_text("full final prompt\n", encoding="utf-8")

            (character_dir / "Assets.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            asset_record(1, "Body-Reference", "RENDER_REVIEW"),
                            asset_record(2, "Body-Reference", "LOCKED", "LOCKED"),
                            asset_record(3, "Head-Image", "RENDER_REVIEW"),
                            asset_record(4, "Body-Reference", "MANIFEST"),
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (character_dir / "Pipelines.json").write_text(
                json.dumps(
                    {
                        "pipelines": {
                            "Body-Reference": {
                                "stages": ["RENDER", "RENDER_REVIEW"],
                                "actor_by_stage": {
                                    "RENDER": "AI_AGENT",
                                    "RENDER_REVIEW": "HUMAN_AGENT",
                                },
                                "worker_by_stage": {},
                            },
                            "Head-Image": {
                                "stages": ["RENDER", "RENDER_REVIEW"],
                                "actor_by_stage": {"RENDER": "AI_AGENT", "RENDER_REVIEW": "HUMAN_AGENT"},
                                "worker_by_stage": {},
                            },
                        }
                    },
                    indent=2,
                )
                + "\n",
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

[Render]
Backend = "manual_chatgpt"
""".lstrip(),
                encoding="utf-8",
            )

            app = ZetApp.from_config(config_path)
            asset_1 = app.asset_repository.get_asset("Test", "Adult", 1)
            candidate_path = app.path_service.candidate_image_path(asset_1)
            candidate_path.parent.mkdir(parents=True)
            candidate_path.write_bytes(b"old image")

            before = app.asset_repository.get_asset("Test", "Adult", 1)
            with self.assertRaisesRegex(ValueError, "Traditional Body-Reference generation is retired"):
                app.reset_pipeline_assets_to_render("Test", "Adult", "Body-Reference")
            after = app.asset_repository.get_asset("Test", "Adult", 1)
            self.assertEqual(before, after)
            self.assertTrue(candidate_path.is_file())
            self.assertFalse((root / "Queue" / "Manual_Render_Queue" / "Ask").exists())

    def test_missing_final_prompt_skips_without_mutating_asset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character_dir = root / "Characters" / "Test" / "Adult"
            character_dir.mkdir(parents=True)
            (root / "Assets" / "Test" / "Adult").mkdir(parents=True)
            (root / "Pipelines").mkdir()
            (root / "Queue").mkdir()

            (character_dir / "Assets.json").write_text(
                json.dumps({"assets": [asset_record(1, "Body-Reference", "RENDER_REVIEW")]}, indent=2) + "\n",
                encoding="utf-8",
            )
            (character_dir / "Pipelines.json").write_text(
                json.dumps(
                    {
                        "pipelines": {
                            "Body-Reference": {
                                "stages": ["RENDER", "RENDER_REVIEW"],
                                "actor_by_stage": {
                                    "RENDER": "AI_AGENT",
                                    "RENDER_REVIEW": "HUMAN_AGENT",
                                },
                                "worker_by_stage": {},
                            }
                        }
                    },
                    indent=2,
                )
                + "\n",
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

[Render]
Backend = "manual_chatgpt"
""".lstrip(),
                encoding="utf-8",
            )

            app = ZetApp.from_config(config_path)
            before = app.asset_repository.get_asset("Test", "Adult", 1)
            with self.assertRaisesRegex(ValueError, "Traditional Body-Reference generation is retired"):
                app.reset_pipeline_assets_to_render("Test", "Adult", "Body-Reference")
            unchanged = app.asset_repository.get_asset("Test", "Adult", 1)
            self.assertEqual(before, unchanged)
            self.assertFalse((root / "Queue" / "Manual_Render_Queue" / "Ask").exists())


if __name__ == "__main__":
    unittest.main()
