# Codex Task: Zet Milestone 7B — AI Proxy Ask Staging

You are implementing Milestone 7B of the Zet project.

Read these planning documents first:

* `Docs/Zet.md`
* `Docs/Zet_Data_Schema_Object_Model_Decisions.md`
* `Docs/Ollama_File_Proxy_For_Zet.md`
* `Docs/Implementation_Ollama_File_Proxy_For_Zet.md`

Also inspect the existing project files from Milestones 1 through 7A.

## Scope

Implement only Milestone 7B: AI Proxy Ask Staging.

This milestone adds the Zet-side ability to stage AI work into a filesystem-backed Ollama proxy queue.

Do not implement Milestone 7C or later.

Do not implement the remote Ollama worker yet.

Do not implement answer harvesting yet.

Do not implement real prompt generation logic beyond writing an inspectable prompt payload file.

Do not implement image rendering.

Do not implement candidate image creation.

Do not implement locked image promotion changes beyond what already exists.

This milestone is only about:

* defining AI proxy queue models
* defining AI proxy queue path logic
* staging Ask folders for assets in `AI_AGENT` stages
* writing ask manifests and prompt payload files
* updating asset metadata fields that reflect staging
* exposing ask staging through CLI and dashboard

## Important Design Rule

Staging an AI ask must not directly advance the asset.

Staging an AI ask must not create an answer.

Staging an AI ask must not call Ollama.

Staging an AI ask must not modify `Pipelines.json`.

The staged ask is only a transport request.

Asset state transitions still belong to Zet service-layer code.

## Existing Expected Structure

Milestone 7A should already have created something close to:

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
    worker.py

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
    worker_service.py

  workers/
    __init__.py
    noop_worker.py

  scripts/
    __init__.py
    inspect_asset.py
    list_assets.py
    move_next.py
    run_housekeeping.py
    run_worker.py
```

Do not rewrite the whole project.

Modify it incrementally.

## Required New Or Updated Files

Create:

```text
zet/models/ai_proxy.py
zet/services/ai_proxy_path_service.py
zet/services/ai_proxy_service.py
zet/scripts/stage_ai_ask.py
```

Update as needed:

```text
zet/app.py
zet/dashboard/app.py
zet/models/__init__.py
zet/services/__init__.py
zet/services/asset_service.py
```

Do not create unrelated files.

## Queue Root

Use the existing configured base AI queue root:

```text
_Lib/AI_Queue/
```

Within that root, use this fixed Ollama proxy layout:

```text
_Lib/AI_Queue/Ollama_Proxy/
  Ask/
  Claims/
  Claimed/
  Answer/
  Failed/
```

Do not make this configurable yet beyond the existing `BaseAIQueuePath`.

Do not create the full tree on read-only dashboard load.

Create queue folders only when staging an ask.

## AI Proxy Models

Create `zet/models/ai_proxy.py`.

Define dataclasses similar to:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AIProxyAsk:
    ask_id: str
    asset_id: int
    character: str
    phase: str
    pipeline: str
    pipeline_stage: str
    ollama_attempt_id: str
    worker_type: str
    ollama_model: str
    prompt_file: str
    expected_output: str
    candidate_output_file: Optional[str] = None


@dataclass
class AIProxyPaths:
    proxy_root: Path
    ask_root: Path
    claims_root: Path
    claimed_root: Path
    answer_root: Path
    failed_root: Path
```

Keep them simple.

These are transport models, not asset-state models.

## AI Proxy Path Service

Create `zet/services/ai_proxy_path_service.py`.

Implement an `AIProxyPathService`.

Required behavior:

* derive the proxy root from `BaseAIQueuePath`
* derive each standard queue folder path
* derive the Ask folder path for a given ask ID

Required methods:

```python
proxy_root() -> Path
ask_root() -> Path
claims_root() -> Path
claimed_root() -> Path
answer_root() -> Path
failed_root() -> Path
ask_path(ask_id: str) -> Path
```

Use `pathlib.Path`.

Do not create directories automatically in simple getter methods.

## AI Proxy Service

Create `zet/services/ai_proxy_service.py`.

Implement an `AIProxyService`.

Required constructor dependencies:

* `AssetRepository`
* `PipelineRepository`
* `PathService`
* `AIProxyPathService`

Additional dependencies are acceptable if already established by the project.

## Ask Staging API

Implement:

```python
stage_current_ai_ask(character: str, phase: str, asset_id: int) -> Path
```

This should be the public service-layer staging action.

Preferred public usage:

```python
app = ZetApp.from_config("config.toml")
asset = app.asset("Tsaeytte", "Adult", 1)

ask_path = asset.stage_ai_ask()
```

Add `AssetRef.stage_ai_ask()` in `zet/app.py` to delegate to the service.

## Staging Preconditions

When staging an ask:

1. load the current asset
2. validate that `asset.actor == "AI_AGENT"`
3. validate that `asset.final_image_output` exists as a field value
4. load the pipeline definition if needed

If the asset is not currently assigned to `AI_AGENT`, raise a clear friendly error:

```text
AI ask staging is only available when Actor is AI_AGENT.
```

Do not stage asks for `PYTHON` or `HUMAN_AGENT` stages in this milestone.

## Ask ID And Attempt ID

Create both:

* `ask_id`
* `ollama_attempt_id`

Use a readable timestamp-based format.

Recommended:

```text
Ask_Asset_{AssetID}_{PipelineStage}_{YYYYMMDD_HHMMSS}
```

and

```text
{YYYYMMDD_HHMMSS}_{AssetID}_{PipelineStage}
```

Examples:

```text
Ask_Asset_1_RENDER_20260627_141000
20260627_141000_1_RENDER
```

These values must be unique enough for ordinary use.

You do not need to add a dedicated `current_ai_attempt_id` field to `Assets.json` in this milestone.

Instead, store the attempt note in `last_ai_update`.

## Ask Folder Contents

Staging an ask should create:

```text
Ask_{...}/
  ask_manifest.json
  OLLAMA_PROMPT.md
```

Do not create answer files yet.

Do not create claim files yet.

Do not create anything under `Answer/` or `Claimed/` yet.

## ask_manifest.json

The ask manifest must be valid JSON and human-inspectable.

Required fields:

```json
{
  "version": 1,
  "ask_id": "Ask_Asset_1_RENDER_20260627_141000",
  "asset_id": 1,
  "character": "Tsaeytte",
  "phase": "Adult",
  "pipeline": "Body-Reference",
  "pipeline_stage": "RENDER",
  "ollama_attempt_id": "20260627_141000_1_RENDER",
  "worker_type": "ollama_generate",
  "ollama_model": "llama3.2:3b",
  "prompt_file": "OLLAMA_PROMPT.md",
  "expected_output": "OLLAMA_RESPONSE.md",
  "candidate_output_file": "Body-Reference_Front.png"
}
```

Use the asset’s actual values.

Keep the format simple.

## OLLAMA_PROMPT.md

Write a placeholder but useful prompt payload file named:

```text
OLLAMA_PROMPT.md
```

This milestone does not require real prompt-engineering logic.

It does require a clearly structured file that a remote worker could use later.

Suggested contents:

```text
# Zet Ollama Prompt

AssetID: 1
Character: Tsaeytte
Phase: Adult
Pipeline: Body-Reference
PipelineStage: RENDER
BodyView: Front
HeadView: _
FinalImageOutput: Body-Reference_Front.png

This is a staged placeholder prompt for Zet AI proxy testing.
```

Use the asset’s actual values.

If `head_view` is null or blank, write `_`.

## Asset Updates During Staging

Staging an ask may update a small set of asset metadata fields.

Required asset updates:

* set `ai_state` to `ASKED`
* set `last_ai_update` to a readable note that includes the attempt ID or ask ID
* update `updated_at`

Do not change:

* `pipeline_stage`
* `actor`
* `asset_state`

unless correction is needed to preserve `AI_AGENT` stage semantics.

Do not advance the stage.

Do not set `LOCKED`.

Do not set `ERROR`.

After saving, run housekeeping so the pipeline folder markers stay current.

## Safe Filesystem Behavior

When staging an ask, the service may create or update only:

* `_Lib/AI_Queue/Ollama_Proxy/Ask/`
* `_Lib/AI_Queue/Ollama_Proxy/Claims/`
* `_Lib/AI_Queue/Ollama_Proxy/Claimed/`
* `_Lib/AI_Queue/Ollama_Proxy/Answer/`
* `_Lib/AI_Queue/Ollama_Proxy/Failed/`
* `ask_manifest.json`
* `OLLAMA_PROMPT.md`
* `Assets.json`, through safe repository save only
* `Assets.backup.*.json`
* housekeeping files in the asset’s `PipelinePath`

Do not create:

* answer manifests
* AI response files
* candidate images
* locked images
* remote claim sidecars

## CLI Script

Create `zet/scripts/stage_ai_ask.py`.

It should be runnable as:

```bash
python3 -m zet.scripts.stage_ai_ask --character Tsaeytte --phase Adult --asset-id 1
```

It should also support:

```text
--config config.toml
```

Default config path:

```text
config.toml
```

Use `argparse`.

The script should:

1. load the app from config
2. stage the current AI ask for the selected asset
3. print a concise success summary

Example output:

```text
AI ask staged for Asset 1:
  Pipeline: Body-Reference
  Stage: RENDER
  AskPath: _Lib/AI_Queue/Ollama_Proxy/Ask/Ask_Asset_1_RENDER_20260627_141000
  AI_State: ASKED
```

If staging is not allowed, print a clear error message and exit with a non-zero status code.

## Dashboard Button

Update `zet/dashboard/app.py`.

Add a dashboard action:

```text
Stage AI Ask
```

The button should call:

```python
asset_ref.stage_ai_ask()
```

Expected behavior:

* only works when `actor = AI_AGENT`
* stages the ask folder
* updates the asset’s `ai_state`, `last_ai_update`, and `updated_at`
* refreshes the dashboard after success
* shows a friendly error when invalid

Do not stage asks automatically on page load.

Do not stage asks automatically when an asset is selected.

Only stage when the button is clicked.

## Dashboard Read-Only Preview

If straightforward, add a small read-only preview for the latest staged ask in the selected asset’s detail area.

Acceptable simple behavior:

* if `last_ai_update` contains staged ask information, display it as part of the asset details
* or, if you can derive the newest ask folder for the asset cheaply, show:
  * ask folder path
  * `ask_manifest.json` contents
  * `OLLAMA_PROMPT.md` contents

This preview is optional for 7B.

Do not over-engineer it.

## Updating ZetApp And AssetRef

Update `zet/app.py`.

Ensure this works:

```python
from zet.app import ZetApp

app = ZetApp.from_config("config.toml")
asset = app.asset("Tsaeytte", "Adult", 1)

ask_path = asset.stage_ai_ask()
```

`AssetRef` must not cache stale asset data.

Every action should load the current asset before acting.

## Validation Requirements

After implementation, run or describe how to run:

```bash
python3 -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
python3 -m zet.scripts.stage_ai_ask --character Tsaeytte --phase Adult --asset-id 1
python3 -m zet.scripts.inspect_asset --character Tsaeytte --phase Adult --asset-id 1
```

Choose an asset that is currently at an `AI_AGENT` stage.

Expected result:

* ask folder is created under `Ask/`
* `ask_manifest.json` exists and is valid JSON
* `OLLAMA_PROMPT.md` exists
* `Assets.json` remains valid JSON
* `ai_state` is `ASKED`
* `last_ai_update` is updated
* `updated_at` is updated
* `pipeline_stage` does not change
* `actor` does not change
* no answer files are created
* no candidate images are created
* no locked images are created

Also test invalid actor cases:

* select an asset with `actor = PYTHON`
* run `stage_ai_ask`
* confirm a friendly error
* confirm no ask folder is created
* confirm no state change

And:

* select an asset with `actor = HUMAN_AGENT`
* run `stage_ai_ask`
* confirm a friendly error
* confirm no ask folder is created
* confirm no state change

Also test in the dashboard:

```bash
streamlit run zet/dashboard/app.py
```

Then:

* select an asset with `actor = AI_AGENT`
* click `Stage AI Ask`
* confirm success message
* confirm the dashboard refreshes
* confirm no stage advancement occurred

## Guardrails

Do not implement beyond Milestone 7B.

Do not implement the remote Ollama worker yet.

Do not implement answer harvesting yet.

Do not call Ollama.

Do not create claim sidecars yet.

Do not create answer folders yet.

Do not generate prompt content beyond a placeholder staged payload file.

Do not render images.

Do not modify `Pipelines.json`.

Do not introduce a database.

Do not add unnecessary third-party dependencies.

Keep implementation simple, readable, and easy to troubleshoot.

Favor clarity over cleverness.
