# Codex Task: Zet Milestone 4 — Add Housekeeping

You are implementing Milestone 4 of the Zet project.

Read these planning documents first:

* `Docs/Zet.md`
* `Docs/Zet_Data_Schema_Object_Model_Decisions.md`

Also inspect the existing project files from Milestones 1, 2, and 3.

## Scope

Implement only Milestone 4: Add Housekeeping.

This milestone adds controlled filesystem side effects after an asset changes `PipelineStage`.

Housekeeping should prepare the asset’s `PipelinePath` and write simple inspection/debug marker files.

Do not implement Milestone 5 or later.

Do not implement the Streamlit dashboard.

Do not implement worker scripts.

Do not implement AI manager behavior.

Do not generate prompts.

Do not render images.

Do not copy candidate images.

Do not promote images to `LOCKED`.

Do not implement regeneration yet unless a placeholder already exists and remains non-functional.

This milestone is only about:

* creating or verifying `PipelinePath`
* recording the current stage in simple marker files
* calling housekeeping automatically after `move_next()`
* exposing a CLI way to run housekeeping manually for one asset
* keeping all behavior simple, visible, and safe

## Existing Expected Structure

Milestone 3 should already have created something close to:

```text
zet/
  __init__.py
  app.py

  models/
    __init__.py
    asset.py
    pipeline.py

  repositories/
    __init__.py
    asset_repository.py
    pipeline_repository.py

  services/
    __init__.py
    config_service.py
    path_service.py
    state_machine.py
    asset_service.py

  scripts/
    __init__.py
    inspect_asset.py
    list_assets.py
    move_next.py
```

Do not rewrite the whole project.

Modify it incrementally.

## Required New or Updated Files

Create:

```text
zet/services/housekeeping_service.py
zet/scripts/run_housekeeping.py
```

Update as needed:

```text
zet/app.py
zet/services/asset_service.py
zet/services/__init__.py
```

Do not create unrelated files.

## Housekeeping Design

Housekeeping is a separate service.

Create `zet/services/housekeeping_service.py`.

Implement a class named `HousekeepingService`.

It should be responsible for preparing the filesystem for the asset’s current `PipelineStage`.

Housekeeping should use `PathService` to derive paths.

Do not duplicate path-building logic inside `HousekeepingService`.

## Required `HousekeepingService` API

Implement:

```python
class HousekeepingService:
    def __init__(self, path_service):
        ...

    def prepare_stage(self, asset: Asset) -> Path:
        ...
```

`prepare_stage(asset)` should:

1. Determine the asset’s `PipelinePath` using `PathService.pipeline_path(asset)`.
2. Create the `PipelinePath` directory if it does not exist.
3. Write or update a `_stage.txt` marker file in `PipelinePath`.
4. Append an entry to a `_history.log` file in `PipelinePath`.
5. Return the `PipelinePath`.

Use `pathlib.Path`.

Use only the Python standard library.

## PipelinePath Pattern

Use the path pattern already established in prior milestones:

```text
_Lib/Pipelines/{Character}/{Phase}/{Pipeline}/{BodyView}/{HeadView or _}/Asset_{AssetID}/
```

If `head_view` is null or blank, use `_`.

Example:

```text
_Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_1/
```

Do not change the path pattern.

## `_stage.txt`

The `_stage.txt` file should be overwritten each time housekeeping runs.

It should contain readable information about the asset’s current state.

Required contents:

```text
AssetID: 1
Character: Tsaeytte
Phase: Adult
Pipeline: Body-Reference
BodyView: Front
HeadView: _
PipelineStage: PROMPT
Actor: PYTHON
AssetState: IN_PROGRESS
AI_State: None
UpdatedAt: 2026-06-27T14:10:00
```

Use the asset’s actual values.

If `head_view` is null or blank, display `_`.

If `ai_state` is null, display `None`.

Do not include JSON in `_stage.txt`.

Keep it human-readable.

## `_history.log`

The `_history.log` file should be appended to each time housekeeping runs.

Each line should be a simple, human-readable event entry.

Example:

```text
2026-06-27T14:10:00 | Asset 1 | Stage=PROMPT | Actor=PYTHON | AssetState=IN_PROGRESS | AI_State=None
```

Use the current timestamp when writing the log entry.

Do not erase previous history.

Do not make this complex.

This is not a formal audit system. It is just a troubleshooting aid.

## When Housekeeping Runs

Update `AssetService.move_next(...)`.

After the updated asset is saved to `Assets.json`, call:

```python
housekeeping_service.prepare_stage(asset)
```

The order should be:

1. load asset
2. determine next stage
3. update asset fields
4. save asset to `Assets.json`
5. run housekeeping for the updated asset
6. return updated asset

This means the filesystem marker reflects the saved asset state.

## Dependency Injection

Update the service wiring so `AssetService` receives a `HousekeepingService`.

If existing constructors are simple, keep them simple.

Do not introduce a complex framework.

The preferred result is that this works:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")
asset = app.asset("Tsaeytte", "Adult", 1)

asset.move_next()
```

After `move_next()`, the asset’s `PipelinePath` should exist and should contain:

```text
_stage.txt
_history.log
```

## Manual Housekeeping CLI

Create `zet/scripts/run_housekeeping.py`.

It should be runnable as:

```bash
python -m zet.scripts.run_housekeeping --character Tsaeytte --phase Adult --asset-id 1
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
2. load the asset
3. run housekeeping for the asset’s current state
4. print the path that was prepared

Example output:

```text
Housekeeping complete for Asset 1:
  PipelinePath: _Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_1
  Wrote: _stage.txt
  Appended: _history.log
```

If the asset cannot be found, print a clear error and exit with a non-zero status code.

## Updating `ZetApp` and `AssetRef`

Update `zet/app.py` as needed.

Ensure this still works:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")

asset_ref = app.asset("Tsaeytte", "Adult", 1)
asset_ref.show()
asset_ref.move_next()
```

Add this read/action method if it fits the existing design:

```python
asset_ref.run_housekeeping()
```

`AssetRef.run_housekeeping()` should:

1. load the current asset
2. call `HousekeepingService.prepare_stage(asset)`
3. return the prepared `PipelinePath`

Do not cache stale asset data in `AssetRef`.

## No Worker Invocation Yet

Housekeeping should not invoke worker scripts.

Housekeeping should not know how to perform stage work.

For example:

* entering `MANIFEST` should not generate a manifest
* entering `PROMPT` should not generate a prompt
* entering `RENDER` should not render an image
* entering an `AI_AGENT` stage should not create an AI queue item

Those behaviors come later.

For Milestone 4, housekeeping only prepares folders and writes marker files.

## Safe Filesystem Behavior

Housekeeping may create:

```text
PipelinePath/
  _stage.txt
  _history.log
```

Housekeeping must not delete files.

Housekeeping must not modify `Assets.json`.

Housekeeping must not modify `Pipelines.json`.

Housekeeping must not modify files outside the asset’s `PipelinePath`.

Housekeeping must not overwrite prompt files, image files, manifest files, or AI result files.

Only `_stage.txt` may be overwritten.

Only `_history.log` may be appended.

## Validation Requirements

After implementation, run or describe how to run:

```bash
python -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
python -m zet.scripts.run_housekeeping --character Tsaeytte --phase Adult --asset-id 1
python -m zet.scripts.move_next --character Tsaeytte --phase Adult --asset-id 1
python -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
```

Expected result:

* `run_housekeeping` creates the asset’s `PipelinePath` if needed.
* `run_housekeeping` writes `_stage.txt`.
* `run_housekeeping` appends `_history.log`.
* `move_next` still advances exactly one stage.
* after `move_next`, housekeeping automatically runs for the new stage.
* `_stage.txt` reflects the current saved asset state.
* `_history.log` contains one line per housekeeping run.
* no prompt files are generated.
* no image files are generated.
* no AI queue folders are created.
* no dashboard files are created.
* `Assets.json` remains valid JSON.
* `Pipelines.json` is not modified.

Also test an asset whose `head_view` is null.

Expected result:

```text
HeadView: _
```

and the path uses:

```text
/_/
```

## Guardrails

Do not implement beyond Milestone 4.

Do not create dashboard code.

Do not create worker scripts.

Do not implement AI manager code.

Do not create AI queue request folders.

Do not generate prompts.

Do not render images.

Do not copy images.

Do not promote images to `LOCKED`.

Do not implement regeneration.

Do not introduce a database.

Do not add third-party dependencies.

Keep the implementation simple, readable, and easy to troubleshoot.

Favor clarity over cleverness.
