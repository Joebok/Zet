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

            results = app.reset_pipeline_assets_to_render("Test", "Adult", "Body-Reference")
            statuses = {result.asset_id: result.status for result in results}
            self.assertEqual(statuses, {1: "RESET", 2: "SKIPPED", 4: "SKIPPED"})

            updated_1 = app.asset_repository.get_asset("Test", "Adult", 1)
            self.assertEqual(updated_1.pipeline_stage, "RENDER")
            self.assertEqual(updated_1.actor, "AI_AGENT")
            self.assertEqual(updated_1.ai_state, "ASKED")
            self.assertFalse(candidate_path.exists())

            updated_2 = app.asset_repository.get_asset("Test", "Adult", 2)
            self.assertEqual(updated_2.asset_state, "LOCKED")
            self.assertEqual(updated_2.pipeline_stage, "LOCKED")

            updated_4 = app.asset_repository.get_asset("Test", "Adult", 4)
            self.assertEqual(updated_4.pipeline_stage, "MANIFEST")
            self.assertEqual(updated_4.actor, "HUMAN_AGENT")

            unchanged_3 = app.asset_repository.get_asset("Test", "Adult", 3)
            self.assertEqual(unchanged_3.pipeline, "Head-Image")
            self.assertEqual(unchanged_3.pipeline_stage, "RENDER_REVIEW")

            ask_dirs = list((root / "Queue" / "Manual_Render_Queue" / "Ask").glob("Ask_Asset_1_RENDER_*"))
            self.assertEqual(len(ask_dirs), 1)
            manifest = json.loads((ask_dirs[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["worker_type"], "manual_chatgpt_render")
            self.assertEqual(manifest["prompt_file"], "Final_Image_Prompt.md")

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
            results = app.reset_pipeline_assets_to_render("Test", "Adult", "Body-Reference")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "SKIPPED")
            self.assertIn("No Final_Image_Prompt.md", results[0].message)
            unchanged = app.asset_repository.get_asset("Test", "Adult", 1)
            self.assertEqual(unchanged.asset_state, "IN_PROGRESS")
            self.assertEqual(unchanged.pipeline_stage, "RENDER_REVIEW")
            self.assertEqual(unchanged.actor, "HUMAN_AGENT")
            self.assertFalse((root / "Queue" / "Manual_Render_Queue" / "Ask").exists())


if __name__ == "__main__":
    unittest.main()
