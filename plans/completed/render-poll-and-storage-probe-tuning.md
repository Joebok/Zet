# Render polling and storage probe tuning
Status: complete
Related issue/specification: Joe's 2026-10-22 report of transient render-status 500s and frequent `.storage-probe-*` files.

## Goal
Reduce routine polling and false storage pauses during long image/LLM jobs. Report temporary storage unavailability as retryable HTTP 503. Preserve storage identity, catalog integrity, and receipt fencing.

## Current behavior
The Image Generation and local character pages poll every two seconds (`zet.js`, `local_asset_pipeline.js`). `StorageHealth.poll` runs full probes at most every two seconds and pauses a resource after a one-second wait; recovery needs two successes two seconds apart. A missing receipt or AI job record forces an extra full probe. `ImageGenerationWorkspace.detail` inspects jobs, so a forced probe can raise `StorageUnavailable` from a GET and reach the browser as 500. Production log and local recovery history show this exact path during renders.

## Desired behavior
Active render pages poll every five seconds. Routine storage checks run every ten seconds, pause only after a five-second stall, and require two successes at least five seconds apart. Expected missing receipt/job records share the routine health check while `require()` still validates the root. A temporary storage pause returns 503 with `Retry-After` on both affected render pages.

## Impact analysis
Files: `zet/web/static/zet.js`, `zet/web/static/local_asset_pipeline.js`, `zet/web/static/storage_status.js`, `zet/services/storage_health_service.py`, `zet/services/ai_queue_lifecycle_service.py`, `zet/repositories/ai_job_repository.py`, `zet/services/storage_bootstrap_service.py`, `zet/web/local_character_asset_pipeline_router.py`. No serialized format or dependency change. Documentation owners: `Docs/COMPONENTS/STORAGE_RECOVERY.md`, `Docs/COMPONENTS/QUEUES.md`, `Docs/CODE_MAP.md` if responsibility moves (none expected).

## Invariants and constraints
Keep universe isolation, queue ownership and receipt completion barriers, root identity checks, authoritative catalog protection, and at most one outstanding probe worker per monitor. Do not run live rendering or add maintained tests. Use existing fast E2E and disposable isolated checks for the changed contracts.

## Implementation steps
### WP1 — Poll cadence and stalled-probe threshold
- Dependencies: none.
- Files/interfaces: storage health service and three browser polling files.
- Work: set ten-second routine probes, five-second stall wait and recovery spacing, and five-second render polling; align storage banner cadence.
- Acceptance: steady-state probes and render GETs run at the requested cadence; a probe stalled under five seconds does not pause storage.
- Validation: isolated disposable timing check and JS syntax checks.
- Status: complete.

### WP2 — Expected missing records and retry response
- Dependencies: WP1.
- Files/interfaces: receipt/job repositories, storage bootstrap middleware, local character router.
- Work: remove full forced probes for expected missing records while retaining root verification; map temporary storage exceptions to retryable 503.
- Acceptance: missing receipt/job records do not multiply full probes; temporary storage errors on both render status endpoints return 503.
- Validation: isolated disposable API/service check.
- Status: complete.

### WP3 — Regression and knowledge sync
- Dependencies: WP1 and WP2.
- Files/interfaces: affected docs and completed plan.
- Work: run approved fast E2E, check diff, update verified storage/queue behavior, and archive plan.
- Acceptance: relevant existing scenarios pass, no unintended changes.
- Validation: `npm.cmd run test:e2e`; `git diff --check`; final diff review.
- Status: complete.

## Validation
Run narrow disposable timing/API checks with temporary storage, JS syntax checks, approved fast E2E, and `git diff --check`. Do not use the live library, queue, renderer, or optional live check.

## Risks and alternatives
A ten-second routine cadence can delay an idle outage indication and recovery display. Direct `require()` root checks and actual I/O failures still guard active operations. A five-second render cadence can delay visible completion by up to about five seconds.

## Progress and decisions
Initial production evidence: transient application-storage probe stalls resolved within seconds; an image-generation workspace traceback ended in `StorageUnavailable` from a forced missing-receipt probe. WP1 and WP2 are implemented. An isolated disposable check passed for a 1.2-second slow probe, ten-second coalescing, two spaced recovery successes, absent receipt/job records without forced probes, and HTTP 503 plus `Retry-After: 10` on both render-status routes. Diff review found that the old wait covered the entire multi-root cycle; the five-second stall limit now tracks each resource separately. A follow-up isolated check passed: three 2.1-second resource probes in one cycle remained healthy, while one 5.5-second resource probe paused. Python compilation, JavaScript syntax checks, `git diff --check`, and all four approved fast E2E scenarios passed after the final code change. No live renderer or production library/queue was used for validation.

## Final results
Render pages poll every five seconds, routine storage probes every ten seconds, and a resource pauses after a five-second stalled operation. Recovery requires two successes five seconds apart. Expected absent receipt/job records no longer force a probe each time. Temporary storage exceptions on both render-status routes return 503 with `Retry-After: 10`. Storage/queue documentation is synchronized. Validation and final diff review passed; live behavior under sustained rendering remains unverified.
