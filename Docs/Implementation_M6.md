# Codex Task: Zet Milestone 6 — Add Dashboard Actions

You are implementing Milestone 6 of the Zet project.

Read these planning documents first:

* `Docs/Zet.md`
* `Docs/Zet_Data_Schema_Object_Model_Decisions.md`

Also inspect the existing project files from Milestones 1, 2, 3, 4, and 5.

## Scope

Implement only Milestone 6: Add Dashboard Actions.

This milestone adds safe dashboard buttons that call the existing service layer.

Do not implement Milestone 7 or later.

Do not implement real worker scripts.

Do not implement AI manager behavior.

Do not generate prompts.

Do not render images.

Do not create AI queue requests.

Do not implement real pipeline work yet.

This milestone is only about adding dashboard controls for existing high-level asset actions.

## Important Design Rule

Dashboard buttons must not directly edit JSON files.

Dashboard buttons must not directly implement state-transition logic.

Dashboard buttons must call the same service-layer methods used by command-line scripts.

The Streamlit dashboard should be a thin UI layer over the existing application/service layer.

Preferred pattern:

```python
app = ZetApp.from_config(config_path)
asset_ref = app.asset(character, phase, asset_id)
asset_ref.move_next()
```

Not this:

```python
# Do not do this in the dashboard
asset.pipeline_stage = "PROMPT"
write_assets_json(...)
```

## Existing Expected Structure

Milestone 5 should already have created something close to:

```text
zet/
  __init__.py
  app.py

  dashboard/
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
    housekeeping_service.py

  scripts/
    __init__.py
    inspect_asset.py
    list_assets.py
    move_next.py
    run_housekeeping.py
```

Do not rewrite the whole project.

Modify it incrementally.

## Required Dashboard Actions

Add these dashboard actions for the selected asset:

```text
Move Next
Run Housekeeping
Retry AI
Regenerate
Promote to LOCKED
```

Implement them carefully according to the sections below.

If a supporting service method does not exist yet, create it in the appropriate service class and call it from the dashboard.

Do not put business logic directly in the dashboard.

## Action: Move Next

The `Move Next` button should call the existing `AssetRef.move_next()` method.

Expected behavior:

* advances the selected asset exactly one `PipelineStage`
* updates `actor`
* updates `asset_state` according to existing Milestone 3 rules
* updates `ai_state` according to existing Milestone 3 rules
* saves `Assets.json`
* runs housekeeping automatically, as implemented in Milestone 4
* refreshes the dashboard view after completion

Do not skip stages.

Do not invoke workers.

Do not generate prompts.

Do not render images.

Do not create AI queue folders.

## Action: Run Housekeeping

The `Run Housekeeping` button should call the existing housekeeping action, preferably:

```python
asset_ref.run_housekeeping()
```

Expected behavior:

* creates the selected asset’s `PipelinePath` if needed
* writes or updates `_stage.txt`
* appends `_history.log`
* does not modify `Assets.json`
* does not modify `Pipelines.json`

After completion, refresh the displayed housekeeping files.

## Action: Retry AI

Add a service-layer method for retrying AI work.

Preferred API:

```python
asset_ref.retry_ai()
```

Internally, delegate to an `AssetService.retry_ai(...)` method.

For Milestone 6, `Retry AI` should only reset fields. It should not create AI queue requests.

Required behavior:

* load the selected asset
* validate that the asset’s current `actor` is `AI_AGENT`
* set `ai_state` to `ASKED`
* set `last_ai_update` to a clear message such as:

  * `Retry requested from dashboard at 2026-06-27T14:10:00`
* update `updated_at`
* save `Assets.json` safely
* run housekeeping after saving
* return the updated asset

If the selected asset does not currently have `actor = AI_AGENT`, raise or display a clear friendly message:

```text
Retry AI is only available when Actor is AI_AGENT.
```

Do not send anything to an AI model.

Do not create files in `AI_Queue`.

## Action: Regenerate

Add a service-layer method for regenerating an asset.

Preferred API:

```python
asset_ref.regenerate()
```

Internally, delegate to an `AssetService.regenerate(...)` method.

For Milestone 6, regeneration should reset state only. It should not delete files and should not invoke workers.

Required behavior:

* load the selected asset
* set `asset_state` to `IN_PROGRESS`
* set `pipeline_stage` to `MANIFEST`
* set `actor` from `Pipelines.json` for the `MANIFEST` stage
* set `ai_state` to `None` unless the `MANIFEST` actor is `AI_AGENT`
* if `MANIFEST` actor is `AI_AGENT`, set `ai_state` to `ASKED`
* clear `error_code`
* clear `error_message`
* update `updated_at`
* save `Assets.json` safely
* run housekeeping after saving
* return the updated asset

Regenerate must not:

* delete existing `PipelinePath`
* delete candidate images
* delete locked images
* clear `_history.log`
* generate prompts
* render images
* create AI queue requests

For now, regeneration only resets the asset’s state to the start of the pipeline.

## Action: Promote to LOCKED

Add a service-layer method for promoting a candidate image to locked asset.

Preferred API:

```python
asset_ref.promote_to_locked()
```

Internally, delegate to an `AssetService.promote_to_locked(...)` method.

Required behavior:

1. Load the selected asset.
2. Determine `CandidateImagePath` using `PathService`.
3. Determine `LockedImagePath` using `PathService`.
4. Validate that the candidate image exists.
5. Create `CharacterAssetPath` if needed.
6. Copy the candidate image to `LockedImagePath`.
7. Set `asset_state` to `LOCKED`.
8. Set `pipeline_stage` to `RENDER_REVIEW`, unless the pipeline’s final stage is different.
9. Set `actor` to `HUMAN_AGENT`, or preserve the current actor if that is more consistent with existing design.
10. Set `ai_state` to `None`.
11. Clear `error_code`.
12. Clear `error_message`.
13. Update `updated_at`.
14. Save `Assets.json` safely.
15. Run housekeeping after saving.
16. Return the updated asset.

Use file copy, not move.

Do not delete the candidate image.

If the locked image already exists, overwrite it only after making a timestamped backup copy in the same folder.

Example locked backup filename:

```text
Body-Reference_Front.backup.20260627_141000.png
```

If the candidate image does not exist, display a clear friendly error:

```text
Cannot promote: candidate image does not exist.
```

Do not create a fake candidate image.

Do not render an image.

## Dashboard Layout Changes

In `zet/dashboard/app.py`, add an action section for the selected asset.

Suggested layout:

```text
Selected Asset Actions

[Move Next] [Run Housekeeping] [Retry AI] [Regenerate] [Promote to LOCKED]
```

Buttons may be arranged in columns.

After an action succeeds:

* show a success message
* reload the selected asset
* refresh the table/detail display
* refresh path information
* refresh image previews
* refresh housekeeping file previews

After an action fails:

* show a friendly error message
* do not crash with a raw stack trace for expected validation failures

## Button Availability

For Milestone 6, it is acceptable for all buttons to be visible all the time, as long as invalid actions show friendly errors.

Preferred behavior:

* `Retry AI` should be disabled or warn unless `actor = AI_AGENT`
* `Promote to LOCKED` should be disabled or warn unless the candidate image exists
* `Move Next` should warn if the asset is already at the final stage
* `Run Housekeeping` should always be allowed
* `Regenerate` should always be allowed

Keep this simple.

Do not over-engineer button state management.

## Service Layer Requirements

Update `AssetService` to include these methods if they do not already exist:

```python
move_next(character: str, phase: str, asset_id: int) -> Asset

run_housekeeping(character: str, phase: str, asset_id: int) -> Path

retry_ai(character: str, phase: str, asset_id: int) -> Asset

regenerate(character: str, phase: str, asset_id: int) -> Asset

promote_to_locked(character: str, phase: str, asset_id: int) -> Asset
```

If `run_housekeeping` already belongs elsewhere, the `AssetRef` may call `HousekeepingService` directly through app wiring. Keep the public API simple.

## AssetRef Requirements

Update `AssetRef` so this preferred API works:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")
asset = app.asset("Tsaeytte", "Adult", 1)

asset.move_next()
asset.run_housekeeping()
asset.retry_ai()
asset.regenerate()
asset.promote_to_locked()
```

`AssetRef` should not cache stale asset data.

Every action should load the current asset before acting.

## CLI Scripts

Create optional CLI scripts only if they are straightforward and help validation.

Preferred scripts:

```text
zet/scripts/retry_ai.py
zet/scripts/regenerate_asset.py
zet/scripts/promote_asset.py
```

Each should support:

```text
--config config.toml
--character Tsaeytte
--phase Adult
--asset-id 1
```

Do not spend excessive complexity on CLI scripts if the dashboard and service layer are complete.

If CLI scripts are created, they must call the same service layer methods as the dashboard.

## Safe Write Requirements

Continue using the safe JSON write behavior from Milestone 3.

When saving `Assets.json`:

* preserve `schema_version`
* preserve `next_asset_id`
* preserve other asset records
* save valid indented JSON
* use a temporary file
* validate the temporary JSON before replacing the original
* create a timestamped backup before mutation

Do not create backups for read-only dashboard loading.

## Filesystem Safety Requirements

Dashboard actions may create or update only the files that their service methods are explicitly allowed to touch.

Allowed:

* `Assets.json`, through safe repository save only
* `Assets.backup.*.json`
* `_stage.txt`
* `_history.log`
* `CharacterAssetPath`
* locked image file copied from candidate image
* backup copy of existing locked image, if overwriting

Not allowed:

* deleting candidate images
* deleting locked images
* deleting pipeline folders
* clearing `_history.log`
* modifying `Pipelines.json`
* creating AI queue requests
* generating prompt files
* generating rendered images

## Validation Requirements

After implementation, run or describe how to run:

```bash
streamlit run zet/dashboard/app.py
```

Then verify in the dashboard:

### Basic Display

* dashboard starts without import errors
* character dropdown works
* phase dropdown works
* asset table displays
* selected asset details display
* path display still works
* image preview still works
* `_stage.txt` and `_history.log` previews still work

### Move Next

Select an asset at `MANIFEST`.

Click `Move Next`.

Expected result:

* asset advances to `PROMPT`
* `asset_state` becomes `IN_PROGRESS`
* `actor` updates from `Pipelines.json`
* `updated_at` updates
* housekeeping runs
* `_stage.txt` reflects the new state
* `_history.log` gets a new line

### Run Housekeeping

Click `Run Housekeeping`.

Expected result:

* `_stage.txt` is written
* `_history.log` gets a new line
* `Assets.json` is not modified

### Retry AI

Select an asset whose `actor = AI_AGENT`.

Click `Retry AI`.

Expected result:

* `ai_state` becomes `ASKED`
* `last_ai_update` is updated
* `updated_at` is updated
* housekeeping runs
* no AI queue files are created

Select an asset whose `actor` is not `AI_AGENT`.

Click `Retry AI`.

Expected result:

* friendly error or warning
* no state change

### Regenerate

Click `Regenerate`.

Expected result:

* `pipeline_stage` becomes `MANIFEST`
* `asset_state` becomes `IN_PROGRESS`
* `actor` becomes the configured actor for `MANIFEST`
* `ai_state` is set according to the actor
* error fields are cleared
* housekeeping runs
* no files are deleted

### Promote to LOCKED

To test promotion, manually place a fake or real image file at the selected asset’s `CandidateImagePath`.

Click `Promote to LOCKED`.

Expected result:

* candidate image is copied to `LockedImagePath`
* candidate image remains in place
* `asset_state` becomes `LOCKED`
* `ai_state` becomes `None`
* error fields are cleared
* housekeeping runs
* locked preview displays the copied image

If no candidate image exists:

* friendly error is shown
* no state change occurs

## Guardrails

Do not implement beyond Milestone 6.

Do not implement real worker scripts.

Do not implement AI manager code.

Do not create AI queue request folders.

Do not generate prompts.

Do not render images.

Do not delete candidate images.

Do not delete locked images.

Do not modify `Pipelines.json`.

Do not introduce a database.

Do not add unnecessary third-party dependencies.

Keep implementation simple, readable, and easy to troubleshoot.

Favor clarity over cleverness.
