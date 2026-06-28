# Ollama File Proxy For Zet

## Short Answer

Yes. There is enough in these two Tsaeytte scripts to extract a good filesystem-backed Ollama proxy pattern for Zet.

The strongest reusable parts are:

- the Ask / Claim / Answer folder workflow
- claim sidecars to reduce double-processing
- manifest-driven job execution
- transient Ollama connectivity retry behavior
- separation between a local coordinator and remote Ollama workers

The parts that should **not** be copied directly are:

- direct job-table coordination logic from `Stage_Ollama_Jobs.py`
- Tsaeytte-specific row fields and task naming
- assumptions about a shared `Job_List.json`
- old advancement logic that overlaps with Zet `AssetService`

In Zet, the proxy should become a thin AI transport layer under the existing asset and pipeline service model, not a second state machine.

## Why This Fits Zet

Zet already has the right architectural pieces:

- `Assets.json` holds asset state
- `Pipelines.json` holds per-stage actor and worker config
- `AssetService` owns state transitions
- `HousekeepingService` owns stage folder preparation
- workers already return structured results instead of mutating state directly

That means the old Ollama proxy pattern can be adapted cleanly:

- Zet stages decide **when** AI work is needed
- a Zet AI proxy service decides **how** to stage Ask folders
- remote Ollama workers only execute prompts and return outputs
- Zet service code decides **what state changes happen next**

This is a strong fit because it preserves the best part of the old system:
the remote worker is dumb, disposable, and replaceable.

## What To Reuse

## 1. Ask / Claim / Answer Folder Pattern

This is the most valuable part of the old design.

Recommended Zet proxy root:

```text
_Lib/AI_Queue/Ollama_Proxy/
  Ask/
  Claims/
  Claimed/
  Answer/
  Failed/
```

Suggested behavior:

- Zet writes an `Ask_*` folder when an asset reaches an `AI_AGENT` stage
- remote workers claim an ask using an exclusive sidecar file
- the worker copies the ask into its claimed folder
- the worker runs local Ollama
- the worker writes output plus an answer manifest
- the worker moves the completed folder to `Answer/`
- Zet harvests `Answer/` and applies the result through service-layer code

This pattern is easy to inspect manually and works well across machines.

## 2. Claim Sidecar Files

The claim file logic from `Ollama_File_Worker.py` is worth reusing almost as-is.

Why it is useful:

- reduces accidental double-claims
- does not require a database
- works better than using whole-folder moves as the first claim signal
- is easy to troubleshoot by hand

Suggested claim manifest example:

```json
{
  "version": 1,
  "ask_folder": "Ask_Asset_17_RENDER_20260627_141000",
  "worker_id": "render-box-02",
  "claimed_at": "2026-06-27T14:10:00",
  "host": "render-box-02",
  "pid": 4821
}
```

## 3. Manifest-Driven Execution

The old worker reads a JSON ask manifest, finds the prompt file and expected output, runs Ollama, and writes an answer manifest.

That is exactly the right pattern for Zet too.

Recommended `ask_manifest.json` fields for Zet:

```json
{
  "version": 1,
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

Important:

- the manifest should describe work
- the manifest should not decide asset state transitions
- the manifest should be safe to inspect and recreate manually

## 4. Transient Ollama Failure Handling

The retry logic in `Ollama_File_Worker.py` is one of the best parts of the old implementation.

The distinction it makes is valuable:

- connection refused / timeout / temporary unavailability:
  retry and possibly return the ask to `Ask/`
- real processing failure:
  write an answer error result for Zet to harvest

That behavior belongs in Zet’s remote worker layer too.

Recommended rule:

- transient local Ollama unavailability should not immediately poison the asset
- real worker completion with an error result should be harvested and turned into asset `BLOCKED` / `ERROR`

## What Not To Reuse Directly

## 1. `Stage_Ollama_Jobs.py` As The Main Coordinator

This script is doing too much for Zet’s architecture.

It currently mixes:

- queue staging
- answer harvesting
- stale job resets
- job table mutation
- advancement routing
- task-specific naming

Zet already has cleaner homes for those concerns:

- `AssetService` for state transitions
- `HousekeepingService` for stage prep
- future AI queue service for ask staging and answer harvesting
- `Assets.json` instead of `Job_List.json`

So the old coordinator should be treated as a source of ideas, not a module to transplant.

## 2. Tsaeytte-Specific Task Naming

This logic is too tied to the old project:

- `body-reference`
- `head-fitment`
- `character-assembly`
- old expected image naming rules
- old markdown table row field conventions

Zet should use its own asset and pipeline model consistently:

- `asset.pipeline`
- `asset.pipeline_stage`
- `asset.final_image_output`
- `PathService`

## 3. Direct Advancement Helpers

The old system appears to use separate advancement helpers after outputs land.

In Zet, advancement should stay in service-layer code only.

That means:

- workers do not advance assets
- answer harvesters do not directly patch JSON
- all state changes should go through `AssetService`

## Recommended Zet Design

## Layer Split

Use four distinct layers.

### 1. Asset / Pipeline State Layer

Already exists in Zet.

Responsibilities:

- decide actor by stage
- decide whether a stage is local Python, remote AI, or human
- update `Assets.json`
- set `asset_state`, `pipeline_stage`, `actor`, `ai_state`

Primary owner:

- `AssetService`

### 2. AI Proxy Staging Layer

New Zet-specific layer to add later.

Responsibilities:

- create Ask folders for `AI_AGENT` stages
- write `ask_manifest.json`
- write prompt payload files
- detect stale asks if needed
- harvest completed Answer folders

Suggested future service:

- `zet/services/ai_proxy_service.py`

### 3. Remote Ollama Worker Layer

Adapted from `Ollama_File_Worker.py`.

Responsibilities:

- claim asks
- run local Ollama
- write answer payloads
- return transient failures to `Ask/` when appropriate
- write answer error manifests for real failures

This worker should remain external and decoupled from Zet internals.

### 4. Answer Application Layer

Back inside Zet.

Responsibilities:

- inspect completed Answer folders
- validate `ollama_attempt_id`
- ignore stale or obsolete answers
- copy response data into the asset pipeline folder if needed
- call `AssetService` to apply result-driven transitions

This is where the spirit of `Stage_Ollama_Jobs.py` belongs in Zet, but in a narrower form.

## Recommended Zet File Layout

Suggested future structure:

```text
_Lib/AI_Queue/Ollama_Proxy/
  Ask/
    Ask_Asset_17_RENDER_20260627_141000/
      ask_manifest.json
      OLLAMA_PROMPT.md
  Claims/
    Ask_Asset_17_RENDER_20260627_141000.claim.json
  Claimed/
    render-box-02/
      Ask_Asset_17_RENDER_20260627_141000/
  Answer/
    Ask_Asset_17_RENDER_20260627_141000/
      ask_manifest.json
      answer_manifest.json
      OLLAMA_PROMPT.md
      OLLAMA_RESPONSE.md
  Failed/
    render-box-02/
```

Inside the asset `PipelinePath`, Zet can keep its own copy of the meaningful artifacts:

```text
_Lib/Pipelines/{Character}/{Phase}/{Pipeline}/{BodyView}/{HeadView or _}/Asset_{AssetID}/
  _stage.txt
  _history.log
  OLLAMA_PROMPT.md
  OLLAMA_RESPONSE.md
  _worker_history.log
```

The proxy queue and the asset pipeline folder should be related, but not identical.

## Recommended Zet State Flow For AI Stages

## Entering An `AI_AGENT` Stage

When `AssetService.move_next()` puts an asset into an AI stage:

1. `asset.actor = AI_AGENT`
2. `asset.ai_state = ASKED`
3. housekeeping prepares the pipeline folder
4. AI proxy staging service writes an ask folder
5. dashboard shows the asset as waiting on AI

At this point, no remote worker result has been applied yet.

## While Waiting

Possible `ai_state` values Zet may eventually want:

- `ASKED`
- `CLAIMED`
- `ANSWER_READY`
- `RETRY_LATER`
- `FAILED`

Milestone 6 already introduced `ASKED`. The rest can be added incrementally later.

## When An Answer Arrives

A future harvest process should:

1. read `answer_manifest.json`
2. confirm `asset_id` and `ollama_attempt_id`
3. reject stale answers for superseded attempts
4. copy the answer text into the asset pipeline folder if needed
5. convert the answer into a Zet `WorkerResult`-like outcome
6. call service-layer logic to apply the result

That keeps the file proxy transport and Zet state machine cleanly separated.

## Suggested Zet Implementation Plan

## Phase 1. Add AI Proxy Data Model

Add a future model such as:

```python
@dataclass
class AIProxyAsk:
    asset_id: int
    pipeline_stage: str
    ollama_attempt_id: str
    model: str
    prompt_file: str
    expected_output: str
```

This stays transport-focused, not state-focused.

## Phase 2. Add `AIProxyService`

Responsibilities:

- stage ask folders
- write manifests
- harvest answers
- classify transient vs real failures

This service should not replace `AssetService`.

It should support `AssetService`.

## Phase 3. Adapt Remote Worker

Create a Zet-specific remote worker script derived from `Ollama_File_Worker.py`.

Keep:

- claim sidecar creation
- polling loop
- Ollama health check
- transient retry logic
- answer manifest writing

Remove or simplify:

- Tsaeytte-specific names
- assumptions about old prompt/output names
- direct references to old coordinator behavior

## Phase 4. Add Answer Harvester

Create a Zet-side script or service that:

- scans `Answer/`
- reads manifests
- updates the corresponding asset through `AssetService`
- archives or marks harvested answers

This is the nearest equivalent to the good parts of `Stage_Ollama_Jobs.py`.

## Recommended Responsibilities Split

Good split for Zet:

- `AssetService`
  owns state changes
- `WorkerService`
  owns local stage workers
- `AIProxyService`
  owns staging and harvesting of remote AI asks/answers
- remote Ollama worker
  owns claim, inference, and answer folder creation only

That separation is much cleaner than letting the old coordinator script carry business logic.

## What Can Be Lifted Almost Verbatim

These parts of `Ollama_File_Worker.py` are strong transplant candidates:

- `TransientOllamaConnectionError`
- `is_transient_ollama_error(...)`
- `wait_for_ollama(...)`
- `call_ollama(...)`
- `write_claim_file(...)`
- `claim_one(...)`
- `release_claim_to_ask(...)`
- `move_to_answer(...)`

These should be renamed and simplified, but the underlying behavior is good.

## What Should Be Rewritten For Zet

These parts should be redesigned instead of copied:

- old ask manifest field names
- `process_claimed(...)` output assumptions
- any direct relationship to old task names
- any code that assumes old queue table semantics
- any coordinator logic that advances jobs outside Zet service methods

## Risks And Design Warnings

## 1. Shared Folder Sync Is Not A Real Lock Manager

The claim sidecar approach is practical, but it is still best-effort.

For Zet, this is probably acceptable if:

- jobs are idempotent
- stale answers can be detected
- duplicated claims are rare and recoverable

## 2. Attempt IDs Matter

If Zet adopts this pattern, every Ask should include a unique `ollama_attempt_id`.

That is important because:

- an asset may be regenerated
- an old remote worker may answer late
- the late answer must not overwrite a newer request

This is one of the most important lessons to carry forward.

## 3. Do Not Let The Proxy Become The State Machine

This is the biggest architectural warning.

The proxy should move files.

Zet should own state.

If those responsibilities get blended, debugging will get much harder.

## Recommended Next Step For Zet

If this direction sounds right, the best next implementation step is:

1. create a Zet AI proxy design milestone
2. add an `AIProxyService` that can stage an ask folder for an `AI_AGENT` stage
3. adapt the remote worker into a Zet-specific `ollama_proxy_worker.py`
4. add a harvester that converts completed answers into service-layer result handling

## Bottom Line

Yes, the old Tsaeytte Ollama proxy is worth mining.

The remote worker script contains a solid reusable transport pattern.

The coordinator script contains useful ideas, but in Zet it should be split apart and rehomed into:

- `AssetService` for state changes
- a future `AIProxyService` for ask/answer staging
- a future answer harvester for result application

So the answer is:

- reuse the file-proxy pattern
- reuse the transient retry and claim logic
- do not reuse the old coordinator structure wholesale
- keep Zet’s state machine in Zet
