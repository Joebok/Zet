# Shared AI jobs

This document owns the unified creative AI request, collection, activity and model
selection interfaces introduced on 2026-10-16. [Queues](QUEUES.md) owns envelope
transfer and retention; workflow components own interpretation of their outputs.

## Ownership and entry points

- [AIJobService](../../zet/services/ai_job_service.py) submits structured requests,
  verifies identities/inventories, drains answers into the local Inbox, exposes
  results, copies validated artifacts and records completion. Compatibility
  synchronous callers wait here; resumable workflows yield rather than wait.
- [AIJobRepository](../../zet/repositories/ai_job_repository.py) stores compact
  request identities under configured `[Storage].Root/AI_Queue/<queue-hash>/<producer>/Jobs/`.
  The shared queue owns execution state. Durable local records/receipts own Zet
  application state; the library index is not required to display activity.
- [AIJobCoordinator](../../zet/services/ai_job_coordinator.py) owns the two-second
  background sweep and registered consumer handlers. An OS-backed lease serializes
  sweeps across dashboard and standalone hosts. Recorded universe ownership
  determines the bound app, including universes without an open browser page.
- [AIWorkflowService](../../zet/services/ai_workflow_service.py) stores registered
  continuation methods/arguments in `Workflows/`. Text requests yield `AIPending`;
  resume reuses a stable task/request identity and compact `StructuredResults/`.
  Only registered service/method pairs can be resumed. Revision and source checks
  remain with domain services. A process-wide active-task registry prevents repeated
  sweeps from enqueueing the same lifecycle/universe/task concurrently; cross-process
  task locks and recurring recovery remain authoritative.
- [AIRequestPreparation](../../zet/services/ai_request_preparation_service.py)
  freezes text options/schema/ordered images and compiled ComfyUI graphs. It does
  not call model or render backends. Managed ComfyUI can be stopped during graph
  compilation; its actual node set is checked by the proxy after admission.

## Wire contract and compatibility

`ai_request.json` version 1 is inventoried inside the existing protocol-v1 File
Proxy envelope. It carries provider/model, prompt/system or workflow/bindings,
schema/output contract, execution options and opaque owner metadata. Inspect
the preparation service and proxy `file_proxy/ai_worker.py` for the authoritative
fields. New envelopes use trusted `ai_codex`, `ai_ollama` and `ai_comfyui` workers.
AI_Proxy owns invocation, upstream configuration, settlement and terminal output.
Zet retains prompt composition, reference preparation, provenance and application.

The proxy keeps old `ollama`/`local_image` registrations for published envelopes
without the new request payload. New submissions never use those registrations.
Old Narrative Codex attempt files can be imported only for their matching attempt;
missing/ambiguous execution is not rerun. Removed historical payloads cannot be
reconstructed. Existing receipts remain readable.

Collection verifies the producer, universe, original request identity and complete
output inventory, copies the payload locally, applies through a domain handler,
writes a receipt, then removes transport files/routes. Copy/application failures
retain evidence. `HARVEST_FAILED` is retried explicitly through Harvest AI Answers;
it does not become a new execution. Incomplete/missing transport transitions remain
visible as transferring/reconciling. Worker launch/interruption failures are
normalized locally from terminal proxy outcomes. Application remains idempotent
under domain and common job locks.

Completed local details are retained for seven days by default, based on the
original completion/harvest timestamp. A daily coordinator maintenance pass prunes
only old records with a verified successful receipt; missing-receipt jobs,
failures, unknown ownership and persistent locks remain. Old successful receipts
are compacted to replay identity and required image-admission proof. The derived
index also keeps only recent deduplicated summaries; the request/receipt store is
the activity source, not a history archive.

### Collection and dependent-image admission

`AIJobService.inspect()` is read-only: it distinguishes transport location,
execution/worker outcomes, collection failure, and blocking reason without draining
an answer or reading image payloads. Full hash verification occurs during collection;
local Inbox admission is reused after successful transfer. `HARVEST_FAILED` remains visible to Image Generation; missing routes or
owner metadata use `RECOVERY_REQUIRED`, while incomplete inventories use
`TRANSFERRING`. Job diagnostics record the failure stage, exception type, affected
path and failure timestamp. A transport success requires `SUCCEEDED`; worker
success independently requires `SUCCESS`.

New filesystem collection failures schedule collection-only retry with a bounded
2–30 second delay (`collection_retry_at`); provider execution is never replayed.
Missing saved requests and ownership/identity errors still require explicit
recovery. A temporarily unavailable library volume is not treated as an orphaned
request. Successful receipts clear the active collection error.

Image Generation loads requests from disk under its process-shared collection
lock. Atomic image and child-state commits precede the receipt; restart can finish
a saved child whose receipt was interrupted. `copy_result(image=True)` records the
applied image checksum as write-time metadata. Local and Minor Character review
use current owned files, independently of old receipts or saved checksums; admission still rechecks
current candidate/attempt, cancellation and evaluation under the domain lock before
request publication. See [ADR 0021](../DECISIONS/0021-file-based-local-image-availability.md).
Producer-local `Followups/` reservations and deterministic Minor review workflow
IDs reuse published work after interrupted state commits. See
[ADR 0017](../DECISIONS/0017-image-harvest-admission.md).

Known queued/running/uncollected jobs outlive subscriber wait deadlines; AI_Proxy
owns execution deadlines. A caller stopping its wait does not create a new attempt.
Collection isolates legacy/run failures from other consumers and bound universes.

`AIJobRecoveryService` reports retained answers without application changes.
Its explicit per-job retry invokes the owning registered handler only for verified
current requests; it never reconstructs missing routes or republishes execution.
The read-only CLI is `python3 -B -m zet.scripts.inspect_ai_recovery --queue-root
<queue> --library-root <universe-root> --universe <id>`. Live repair and deployment
are separate operator actions; historical-job repair is not required for rollout.

## Activity APIs and UI

`GET /api/ai/jobs` accepts `universe_filter`, `provider`, `workflow`, `status`,
`cursor` and `limit`. It merges request records, queue folders, Inbox and receipts,
deduplicates by job identity, then paginates. Active work is ordered before terminal
history. All local-producer universes are included by default. Workflow links use
the recorded universe and target identifiers. Manual tasks are labeled separately.

[ai_queue.js](../../zet/web/static/ai_queue.js) loads on page activation and polls
every two seconds while visible; navigation stops its timer and aborts its request.
Errors preserve previous rows and display an unavailable message. Queue counters
and recent harvests use the same durable feed, independent of index reconciliation.
The activity table displays Universe, Status, Workflow / target, Task, Model,
Created and Details, in that order. The former Body-Reference-only Codex panel is
removed.

### Deleting retained failures

`DELETE /api/ai/jobs/{job_id}`, through `ZetApp.delete_failed_ai_job`, delegates
to [AIJobCleanupService](../../zet/services/ai_job_cleanup_service.py). AI Queue
offers a confirmed **Delete job** action beside the status on `HARVEST_FAILED` and
`RECOVERY_REQUIRED` rows. The service rechecks current status under the coordinator
and common job locks, refuses Ask/Running work and explicit foreign-producer
metadata, rejects conflicting job identities and linked/junction paths, and removes
only known job-scoped transport/local-state files. Missing ownership metadata does
not prevent cleanup of an eligible failed/recovery-required row. Missing files are
harmless.

Cleanup includes Answer, Inbox, Debug, manual queue payloads, matching archived
payloads, staging/partial transfers, Jobs, Routes, Receipts, StructuredResults and
parent Followup reservations/queue markers. It never follows output destinations
into the library or deletes domain workflow records, images or shared lock files.
Busy files leave a visible `HARVEST_FAILED` deletion row with a retry action.
Shared `Superseded` markers are validated against `Zet_File_Proxy_State` under
the shared queue; producer-local markers use the configured local lifecycle root.

A minimal hashed `DeletedJobs` marker is committed before payload removal. Queries,
collection, adoption and publication fence the deleted identity, including late
synced answers and deterministic continuation replay. Start a new workflow attempt
to request replacement work. See [ADR 0019](../DECISIONS/0019-failed-ai-job-deletion.md).

## Model catalog and shared control

AI_Proxy publishes `File_Proxy/Control/model_catalog.json` and serves
`/_proxy/models`. Its background metadata refresh does not take the GPU slot.
Zet's [AIModelCatalogService](../../zet/services/ai_model_catalog_service.py) keeps
a producer-local last-known-good copy. `GET /api/ai/models` reads it; `POST` requests
a proxy refresh through `Control/refresh-models.json`. The compatibility Ollama
options API uses the same catalog. No selector discovers models directly. ComfyUI
metadata is best-effort while its managed process is stopped; render preparation
does not require a checkpoint to appear in that catalog. Registered Qwen profiles
are checked locally, then AI_Proxy admits the render and reports any actual
missing-model or backend failure as a job result.

[ai_model_picker.js](../../zet/web/static/ai_model_picker.js) exposes `open` and
`attach` with `value`, `providers`, `required`, `allowDefault` and compatibility
`bareCodex` options. Call `sync(control)` after restoring a backing field programmatically
so the popup button reflects the saved selection. Minor Characters does this after
loading its workspace, including saved models missing from the current catalog.
Its Codex and Ollama dropdowns are mutually exclusive; Apply
commits, Cancel/Escape preserve the original, and inherited fields have an explicit
default action. Vision restrictions use catalog capabilities and are validated
again on submission. Unknown/unavailable saved choices are retained visibly, not
silently replaced. ComfyUI profile/checkpoint controls read cached render metadata;
the catalog is not treated as proof that a render checkpoint is currently
available.

Dashboard collection always runs while the dashboard runs. `AIHarvest.AutoEnabled`
and its interval control the optional standalone host; its default interval is now
two seconds, while existing configured intervals are preserved. The standalone
host reuses its app/coordinator rather than rebuilding them on every sweep.

## Validation boundary

The approved fourth fast scenario covers two-universe queue visibility, page-away
collection, history/reload and shared selector capability/mutual exclusion. S1-S3
remain representative domain regressions. Disposable prepared-response checks
cover continuation restart, duplicate collection, partial transfers, retained
application failures/retry and ownership fencing. These do not establish live
model availability, artistic quality or production deployment.

## Migration inventory

| Requesters | Native adapter | Registered application/continuation | Capability |
|---|---|---|---|
| Narrative interview, synthesis and images | Codex/Ollama/ComfyUI | Narrative generation through `zet-narrative-scenes` | text, vision when attachments, or image generation |
| Image Generation and image-prompt/identity analysis | ComfyUI and Codex/Ollama | `zet-image-generation`, durable `image_prompt` methods | image generation or vision |
| Reconstruction/true-up, Quick Character and Costume Wizard | Codex/Ollama plus render children | durable `reconstruction`, `minor`, `costume` methods and shared structured results | vision |
| Minor Character stages and advisory reviews | Codex/Ollama/ComfyUI | common coordinator plus durable minor continuations | vision or image generation |
| Body/Head/Assembly/Dressing, supplemental slots | ComfyUI plus Codex/Ollama | generic AI harvester with domain attempt/slot fences | image generation or vision |
| Ranking, prompt improvement | Codex/Ollama | common structured/result delivery and existing domain application | vision where images are supplied |

Character prompt review registers `template_revision._review_job` with `AIWorkflowService`; `_propose_job` remains for historical pending image-evidence revisions. Dedicated image refinement registers `character_refinement._analysis_job` and `_render_job`, retaining immutable attempt/request identities and frozen correction inputs. Namespaced refinement ownership distinguishes these sessions from Minor Characters and links AI Queue rows back to the dedicated refinement page. Their batch-local revision records retain frozen evidence, proposed text and compiler results independently of request retention. Requests carry normal character batch/costume ownership for AI Queue navigation; [local characters](LOCAL_CHARACTERS.md#prompt-review-staged-generation-and-image-refinement-2026-10-18) owns review, trial activation and explicit master promotion.

Every row publishes through `FileProxyClient`; no new request uses the legacy app
workers. Those workers remain solely for immutable envelopes already published.
Their runtime evidence lookup is compatibility execution metadata; model selectors
and the compatibility `list_models()` API read the proxy-owned catalog. Repository
coding automation and Codex quota inspection are outside creative job execution.

## Storage pauses and fresh attempts (2026-10-17)
`PAUSED_STORAGE` and `RECOVERING` are nonterminal. Logical request IDs resolve through fenced replacement transport attempts for verified interruption/storage failures. Collection retry never replays execution. Registered continuation intent is journaled locally before its normal application copy, and queue activity can show explicitly stale local metadata with unknown counts during an outage. Missing frozen inputs and genuine content/provider errors remain actionable failures. See [storage recovery](STORAGE_RECOVERY.md).

Generic legacy harvest cleanup must not complete a registered domain's answer merely
because it carries a shared harvest marker. The owning handler applies and commits
its receipt before payload cleanup. This was verified with a disposable race check
and the existing S3 retry journey. See [ADR 0023](../DECISIONS/0023-streamlined-image-integrity.md).

## Role-aware text preparation (2026-10-22)

New text producers name an explicit LLM role and downstream render context. FileProxyClient applies the repo-owned Qwen modules after native request preparation and before inventory/publication, covering prebuilt requests too. The frozen request retains effective instructions and guidance hashes; continuation identity, recovery, provider execution and collection remain with their existing owners. [LLM roles](LLM_ROLES.md) owns classification, model inheritance and provenance details.

Image prompt and identity analysis starts and polls through the request-bound
universe app. Its durable `_state/ImagePromptJobs/<job-id>.json` record carries
`universe_id`; status reads only that record, rejects foreign ownership and keeps
checksums/drafts on disk. State locks protect transitions, while model work happens
outside the prompt-job lock. Historical drafts are retained without loading an
unbounded in-memory history.
