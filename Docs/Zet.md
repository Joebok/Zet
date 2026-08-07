# Zet

Zet is a local, file-backed pipeline dashboard for creating, reviewing, rendering, and eventually locking character image assets.

The current implementation is centered on one character phase at a time. A character phase, such as `Tsaeytte / Adult`, owns its character template, asset records, pipeline definitions, and generated pipeline working files.

## Current Status

Zet currently supports:

- file-backed asset and pipeline records
- FastAPI dashboard controls
- service-layer asset state transitions
- body-reference prompt compilation
- render-queue prompt inspection
- optional AI prompt condensing before render
- optional local prompt-inspection image previews
- filesystem AI proxy ask/answer flow
- local image rendering through a backend-neutral render worker
- ComfyUI as the first local image render backend
- answer harvesting back into Zet state
- candidate image display in the dashboard

The current first working end-to-end path is:

```text
Body-Reference asset
MANIFEST -> PROMPT -> RENDER -> RENDER_REVIEW -> LOCKED
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
AIProxyRoot        = BaseAIQueuePath / File_Proxy
```

For assets without `HeadView`, Zet uses `_` in the pipeline path.

## Character Phase Files

For a character phase, such as `_Lib/Characters/Tsaeytte/Adult/`, the important files are:

- `Assets.json`
- `Pipelines.json`
- `Character.md`
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
- `RENDER`
- `RENDER_REVIEW`
- `LOCKED`
- `ERROR`

The standard configured flow is:

```text
MANIFEST -> PROMPT -> RENDER -> RENDER_REVIEW
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

- `RENDER_REVIEW`

Render review has a dedicated FastAPI dashboard page. It handles promotion to `LOCKED` and supports fail paths back to `RENDER` or full regeneration.

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
- `PipelineControlService`

The dashboard should remain a UI layer. Reusable behavior belongs in services or scripts, not directly in UI callbacks.

`ZetApp` is the facade used by scripts and the dashboard. `AssetRef` is the convenience wrapper for asset-specific actions.

## Dashboard

The primary dashboard is implemented in FastAPI at `zet/web/app.py`.

The old Streamlit dashboard has been retired. New dashboard work belongs in `zet/web/` and should call backend services rather than owning workflow logic directly.

The FastAPI dashboard lives under:

```text
zet/web/
```

Run it locally with:

```text
dashboard.bat
```

Current dashboard pages:

- `Assets`
- `Manifest`
- `Prompt Inspection`
- `Image Review`
- `Render Console`
- `AI Controls`
- `Pipeline Controls`

The Template Editor is intentionally deferred while the body-reference authoring workflow is reconsidered.

### Scene Image Review

The first successful image saved for a scene is published directly to `Stories/<story>/<scene>.png`. Local test renders do not count as published or candidate images. Later successful saves are written to `Pipelines/Stories/<story>/<scene>/Candidate/<scene>.png` and appear in Image Review beside the currently published image.

Promoting a scene candidate backs up the current published image under `Locked_Backups`, publishes the candidate, and clears the pending review. Discarding removes only the candidate. Other dashboard pages always display the published image and link the `Candidate Image Pending` overlay to the matching scene in Image Review.

### Direct Character Assembly

Character-Assembly consumes matching locked `body_reference` and `head_image` references. Head-Image controls identity, age, face, ears, hairstyle, gaze, and head orientation; Body-Reference controls the final body, shoulders, clothing, pose, framing, and background. Reconstruction is limited to the neck and immediate neck/hair/shoulder junction.

The former Head-Fitment pipeline is retired and has no active configuration, routes, workers, assets, or reference role. Its implementation and historical artifacts are retained only in archives.

### Assets Page

The Assets page shows asset records for the selected character and phase.

Implemented controls include:

- `Open Prompt Inspection`
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

### Prompt Inspection Page

Prompt Inspection displays and recompiles prompts from queued `RENDER` tasks. It supports prompt copy/search, source attribution, Previous/Next navigation, and optional local test renders. It does not represent a pipeline stage or advance asset state.

### Template Editor

The Template Editor is used to inspect and edit configured prompt template sections.

It currently works with config-driven prompt task bundles and template section metadata.

### AI Controls

AI Controls shows the filesystem proxy queue status:

- Ask
- Running
- Answer

Harvested answer folders are no longer counted as pending answers.

AI Controls also supports:

- Harvest AI Answers

When `AIHarvest.AutoEnabled` is true, `run_auto_harvest.bat` starts a separate background harvester loop that runs at `AIHarvest.IntervalSeconds`. The dashboard does not refresh itself to harvest.

### Pipeline Controls

Pipeline Controls shows project-level automation settings beside the selected character/phase pipeline definitions.

It can edit known safe settings in `config.toml`:

- `PromptCondense.Enabled`
- `PromptCondense.Model`
- `PromptCondense.PromptFile`
- `LocalRender.AutoQueueAfterCondense`
- `LocalRender.Preset`
- `AIHarvest.AutoEnabled`
- `AIHarvest.IntervalSeconds`
- `Render.Backend`

Config saves are written through `PipelineControlService`, which creates a timestamped `config.backup.*.toml` file and validates the updated TOML before replacing `config.toml`.

The selected character/phase `Pipelines.json` is shown as a read-only table of stages, actors, worker modules, and current asset counts. Structural pipeline editing is intentionally deferred until there is validation and safe write support for `Pipelines.json`.

Pipeline Controls also includes a batch render reset action. For a selected pipeline, it can move matching assets back to:

```text
pipeline_stage = RENDER
actor = AI_AGENT
ai_state = ASKED
```

The batch reset clears stale proxy queue items for each affected asset, removes old candidate render outputs and local render metadata, and stages fresh render asks. Locked assets are skipped unless `Include locked assets` is enabled. This is not a full regeneration; compiled prompts and prompt-inspection artifacts are preserved.

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
Backend = "stable_matrix"

[StableMatrix]
Profile = "body-reference-preview"

[AIHarvest]
AutoEnabled = true
IntervalSeconds = 300
```

When enabled, moving a Body-Reference asset from `PROMPT` to `RENDER` stages an auxiliary proxy ask with:

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

This task does not advance the asset or change `Final_Image_Prompt.md` if it fails.

When `LocalRender.AutoQueueAfterCondense` is true, harvesting a successful `prompt_condense` answer queues a review-only `local_image_render` ask. That ask writes a test image into `Local_Test_Renders/` and does not advance the asset.

Local render calls prefer `Condensed_Image_Prompt.md` when it exists. If no condensed prompt exists, they use `Final_Image_Prompt.md`.

Manual ChatGPT final render tasks always use `Final_Image_Prompt.md`. The condensed prompt is treated as a local-render aid, not the source of truth for the human ChatGPT render console.

## Local Rendering

Zet supports Stable Matrix and ComfyUI behind a backend-neutral local render request/result contract. Scene previews use `Scene_Render_IR.json` as the canonical structured input; prompt-only asset previews use their labeled prompt.

Local test renders remain review aids. They do not modify prompts, advance a pipeline stage, or overwrite final output.

See [Local Image Generation](Local_Image_Generation.md) for complete configuration, compilation, backend, queue, CLI, artifact, troubleshooting, and example documentation.

## Filesystem AI Proxy

Zet is a subscriber to the standalone filesystem proxy for asynchronous AI and local render work.

Queue root:

```text
BaseAIQueuePath / File_Proxy
```

Current queue folders:

```text
Ask/zet/
Running/zet/
Answer/zet/
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

Current standalone-proxy worker types:

- `ollama_generate`
- `local_image_render`

Manual ChatGPT renders use the separate `BaseAIQueuePath / Manual_Render_Queue` workflow.

`local_image_render` is backend-neutral. The concrete backend is selected by `render_preset`.

The earlier `comfyui_render` name is kept only for compatibility in the local image worker.

## Proxy Workers

Zet provides these one-job worker executables:

- `AI_Manager/ollama_proxy_worker.py`
- `AI_Manager/local_image_proxy_worker.py`

The standalone proxy owns polling, claiming, retries, and queue transitions. It invokes one Zet worker with `--job-dir`; the worker reads inputs and writes outputs without moving the job folder.

The local image handler:

- calls the backend-neutral local render dispatcher
- writes the expected image output into the supplied job folder
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

The standalone proxy is maintained in `C:/Users/Joe/Projects/AI_Proxy` and uses the same `BaseAIQueuePath / File_Proxy` queue as Zet.

HTTPS over Tailscale for the Render Console is intentionally on hold. The current practical deployment is localhost or plain HTTP over the private Tailscale network.

## Process Management

AI Controls includes a process-management section for the local Zet service set.

Current tracked processes:

- Zet Web Dashboard
- File Proxy
- Auto Harvester

The primary dashboard and service processes can be started, stopped, or restarted from AI Controls. Duplicate process counts are shown so accidental multiple workers or harvesters are easier to spot. The Render Console is integrated into the main FastAPI dashboard and no longer has a standalone server.

## Current Open Items

1. Revisit the Template Editor after the body-reference authoring workflow is clarified.
2. Add safe validated editing for `Pipelines.json` stages, actors, and worker modules when that becomes necessary.
3. Add a clean way to archive or hide old harvested answer folders.
4. Add dashboard visibility for harvested vs pending answers.
5. Add stale claim detection and recovery for interrupted workers.
6. Make standalone worker deployment reproducible instead of manually copying files into `C:/Users/Joe/Ollama`.
7. Improve body-reference prompt and/or ComfyUI workflow so renders obey tank top and shorts more reliably.
8. Add support for additional local image backends behind `Local_Render_Adapters/local_render.py`.
9. Add tests for harvester idempotency, stale answer handling, and automatic ask staging.
10. Keep moving reusable behavior out of dashboard code and into services.
