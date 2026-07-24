# Local Image Generation

This document describes Zet's complete local image generation process: configuration, scene compilation, backend dispatch, ComfyUI and Stable Matrix execution, filesystem queue processing, artifact harvesting, direct CLI use, and troubleshooting.

The checked-in example bundle is in [`Docs/ComfyUI_Example`](ComfyUI_Example/README.md). It is a real successful preview of the `FirstDay` story scene `Chapter-03-Collision`.

## Purpose and boundaries

Local image generation produces review images from Zet prompts and scene data. It is separate from the final story-image workflow:

- A local preview does not advance an asset or scene pipeline stage.
- A local preview does not overwrite the final story image.
- Manual ChatGPT final renders continue to use `Final_Image_Prompt.md`.
- Scene previews use `Scene_Render_IR.json` as their canonical structured input.
- Prompt-only character assets can render through either backend without an IR.

Two local backends are implemented:

| Backend | Primary API | Structured scene layout |
| --- | --- | --- |
| Stable Matrix | Automatic1111-compatible `/sdapi/v1/txt2img` | `Local_Render_Brief.json`, optionally Forge Couple |
| ComfyUI | `/prompt`, `/history/{prompt_id}`, `/view` | Compiled directly from `Scene_Render_IR.json` |

## End-to-end flow

```mermaid
flowchart TD
    A["Story scene JSON"] --> B["StoryRenderService"]
    B --> C["Scene_Render_IR.json (canonical)"]
    C --> D["Final_Image_Prompt.md"]
    C --> E["Local_Render_Brief.json"]
    E --> F["Local_Render_Prompt.md"]
    E --> G["Local_Render_Forge_Couple_Prompt.md"]
    H["Render Console: Gen Local Image"] --> I["local_image_render queue ask"]
    C --> I
    F --> I
    I --> J["local_image_proxy_worker"]
    J --> K{"Selected profile backend"}
    K --> L["Stable Matrix adapter"]
    K --> M["ComfyUI IR compiler"]
    M --> N["ComfyUI API workflow"]
    L --> O["Backend image + metadata"]
    N --> O
    O --> P["Answer folder"]
    P --> Q["AIAnswerHarvester"]
    Q --> R["Pipeline Local_Test_Renders"]
    Q --> S["Workflow/result artifacts"]
```

## Configuration

Project settings are stored in `config.toml`. The Image Config page edits the same values.

### Backend selection

```toml
[LocalRender]
AutoQueueAfterCondense = false
Backend = "comfyui"
```

`Backend` is either `stable_matrix` or `comfyui`. Stable Matrix remains the compatibility default when the setting is absent.

### Stable Matrix settings

```toml
[StableMatrix]
Profile = "body-reference-preview"
PositivePromptGlobals = "(masterpiece, best quality, highres), sharp focus"
NegativePromptGlobals = "EasyNegative"
LayoutBackend = "forge_couple_basic"
StrictPrimarySubjectCount = true
ForgeCoupleDebugBasePass = true
Checkpoint = "sd\\checkpoint.safetensors"
```

- `Profile` selects a Stable Matrix entry from `Config/Local_Render_Presets.json`.
- `PositivePromptGlobals` and `NegativePromptGlobals` are appended without duplicating existing terms.
- `LayoutBackend` is `forge_couple_basic` or `plain_txt2img`.
- `Checkpoint` is sent as `override_settings.sd_model_checkpoint`.
- Forge Couple settings affect only Stable Matrix.

### ComfyUI settings

```toml
[ComfyUI]
Profile = "comfyui-core-preview"
ServerURL = "http://127.0.0.1:8188"
Checkpoint = "checkpoint.safetensors"
PositivePromptGlobals = "(masterpiece, best quality, highres), sharp focus"
NegativePromptGlobals = "EasyNegative"
PollSeconds = 1.0
TimeoutSeconds = 300.0
```

- `Profile` selects a ComfyUI entry from `Config/Local_Render_Presets.json`.
- `ServerURL` identifies an unauthenticated local ComfyUI server.
- `Checkpoint` must exactly match a filename reported by ComfyUI.
- Prompt globals are independent from Stable Matrix globals.
- `PollSeconds` controls history polling.
- `TimeoutSeconds` limits a workflow run.

### Render profiles

`Config/Local_Render_Presets.json` holds backend-specific generation parameters. The default ComfyUI profile is:

```json
{
  "comfyui-core-preview": {
    "backend": "comfyui",
    "short_side": 640,
    "max_long_side": 960,
    "steps": 28,
    "cfg": 7.0,
    "sampler_name": "dpmpp_2m",
    "scheduler": "karras",
    "denoise": 1.0,
    "seed": "random",
    "output_subdir": "Local_Test_Renders"
  }
}
```

Profiles contain generation parameters, not project-specific checkpoint or prompt-global choices. The Image Config API returns profiles grouped by backend so each backend keeps its own selection.

### Image Config page

Open **Controls → Image Config**:

1. Choose Stable Matrix or ComfyUI in **Image generation**.
2. Configure the visible backend panel.
3. Use the backend's checkpoint refresh button.
4. Save project settings.

Stable Matrix checkpoint discovery uses `/sdapi/v1/sd-models`. ComfyUI checkpoint discovery reads `CheckpointLoaderSimple` choices from `/object_info/CheckpointLoaderSimple`.

Switching the dropdown does not copy or overwrite checkpoint and prompt-global values between backends.

## Scene compilation and the canonical IR

A story scene begins with:

```text
<BaseLibraryPath>/Stories/<story>/<scene>.scene.json
```

When Zet compiles or stages the scene, `StoryRenderService`:

1. Loads and normalizes schema-v3 scene JSON.
2. Resolves asset and auxiliary-resource references.
3. Loads story settings and prompt-section templates.
4. Calls `compile_scene_render_ir(...)`.
5. Writes the pipeline artifacts.

The pipeline folder is:

```text
<BasePipelinePath>/Stories/<story>/<scene>/
```

### `Scene_Render_IR.json`

The IR is the canonical local scene-render intermediate. It has `schema_version: 3` and contains:

- scene identity and story beat;
- source paths and hashes;
- canvas orientation and aspect ratio;
- composition and left-to-right ordering;
- art style and visual-continuity data;
- environment;
- resolved scene elements;
- placements, pose, motion, gaze, and depth;
- props and interactions;
- dialogue for non-diffusion downstream consumers;
- reference assignments;
- resolved source descriptions.

Before ComfyUI compilation, Zet validates:

- schema version 3;
- required object and array structures;
- nonblank, unique element IDs;
- placement references to known elements.

ComfyUI prompt generation uses the descriptions already resolved into the IR. It does not maintain a second character, costume, or place lookup table.

### Derived scene artifacts

| Artifact | Role |
| --- | --- |
| `Final_Image_Prompt.md` | Full manual/final render prompt |
| `Scene_Render_Validation.json` | Scene warnings and errors |
| `Local_Render_Brief.json` | Backend-neutral preview prompt/layout derivation |
| `Local_Render_Prompt.md` | Labeled positive/negative txt2img prompt |
| `Local_Render_Forge_Couple_Prompt.md` | Human-readable Stable Matrix Forge Couple form |
| `Prompt_Source_Map.json` | Source attribution for generated prompt sections |
| `dependency_manifest.json` | Resolved reference-file contract |

The local brief and prompt files are derived artifacts. If they disagree with the IR, regenerate the scene pipeline rather than editing the derived files as a long-term fix.

## Backend-neutral render contract

Local rendering is dispatched through `LocalRenderRequest` and returns `LocalRenderResult`.

The request carries:

- project root;
- final or local prompt path;
- job output directory;
- selected profile;
- optional prompt-review path;
- optional `Scene_Render_IR.json` path;
- reference-file records;
- aspect ratio;
- optional Stable Matrix layout.

The result carries:

- generated image path;
- backend metadata path;
- prompt-review path;
- backend prompt ID;
- extra artifact paths for harvesting.

The compatibility entrypoint remains `Scripts.Local_Render_Adapters.render_image(...)`. It converts legacy keyword arguments into the backend-neutral request and dispatches on the profile's `backend` value.

## Stable Matrix execution

Stable Matrix supports both prompt-only assets and scene previews.

### Prompt construction

The adapter reads a labeled prompt:

```text
prompt: positive prompt text
negative: negative prompt text
```

For prompt-only assets it sends a normal txt2img request. For scenes:

- `plain_txt2img` uses the flat local prompt;
- `forge_couple_basic` uses the structured lines and mappings derived from `Local_Render_Brief.json`;
- configured Stable Matrix globals and checkpoint overrides are applied immediately before submission.

### Request and outputs

The adapter posts to `/sdapi/v1/txt2img`, decodes the first returned image, and writes:

```text
Stable_Matrix_API_Call.json
Local_Test_Renders/test_<timestamp>.png
Local_Test_Renders/test_<timestamp>.json
```

`Stable_Matrix_API_Call.json` records the exact payload sent to the backend.

## ComfyUI execution

ComfyUI supports two compilation modes.

### Scene IR mode

`compile_ir_to_comfyui_workflow(...)`:

1. Validates the IR.
2. Derives a global prompt, negative prompt, and ordered character-region prompts.
3. Appends ComfyUI-specific prompt globals.
4. Derives dimensions from the IR aspect ratio and profile limits.
5. Resolves a fixed or random seed.
6. Produces a ComfyUI API-format workflow.

One character receives the full canvas. Multiple characters receive ordered, slightly overlapping horizontal regions based on scene composition. The overlap helps preserve whole-image coherence while keeping character conditioning distinct.

The initial workflow uses only built-in nodes:

- `CheckpointLoaderSimple`;
- `CLIPTextEncode`;
- `EmptyLatentImage`;
- `ConditioningSetArea`;
- `ConditioningCombine`;
- `KSampler`;
- `VAEDecode`;
- `SaveImage`.

Dialogue is intentionally omitted from diffusion prompts.

### Prompt-only mode

If no IR is supplied, the adapter compiles the labeled positive and negative prompt into a plain core-node txt2img workflow. This permits character-asset local previews when ComfyUI is selected.

### Dimensions

The compiler preserves the requested aspect ratio subject to profile limits:

- start with `short_side`;
- calculate the corresponding long side;
- cap the long side at `max_long_side`;
- reduce the other side when capped;
- round both dimensions to multiples of eight.

The example scene requests `4:5` and compiles to `640 × 800`.

### Submission and download

`run_comfyui_workflow(...)`:

1. Posts `{"prompt": workflow}` to `/prompt`.
2. Rejects returned workflow or node validation errors.
3. Polls `/history/{prompt_id}` until completion or timeout.
4. Rejects execution-error status.
5. Reads output image descriptors.
6. Downloads each image through `/view`.
7. Sanitizes server filenames before writing locally.

Connection failures are reported as backend-unavailable errors. Invalid JSON, missing prompt IDs, timeout, execution failures, and missing output images are reported as local-render errors.

### ComfyUI artifacts

```text
ComfyUI_Workflow_API.json
Local_Test_Renders/ComfyUI_Render_Metadata.json
Local_Test_Renders/<ComfyUI output image>
```

The workflow file is directly submit-ready API JSON, not the ordinary ComfyUI editor graph format.

Render metadata records:

- timestamps and elapsed time;
- backend, profile, and full profile settings;
- server URL and checkpoint;
- source IR path and SHA-256;
- source prompt path;
- compiled global, negative, and region prompts;
- resolved seed and dimensions;
- ComfyUI prompt ID and output descriptors;
- downloaded image paths.

## Filesystem queue lifecycle

The Render Console's **Gen Local Image** action uses the filesystem proxy.

### 1. Staging

For a scene preview, Zet creates an `Ask_*` folder containing:

- `ask_manifest.json`;
- `Local_Render_Prompt.md`;
- `Scene_Render_IR.json` when ComfyUI is selected.

Important manifest fields include:

| Field | Meaning |
| --- | --- |
| `worker_type` | `local_image_render` |
| `task_type` | `local_test_render` |
| `render_preset` | Selected backend profile |
| `scene_render_ir_file` | Queue-local canonical IR filename |
| `expected_output` | Queue answer image filename |
| `target_output_dir` | Pipeline `Local_Test_Renders` folder |
| `artifact_output_dir` | Pipeline folder for workflow/metadata |
| `source_ask_id` | Render Console task that requested the preview |

Reference records are carried through the manifest even though the v1 ComfyUI core workflow does not yet condition on reference images.

### 2. Claiming and rendering

`AI_Manager/local_image_proxy_worker.py`:

1. Claims one compatible ask.
2. Moves it to `Claimed/<worker-id>/`.
3. Dispatches through the selected render profile.
4. Copies the chosen image to `expected_output`.
5. Copies backend artifacts into the answer folder.
6. Writes `LOCAL_RENDER_METADATA.json`.
7. Writes `answer_manifest.json`.
8. Moves the completed folder to `Answer/`.

If the backend is temporarily unavailable, the worker can return the ask for later retry. Other failures produce an error answer.

### 3. Harvesting

`AIAnswerHarvester`:

1. Verifies the successful answer and expected output.
2. Copies the preview image to `target_output_dir`.
3. Copies declared safe artifact filenames to `artifact_output_dir`.
4. Writes `harvest_manifest.json`.
5. Archives the harvested answer according to the normal proxy lifecycle.

Only basename artifact declarations are accepted, preventing an answer from copying files outside its destination.

## Direct ComfyUI CLI

The direct command bypasses the queue and renders one canonical IR:

```powershell
python3 -m zet.scripts.render_comfyui_preview `
  C:\path\to\Scene_Render_IR.json `
  --config config.toml
```

Options:

| Option | Meaning |
| --- | --- |
| `--profile NAME` | Override `[ComfyUI].Profile` |
| `--checkpoint NAME` | Override `[ComfyUI].Checkpoint` |
| `--seed INTEGER` | Force a reproducible seed |
| `--output-dir PATH` | Override the IR's parent output folder |
| `--compile-only` | Write the workflow without contacting ComfyUI |

Examples:

```powershell
# Deterministic compile and render
python3 -m zet.scripts.render_comfyui_preview `
  .\Docs\ComfyUI_Example\Scene_Render_IR.json `
  --config .\Docs\ComfyUI_Example\Config_Example.toml `
  --seed 8343556516923134802 `
  --output-dir .\.codex_tmp\comfyui-example

# Inspect the generated API graph without running it
python3 -m zet.scripts.render_comfyui_preview `
  .\Docs\ComfyUI_Example\Scene_Render_IR.json `
  --config .\Docs\ComfyUI_Example\Config_Example.toml `
  --compile-only `
  --output-dir .\.codex_tmp\comfyui-compile
```

The example config is documentation-only. Adjust its checkpoint to an installed ComfyUI checkpoint before rendering.

## Example: FirstDay / Chapter-03-Collision

The example snapshot was generated on July 24, 2026.

Key facts:

| Property | Value |
| --- | --- |
| Story | `FirstDay` |
| Scene | `Chapter-03-Collision` |
| IR schema | 3 |
| Canvas | portrait `4:5` |
| Scene elements | 5 |
| Placed primary characters | 4 |
| Profile | `comfyui-core-preview` |
| Checkpoint | `waiNTRMIXIllustrious_v11.safetensors` |
| Output size | `640 × 800` |
| Steps / CFG | `28 / 7.0` |
| Sampler / scheduler | `dpmpp_2m / karras` |
| Seed | `8343556516923134802` |
| ComfyUI elapsed time | `37.618` seconds |
| Status | `SUCCESS` |

The compiled workflow contains four area-conditioning branches, one per visible character, combined with the global scene conditioning.

![Chapter-03-Collision local ComfyUI preview](ComfyUI_Example/Local_Test_Render.png)

The bundle's queue files demonstrate the exact successful ask → answer → harvest lifecycle. Absolute paths in those snapshots record the machine and queue locations used during the run; they are provenance, not portable configuration.

## Output-folder reference

A fully compiled and locally rendered scene can contain:

```text
Chapter-03-Collision/
├── Scene_Render_IR.json
├── Scene_Render_Validation.json
├── Final_Image_Prompt.md
├── Local_Render_Brief.json
├── Local_Render_Prompt.md
├── Local_Render_Forge_Couple_Prompt.md
├── Prompt_Source_Map.json
├── dependency_manifest.json
├── ComfyUI_Workflow_API.json
├── ComfyUI_Render_Metadata.json
└── Local_Test_Renders/
    └── test_<timestamp>.png
```

The harvested ComfyUI metadata is copied to the pipeline folder for Render Console inspection. Direct CLI runs retain it under `Local_Test_Renders`.

## Troubleshooting

### Checkpoint list is empty

- Confirm the selected backend.
- Confirm the backend server is running.
- For ComfyUI, confirm `CheckpointLoaderSimple` is available through `/object_info/CheckpointLoaderSimple`.
- Save a changed ComfyUI server URL before refreshing.

### ComfyUI rejects the workflow

- Confirm the configured checkpoint filename exactly matches ComfyUI.
- Confirm the selected profile uses valid sampler and scheduler names for that installation.
- Inspect `ComfyUI_Workflow_API.json`.
- Read the node errors returned by `/prompt`.

### Render times out

- Increase `[ComfyUI].TimeoutSeconds`.
- Inspect ComfyUI's console and queue.
- Confirm the workflow did not remain pending behind another job.
- Keep `PollSeconds` non-negative.

### Scene preview says the IR is missing

Restage or recompile the scene so its pipeline folder contains `Scene_Render_IR.json`. Do not substitute the raw `.scene.json`; the ComfyUI compiler expects the resolved IR.

### Prompt-only asset preview uses no area conditioning

This is expected. Prompt-only assets lack scene placements, so ComfyUI emits a normal global txt2img workflow.

### Reference images are listed but not used by ComfyUI

This is expected in the core-node baseline. The dependency and queue manifests retain reference provenance for future IP-Adapter, ControlNet, or masked conditioning profiles.

### Generated composition is weak

- Inspect the IR's `composition.left_to_right` and placements.
- Inspect the compiled region prompts in `ComfyUI_Render_Metadata.json`.
- Use a fixed seed when comparing prompt or profile changes.
- Treat the current horizontal area layout as a preview baseline, not deterministic pose control.

## Current limitations

- No reference-image conditioning in the core ComfyUI profile.
- No ControlNet, OpenPose, IP-Adapter, LoRA, or custom nodes.
- No generated dialogue, captions, or speech bubbles.
- Area conditioning guides placement but does not guarantee identity separation or pose.
- The first ComfyUI image is used as the queue's preview result when a workflow returns multiple images.
- Local ComfyUI assumes an unauthenticated local server.

Future workflow work should preserve `Scene_Render_IR.json` as the source of scene layout, prompts, masks, references, and deterministic controls.

## Developer verification

Relevant automated coverage includes:

- IR validation and deterministic workflow compilation;
- prompt-only workflow compilation;
- aspect-ratio sizing;
- ComfyUI validation, execution-error, timeout, and safe-download handling;
- checkpoint discovery;
- CLI compile-only behavior;
- queue IR propagation;
- backend configuration persistence;
- Image Config controls.

Run:

```powershell
python3 -m pytest -q
node --check .\zet\web\static\zet.js
git diff --check
```

