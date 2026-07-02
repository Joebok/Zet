import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from zet.web.app import create_app


class WebAppTests(unittest.TestCase):
    def test_assets_api_serves_context_list_and_detail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character_dir = root / "Characters" / "Test" / "Adult"
            character_dir.mkdir(parents=True)
            (root / "Assets" / "Test" / "Adult").mkdir(parents=True)
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
                                "asset_state": "LOCKED",
                                "pipeline_stage": "LOCKED",
                                "actor": "HUMAN_AGENT",
                                "ai_state": None,
                                "final_image_output": "front.png",
                                "last_ai_update": None,
                                "error_code": None,
                                "error_message": None,
                                "updated_at": None,
                            }
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
                                "actor_by_stage": {"RENDER": "AI_AGENT", "RENDER_REVIEW": "HUMAN_AGENT"},
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
""".lstrip(),
                encoding="utf-8",
            )

            client = TestClient(create_app(config_path))
            context = client.get("/api/context")
            self.assertEqual(context.status_code, 200)
            self.assertEqual(context.json()["default_character"], "Test")

            assets = client.get("/api/assets", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(assets.status_code, 200)
            self.assertEqual(assets.json()["assets"][0]["asset_id"], 1)

            detail = client.get("/api/assets/1", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["asset"]["pipeline_stage"], "LOCKED")


if __name__ == "__main__":
    unittest.main()
