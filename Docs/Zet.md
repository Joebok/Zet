# Zet

Zet is a local, file-backed pipeline dashboard for creating, reviewing, rendering, and eventually locking character image assets.

The current implementation is centered on one character phase at a time. A character phase, such as `Tsaeytte / Adult`, owns its character template, asset records, pipeline definitions, and generated pipeline working files.

## Current Status

Zet currently supports:

- file-backed asset and pipeline records
- Streamlit dashboard controls
- service-layer asset state transitions
- body-reference prompt compilation
- human prompt review
- optional AI prompt condensing before prompt review
- optional local prompt-review image previews
- filesystem AI proxy ask/answer flow
- local image rendering through a backend-neutral render worker
- ComfyUI as the first local image render backend
- answer harvesting back into Zet state
- candidate image display in the dashboard

The current first working end-to-end path is:

```text
Body-Reference asset
MANIFEST -> PROMPT -> PROMPT_REVIEW -> RENDER -> RENDER_REVIEW -> LOCKED
```

The current mature test asset is `asset_id = 1` for `Tsaeytte / Adult / Body-Reference / Front`.

## File Organization

`config.toml` defines shared project-local paths and platform-specific overrides for external paths.

Current config pattern:

```toml
[BaseFolders]
BaseCharacterPath = "_Lib/Characters/"
BaseAssetPath = "_Lib/Assets/"
BasePipelinePath = "_Lib/Pipelines/"
BaseAIQueuePath = "_Lib/AI_Queue/"

[BaseFoldersByPlatform.Windows]
BaseAIQueuePath = "C:/Users/Joe/Library/CloudStorage/Dropbox/AI_Queue/"

[BaseFoldersByPlatform.Darwin]
BaseAIQueuePath = "/Users/joe/Library/CloudStorage/Dropbox/AI_Queue/"
```

The shared project-local paths should remain portable. The AI queue path is external because it is shared between the main Zet app and separate AI/render worker processes, potentially on different machines.

Derived paths:

```text
CharacterPath      = BaseCharacterPath / Character / Phase
CharacterAssetPath = BaseAssetPath / Character / Phase
PipelineBasePath   = BasePipelinePath / Character / Phase
PipelinePath       = PipelineBasePath / Pipeline / BodyView / HeadView-or-_ / Asset_{AssetID}
CandidateImagePath = PipelinePath / FinalImageOutput
LockedImagePath    = CharacterAssetPath / FinalImageOutput
AIProxyRoot        = BaseAIQueuePath / Ollama_Proxy
```

For assets without `HeadView`, Zet uses `_` in the pipeline path.

## Character Phase Files

For a character phase, such as `_Lib/Characters/Tsaeytte/Adult/`, the important files are:

- `Assets.json`
- `Pipelines.json`
- `Character_Image_Template.md`
- generated prompt/compiler outputs under pipeline-specific folders, such as `Body_Reference/Front/`

`Assets.json` stores asset records and mutable progress state.

`Pipelines.json` stores pipeline definitions, ordered stages, actor assignments, and configured worker module names.

## Asset Model

An asset represents one intended final image.

Current asset fields:

- `asset_id`
- `character`
- `phase`
- `pipeline`
- `body_view`
- `head_view`
- `costume`
- `expression`
- `asset_state`
- `pipeline_stage`
- `actor`
- `ai_state`
- `final_image_output`
- `last_ai_update`
- `error_code`
- `error_message`
- `updated_at`

`asset_id` is the stable programmatic handle. The logical identity is still described by character, phase, pipeline, view, costume, and expression fields.

## Asset State

Current asset state values in active use:

- `NEW`
- `IN_PROGRESS`
- `LOCKED`
- `BLOCKED`

`BLOCKED` is used when a human or worker failure stops progress and needs attention.

The earlier planned `LOCK_REVIEW` and `ERROR` asset-state concepts are not active as top-level asset states. `ERROR` is currently a pipeline stage used with `asset_state = BLOCKED`.

## Pipeline Stages

Current stages used by the configured pipelines:

- `MANIFEST`
- `PROMPT`
- `PROMPT_REVIEW`
- `RENDER`
- `RENDER_REVIEW`
- `LOCKED`
- `ERROR`

The standard configured flow is:

```text
MANIFEST -> PROMPT -> PROMPT_REVIEW -> RENDER -> RENDER_REVIEW
```

Approved render reviews promote the asset into:

```text
LOCKED
```

`GPT_HANDOFF` was part of the original planning vocabulary but is not part of the current configured pipeline flow.

## Actors

Allowed actors:

- `PYTHON`
- `AI_AGENT`
- `HUMAN_AGENT`

### `PYTHON`

`PYTHON` means the next work can be performed by local Zet code or a configured worker.

The dashboard exposes actions such as `Run Current Worker`, `Run Housekeeping`, and `Regenerate`.

### `HUMAN_AGENT`

`HUMAN_AGENT` means a person must make a review or control decision in the dashboard.

Currently implemented human review points:

- `PROMPT_REVIEW`
- `RENDER_REVIEW`

Prompt review has a dedicated page. Render review is currently represented by the asset detail page showing candidate/locked images; a richer render review page is still needed.

### `AI_AGENT`

`AI_AGENT` means the asset is queued for asynchronous work through the filesystem proxy.

Current `ai_state` value in active use:

- `ASKED`

The older planned values `WAITING` and `ANSWERED` are not actively used. The queue folders and answer manifests provide the richer operational state.

When `AssetService.move_next()` moves an asset into an `AI_AGENT` stage, Zet now stages an AI proxy ask automatically.

## Service Architecture

The current backend is organized around repository and service layers.

Key backend components:

- `AssetRepository`
- `PipelineRepository`
- `PathService`
- `StateMachine`
- `HousekeepingService`
- `WorkerService`
- `AssetService`
- `AIProxyService`
- `AIAnswerHarvester`
- `PromptReviewService`

The dashboard should remain a UI layer. Reusable behavior belongs in services or scripts, not directly in Streamlit callbacks.

`ZetApp` is the facade used by scripts and the dashboard. `AssetRef` is the convenience wrapper for asset-specific actions.

## Dashboard

The dashboard is currently implemented in Streamlit at `zet/dashboard/app.py`.

Current dashboard pages:

- `Assets`
- `Prompt Review`
- `Template Editor`
- `AI Controls`

### Assets Page

The Assets page shows asset records for the selected character and phase.

Implemented controls include:

- `Open Prompt Review`
- `Stage AI Ask`
- `Run Current Worker`
- `Run Housekeeping`
- `Retry AI`
- `Regenerate`
- `Promote to LOCKED`

The page also shows:

- selected asset summary
- candidate image
- locked image
- raw asset details
- derived paths
- stage marker
- history log

`Run Current Worker` polls the asset table. It runs configured workers for eligible `PYTHON` assets, continuing through additional `PYTHON` stages when a worker advances an asset and another configured worker can handle the next stage.

`Regenerate` is treated as a fresh start for that asset. It clears the asset pipeline working folder, removes stale proxy queue items for the asset, and removes known generated Body-Reference artifacts such as `Final_Image_Prompt.md`, `Condensed_Image_Prompt.md`, review files, dependency manifests, and local test renders before returning the asset to `MANIFEST`.

### Prompt Review Page

The Prompt Review page is active for assets at:

```text
pipeline_stage = PROMPT_REVIEW
actor = HUMAN_AGENT
```

Implemented features:

- prompt display with readable contrast
- prompt copy control
- prompt search
- two-column layout
- Previous / Next navigation across assets waiting for prompt review
- optional local test image generation
- latest local test render display
- Approve
- Fail

Approve advances the asset. If the next stage is `AI_AGENT`, the proxy ask is staged automatically.

Fail currently blocks the asset by setting:

```text
asset_state = BLOCKED
pipeline_stage = ERROR
actor = HUMAN_AGENT
error_code = PROMPT_REVIEW_FAILED
```

### Template Editor

The Template Editor is used to inspect and edit configured prompt template sections.

It currently works with config-driven prompt task bundles and template section metadata.

### AI Controls

AI Controls shows the filesystem proxy queue status:

- Ask
- Claimed
- Answer
- Failed

Harvested answer folders are no longer counted as pending answers.

AI Controls also supports:

- Harvest AI Answers
- Stop Proxy
- Resume Proxy
- Send Monitor Test

When `AIHarvest.AutoEnabled` is true, `run_auto_harvest.bat` starts a separate background harvester loop that runs at `AIHarvest.IntervalSeconds`. The dashboard does not refresh itself to harvest.

## Body-Reference Prompt Pipeline

Body-reference prompt generation uses:

- `Config/Prompt_Task_Bundles.json`
- `Config/Prompt_Templates/body_reference_v1.md`
- `Config/Prompt_Section_Metadata.json`
- `Config/Prompt_Review_Checklists.json`
- `Scripts/Run_Body_Reference_Jobs.py`
- `Scripts/Review_Prompt_Static.py`

Generated body-reference prompt artifacts include:

- `Compiled_Sections.md`
- `Final_Image_Prompt.md`
- `Prompt_Review.md`
- `Image_Review.md`
- `dependency_manifest.json`

When prompt condensing is enabled, an auxiliary proxy task can produce:

- `Condensed_Image_Prompt.md`

The current body-reference prompt direction emphasizes:

- full-body technical reference image
- requested body view
- no crop
- visible full feet
- neutral standing pose
- plain studio background
- tank top and shorts as the technical modesty layer
- negative constraints separated for local renderers

The prompt compiler should not try to correct character-template content mistakes. Character-template content should be edited at the template level.

## Prompt Condensing

Prompt condensing is an optional auxiliary AI task controlled by:

```toml
[PromptCondense]
Enabled = true
Model = "llama3.2-vision:11b"
PromptFile = "Config/Prompt_Condense_Tasks/body_reference_condense.md"

[LocalRender]
AutoQueueAfterCondense = true
Preset = "body-reference-preview"

[AIHarvest]
AutoEnabled = true
IntervalSeconds = 300
```

When enabled, moving a Body-Reference asset from `PROMPT` to `PROMPT_REVIEW` stages an auxiliary proxy ask with:

```text
worker_type = ollama_generate
task_type   = prompt_condense
auxiliary   = true
```

The condense task reads `Final_Image_Prompt.md` and asks the configured Ollama model to produce concise render-facing text for local image generators.

The condense request text is editable in:

```text
Config/Prompt_Condense_Tasks/body_reference_condense.md
```

The harvester copies successful condense output to:

```text
Condensed_Image_Prompt.md
```

This task does not advance the asset, change `Final_Image_Prompt.md`, approve prompt review, or block prompt review if it fails.

When `LocalRender.AutoQueueAfterCondense` is true, harvesting a successful `prompt_condense` answer queues a review-only `local_image_render` ask. That ask writes a test image into `Local_Test_Renders/` and does not advance the asset.

Local render calls prefer `Condensed_Image_Prompt.md` when it exists. If no condensed prompt exists, they use `Final_Image_Prompt.md`.

Manual ChatGPT final render tasks always use `Final_Image_Prompt.md`. The condensed prompt is treated as a local-render aid, not the source of truth for the human ChatGPT render console.

## Local Rendering

Zet has a backend-neutral local render layer under:

```text
Scripts/Local_Render_Adapters/
```

Current files:

- `common.py`
- `local_render.py`
- `comfyui_adapter.py`
- `__init__.py`

`local_render.render_image(...)` is the generic dispatch point.

ComfyUI is currently the only implemented backend. It is selected through `Config/Local_Render_Presets.json`:

```json
{
  "body-reference-preview": {
    "backend": "comfyui"
  }
}
```

The current ComfyUI workflow file is:

```text
Config/Local_Render_Workflows/body_reference_preview_comfyui-api.json
```

The local render adapter:

- reads `Final_Image_Prompt.md`
- splits positive prompt and `Negative constraints:`
- loads workflow JSON
- injects prompt/settings where supported
- queues ComfyUI via local API
- downloads the generated image
- writes PNG and JSON metadata

## Review-Only Local Test Renders

Prompt review can generate optional local test images.

These are saved under the job output directory:

```text
Local_Test_Renders/test_YYYYMMDD_HHMMSS.png
Local_Test_Renders/test_YYYYMMDD_HHMMSS.json
```

This is only a review aid.

It does not:

- modify `Final_Image_Prompt.md`
- approve prompt review
- advance the job
- overwrite final body-reference output
- require ComfyUI for normal prompt compilation

## Filesystem AI Proxy

Zet uses a filesystem proxy for asynchronous AI and local render work.

Queue root:

```text
BaseAIQueuePath / Ollama_Proxy
```

Current queue folders:

```text
Ask/
Claims/
Claimed/
Answer/
Failed/
Control/
Monitor/
```

Ask folders contain:

- `ask_manifest.json`
- prompt/input files

Answer folders contain:

- `ask_manifest.json`
- `answer_manifest.json`
- output files
- optional metadata
- `harvest_manifest.json` after Zet harvests them

### Ask Types

Current worker types:

- `ollama_generate`
- `local_image_render`
- `manual_chatgpt_render`

`local_image_render` is backend-neutral. The concrete backend is selected by `render_preset`.

The earlier `comfyui_render` name is kept only for compatibility in the local image worker.

## Proxy Workers

Current worker scripts:

- `AI_Manager/proxy_worker.py`
- `AI_Manager/ollama_proxy_worker.py`
- `AI_Manager/local_image_proxy_worker.py`
- `AI_Manager/comfyui_proxy_worker.py`

`proxy_worker.py` is the preferred worker entry point. It claims one supported ask at a time and dispatches either `ollama_generate` or `local_image_render` work on the same machine, preventing concurrent condense/render jobs from competing for local resources.

`comfyui_proxy_worker.py` is now only a compatibility wrapper around `local_image_proxy_worker.py`.

The individual Ollama and local image workers remain useful for diagnostics, but should not both be run on the same machine when serialized local work is desired.

The local image handler:

- claims `local_image_render` asks
- calls the backend-neutral local render dispatcher
- writes the expected image output into the Answer folder
- writes `LOCAL_RENDER_METADATA.json`
- does not modify Zet asset state

Zet state changes happen only when the harvester applies answers.

## Answer Harvesting

`AIAnswerHarvester` scans `Answer/` and applies answer folders.

Manual harvesting is available from AI Controls. Continuous harvesting is handled by:

```text
run_auto_harvest.bat
python3 -B -m zet.scripts.auto_harvest_ai_answers --config config.toml
```

For successful answers it:

- validates the attempt against the asset’s current expected attempt when available
- copies the expected output into `PipelinePath`
- copies local render metadata when present
- clears `ai_state`
- updates `last_ai_update`
- advances to the next pipeline stage
- writes `harvest_manifest.json`

Harvested answer folders remain in `Answer/`, but are ignored by queue status counts.

The harvester can also re-apply a previously harvested successful answer if the asset is back at the same AI stage and the answer still matches the expected attempt. This supports recovery from dashboard/service restarts or accidental state regressions.

## Configuration Across Machines

Zet is currently developed on both Windows and macOS.

Platform-specific config overrides are supported through:

```toml
[BaseFoldersByPlatform.Windows]

[BaseFoldersByPlatform.Darwin]
```

The main known cross-machine path is the external Dropbox AI queue. Project-local `_Lib/...` paths should remain relative and portable.

Standalone worker deployments outside the repo, such as `C:/Users/Joe/Ollama`, must be kept in sync manually for now. The batch files there should point at the same `Ollama_Proxy` path resolved by Zet.

HTTPS over Tailscale for the Render Console is intentionally on hold. The current practical deployment is localhost or plain HTTP over the private Tailscale network.

## Process Management

AI Controls includes a process-management section for the local Zet service set.

Current tracked processes:

- Dashboard
- Unified Proxy Worker
- Auto Harvester
- Render Console

The dashboard process is status-only. The other services can be started, stopped, or restarted from AI Controls. Duplicate process counts are shown so accidental multiple workers or harvesters are easier to spot.

## Current Open Items

1. Build a proper `RENDER_REVIEW` page with approve/fail actions and image review history.
2. Move `Promote to LOCKED` into Render Review instead of relying on the Assets detail panel.
3. Add two render-review fail paths: `Fail to Render` to requeue the current render stage, and `Fail to Regenerate` to reset upstream work through regeneration.
4. Add pipeline/config visibility and safe controls for stages, actors, workers, render backend, prompt condense, auto preview render, and auto harvest interval.
5. Add a clean way to archive or hide old harvested answer folders.
6. Add dashboard visibility for harvested vs pending answers.
7. Add stale claim detection and recovery for interrupted workers.
8. Make standalone worker deployment reproducible instead of manually copying files into `C:/Users/Joe/Ollama`.
9. Improve body-reference prompt and/or ComfyUI workflow so renders obey tank top and shorts more reliably.
10. Add support for additional local image backends behind `Local_Render_Adapters/local_render.py`.
11. Add tests for harvester idempotency, stale answer handling, and automatic ask staging.
12. Decide whether Streamlit remains the long-term UI or becomes an operations console behind a future API/frontend.
13. Keep moving reusable behavior out of dashboard code and into services.
