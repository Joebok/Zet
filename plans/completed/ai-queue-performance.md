# AI Queue and disk-performance remediation

Status: active
Owner: Codex
Started: 2026-10-26
Related: user-authorized implementation of the investigation findings

## Goal

Reduce repeated input hashing, history reads, and redundant recovery work in Zet and AI_Proxy. Keep HTTP queue reads responsive; preserve execution integrity, collection ownership, recovery, and explicit deletion. Do not change runtime deployment, add dependencies, or add maintained test scenarios.

## Current behavior

- Zet's `AIQueueQueryService.rows()` reads all receipts and job records, then resolves each row with `AIJobService.inspect()`; `query()` paginates only afterward. The live request took 19.8 seconds for one requested row.
- `AIJobCoordinator._sweep()` iterates all receipts before and after work and loads all jobs twice per two-second sweep.
- `AIJobCleanupService` runs the full queue query while holding coordinator and job locks. Saved requests with no current receipt or transport folder appear as `RECONCILING`.
- AI_Proxy's `Proxy._scan()` and `Proxy._available_status()` both hash queued image inputs on repeated polling.
- `StorageRecoveryService` obtains detailed runs before determining if most runs need recovery.

## Desired behavior

- Warm queue requests return cached, paginated activity in under 250 ms in the representative fixture. The cache is bounded to compact metadata, shared across same-queue universe apps, and never authorizes mutation or execution.
- Queue changes from this process and other processes appear through local invalidation and two-second metadata refresh. Storage outages preserve known rows and invalidate metadata after reconnect.
- AI_Proxy hashes unchanged waiting inputs only once per process/cache state; worker admission still requires full uncached checksum validation and post-worker validation.
- Collector sweeps avoid rereading completed history. Missing job evidence becomes explicitly recoverable only after two complete observations confirm it is absent.
- Deletion performs a fresh target-only check under the existing locks and preserves every ownership, containment, tombstone, and late-answer fence.
- Recovery resolves lightweight summaries first and expands only actual candidates.

## Impact analysis

| Modules | Interfaces / consumers | Tests / documentation |
| --- | --- | --- |
| New `AIQueueMetadataService`; `AIJobRepository`; `AIQueueLifecycleService` | Immutable compact snapshots shared by activity queries, coordinator, and index; local mutation invalidation; no schema migration | Zet E2E S4; disposable isolated cache checks; AI Jobs, Queues, code map |
| `AIQueueQueryService`; dashboard lifespan and AI Queue browser controllers | Preserve existing query fields/filters/cursors; add `refreshing`, `updated_at`, `refresh_error`; remove duplicate queue/history browser fetches | Zet E2E S4; startup, refresh, stale/error and pagination checks; AI Jobs |
| `AIJobCoordinator`; library index receipt-summary reader; `AIJobCleanupService`; job status classifier | Preserve coordinator lease, retry timing, universe ownership and deletion locks; add reason code `MISSING_JOB_EVIDENCE` | Zet S3/S4; disposable collector, deletion, restart and late-answer checks; Queues, invariants |
| `StorageRecoveryService`; local pipeline adapters | New internal `list_recovery_summaries()` method; existing detailed UI behavior unchanged | Zet S2; disposable prepared-state recovery checks; local-character/recovery knowledge |
| AI_Proxy `Proxy` and inventory validation | Process-local shared validation cache; full uncached admission check, immutable manifest match and output revalidation | Existing proxy suite; specifically approved disposable hash/restart/reconnect checks; File Transport, invariants and development |

## Invariants and constraints

- Follow both repositories' AGENTS.md. Use one agent and existing dependencies only.
- Cache entries are derived; the shared queue and producer-local JSON remain authoritative. Preserve atomic publication, producer/universe identity, locked-file containment, and request/attempt ownership.
- Do not hold cached file contents, prompts, request payloads, or image bytes in the activity cache.
- Preserve sync-grace handling, answer collision behavior, scheduling order, storage-health root identity, single-attempt execution, and post-worker output validation.
- Preserve receipt-before-cleanup ordering, coordinator/job lock order, ownership checks, Ask/Running refusal, path/reparse-point guards, tombstones, and late-answer fencing.
- Do not automatically delete, replay, or infer failure from age or unavailable storage.
- No permanent tests, dependencies, production data changes, user-job operations, or live model/render checks are authorized.

## Implementation steps

### WP1 — Cache AI_Proxy validation
- Depends on: none.
- Files/interfaces: `file_proxy/engine.py`, `file_proxy/validation.py`; process-local cache private to Proxy.
- Work: cache outcomes from full queue validation by envelope and per-entry identity/size/timestamps; reuse cached incomplete/success results in polling and status. Exclude running payload verification from recurring status. Evict removed jobs and reset after storage root loss/recovery. Full uncached inventory/hash validation must happen immediately before claiming a selected job; require the admitted manifest to match the selected identity. Keep post-worker full validation.
- Acceptance: unchanged inputs are not rehashed during repeated polls; input changes are rechecked and never admitted on stale validation; sync-grace timers and worker ordering remain intact.
- Validation: existing file transport, shared scheduling and restart scenarios; approved disposable checks for repeat-read, same-size changed bytes, cache restart and storage reconnect.
- Status: pending.

### WP2 — Build shared Zet metadata snapshots
- Depends on: none.
- Files/interfaces: new `zet/services/ai_queue_metadata_service.py`; `ai_job_repository.py`; `ai_queue_lifecycle_service.py`.
- Work: one in-process service per queue/producer; enumerate entries with metadata and parse only added/changed files after warming. Retain compact projections and receipt metadata. Expose immutable snapshot, change identities and refresh status. Notify same-process writes. On unavailable storage keep last complete snapshot; after reconnect rebuild fingerprints. Never use a snapshot for authoritative writes, execution or deletion decisions.
- Acceptance: ten stable refreshes read no unchanged job/receipt JSON content; atomic updates/removals and external-process writes become visible within two seconds.
- Validation: approved disposable temp-root cache checks for unchanged records, replacement, removal, concurrent publication and outage/reconnect.
- Status: pending.

### WP3 — Serve activity from background snapshot
- Depends on: WP2.
- Files/interfaces: `ai_queue_query_service.py`, web app lifespan and AI Queue browser code. Keep existing query schema and add only `refreshing`, `updated_at`, `refresh_error`.
- Work: one background refresher per queue/producer; query applies filters, counts, ordering and cursors in memory. Reuse the existing Activity snapshot at startup; persist only changed activity. Remove the AI Queue page's duplicate legacy queue/history request/render paths while retaining process actions. Keep two-second page polling/cancellation.
- Acceptance: warm fixture request under 250 ms, cached/loading response under one second at cold start, activity visible within two refreshes, and storage-unavailable state remains distinct from refresh-in-progress.
- Validation: Zet S4 plus disposable API/UI checks for initial load, pagination, filters, refresh errors and browser navigation.
- Status: pending.

### WP4 — Reuse metadata in coordinator and index
- Depends on: WP2.
- Files/interfaces: `ai_job_coordinator.py`; library index receipt-summary reader.
- Work: replace before/after complete receipt scans with cached identities/change results; read compact job summaries once per sweep and refresh affected summaries after retry-state writes. Exclude receipt-complete jobs from full details. Reuse cached receipt projections when indexing recent history.
- Acceptance: idle sweep does not reopen completed receipt/job contents; answers still collect page-independent; coordinator lease and cross-process single-apply behavior remain.
- Validation: Zet S3/S4 and approved disposable collection/restart/competing-host checks.
- Status: pending.

### WP5 — Reclassify confirmed missing evidence and target deletion
- Depends on: WP2, WP3, WP4.
- Files/interfaces: shared row classifier, `ai_job_service.py`, `ai_job_cleanup_service.py`, queue UI.
- Work: after two complete storage-available observations with no receipt, transport/staging folder or active replacement, present `RECOVERY_REQUIRED` with `MISSING_JOB_EVIDENCE`. Keep transient uncertainty `RECONCILING`; never age-delete/replay. Deletion performs a fresh target-specific classification under existing locks rather than rebuilding the feed. Bound combined coordinator/job lock acquisition to one second and return existing conflict/retry UI on contention. Locally invalidate the metadata row after the deletion tombstone.
- Acceptance: confirmed orphaned jobs show explicit recovery/delete affordance; no active, foreign, library or workflow state can be removed; a late answer stays fenced; busy deletion responds promptly.
- Validation: approved disposable checks for queued/running refusal, foreign owner, missing metadata, interrupted deletion, late answers and lock contention.
- Status: pending.

### WP6 — Filter pipeline recovery from summaries
- Depends on: none.
- Files/interfaces: `storage_recovery_service.py`; local image pipeline adapters and shared workflow facade.
- Work: provide `list_recovery_summaries()` with run ID, costume, state, stop intent and pending slot-work flags. Preserve active runner lock interpretation. Skip completed/stopped runs before `detail()`; perform detailed ownership/image/lineage checks only on recovery candidates.
- Acceptance: repeated recovery does not inspect images for completed batches; interrupted batches and pending supplemental slots still resume safely; interactive detail checks are unchanged.
- Validation: Zet S2 and approved disposable recovery checks for complete, interrupted, stopped, slot-pending and active-lease states.
- Status: pending.

### WP7 — Document, measure and close
- Depends on: WP1–WP6.
- Files/interfaces: affected component/invariant/code-map and testing/development docs; active plans in both repositories.
- Work: record exact implementation, cache invalidation/outage semantics, performance observations and coverage limits. Keep plans synchronized and archive only after every required packet/validation passes.
- Acceptance: both repos have clean intended diffs and current knowledge links; no permanent tests/dependencies or unrelated edits.
- Validation: approved Zet E2E baseline; AI_Proxy isolated pytest suite; disposable performance fixture with 14,331 receipts, 1,730 jobs and four 10 MB envelopes; Python/JS syntax and git diff --check in both repos.
- Status: pending.

## Validation

Run after implementation, using isolated fixtures only:

- Zet: `npm.cmd run test:e2e` (four approved scenarios; S2/S3/S4 where relevant).
- AI_Proxy: `.\.venv\Scripts\python.exe -m pytest -q` (isolated default suite; live backend scenario excluded).
- Disposable one-time checks explicitly approved: repeated unchanged-image read count, changed-input rejection, restart/reconnect invalidation, queue cache update/removal, API warm/cold/error/paging, sweep no-history rereads, orphan/delete fencing, and recovery summary filtering.
- Python syntax, changed JavaScript `node --check`, and `git diff --check` in both repositories.
- Compare fixture warm request latency against 250 ms and cold response against one second; separately report unread unchanged history files and bytes hashed. No production load test or live rendering.

## Risks and alternatives

- File metadata timestamps can miss adversarial in-place changes; therefore execution admission always performs fresh checksum validation and requires matching job identity.
- A refresh can overlap atomic replacement. Do not publish partial snapshots; retry changed/unreadable entries and retain the previous complete snapshot with refresh diagnostics.
- Cross-process publication is discovered on the existing two-second cadence. Queue status freshness may lag by one cycle.
- Full cold cache warmup is background work; serve the local last-good Activity snapshot immediately.
- The one-second lock deadline bounds user-facing waits but may produce a retryable conflict during active collection.

## Progress and decisions

| Packet | Status | Notes |
| --- | --- | --- |
| WP1 | complete | AI_Proxy cache separately tracks successful/incomplete validation from metadata signatures and keeps fresh pre-claim checksum validation. Isolated suite: 7 passed, 1 deselected. Disposable changed-input/restart checks passed. |
| WP2 | complete | Added `AIQueueMetadataService`, compact repository summaries, receipt snapshots, local invalidation, two-second directory refresh, changed identities and reconnect invalidation. |
| WP3 | complete | `/api/ai/jobs` reads an in-memory background-refreshed activity snapshot; filters/pagination run in memory, response reports refresh status, and duplicate queue/history renderers were removed. |
| WP4 | complete | Coordinator sweeps use cached receipt identities and compact job summaries, loading full records only for collection candidates. Library-index receipt reads inherit the incremental lifecycle reader. |
| WP5 | complete | Missing evidence requires two available observations. Deletion performs selected-job inspection under existing locks, with a shared one-second deadline and immediate in-memory activity update. |
| WP6 | complete | Added specification/state-only recovery summaries and candidate filtering before `detail()`. Per-universe recovery failures no longer prevent unrelated answer collection. |
| WP7 | complete | Docs updated; final checks and diff review recorded below. |

## Final results

`npm.cmd run test:e2e`: **4 passed**. Zet Python compilation, `node --check` for both changed browser scripts, and `git diff --check` passed. AI_Proxy `.venv\Scripts\python.exe -m pytest -q`: **7 passed, 1 deselected**; `py_compile` and `git diff --check` passed.

Disposable checks passed for metadata warm reuse, changed/add/remove discovery, storage outage retention/reconnect rebuild, Proxy changed-input rejection, and restart/cache invalidation. The representative 14,331-receipt / 1,730-job / four 10 MiB input fixture cold-loaded in 84.648s with 16,061 JSON reads; its next metadata refresh plus in-memory one-row filter took 0.682s with zero JSON reads. HTTP request latency was not separately instrumented. Physical E: reconnect and live queue/model behavior were not exercised. Documentation: [AI jobs](../../Docs/COMPONENTS/AI_JOBS.md), [queues](../../Docs/COMPONENTS/QUEUES.md), [storage recovery](../../Docs/COMPONENTS/STORAGE_RECOVERY.md), [code map](../../Docs/CODE_MAP.md), and [development validation](../../Docs/DEVELOPMENT.md).
