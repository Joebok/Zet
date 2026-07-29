from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import uvicorn
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_web_app import WebAppTests
from zet.app import ZetApp
from zet.services.character_onboarding_service import CharacterOnboardingService
from zet.services.source_editor_service import SourceEditorService
import zet.web.app as web_app_module
from zet.web.app import create_app


project_root = Path(__file__).resolve().parents[2]
root = (project_root / "test-results" / "dashboard-browser-project").resolve()
if root.exists():
    if root.parent != (project_root / "test-results").resolve():
        raise RuntimeError(f"Refusing to clear unexpected browser fixture path: {root}")
    shutil.rmtree(root)
root.mkdir(parents=True)


class BrowserTestSourceEditorService(SourceEditorService):
    def __init__(self, zet_app, project_root):
        super().__init__(zet_app, root)


web_app_module.SourceEditorService = BrowserTestSourceEditorService
fixture = WebAppTests()
config_path = fixture._write_fixture(root, stage="RENDER", actor="AI_AGENT")
fixture._write_manual_render_ask(root)

config_text = config_path.read_text(encoding="utf-8").replace(
    "[BaseFolders]\n",
    f'[BaseFolders]\nBaseLibraryPath = "{root.as_posix()}"\n',
)
config_path.write_text(config_text, encoding="utf-8")

character_dir = root / "Characters" / "Test" / "Adult"
(character_dir / "Character_Image_Template.md").write_text(
    "\n".join(
        [
            "Character Name: Test",
            "Character Phase: Adult",
            "Species / Ancestry: Human",
            "Gender Presentation: Neutral",
            "Canonical Art Style: Graphic novel",
        ]
    )
    + "\n",
    encoding="utf-8",
)
# Browser tests exercise dashboard behavior, not compiler-bundle validation.
CharacterOnboardingService.validate_template = lambda self, template_path: []
assets_path = character_dir / "Assets.json"
assets = json.loads(assets_path.read_text(encoding="utf-8"))
assets["assets"].extend(
    [
        {
            **assets["assets"][0],
            "asset_id": 2,
            "asset_state": "IN_PROGRESS",
            "pipeline_stage": "RENDER",
            "actor": "AI_AGENT",
            "final_image_output": "landscape.png",
        },
        {
            **assets["assets"][0],
            "asset_id": 3,
            "asset_state": "IN_PROGRESS",
            "pipeline_stage": "MANIFEST",
            "actor": "PYTHON",
            "final_image_output": "square.png",
        },
    ]
)
assets_path.write_text(json.dumps(assets, indent=2) + "\n", encoding="utf-8")

pipeline_root = root / "Pipelines" / "Test" / "Adult" / "Body-Reference" / "Front" / "_"
for asset_id, name, size, color in (
    (1, "front.png", (600, 900), "navy"),
    (2, "landscape.png", (1200, 600), "teal"),
    (3, "square.png", (800, 800), "purple"),
):
    workspace = pipeline_root / f"Asset_{asset_id}"
    workspace.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(workspace / name)
    (workspace / "Final_Image_Prompt.md").write_text(
        f"Deterministic prompt for Asset {asset_id}\n",
        encoding="utf-8",
    )

local_images = pipeline_root / "Asset_1" / "Local_Test_Renders"
local_images.mkdir(parents=True, exist_ok=True)
for name, size, color in (
    ("portrait.png", (600, 900), "red"),
    ("landscape.png", (1200, 600), "green"),
    ("square.png", (800, 800), "blue"),
):
    Image.new("RGB", size, color).save(local_images / name)

stories_root = root / "Stories"
for slug, title in (
    ("Alpha-Story", "Alpha Story"),
    ("Beta-Story", "Beta Story"),
    ("Gamma-Story", "Gamma Story"),
):
    story_dir = stories_root / slug
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / f"{slug}.md").write_text(
        f"Title: `[{title}]`\n\nA deterministic browser-test story.\n",
        encoding="utf-8",
    )
    for scene_slug in ("Opening-Scene", "Closing-Scene"):
        (story_dir / f"{scene_slug}.md").write_text(
            f"Scene: `[{scene_slug.replace('-', ' ')}]`\n\nScene text.\n",
            encoding="utf-8",
        )
        Image.new("RGB", (800, 600), "orange").save(story_dir / f"{scene_slug}.png")

zet_app = ZetApp.from_config(config_path)
for story_slug in ("Alpha-Story", "Beta-Story", "Gamma-Story"):
    story_path = stories_root / story_slug / f"{story_slug}.md"
    zet_app.story_service.save_story_settings(
        stories_root / story_slug / f"{story_slug}.story.json",
        zet_app.story_service.create_default_story_settings(story_path),
    )
    for scene_slug in ("Opening-Scene", "Closing-Scene"):
        builder_path = zet_app.story_service.scene_builder_json_path(story_slug, scene_slug)
        zet_app.story_service.save_scene_v3(
            builder_path,
            zet_app.story_service.create_default_scene_builder_data(story_slug, scene_slug),
        )

analysis_path = zet_app.story_service.scene_pipeline_path("Alpha-Story", "Opening-Scene") / "AI_Prompt_Analysis.md"
analysis_path.parent.mkdir(parents=True, exist_ok=True)
analysis_path.write_text("# Prompt Analysis\n\nDeterministic browser-test analysis.\n", encoding="utf-8")

zine_dir = root / "Assets" / "Zines" / "Browser-Zine"
zine_dir.mkdir(parents=True, exist_ok=True)
(zine_dir / "Browser-Zine.json").write_text(
    json.dumps(
        {
            "zine_name": "Browser Zine",
            "zine_slug": "Browser-Zine",
            "output_image": "Browser-Zine.png",
            "slots": {
                "front": "{{SCENE:Alpha-Story:Opening-Scene}}",
                "page_1": "{{SCENE:Alpha-Story:Opening-Scene}}",
                "page_2": "",
                "page_3": "{{SCENE:Alpha-Story:Closing-Scene}}",
                "page_4": "",
                "page_5": "{{SCENE:Beta-Story:Opening-Scene}}",
                "page_6": "",
                "back": "{{SCENE:Beta-Story:Closing-Scene}}",
            },
            "guides": {"enabled": True},
            "spreads": {"1": False, "3": False, "5": False},
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
Image.new("RGB", (1320, 1020), "white").save(zine_dir / "Browser-Zine.png")

answer_dir = root / "Queue" / "Manual_Render_Queue" / "Answer" / "Ask_Harvested"
answer_dir.mkdir(parents=True, exist_ok=True)
(answer_dir / "harvest_manifest.json").write_text("{}\n", encoding="utf-8")

app = create_app(config_path)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
