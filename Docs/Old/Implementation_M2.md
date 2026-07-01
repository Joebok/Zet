# Codex Task: Zet Milestone 2 — Load and Inspect Assets

You are implementing Milestone 2 of the Zet project.

Read these planning documents first:

* `Zet.md`
* `Zet_Data_Schema_Object_Model_Decisions.md`

Also inspect the existing project files created during Milestone 1.

## Scope

Implement only Milestone 2: Load and Inspect Assets.

Do not implement Milestone 3 or later.

Do not implement state transitions yet.

Do not implement `move_next()`, `regenerate()`, `promote_to_locked()`, AI manager behavior, Streamlit dashboard behavior, worker scripts, image rendering, prompt generation, or housekeeping side effects.

This milestone is only about:

* loading config
* loading asset records
* representing assets as Python objects
* deriving important filesystem paths
* printing or inspecting asset information

## Assumptions

Milestone 1 should already have created:

```text
config.toml

_Lib/
  Characters/
    Tsaeytte/
      Adult/
        Assets.json
        Pipelines.json

  Assets/
    Tsaeytte/
      Adult/

  Pipelines/
    Tsaeytte/
      Adult/

  AI_Queue/
```

If these files or folders are missing, do not silently replace the project. Report what is missing.

## Required Python Package Structure

Create the following package structure:

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

Do not create unrelated files.

## Field Naming

Use Pythonic `snake_case` names in code.

The JSON files should also use `snake_case` field names.

Expected asset fields include:

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

## Implement `Asset` Dataclass

Create `zet/models/asset.py`.

Define an `Asset` dataclass.

The dataclass should match the fields from `Assets.json`.

Use `Optional[str]` where a field may be null.

`asset_id` should be an `int`.

Example shape:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class Asset:
    asset_id: int

    character: str
    phase: str
    pipeline: str
    body_view: str
    head_view: Optional[str] = None
    costume: Optional[str] = None
    expression: Optional[str] = None

    asset_state: str = "NEW"
    pipeline_stage: str = "MANIFEST"
    actor: str = "PYTHON"
    ai_state: Optional[str] = None

    final_image_output: Optional[str] = None
    last_ai_update: Optional[str] = None

    error_code: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: Optional[str] = None
```

The `Asset` dataclass should remain mostly data-only for now.

Do not add methods that mutate state.

## Implement Config Loading

Create `zet/services/config_service.py`.

Implement a small config object and config loader.

Requirements:

* load `config.toml`
* expose these base folders:

  * `base_character_path`
  * `base_asset_path`
  * `base_pipeline_path`
  * `base_ai_queue_path`
* use only the Python standard library if possible
* Python 3.11+ has `tomllib`; use `tomllib`
* raise a clear exception if `config.toml` is missing or invalid

Example intended usage:

```python
config = ConfigService.load("config.toml")
print(config.base_character_path)
```

## Implement `PathService`

Create `zet/services/path_service.py`.

`PathService` should derive paths from config and asset fields.

Required methods:

```python
character_path(character: str, phase: str) -> Path

character_asset_path(character: str, phase: str) -> Path

pipeline_base_path(character: str, phase: str) -> Path

pipeline_path(asset: Asset) -> Path

candidate_image_path(asset: Asset) -> Path

locked_image_path(asset: Asset) -> Path
```

Use `pathlib.Path`.

The decided `PipelinePath` pattern is:

```text
_Lib/Pipelines/{Character}/{Phase}/{Pipeline}/{BodyView}/{HeadView or _}/Asset_{AssetID}/
```

If `asset.head_view` is null or blank, use `_`.

Example:

```text
_Lib/Pipelines/Tsaeytte/Adult/Body-Reference/Front/_/Asset_1/
```

`candidate_image_path(asset)` should return:

```text
{PipelinePath}/{final_image_output}
```

`locked_image_path(asset)` should return:

```text
{CharacterAssetPath}/{final_image_output}
```

Do not create directories in `PathService`.

This milestone only calculates paths.

## Implement `AssetRepository`

Create `zet/repositories/asset_repository.py`.

`AssetRepository` is responsible for reading asset data from `Assets.json`.

Required behavior:

* initialize with a `PathService`
* load assets for a selected `character` and `phase`
* return `Asset` objects
* get one asset by `asset_id`
* list all assets for a selected `character` and `phase`
* raise clear exceptions if `Assets.json` is missing, malformed, or missing required fields

Required methods:

```python
list_assets(character: str, phase: str) -> list[Asset]

get_asset(character: str, phase: str, asset_id: int) -> Asset
```

For Milestone 2, read-only behavior is sufficient.

Do not implement saving yet unless it is trivial and clearly separated.

Do not mutate `Assets.json`.

## Implement High-Level `ZetApp`

Create `zet/app.py`.

`ZetApp` should act as the simple entry point for later work.

Required behavior:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")
assets = app.list_assets("Tsaeytte", "Adult")
asset_ref = app.asset("Tsaeytte", "Adult", 1)
```

For this milestone, `app.asset(...)` should return an `AssetRef` wrapper.

Create `AssetRef` inside `app.py` unless a separate file seems clearly better.

`AssetRef` should support read-only inspection methods:

```python
get() -> Asset

show() -> None

pipeline_path() -> Path

candidate_image_path() -> Path

locked_image_path() -> Path
```

Do not implement these yet:

```python
move_next()
regenerate()
retry_ai()
promote_to_locked()
```

If you include these method names as placeholders, they must raise `NotImplementedError` with a clear Milestone 3+ message.

Preferred API goal for this milestone:

```python
app = ZetApp.from_config("config.toml")

asset = app.asset("Tsaeytte", "Adult", 1)

asset.show()
print(asset.pipeline_path())
print(asset.candidate_image_path())
print(asset.locked_image_path())
```

## Implement CLI Inspection Scripts

Create `zet/scripts/list_assets.py`.

It should be runnable as:

```bash
python -m zet.scripts.list_assets --character Tsaeytte --phase Adult
```

It should print a readable list of assets including at least:

* `asset_id`
* `pipeline`
* `body_view`
* `head_view`
* `asset_state`
* `pipeline_stage`
* `actor`

Create `zet/scripts/inspect_asset.py`.

It should be runnable as:

```bash
python -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
```

It should print:

* all asset fields
* `PipelinePath`
* `CandidateImagePath`
* `LockedImagePath`

Both scripts should support an optional config path:

```bash
--config config.toml
```

Default should be:

```text
config.toml
```

Use `argparse`.

## Validation Requirements

After implementation, run or describe how to run:

```bash
python -m zet.scripts.list_assets --character Tsaeytte --phase Adult
python -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
```

The output should demonstrate that:

* `config.toml` loads
* `Assets.json` loads
* asset records become `Asset` objects
* assets can be retrieved by `asset_id`
* paths are derived correctly
* no state changes occur
* no files are mutated

## Guardrails

Do not implement beyond Milestone 2.

Do not modify `Assets.json` except to fix a schema error that prevents Milestone 2 from working.

Do not modify `Pipelines.json` unless necessary to correct invalid JSON.

Do not create dashboard code.

Do not create worker scripts.

Do not create AI manager code.

Do not create image-rendering or prompt-generation logic.

Keep the implementation simple, readable, and easy to troubleshoot.

Favor clarity over cleverness.
