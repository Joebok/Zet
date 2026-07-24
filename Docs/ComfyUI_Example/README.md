# FirstDay / Chapter-03-Collision ComfyUI Example

This folder is a real successful local-preview snapshot from the `FirstDay` story scene `Chapter-03-Collision`, generated July 24, 2026.

See [`../Local_Image_Generation.md`](../Local_Image_Generation.md) for the complete process.

## Files

| File | Role |
| --- | --- |
| `Chapter-03-Collision.md` | Story scene narrative and scene metadata |
| `Chapter-03-Collision.scene.json` | Source Scene Builder document |
| `Scene_Render_IR.json` | Canonical resolved scene-render intermediate |
| `Scene_Render_Validation.json` | Compilation validation result |
| `Final_Image_Prompt.md` | Full manual/final render prompt |
| `Local_Render_Brief.json` | Derived local scene layout and prompts |
| `Local_Render_Prompt.md` | Plain labeled txt2img prompt |
| `Local_Render_Forge_Couple_Prompt.md` | Stable Matrix Forge Couple inspection form |
| `Prompt_Source_Map.json` | Prompt source attribution |
| `dependency_manifest.json` | Resolved reference provenance |
| `ComfyUI_Workflow_API.json` | Submit-ready ComfyUI API graph |
| `ComfyUI_Render_Metadata.json` | Successful run settings and result metadata |
| `Local_Test_Render.png` | Harvested local ComfyUI preview |
| `Queue_Ask_Manifest.json` | Local-render queue request |
| `Queue_Answer_Manifest.json` | Worker result |
| `Queue_Local_Render_Metadata.json` | Backend artifact handoff |
| `Queue_Harvest_Manifest.json` | Applied/harvested result |
| `Config_Example.toml` | Minimal portable configuration example |
| `Render_Profile_Example.json` | ComfyUI render profile used by the snapshot |
| `Config/Local_Render_Presets.json` | Profile location expected by the CLI |

The copied manifests and render metadata contain absolute Windows paths from the original run. They are retained as provenance and should not be reused as configuration.

## Recompile without rendering

From the Zet repository root:

```powershell
python3 -m zet.scripts.render_comfyui_preview `
  .\Docs\ComfyUI_Example\Scene_Render_IR.json `
  --config .\Docs\ComfyUI_Example\Config_Example.toml `
  --compile-only `
  --output-dir .\.codex_tmp\comfyui-example
```

Before a real render, edit `Config_Example.toml` so `Checkpoint` matches a checkpoint installed in ComfyUI.

## Recorded result

- Profile: `comfyui-core-preview`
- Size: `640 × 800`
- Seed: `8343556516923134802`
- Prompt ID: `a8c0736d-1ecc-4b13-bb6b-1f7e2e5740c0`
- Status: `SUCCESS`

![Local ComfyUI preview](Local_Test_Render.png)
