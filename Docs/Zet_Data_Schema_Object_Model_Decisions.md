# Zet Data Schema and Object Model Decisions

This document records the current implementation decisions for Zet. Current implementation takes precedence over earlier planning notes.

## Storage Decision

Zet remains file-backed.

Primary mutable data files:

- `Assets.json`
- `Pipelines.json`
- queue manifests under `BaseAIQueuePath / Ollama_Proxy`
- pipeline working files under `_Lib/Pipelines/...`

Primary formats:

- JSON for structured state and manifests
- Markdown for character templates, compiled prompts, review notes, and human-readable logs
- image files for candidate and locked outputs

No SQL database is currently used.

This remains appropriate because Zet is still a local/personal workflow tool with modest data volume and a strong need for inspectable, manually repairable files.

## Configuration Decision

`config.toml` is the root configuration file.

Shared base paths live in `[BaseFolders]`.

Machine-specific overrides live in:

```toml
[BaseFoldersByPlatform.Windows]
[BaseFoldersByPlatform.Darwin]
```

The current intended use is:

- keep project-local paths relative
- override only external machine-specific paths
- especially override `BaseAIQueuePath`

`ConfigService` applies platform overrides based on `platform.system()` and expands `~` and environment variables.

Current resolved path behavior:

- Windows uses `C:/Users/Joe/Library/CloudStorage/Dropbox/AI_Queue/`
- macOS uses `/Users/joe/Library/CloudStorage/Dropbox/AI_Queue/`
- fallback is `_Lib/AI_Queue/`

## Asset Identity Decision

Every asset has a stable `asset_id`.

`asset_id` is the primary programmatic handle.

The logical identity remains described by:

- `character`
- `phase`
- `pipeline`
- `body_view`
- `head_view`
- `costume`
- `expression`

Code should prefer `asset_id` when selecting or mutating a specific asset.

## Asset Path Decision

`asset_id` is included in pipeline working paths.

Current pattern:

```text
_Lib/Pipelines/{Character}/{Phase}/{Pipeline}/{BodyView}/{HeadView-or-_}/Asset_{AssetID}/
```

Example:

```text
_Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_1/
```

This prevents collisions between assets that share views but differ by future fields such as costume, expression, prompt variant, or render pass.

## Asset Dataclass Decision

Assets are represented by the `Asset` dataclass in `zet/models/asset.py`.

Current fields:

```text
asset_id
character
phase
pipeline
body_view
head_view
costume
expression
asset_state
pipeline_stage
actor
ai_state
final_image_output
last_ai_update
error_code
error_message
updated_at
```

The dataclass is intentionally mostly data-only.

Filesystem-changing behavior belongs in services or wrappers, not in the raw dataclass.

## Repository Decision

Repositories own file persistence and lookup.

Current repositories:

- `AssetRepository`
- `PipelineRepository`
- `TurnaroundRepository`
- `IdentityKeyRepository`
- `AuxiliaryResourceRepository`

`AssetRepository` responsibilities:

- load `Assets.json`
- find an asset by `asset_id`
- save asset changes
- write JSON safely

`PipelineRepository` responsibilities:

- load `Pipelines.json`
- return configured pipeline definitions

Repositories should not contain pipeline business logic.

## Service Layer Decision

Services own meaningful actions and workflows.

Current important services:

- `PathService`
- `StateMachine`
- `HousekeepingService`
- `WorkerService`
- `AssetService`
- `AIProxyService`
- `AIAnswerHarvester`
- `PromptReviewService`
- `ConfigService`

The service layer is the boundary that should be reusable by scripts, the FastAPI dashboard, and any legacy/diagnostic UI.

The dashboard must not become the home of reusable business logic.

## Regenerate Cleanup Decision

`Regenerate` means the asset starts over from scratch.

Before setting the asset back to `MANIFEST`, Zet clears:

- the asset's `PipelinePath`
- stale proxy queue folders for that asset
- generated Body-Reference prompt artifacts for the asset view
- `Final_Image_Prompt.md`
- `Condensed_Image_Prompt.md`
- `Compiled_Sections.md`
- `dependency_manifest.json`
- `Prompt_Review.md`
- `Image_Review.md`
- `Local_Test_Renders/`

This prevents old condensed prompts, ComfyUI/local test images, harvested answers, or generated prompt files from being reused after a regeneration request.

## Application Facade Decision

`ZetApp` is the application facade.

`AssetRef` is the asset-specific convenience wrapper.

Current pattern:

```python
app = ZetApp.from_config("config.toml")
asset_ref = app.asset("Tsaeytte", "Adult", 1)

asset_ref.get()
asset_ref.move_next()
asset_ref.regenerate()
asset_ref.retry_ai()
asset_ref.promote_to_locked()
asset_ref.pipeline_path()
asset_ref.candidate_image_path()
asset_ref.locked_image_path()
```

Prompt review and local render operations are exposed through `PromptReviewService` and facade methods.

## Reference Slot Decision

Assets may carry structured image references in `reference_files`.

The persisted `Asset` record also includes `identity_key_id`, `expression_definition_path`, and `costume_path` for workflows that own those resources.

Head-fitment uses explicit reference slots instead of searching markdown for image filenames:

- `body_reference`: a locked Body-Reference output image
- `headshot`: a headshot reference image stored under `Reference_Images/Headshots/`

These slots are selected during the `MANIFEST` stage from the FastAPI dashboard Manifest page. The selected references are saved on the asset and propagated into manual ChatGPT render asks through `ask_manifest.json.reference_files`.

Template text should describe how references are used. It should not be the source of truth for which image files are attached to a render task.

Head-fitment prompt compilation is static. It does not use ComfyUI. The `PROMPT` stage writes `Final_Image_Prompt.md` from the selected template sections and then advances directly to the manual ChatGPT `RENDER` stage.

## Pipeline Configuration Decision

Pipeline definitions live in `Pipelines.json` under the selected character phase.

Current pipeline definition fields:

- `stages`
- `actor_by_stage`
- `worker_by_stage`

Asset progress belongs in `Assets.json`.

Pipeline rules belong in `Pipelines.json`.

The current configured pipelines are:

- `Body-Reference`
- `Head-Image`
- `Character-Assembly`

The current stage sequence for these pipelines is:

```text
MANIFEST -> PROMPT -> RENDER -> RENDER_REVIEW
```

## Actor Decision

Allowed actors:

- `PYTHON`
- `AI_AGENT`
- `HUMAN_AGENT`

`PYTHON` stages can be advanced or worked locally.

`HUMAN_AGENT` stages require dashboard review or action.

`AI_AGENT` stages are asynchronous and use the filesystem proxy.

When an asset enters an `AI_AGENT` stage through `AssetService.move_next()`, Zet stages an ask folder automatically.

## AI State Decision

`ai_state` currently uses `ASKED` when an asset is waiting on proxy work.

Older planned values such as `WAITING` and `ANSWERED` are not actively used.

Richer operational state is represented by queue folders:

- `Ask`
- `Claimed`
- `Answer`
- `Failed`

`last_ai_update` stores a human-readable message containing the ask id and attempt id, such as:

```text
AI ask staged: Ask_Asset_1_RENDER_20260701_062417 (20260701_062417_1_RENDER)
```

The harvester uses this attempt id to detect stale answers when possible.

## Prompt Inspection Decision

Prompt inspection behavior lives in `PromptReviewService` and applies to queued `RENDER` tasks. `PROMPT_REVIEW` is unsupported as a pipeline stage.

Prompt inspection context includes:

- asset
- prompt path
- prompt text
- prompt inspection artifact path
- prompt candidate paths
- latest local test render

Prompt inspection local test renders do not advance asset state.

## Body-Reference Compiler Decision

Body-reference prompt generation is config-driven.

Current key config/scripts:

- `Config/Prompt_Task_Bundles.json`
- `Config/Prompt_Templates/body_reference_v1.md`
- `Config/Prompt_Section_Metadata.json`
- `Config/Prompt_Review_Checklists.json`
- `Scripts/Run_Body_Reference_Jobs.py`
- `Scripts/Review_Prompt_Static.py`

Compiler behavior should assemble configured sections and templates. It should not silently correct content problems from a character template.

If Tsaeytte’s template says the wrong thing, edit Tsaeytte’s template.

## Local Render Adapter Decision

Local image generation must be backend-neutral outside the adapter layer.

Current adapter package:

```text
Scripts/Local_Render_Adapters/
```

Current files:

- `common.py`
- `local_render.py`
- `comfyui_adapter.py`
- `stable_matrix_adapter.py`
- `__init__.py`

`local_render.render_image(...)` is the generic entrypoint.

Reusable render contracts and ComfyUI compilation/execution belong under `zet/services`; adapter modules connect those services to the compatibility entrypoint and queue worker.

The active backend comes from `config.toml` `LocalRender.Backend`. The selected backend's profile comes from `Config/Local_Render_Presets.json`.

Current profile backends:

```json
{
  "stable-example": {"backend": "stable_matrix"},
  "comfyui-example": {"backend": "comfyui"}
}
```

Future image generation backends should add new adapter modules and one dispatch branch in `local_render.py`, without changing dashboard code, asset state logic, or queue contract.

## Prompt Condense Decision

Prompt condensing is an optional auxiliary AI task.

Config:

```toml
[PromptCondense]
Enabled = true
PromptFile = "Config/Prompt_Condense_Tasks/body_reference_condense.md"

[AIModels]
PromptCondense = "structured-reasoning:latest"

[LocalRender]
AutoQueueAfterCondense = true
Preset = "body-reference-preview"
```

The condense request text is editable in `Config/Prompt_Condense_Tasks/body_reference_condense.md`.

When enabled, moving a Body-Reference asset from `PROMPT` to `RENDER` stages a filesystem proxy ask.

The ask uses:

```text
worker_type = ollama_generate
task_type = prompt_condense
auxiliary = true
expected_output = Condensed_Image_Prompt.md
```

The condense answer is harvested into the prompt output directory as:

```text
Condensed_Image_Prompt.md
```

Auxiliary condense answers do not advance pipeline state and do not mutate `Final_Image_Prompt.md`.

When `LocalRender.AutoQueueAfterCondense` is true, harvesting a successful condense answer queues an auxiliary `local_image_render` ask for prompt inspection. The resulting image is copied into `Local_Test_Renders/` and does not advance the asset.

Local image rendering prefers `Condensed_Image_Prompt.md` when present and falls back to `Final_Image_Prompt.md`.

## File Proxy Decision

The filesystem proxy is the boundary between Zet state and external work.

Queue root:

```text
BaseAIQueuePath / Ollama_Proxy
```

Queue folders:

- `Ask`
- `Claims`
- `Claimed`
- `Answer`
- `Failed`
- `Control`
- `Monitor`

Ask folders contain `ask_manifest.json` plus input files.

Answer folders contain `answer_manifest.json`, output files, and eventually `harvest_manifest.json`.

Workers must not edit `Assets.json`.

Workers must not advance pipeline stages.

Workers only:

- claim asks
- perform external work
- write answer folders

Zet harvests answers and applies state changes.

## Worker Type Decision

Current worker types:

- `ollama_generate`
- `local_image_render`

`ollama_generate` is handled by:

```text
AI_Manager/proxy_worker.py
AI_Manager/ollama_proxy_worker.py
```

`ollama_generate` can be used for stage-advancing text asks or auxiliary tasks such as `prompt_condense`.

`local_image_render` is handled by:

```text
AI_Manager/proxy_worker.py
AI_Manager/local_image_proxy_worker.py
```

`AI_Manager/proxy_worker.py` is the preferred deployed worker because it claims exactly one supported ask at a time and dispatches text or image work serially on the machine.

The queue contract should use `local_image_render`, not `comfyui_render`.

`comfyui_render` is accepted only for compatibility.

## Render Metadata Decision

Local image render workers write:

```text
LOCAL_RENDER_METADATA.json
```

Older:

```text
COMFYUI_RENDER_METADATA.json
```

is still accepted by the harvester for compatibility.

The harvester copies render metadata into `PipelinePath` when present.

## Harvesting Decision

`AIAnswerHarvester` is responsible for applying completed answer folders.

On successful answer harvest it:

- reads `answer_manifest.json`
- reads `ask_manifest.json`
- validates character and phase
- checks attempt id when available
- copies expected output to `PipelinePath`
- copies local render metadata when available
- updates asset AI fields
- advances to the next pipeline stage
- runs housekeeping
- writes `harvest_manifest.json`

Harvested answers remain in `Answer/`.

Queue status should ignore answer folders with `harvest_manifest.json`.

The harvester can re-apply a previously harvested successful answer if:

- the answer status is `SUCCESS`
- the asset is back at the same AI stage
- the asset still expects the same attempt id

This is a recovery feature, not the normal flow.

## Dashboard Boundary Decision

The FastAPI dashboard is the primary operations UI. The old Streamlit dashboard and standalone Render Console are retired.

The dashboard may own:

- layout
- session state
- navigation
- widget state
- rendering tables/images/text
- calling app/service methods

It should not own:

- prompt file discovery
- pipeline transitions
- render orchestration
- answer harvesting logic
- file proxy business rules
- reusable path derivation

This boundary is also recorded in `AGENTS.md`.

## Milestone Status

### Completed Or Mostly Working

- file-backed schema
- `Asset` dataclass
- asset and pipeline repositories
- path derivation
- state machine
- housekeeping
- FastAPI dashboard
- dashboard actions
- prompt inspection page
- render review page
- integrated render console
- body-reference prompt compiler integration
- optional prompt-inspection local test renders
- AI proxy ask staging
- local image render worker
- ComfyUI backend adapter
- answer harvesting
- cross-platform queue path config

### Partially Working

- worker deployment outside the repo
- stale worker/claim recovery
- queue observability
- body-reference prompt/render quality

### Not Yet Implemented Or Needs Design

- Template Editor migration after the body-reference authoring workflow is clarified
- automated worker packaging/deployment
- richer AI/proxy state model
- answer archival/retention policy
- multi-backend local image generation beyond ComfyUI
- formal tests for pipeline transitions and harvesting edge cases
- production-grade frontend/API separation

## Current Open Questions

1. Should old harvested answer folders be archived out of `Answer/`, or is `harvest_manifest.json` enough?
2. Should the AI proxy root continue to be called `Ollama_Proxy` now that it also handles local image rendering?
3. How should workers be deployed and updated on the AI machine?
4. Should worker heartbeat/monitoring be generalized beyond Ollama monitor tests?
5. Should `ai_state` remain simple, or should it mirror queue states like `CLAIMED`, `ANSWER_READY`, and `FAILED`?
6. How should prompt/render artifacts be versioned when an asset regenerates multiple times?
7. Which fields are needed for multiple candidate renders per asset?
