# Zet Data Schema and Object Model Decisions

## Core Data Storage Decision

Zet will use file-based data storage.

The primary data format will be `.json`.

This keeps the project:

- simple to inspect
- easy to repair manually
- easy to back up
- independent of a database server
- appropriate for a personal project with modest data volume

No SQL database or DB server will be used for the initial implementation.

## Asset Identity Decision

Every asset will have a stable `AssetID`.

`AssetID` will be the primary programmatic handle for an asset.

The logical asset identity is still formed from fields such as:

- `Character`
- `Phase`
- `Pipeline`
- `BodyView`
- `HeadView`
- `Costume`
- `Expression`

However, code should generally interact with assets by `AssetID`.

Example API goal:

```python
asset = app.asset(17)
asset.move_next()
```

## AssetID in Paths

`AssetID` will be included in pipeline working paths.

This avoids collisions between assets that share the same `Character`, `Phase`, `Pipeline`, and view information but differ by costume, expression, or other future fields.

Preferred path pattern:

```text
_Lib/Pipelines/{Character}/{Phase}/{Pipeline}/{BodyView}/{HeadView or _}/Asset_{AssetID}/
```

Example:

```text
_Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_17/
```

## Repository / Service Separation

Zet will separate data access from actions.

### `AssetRepository`

`AssetRepository` is responsible for reading and writing asset records.

Its responsibilities include:

- loading `Assets.json`
- finding an asset by `AssetID`
- saving asset changes
- creating new asset records
- performing safe JSON writes
- optionally creating backups before mutation

`AssetRepository` should not contain pipeline business logic.

### `AssetService`

`AssetService` is responsible for meaningful asset actions.

Its responsibilities include:

- moving an asset to the next `PipelineStage`
- regenerating an asset
- promoting a candidate image to `LOCKED`
- retrying AI work
- invoking housekeeping
- invoking worker scripts
- applying state-transition rules

`AssetService` uses `AssetRepository` to load and save data, but the action logic belongs in the service layer.

## Data Object Decision

An `Asset` should be represented as a Python object using a `dataclass`.

The `Asset` object should mostly contain data fields.

The preferred design is not to put filesystem-changing behavior directly inside the raw `Asset` dataclass.

Instead, use a higher-level wrapper or application API so code can still be clean and expressive.

Preferred API goal:

```python
app = ZetApp.from_config("config.toml")

asset = app.asset(17)

asset.show()
asset.move_next()
asset.regenerate()
asset.retry_ai()
asset.promote_to_locked()
asset.pipeline_path()
asset.candidate_image_path()
asset.locked_image_path()
```

Internally, this high-level API may call:

- `AssetRepository`
- `PipelineRepository`
- `AssetService`
- `PathService`
- `HousekeepingService`
- `AIStateService`

## Pipeline Configuration Decision

Pipeline definitions should live in `Pipelines.json`.

`Pipelines.json` should describe how each pipeline behaves.

It should contain information such as:

- valid stages for each pipeline
- actor assigned to each stage
- worker script assigned to each stage
- optional review stages
- allowed state transitions

Asset-specific progress should remain in `Assets.json`.

Pipeline configuration should remain in `Pipelines.json`.

## High-Level Milestones

### Milestone 1: Static Schema

Create the initial file structure and static data files.

Deliverables:

- `config.toml`
- `Assets.json`
- `Pipelines.json`
- a few manually-created fake asset records

Goal:

Confirm the schema is understandable and manually editable before writing much code.

### Milestone 2: Load and Inspect Assets

Create the first Python data model and repository layer.

Deliverables:

- `Asset` dataclass
- `AssetRepository`
- `ZetConfig`
- `PathService`

Goal:

Make it possible to load an asset by `AssetID` and inspect its fields and derived paths.

Example:

```python
app = ZetApp.from_config("config.toml")
asset = app.asset(17).get()

print(asset.pipeline_stage)
print(app.asset(17).pipeline_path())
```

### Milestone 3: Move Stages Without Doing Work

Create the state-transition layer.

Deliverables:

- `PipelineRepository`
- `StateMachine`
- `AssetService.move_next()`

Goal:

Make this work:

```python
app.asset(17).move_next()
```

At this stage, moving an asset should only update JSON.

No prompt generation, image rendering, AI handoff, or file copying is required yet.

### Milestone 4: Add Housekeeping

Add basic filesystem effects when an asset changes stages.

Deliverables:

- `HousekeepingService`
- automatic creation of `PipelinePath`
- simple stage marker files such as `_stage.txt`

Goal:

Make the pipeline visibly do something while still remaining safe and easy to debug.

Example marker file:

```text
Asset 17 entered PROMPT at 2026-06-27T14:10:00
```

### Milestone 5: Add Read-Only Dashboard

Create the first Streamlit dashboard view.

Deliverables:

- character selector
- phase selector
- asset table
- selected asset detail view

Goal:

Read from `Assets.json` and display asset information without mutating anything.

### Milestone 6: Add Dashboard Actions

Add dashboard buttons that call the same service methods used by scripts.

Deliverables:

- `Move Next`
- `Regenerate`
- `Retry AI`
- `Promote to LOCKED`

Goal:

Ensure dashboard actions use the same underlying service layer as command-line scripts.

### Milestone 7: Add Real Workers

Begin implementing actual pipeline behavior.

Initial workers may include:

- manifest worker
- prompt worker
- AI handoff worker
- render review worker

Goal:

Only start doing real pipeline work after the schema, object model, state transitions, and dashboard controls are stable.
