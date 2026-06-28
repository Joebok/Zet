# Implementation Plan: Ollama File Proxy For Zet

## Goal

Implement a filesystem-backed Ollama proxy for Zet that:

- stages AI requests from Zet into an inspectable queue
- allows one or more remote machines to claim and process those requests
- harvests completed answers back into Zet
- keeps all asset state transitions inside Zet service-layer code

This plan is intentionally incremental.

It avoids:

- database work
- direct state mutation by remote workers
- early coupling to real image rendering
- mixing AI transport logic into the dashboard

## Design Principles

The implementation should follow these rules:

- Zet owns asset state
- the proxy owns file transport only
- remote workers are disposable
- all state transitions still go through `AssetService`
- all queue files remain human-inspectable
- stale or late answers must be safely ignorable

## Recommended Rollout

Use four implementation phases after the current worker framework.

## Phase 1. Add AI Proxy Models And Filesystem Layout

This phase introduces queue data structures and path helpers only.

No Ollama calls yet.

## Files To Add

```text
zet/models/ai_proxy.py
zet/services/ai_proxy_path_service.py
```

## Files To Update

```text
zet/services/config_service.py
config.toml
```

## Config Changes

Keep the current:

```toml
[BaseFolders]
BaseAIQueuePath = "_Lib/AI_Queue/"
```

Add a derived convention only, not a new required root setting:

```text
_Lib/AI_Queue/Ollama_Proxy/
```

## Data Models

Add models similar to:

```python
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
    candidate_output_file: str | None = None


@dataclass
class AIProxyAnswer:
    ask_id: str
    asset_id: int
    ollama_attempt_id: str
    status: str
    worker_id: str
    expected_output: str
    error_type: str | None = None
    error_message: str | None = None
```

## Path Service Responsibilities

Create an `AIProxyPathService` that derives:

- proxy root
- `Ask/`
- `Claims/`
- `Claimed/`
- `Answer/`
- `Failed/`
- ask folder path by ask ID
- answer folder path by ask ID

This keeps queue path logic out of `AssetService`.

## Deliverable

At the end of Phase 1, Zet can deterministically compute all proxy paths and data shapes, but does not stage or harvest work yet.

## Phase 2. Add Ask Staging From Zet

This phase adds the Zet-side ability to create an ask folder for an asset in an `AI_AGENT` stage.

Still no remote processing yet.

## Files To Add

```text
zet/services/ai_proxy_service.py
zet/scripts/stage_ai_ask.py
```

## Files To Update

```text
zet/services/asset_service.py
zet/app.py
zet/dashboard/app.py
```

## Core Service API

Recommended methods:

```python
class AIProxyService:
    def stage_current_ai_ask(character: str, phase: str, asset_id: int) -> Path:
        ...

    def current_attempt_id(asset: Asset) -> str:
        ...
```

## Recommended Behavior

`stage_current_ai_ask(...)` should:

1. load the asset
2. validate `asset.actor == "AI_AGENT"`
3. validate required pipeline files already exist if needed
4. generate a unique `ollama_attempt_id`
5. create an ask folder under `Ask/`
6. write `ask_manifest.json`
7. write the prompt payload file, such as `OLLAMA_PROMPT.md`
8. optionally write a small `_ask_staged.txt` marker in `PipelinePath`
9. update only the asset fields that are appropriate for queueing, if any

Recommended asset field updates:

- keep `ai_state = ASKED`
- update `last_ai_update` with a clear staging note
- update `updated_at`

Do not advance stage here.

## Ask Folder Contents

Recommended shape:

```text
Ask_Asset_17_RENDER_20260627_141000/
  ask_manifest.json
  OLLAMA_PROMPT.md
```

## Ask Manifest Fields

Use:

```json
{
  "version": 1,
  "ask_id": "Ask_Asset_17_RENDER_20260627_141000",
  "asset_id": 17,
  "character": "Tsaeytte",
  "phase": "Adult",
  "pipeline": "Body-Reference",
  "pipeline_stage": "RENDER",
  "ollama_attempt_id": "20260627_141000_17_RENDER",
  "worker_type": "ollama_generate",
  "ollama_model": "llama3.2:3b",
  "prompt_file": "OLLAMA_PROMPT.md",
  "expected_output": "OLLAMA_RESPONSE.md",
  "candidate_output_file": "Body-Reference_Front.png"
}
```

## Deliverable

At the end of Phase 2, Zet can stage AI work into queue folders, and a human can inspect those asks manually.

## Phase 3. Add Remote Ollama Worker

This phase adapts the old `Ollama_File_Worker.py` into a Zet-specific external worker.

This should live outside the main Zet service model, but can stay in the repo for convenience.

## Files To Add

Suggested:

```text
AI_Manager/ollama_proxy_worker.py
```

Optional:

```text
AI_Manager/ollama_proxy_worker.ps1
```

## Code To Reuse From Old Script

Reuse or adapt:

- `TransientOllamaConnectionError`
- `is_transient_ollama_error(...)`
- `wait_for_ollama(...)`
- `call_ollama(...)`
- `write_claim_file(...)`
- `claim_one(...)`
- `release_claim_to_ask(...)`
- `move_to_answer(...)`

## Code To Rewrite

Rewrite:

- prompt and output naming assumptions
- old manifest field names
- any Tsaeytte-specific task mapping
- any coupling to old coordinator expectations

## Remote Worker Contract

The worker should:

1. watch `Ask/`
2. claim an ask with a sidecar file
3. copy it into `Claimed/{worker_id}/`
4. read `ask_manifest.json`
5. call local Ollama
6. write `answer_manifest.json`
7. write `OLLAMA_RESPONSE.md`
8. move folder to `Answer/`

For transient connectivity failure:

- retry locally first
- if still unavailable, return ask to `Ask/`

For real processing failure:

- write an error answer manifest
- move folder to `Answer/` or `Failed/`, depending on the chosen policy

## Answer Manifest Fields

Recommended:

```json
{
  "version": 1,
  "ask_id": "Ask_Asset_17_RENDER_20260627_141000",
  "asset_id": 17,
  "ollama_attempt_id": "20260627_141000_17_RENDER",
  "worker_id": "render-box-02",
  "status": "SUCCESS",
  "expected_output": "OLLAMA_RESPONSE.md",
  "started_at": "2026-06-27T14:10:00",
  "completed_at": "2026-06-27T14:10:33",
  "elapsed_seconds": 33.1,
  "error_type": "",
  "error_message": ""
}
```

## Deliverable

At the end of Phase 3, remote machines can independently process Zet ask folders and return answers.

## Phase 4. Add Answer Harvesting In Zet

This phase brings completed answers back into Zet and applies results through service-layer logic.

## Files To Add

```text
zet/services/ai_answer_harvester.py
zet/scripts/harvest_ai_answers.py
```

## Files To Update

```text
zet/services/asset_service.py
zet/app.py
zet/dashboard/app.py
```

## Core Service API

Recommended methods:

```python
class AIAnswerHarvester:
    def harvest_once() -> list[HarvestResult]:
        ...

    def apply_answer_folder(answer_path: Path) -> HarvestResult:
        ...
```

Recommended `AssetService` entrypoint:

```python
def apply_ai_answer(character: str, phase: str, asset_id: int, answer_result: AIProxyAnswer) -> Asset:
    ...
```

## Required Validation Logic

The harvester must validate:

- `asset_id` matches an existing asset
- `ollama_attempt_id` matches the asset’s current expected attempt
- the answer is not stale
- required answer files exist

If an answer is stale:

- ignore it
- archive or mark it as stale
- do not mutate the asset

This is critical.

## Success Flow

On successful answer harvest:

1. copy `OLLAMA_RESPONSE.md` into `PipelinePath`
2. optionally transform the answer into a local worker output file if needed
3. update asset `ai_state`
4. call `move_next()` or a dedicated transition method if the AI stage is complete
5. run housekeeping

## Failure Flow

On failed answer harvest:

1. set `asset_state = BLOCKED`
2. set `pipeline_stage = ERROR`
3. set `actor = HUMAN_AGENT`
4. set `ai_state = None`
5. populate error fields
6. save asset
7. run housekeeping

## Deliverable

At the end of Phase 4, Zet can round-trip a staged ask through a remote Ollama worker and apply the result back into asset state.

## Recommended Method Ownership

Keep responsibilities sharply divided:

### `AssetService`

- state transitions
- actor updates
- `ai_state` updates
- error handling
- safe writes to `Assets.json`

### `AIProxyPathService`

- all queue folder path derivation

### `AIProxyService`

- ask staging
- ask manifest writing
- tracking current attempt IDs

### `AIAnswerHarvester`

- scanning `Answer/`
- reading answer manifests
- stale answer rejection
- invoking service-layer state application

### Remote worker

- claim
- Ollama execution
- answer file writing
- transient retry

## Recommended Attempt ID Strategy

Every staged AI ask should have a unique attempt ID.

Recommended format:

```text
{timestamp}_{asset_id}_{pipeline_stage}
```

Example:

```text
20260627_141000_17_RENDER
```

Store it in:

- `ask_manifest.json`
- `answer_manifest.json`
- `last_ai_update` or a future dedicated field

If Zet later gains a dedicated asset field such as `current_ai_attempt_id`, use that instead of overloading `last_ai_update`.

## Recommended Future Asset Fields

These are optional, but likely worth adding later:

```text
current_ai_attempt_id
current_ai_provider
current_ai_model
```

Do not add them until the proxy implementation truly needs them.

For now, Zet can proceed with existing fields plus queue manifests.

## Recommended Dashboard Scope

Keep dashboard support narrow.

Good dashboard actions for the proxy phase:

- `Stage AI Ask`
- `Harvest AI Answers`
- read-only preview of latest ask manifest
- read-only preview of latest answer manifest

Avoid:

- real-time remote worker monitoring
- queue mutation outside service methods
- direct queue folder editing in the dashboard

## Testing Plan

## Local Zet Tests

1. stage an ask for an `AI_AGENT` asset
2. verify ask folder contents
3. verify no unexpected asset mutation
4. place a fake answer folder manually
5. run answer harvester
6. verify asset state changes correctly

## Remote Worker Tests

1. point worker at proxy root
2. confirm claims are created
3. confirm answers are written
4. simulate Ollama unavailable
5. confirm ask is returned to `Ask/`

## Stale Answer Tests

1. stage ask A
2. regenerate or restage asset to create ask B
3. return answer for ask A late
4. verify harvester ignores answer A
5. return answer for ask B
6. verify only answer B is applied

## Suggested Milestone Names

If you want to formalize this into Zet milestones, a clean split would be:

1. `Milestone 7B - AI Proxy Ask Staging`
2. `Milestone 7C - Remote Ollama Worker`
3. `Milestone 7D - AI Answer Harvesting`
4. `Milestone 7E - Dashboard AI Queue Controls`

## Bottom Line

The best implementation path is:

- do not transplant the old coordinator
- transplant the remote worker transport ideas
- add a Zet-native ask staging service
- add a Zet-native answer harvester
- keep `AssetService` as the only owner of state transitions

That gives you the strengths of the old filesystem Ollama proxy without reintroducing the architectural tangles of the earlier project.
