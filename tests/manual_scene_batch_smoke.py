"""Run three real Qwen renders in an isolated library, then publish and build a Zine.

Run: python3 -m tests.manual_scene_batch_smoke
The temporary library and transport artifacts are retained for inspection. The
normal queue worker is simulated locally; ComfyUI itself must be running.
"""
from pathlib import Path
import json
import shutil
import tempfile
import time
from urllib.request import urlopen

from Scripts.Local_Render_Adapters.local_render import render_image
from zet.app import ZetApp
from zet.services.atomic_file_service import write_json_atomic
from zet.services.config_service import ConfigService
from zet.services.local_render_policy import SCENE_PROFILE


def main():
    project = Path(__file__).resolve().parents[1]
    config = ConfigService.load(project / "config.toml")
    # Preflight before creating any smoke-test artifacts.
    with urlopen(config.comfyui_server_url.rstrip("/") + "/object_info", timeout=10) as response:
        assert "TextEncodeQwenImage21" in json.load(response), "Install the configured Qwen Image 2.1 node in ComfyUI."
    root = Path(tempfile.mkdtemp(prefix="zet-local-scene-smoke-"))
    print(f"Smoke library: {root}", flush=True)
    (root / "Config/Prompt_Templates").mkdir(parents=True)
    for relative in ["Config/Local_Render_Presets.json", "Config/Prompt_Templates/final_image_prompt_tail_v1.md",
                     "Shared_Library/Stories/_Story_Template.md", "Shared_Library/Stories/_Scene_Template.md"]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / relative, target)
    config_path = root / "config.toml"
    config_path.write_text(f'''[BaseFolders]
BaseLibraryPath = "{root.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
[ComfyUI]
Profile = "{SCENE_PROFILE}"
ServerURL = "{config.comfyui_server_url}"
TimeoutSeconds = 1800
[AIHarvest]
AutoEnabled = false
''', encoding="utf-8")
    app = ZetApp.from_config(config_path, validate_catalog=False)
    app.create_story("Smoke")
    app.create_scene("Smoke", "Clearing")
    data = app.load_scene_builder("Smoke", "Clearing").data
    data["scene"]["story_beat"] = "A cloaked traveler crosses a quiet woodland clearing."
    data["setup"]["environment"]["general_background_notes"] = "A sunlit forest clearing with a winding dirt path."
    data["scene_elements"] = [{"id": "traveler", "display_name": "Traveler", "resource_type": "Scene-Only",
                               "element_type": "Character", "fallback_visual_description": "A cloaked adult traveler carrying a wooden staff."}]
    data["placements"] = [{"id": "p1", "scene_element_id": "traveler", "depth": "midground", "position_within_cell": "center"}]
    data["subscenes"] = [{"id": "background", "name": "Background", "kind": "background", "enabled": True},
                         {"id": "traveler_view", "name": "Traveler", "kind": "element", "anchor_element_id": "traveler", "enabled": True}]
    app.save_scene_builder("Smoke", "Clearing", data)
    service = app.local_scene_batch_service
    run = service.create("Smoke", "Clearing", {})
    for target in run["views"]:
        run = service.action("Smoke", "Clearing", run["run_id"], "start", {})
        group = run["groups"][target]
        for candidate in group["candidates"][:4]:
            print(f"Rendering {target} {candidate['slot']}/4", flush=True)
            result = render_image(project_root=root, final_prompt_path=Path(group["prompt_path"]),
                                  job_output_dir=Path(candidate["work_path"]).parent, preset_name=SCENE_PROFILE,
                                  scene_render_ir_path=Path(group["ir_path"]), reference_files=group["reference_images"], seed=candidate["seed"])
            ask = service.proxy.ask_root() / candidate["ask_id"]
            manifest = json.loads((ask / "ask_manifest.json").read_text(encoding="utf-8"))
            answer = service.proxy.answer_root() / candidate["ask_id"]
            answer.mkdir(parents=True)
            write_json_atomic(answer / "ask_manifest.json", manifest)
            shutil.copy2(result.image_path, answer / manifest["expected_output"])
            write_json_atomic(answer / "answer_manifest.json", {"ask_id": candidate["ask_id"], "status": "SUCCESS", "expected_output": manifest["expected_output"]})
            run = service.detail("Smoke", "Clearing", run["run_id"])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            run = service.detail("Smoke", "Clearing", run["run_id"])
            if run["rankings"].get(target, {}).get("status") == "COMPLETE":
                break
            time.sleep(.1)
        assert run["rankings"][target]["status"] == "COMPLETE", run["rankings"]
        run = service.action("Smoke", "Clearing", run["run_id"], "select", {"target_id": target, "candidate_id": candidate["candidate_id"]})
    run = service.action("Smoke", "Clearing", run["run_id"], "publish", {})
    assert run["status"] == "COMPLETE"
    tag = "{{SCENE:Smoke:Clearing}}"
    zine = app.zine_service.create_zine({"zine_name": "Smoke", "slots": {key: tag for key in
                                     ["front", "page_1", "page_2", "page_3", "page_4", "page_5", "page_6", "back"]}})
    assert zine.record.image_exists
    print(f"PASS: background -> subscene -> Full Scene -> publication -> Zines. Artifacts: {root}", flush=True)


if __name__ == "__main__":
    main()
