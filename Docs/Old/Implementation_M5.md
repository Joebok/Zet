# Codex Task: Zet Milestone 5 — Add Read-Only Dashboard

You are implementing Milestone 5 of the Zet project.

Read these planning documents first:

* `Docs/Zet.md`
* `Docs/Zet_Data_Schema_Object_Model_Decisions.md`

Also inspect the existing project files from Milestones 1, 2, 3, and 4.

## Scope

Implement only Milestone 5: Add Read-Only Dashboard.

This milestone creates the first Streamlit dashboard view for inspecting Zet asset records.

The dashboard must be read-only.

Do not implement Milestone 6 or later.

Do not add dashboard buttons that mutate state.

Do not implement `Move Next`, `Regenerate`, `Retry AI`, or `Promote to LOCKED` buttons yet.

Do not implement worker scripts.

Do not implement AI manager behavior.

Do not generate prompts.

Do not render images.

Do not copy image files.

Do not promote images to `LOCKED`.

This milestone is only about:

* launching a Streamlit dashboard
* selecting `Character` and `Phase`
* listing assets from `Assets.json`
* selecting one asset
* displaying asset details
* displaying derived paths
* optionally displaying existing candidate or locked images if they already exist
* optionally displaying existing marker/log files created by housekeeping

## Existing Expected Structure

Milestone 4 should already have created something close to:

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

## Required New or Updated Files

Create:

```text
zet/dashboard/
  __init__.py
  app.py
```

Optionally create helper files if they clearly improve readability:

```text
zet/dashboard/components.py
```

Do not create unrelated files.

Do not create dashboard action handlers that mutate state yet.

## Dependency

This milestone introduces Streamlit.

If dependency files already exist, update them appropriately.

If no dependency file exists, create a simple `requirements.txt` at the project root containing:

```text
streamlit
```

Do not add unnecessary dependencies.

Use the Python standard library plus existing project code wherever possible.

## Running the Dashboard

The dashboard should be runnable as:

```bash
streamlit run zet/dashboard/app.py
```

The dashboard should also work when launched from the project root.

Use `config.toml` from the project root by default.

For this milestone, it is acceptable to hard-code the default config path as:

```text
config.toml
```

Optionally, a sidebar text input may allow the config path to be changed.

## Dashboard Purpose

The dashboard is a read-only inspection tool for one `Character` / `Phase` at a time.

It should use the existing application/repository/service layer where possible.

Do not bypass the existing `ZetApp`, `AssetRepository`, or `PathService` unless there is a good reason.

The dashboard should not implement independent JSON parsing logic if the repository layer already provides it.

## Character and Phase Discovery

Implement simple filesystem-based discovery.

Use the configured `BaseCharacterPath`.

A character is a folder directly under `BaseCharacterPath`.

A phase is a folder directly under:

```text
BaseCharacterPath / Character
```

Example:

```text
_Lib/Characters/Tsaeytte/Adult/
```

The dashboard should show:

* a `Character` dropdown
* a `Phase` dropdown

The dashboard works with one selected `Character` and `Phase` at a time.

If no characters are found, show a clear message.

If a character has no phases, show a clear message.

Do not create missing character or phase folders.

## Main Dashboard Layout

Create a simple readable dashboard with this structure:

```text
Zet Dashboard

Sidebar or top controls:
  Config path
  Character dropdown
  Phase dropdown

Main area:
  Asset table
  Selected asset detail
  Path information
  Candidate / Locked image preview
  Housekeeping files preview
```

Keep the layout simple.

Do not over-design the UI.

Favor clarity over cleverness.

## Asset Table

Show the assets for the selected `Character` and `Phase`.

The asset table should include at least:

```text
asset_id
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
updated_at
```

It is acceptable to use:

```python
st.dataframe(...)
```

or another simple Streamlit table component.

The table should be read-only.

## Selecting an Asset

Provide a simple way to select an asset.

Preferred simple approach:

* show a `selectbox` containing asset IDs
* when an asset ID is selected, load that asset and display details below the table

Example label:

```text
Selected Asset
```

Do not rely on editable grid row selection for this milestone.

Keep selection explicit and reliable.

## Asset Detail Display

For the selected asset, display all asset fields.

A simple JSON-style or key/value display is fine.

Examples:

```python
st.json(...)
```

or

```python
st.table(...)
```

Display null values clearly.

## Derived Path Display

For the selected asset, show these derived paths:

```text
CharacterPath
CharacterAssetPath
PipelinePath
CandidateImagePath
LockedImagePath
```

Use `PathService` methods where possible.

Display whether each path exists.

Example display:

```text
PipelinePath:
_Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_1
Exists: yes
```

Do not create missing paths from the dashboard.

## Candidate and Locked Image Preview

For the selected asset:

* if `CandidateImagePath` exists, display the image with the caption `Candidate`
* if `LockedImagePath` exists, display the image with the caption `Locked`

If either image is missing, show a simple message such as:

```text
No candidate image found.
No locked image found.
```

Do not create image files.

Do not copy image files.

Do not promote images.

Use `st.image(...)` only for existing image files.

## Housekeeping Files Preview

If the selected asset’s `PipelinePath` exists, check for:

```text
_stage.txt
_history.log
```

If `_stage.txt` exists, display its contents under a heading:

```text
Stage Marker
```

If `_history.log` exists, display its contents under a heading:

```text
History Log
```

If either file is missing, show a simple message.

Do not create or update housekeeping files from the dashboard.

Do not call `HousekeepingService.prepare_stage(...)` from the dashboard in Milestone 5.

## Error Handling

The dashboard should show clear user-facing errors for:

* missing `config.toml`
* invalid `config.toml`
* missing `Assets.json`
* malformed `Assets.json`
* no characters found
* no phases found
* no assets found for the selected character-phase

Use Streamlit error/warning/info messages as appropriate:

```python
st.error(...)
st.warning(...)
st.info(...)
```

Do not crash with a raw stack trace for expected missing-file cases.

Unexpected exceptions may still be shown during development, but keep common errors readable.

## Read-Only Guarantee

The dashboard must not mutate project state.

In this milestone, the dashboard must not:

* write to `Assets.json`
* write to `Pipelines.json`
* create folders
* create files
* call `move_next()`
* call `run_housekeeping()`
* call `save_asset()`
* call state-change services
* call worker scripts
* call AI manager code
* copy images
* delete files

Reading files is allowed.

Displaying existing images is allowed.

Displaying existing text files is allowed.

## Optional Utility: Convert Assets to Rows

If useful, add a small helper function to convert a list of `Asset` objects into dictionaries suitable for table display.

Example:

```python
def asset_to_row(asset: Asset) -> dict:
    ...
```

Keep helper functions simple.

Do not add pandas unless Streamlit requires it for your chosen table display.

If pandas is already installed as a Streamlit dependency, it is acceptable to use it, but it is not required.

## Validation Requirements

After implementation, run or describe how to run:

```bash
streamlit run zet/dashboard/app.py
```

Then verify:

* the dashboard starts without import errors
* the dashboard loads `config.toml`
* the dashboard discovers `Tsaeytte`
* the dashboard discovers `Adult`
* the dashboard displays assets from `_Lib/Characters/Tsaeytte/Adult/Assets.json`
* the asset table shows expected fields
* selecting an asset displays its full details
* derived paths are displayed
* path existence is displayed
* existing candidate image is shown if present
* existing locked image is shown if present
* missing images show friendly messages
* `_stage.txt` is displayed if present
* `_history.log` is displayed if present
* no files are created or modified by opening the dashboard
* no asset state changes occur

## Guardrails

Do not implement beyond Milestone 5.

Do not create dashboard mutation buttons.

Do not implement `Move Next`.

Do not implement `Regenerate`.

Do not implement `Retry AI`.

Do not implement `Promote to LOCKED`.

Do not implement worker scripts.

Do not implement AI manager code.

Do not create AI queue folders.

Do not generate prompts.

Do not render images.

Do not copy images.

Do not modify JSON data from the dashboard.

Do not introduce a database.

Do not add unnecessary third-party dependencies.

Keep the implementation simple, readable, and easy to troubleshoot.

Favor clarity over cleverness.
