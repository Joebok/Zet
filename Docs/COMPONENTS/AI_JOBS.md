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
  request identities under the existing producer-local queue root in `Jobs/`.
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
  remain with domain services.
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
The former Body-Reference-only Codex panel is removed.

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
| Ranking, prompt improvement, gate diagnostics | Codex/Ollama | common structured/result delivery and existing domain application | vision where images are supplied |

Every row publishes through `FileProxyClient`; no new request uses the legacy app
workers. Those workers remain solely for immutable envelopes already published.
Their runtime evidence lookup is compatibility execution metadata; model selectors
and the compatibility `list_models()` API read the proxy-owned catalog. Repository
coding automation and Codex quota inspection are outside creative job execution.
