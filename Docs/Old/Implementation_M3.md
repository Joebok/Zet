# Codex Task: Zet Milestone 3 — Move Stages Without Doing Work

You are implementing Milestone 3 of the Zet project.

Read these planning documents first:

* `Docs/Zet.md`
* `Docs/Zet_Data_Schema_Object_Model_Decisions.md`

Also inspect the existing project files from Milestone 1 and Milestone 2.

## Scope

Implement only Milestone 3: Move Stages Without Doing Work.

This milestone adds controlled mutation of `Assets.json` so an asset can advance from one `PipelineStage` to the next.

Do not implement Milestone 4 or later.

Do not implement real housekeeping side effects yet.

Do not implement dashboard behavior.

Do not implement worker scripts.

Do not implement AI manager behavior.

Do not implement prompt generation.

Do not implement image rendering.

Do not copy image files.

Do not create candidate images.

This milestone is only about:

* loading pipeline definitions
* determining valid next stages
* updating asset state fields
* saving the updated asset back to `Assets.json`
* exposing a high-level `move_next()` API
* adding a CLI script to move an asset forward
* keeping all writes safe and inspectable

## Existing Expected Structure

Milestone 2 should already have created something close to:

```text
zet/
  __init__.py
  app.py

  models/
    __init__.py
    asset.py

  repositories/
    __init__.py
    asset_repository.py

  services/
    __init__.py
    config_service.py
    path_service.py

  scripts/
    __init__.py
    inspect_asset.py
    list_assets.py
```

Do not rewrite the whole project if this structure already exists.

Modify it incrementally.

## Required New or Updated Files

Create or update these files:

```text
zet/models/pipeline.py
zet/repositories/pipeline_repository.py
zet/services/state_machine.py
zet/services/asset_service.py
zet/scripts/move_next.py
```

You may also update existing files as needed:

```text
zet/app.py
zet/repositories/asset_repository.py
zet/models/__init__.py
zet/repositories/__init__.py
zet/services/__init__.py
```

Do not create unrelated files.

## Important Design Rules

### Asset Data Versus Actions

The raw `Asset` dataclass should remain mostly data-only.

Do not put state-transition business logic directly into the `Asset` dataclass.

State-changing behavior should live in service classes, especially `AssetService`.

The high-level API may expose convenient methods through an `AssetRef` wrapper.

Preferred external API:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")

asset = app.asset("Tsaeytte", "Adult", 1)
asset.move_next()
```

Internally, `AssetRef.move_next()` should delegate to `AssetService.move_next(...)`.

## Pipeline Definition Model

Create `zet/models/pipeline.py`.

Define a simple dataclass for pipeline definitions.

Expected fields:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class PipelineDefinition:
    name: str
    stages: list[str]
    actor_by_stage: dict[str, str]
    worker_by_stage: dict[str, str]
```

For Milestone 3, `worker_by_stage` is only loaded and preserved. It is not used to invoke workers yet.

## Pipeline Repository

Create `zet/repositories/pipeline_repository.py`.

`PipelineRepository` loads `Pipelines.json` for a selected `Character` and `Phase`.

Required methods:

```python
list_pipelines(character: str, phase: str) -> list[PipelineDefinition]

get_pipeline(character: str, phase: str, pipeline_name: str) -> PipelineDefinition
```

Requirements:

* use `PathService.character_path(character, phase)` to locate `Pipelines.json`
* parse the existing `Pipelines.json`
* return `PipelineDefinition` objects
* raise clear exceptions if:

  * `Pipelines.json` is missing
  * JSON is malformed
  * the requested pipeline does not exist
  * required keys are missing
  * a pipeline has no stages
  * a stage has no actor assignment

Do not mutate `Pipelines.json`.

## State Machine

Create `zet/services/state_machine.py`.

The state machine determines the next `PipelineStage`.

Implement a class such as:

```python
class StateMachine:
    def next_stage(self, pipeline: PipelineDefinition, current_stage: str) -> str:
        ...
```

Required behavior:

* validate that `current_stage` exists in `pipeline.stages`
* return the next stage in `pipeline.stages`
* if `current_stage` is the final stage, return the final stage again or raise a clear exception

Preferred behavior:

* if the asset is already at the final stage, raise a clear exception such as:

```text
Asset is already at final pipeline stage: RENDER_REVIEW
```

Do not silently wrap around to the first stage.

Do not skip stages.

Do not implement optional-stage logic yet.

The stage order should come entirely from `Pipelines.json`.

## Asset Repository Save Support

Update `zet/repositories/asset_repository.py`.

Milestone 2 may have implemented read-only behavior. Milestone 3 requires save behavior.

Add:

```python
save_asset(asset: Asset) -> None
```

Required behavior:

* load the existing `Assets.json`
* find the matching record by `asset_id`
* replace only that asset record
* preserve other top-level JSON fields such as `schema_version` and `next_asset_id`
* preserve other asset records unchanged
* write the file back safely

## Safe JSON Writes

Implement safe writes for `Assets.json`.

At minimum:

1. Serialize the new JSON with indentation.
2. Write to a temporary file next to `Assets.json`.
3. Read the temporary file back to confirm it is valid JSON.
4. Replace the original `Assets.json` with the temporary file.

Preferred:

* before replacing the original, write a timestamped backup copy.

Example backup filename:

```text
Assets.backup.20260627_141000.json
```

Backup files should live next to `Assets.json`.

Do not create excessive backups for read-only operations.

Only create backups when actually saving a changed asset.

Use the Python3 standard library.

## Asset Service

Create `zet/services/asset_service.py`.

`AssetService` should coordinate asset actions.

Required constructor dependencies:

* `AssetRepository`
* `PipelineRepository`
* `StateMachine`

Additional dependencies are acceptable if already established by Milestone 2.

Implement:

```python
move_next(character: str, phase: str, asset_id: int) -> Asset
```

Required behavior for `move_next`:

1. Load the asset by `asset_id`.
2. Load the asset’s pipeline definition from `Pipelines.json`.
3. Validate the asset’s current `pipeline_stage`.
4. Determine the next stage using `StateMachine`.
5. Update `asset.pipeline_stage`.
6. Update `asset.actor` based on `pipeline.actor_by_stage[next_stage]`.
7. Update `asset.updated_at` to the current local timestamp in ISO-like format.
8. Update `asset.asset_state` according to the rules below.
9. Update `asset.ai_state` according to the rules below.
10. Save the asset using `AssetRepository.save_asset`.
11. Return the updated `Asset`.

## AssetState Rules for Milestone 3

Use these simple rules:

* If an asset moves out of `MANIFEST`, set `asset_state` to `IN_PROGRESS`.
* If an asset moves into the final pipeline stage, keep `asset_state` as `IN_PROGRESS` for now.
* Do not set `asset_state` to `LOCK_REVIEW` yet.
* Do not set `asset_state` to `LOCKED`.
* Do not set `asset_state` to `BLOCKED` unless an error handler is explicitly invoked.
* If `pipeline_stage` is `ERROR`, `move_next()` should raise a clear exception and should not modify the asset.

Rationale: Milestone 3 only tests stage movement. Final review and locking behavior comes later.

## AI_State Rules for Milestone 3

Use these simple rules:

* If the new `actor` is `AI_AGENT`, set `ai_state` to `ASKED`.
* If the new `actor` is not `AI_AGENT`, set `ai_state` to `None`.

Do not implement AI manager behavior.

Do not create AI queue files.

Do not send anything to an AI model.

## Actor Rules

Valid `actor` values are:

```text
PYTHON
AI_AGENT
HUMAN_AGENT
```

When moving to a new stage:

* look up the actor in `pipeline.actor_by_stage`
* assign that actor to `asset.actor`
* raise a clear exception if no actor is defined for the new stage
* raise a clear exception if the actor is not one of the valid actor values

## Updating `ZetApp` and `AssetRef`

Update `zet/app.py`.

Ensure this works:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")

asset_ref = app.asset("Tsaeytte", "Adult", 1)
updated_asset = asset_ref.move_next()
```

`AssetRef.move_next()` should call `AssetService.move_next(...)`.

After moving, `AssetRef.get()` should return the updated asset if called again.

Do not cache stale asset data in `AssetRef`.

## CLI Script

Create `zet/scripts/move_next.py`.

It should be runnable as:

```bash
python3 -m zet.scripts.move_next --character Tsaeytte --phase Adult --asset-id 1
```

It should also support:

```bash
--config config.toml
```

Default config path:

```text
config.toml
```

Use `argparse`.

The script should:

1. load the app from config
2. move the asset to the next stage
3. print a concise before/after summary

Example output:

```text
Asset 1 moved:
  Pipeline: Body-Reference
  Stage: MANIFEST -> PROMPT
  Actor: Python3 -> PYTHON
  AssetState: NEW -> IN_PROGRESS
  AI_State: None -> None
```

If the asset cannot be moved, print a clear error message and exit with a non-zero status code.

## Validation Requirements

After implementation, run or describe how to run:

```bash
python3 -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
python3 -m zet.scripts.move_next --character Tsaeytte --phase Adult --asset-id 1
python3 -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
```

Expected result:

* before moving, asset 1 is at `MANIFEST`
* after moving, asset 1 is at `PROMPT`
* `actor` is updated according to `Pipelines.json`
* `asset_state` becomes `IN_PROGRESS`
* `updated_at` is populated
* `Assets.json` remains valid JSON
* a backup file is created only when saving
* no `Pipelines.json` mutation occurs
* no prompt files are generated
* no image files are generated
* no AI queue files are generated

Also test repeated movement:

```bash
python3 -m zet.scripts.move_next --character Tsaeytte --phase Adult --asset-id 1
python3 -m zet.scripts.move_next --character Tsaeytte --phase Adult --asset-id 1
```

Expected result:

* stage advances one step per command
* stages are not skipped
* actor is updated each time
* when the asset enters a stage assigned to `AI_AGENT`, `ai_state` becomes `ASKED`

## Guardrails

Do not implement beyond Milestone 3.

Do not implement housekeeping side effects.

Do not create worker scripts.

Do not invoke worker scripts.

Do not create dashboard code.

Do not implement AI manager code.

Do not create AI queue request folders.

Do not generate prompts.

Do not render images.

Do not promote images to `LOCKED`.

Do not implement regeneration yet.

Keep the implementation simple, readable, and easy to troubleshoot.

Favor clarity over cleverness.

