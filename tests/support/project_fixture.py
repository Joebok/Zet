from __future__ import annotations

import json
from pathlib import Path


def write_project_fixture(root: Path, *, stage: str = "LOCKED", actor: str = "HUMAN_AGENT") -> Path:
    character_dir = root / "Characters" / "Test" / "Adult"
    prompt_dir = character_dir / "Body_Reference" / "Front"
    pipeline_dir = root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_" / "Asset_1"
    character_dir.mkdir(parents=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    (root / "Assets" / "Test" / "Adult").mkdir(parents=True)
    (root / "Queue").mkdir()
    (root / "Config").mkdir()
    (root / "Config" / "AI_Prompt_Analysis_Instructions.md").write_text(
        "Analyze the compiled prompt.\n", encoding="utf-8"
    )
    (prompt_dir / "Final_Image_Prompt.md").write_text("full final prompt\n", encoding="utf-8")
    (pipeline_dir / "front.png").write_bytes(b"test image")
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
                        "pipeline_stage": stage,
                        "actor": actor,
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
                        "stages": ["MANIFEST", "RENDER", "RENDER_REVIEW"],
                        "actor_by_stage": {
                            "MANIFEST": "PYTHON",
                            "RENDER": "AI_AGENT",
                            "RENDER_REVIEW": "HUMAN_AGENT",
                        },
                        "worker_by_stage": {
                            "MANIFEST": "zet.workers.noop_worker",
                            "PROMPT": "zet.workers.body_reference_prompt_worker",
                        },
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
    return config_path

def write_manual_render_ask(root: Path) -> Path:
    ask_path = root / "Queue" / "Manual_Render_Queue" / "Ask" / "Ask_Asset_1_RENDER_TEST"
    ask_path.mkdir(parents=True, exist_ok=True)
    (ask_path / "ask_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ask_id": "Ask_Asset_1_RENDER_TEST",
                "asset_id": 1,
                "character": "Test",
                "phase": "Adult",
                "pipeline": "Body-Reference",
                "pipeline_stage": "RENDER",
                "ollama_attempt_id": "render-test",
                "worker_type": "manual_chatgpt_render",
                "ollama_model": "",
                "prompt_file": "Final_Image_Prompt.md",
                "expected_output": "front.png",
                "candidate_output_file": "front.png",
                "task_type": "render",
                "render_preset": "chatgpt-manual",
                "manual": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (ask_path / "Final_Image_Prompt.md").write_text("manual render prompt\n", encoding="utf-8")
    return ask_path
