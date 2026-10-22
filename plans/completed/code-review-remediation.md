# Code review remediation
Status: complete
Related issue/specification: [Docs/CodeReview.md](../../Docs/CodeReview.md), reviewed before `1f271251aa641539b18430a9818e24cb0d5858e4`.

## Goal
Fix verified file confinement, universe ownership, atomic publication, startup recovery, and request latency issues. Improve catalog query scaling and prevent duplicate workflow queueing. Preserve existing durable records and approved test scope. The A1/A2 architectural extractions and unproven sanitizer migration are excluded.

## Current behavior
- `/api/file` serves `PathService.resolve_path` results without confinement; template download links omit universe context.
- Prompt analysis uses the startup singleton and loads every historical job into memory. Durable workflow execution yields `AIPending`; status still shares job locks with preparation and result collection.
- Local asset chain publication derives labels from numeric staging paths and commits each catalog asset separately before updating local JSON.
- Universe selection writes directly; per-request universe discovery scans descriptors synchronously.
- Inventory routes slice only after full entity-catalog hydration; entity and variant projections issue per-row queries.
- Async upload routes call blocking services on the event loop; continuation resume can enqueue duplicate task IDs.
- Coordinator host state and per-universe caches can remain stale after project settings reload.

## Desired behavior
Serve files only from the selected universe or repository shared library. Bind prompt jobs and current settings to their owning universe. Make catalog publication transactional and repairable across its JSON boundary. Bound request work, catalog I/O and continuation queue submissions while preserving API response contracts, stored batch records, workflow identities and the approved E2E suite.

## Impact analysis
Affected owners: `PathService`/file route; `UniverseService`/request middleware; prompt and workflow services; entity catalog repository/service; `LocalAssetStoreService`; coordinator; upload routes. Entity catalog migration advances one version and retains the existing backup-on-upgrade behavior. Publication journal/receipt formats must be documented. No new permanent scenario, dependency, live model/render call, or data cleanup is approved.

## Invariants and constraints
- Universe-owned files/results stay bound to their universe; symlinks/junctions cannot bypass serving containment.
- `catalog.sqlite3` remains authoritative; published images must exist before catalog commit. Reused origins and logical references cannot be archived as compensation.
- Existing local assets, prompt drafts, frozen AI requests, queue receipts and review schemas remain readable. No automatic prompt-record deletion.
- Run the approved four E2E scenarios serially; disposable checks use temporary roots. No coverage expansion without Joe's approval.

## Implementation steps

### WP1 — Confine file serving · C1
- Dependencies: none. Files: `path_service.py`, `web/app.py`, `static/zet.js`.
- Add a serving-specific resolver limited to the selected universe and `Shared_Library`; resolve junctions/symlinks and reject traversal, directories and outside paths with 404. Keep internal generic resolution compatible. Add universe context to template-download URLs.
- Acceptance: permitted universe/shared images and downloads work; traversal, absolute outside paths, foreign nested universes and supported junction escapes return 404.
- Validation: disposable route checks; Python syntax; `git diff --check`.
- Status: complete.

### WP2 — Recover universe selection · C7
- Dependencies: none. File: `universe_service.py`.
- Use `write_json_atomic`; recover malformed JSON/shape to the existing deterministic first-universe fallback, with a warning. Preserve errors for inaccessible storage.
- Acceptance: valid/missing/malformed records select predictably; a failed atomic replacement preserves old bytes.
- Validation: disposable temporary-container checks; Python syntax; `git diff --check`.
- Status: complete.

### WP3 — Make prompt jobs universe-bound and disk-backed · C2/C5/P6
- Dependencies: none. Files: `image_prompt_generation_service.py`, `web/app.py`.
- Resolve start/status against the request-bound app. Persist and validate universe ownership, resolving legacy ownership from its containing store. Remove full-history loading and the in-memory job map; read one record per operation. Keep locks for state transitions, outside model preparation/collection. Preserve continuation replay and checksum checks.
- Acceptance: two-universe ownership and replay work; foreign jobs are rejected; suspended model jobs do not block status reads; drafts remain retained.
- Validation: temporary-library checks with prepared/suspended responses; Python syntax; `git diff --check`.
- Status: complete.

### WP4 — Refresh app ownership after settings changes · C8
- Dependencies: WP3. Files: `web/app.py`, `ai_job_coordinator.py`.
- Invalidate/rebuild cached apps lazily after project-wide automation settings saves, stopping obsolete reconcilers. Resolve the current coordinator host app before sweeps and refresh repository/recovery references when roots change. Preserve compatible generation-service rebinding and durable work.
- Acceptance: host and second-universe requests use current settings and retain one active reconciler each.
- Validation: disposable reload checks; Python syntax; `git diff --check`.
- Status: complete.

### WP5 — Remove universe discovery from the event loop · P3
- Dependencies: WP4. Files: `universe_service.py`, `web/app.py`.
- Cache successful descriptors for two seconds, invalidate on local create/update, force refresh for universe listing, and offload cache misses/refresh to a worker thread. Bind canonical descriptor IDs.
- Acceptance: repeated requests avoid scans, equivalent trimmed IDs share one app, explicit refresh observes changes, and slow discovery does not block unrelated requests.
- Validation: temporary service and async middleware checks; Python syntax; `git diff --check`.
- Status: complete.

### WP6 — Preserve meaningful publication labels · C3
- Dependencies: none. Files: `local_asset_store_service.py` and Body/Head/Assembly/Dressing callers.
- Pass labels explicitly through direct locks and chain promotion. Use batch name or a character/phase/pipeline/view fallback; preserve costume classification and origin identities. Do not relabel historical catalog rows.
- Acceptance: direct and chain publication, including Head-Image Edit, retain descriptive labels.
- Validation: disposable catalog checks; approved S2; Python syntax; `git diff --check`.
- Status: complete.

### WP7 — Publish a chain in one catalog transaction · C4
- Dependencies: none. Files: `entity_library_repository.py`, `entity_library_service.py`.
- Add a transactional batch publication interface shared by single-image publication. Stage image bytes first; transact rows, classifications, status restoration and logical references together. Add a schema-versioned receipt keyed by operation ID; reuse origins/asset IDs safely on retry.
- Acceptance: injected failure leaves no partial catalog approval; prior reused assets/references survive rollback; older catalogs upgrade with backup.
- Validation: disposable catalog initialization/migration and fault-injection checks; Python syntax; `git diff --check`.
- Status: complete.

### WP8 — Recover the catalog/local-state boundary · C4
- Dependencies: WP7. Files: focused publication-recovery service, `local_asset_store_service.py`, `storage_recovery_service.py`.
- Journal previous/next local JSON before publication. Under the workspace lock, write intended local state before committing the catalog receipt. On recovery, finish JSON when the receipt committed; otherwise restore previous JSON and remove only newly staged files. Recover pending operations before local-store reads; never archive reused assets as compensation. Document the protocol in an ADR.
- Acceptance: interruption on either side of JSON replacement/catalog commit converges idempotently after restart.
- Validation: temporary-root crash-point/fault-injection checks; Python syntax; `git diff --check`.
- Status: complete.

### WP9 — Page catalog queries before hydration · P1
- Dependencies: none. Files: `entity_library_service.py`, `entity_library_repository.py`, `web/app.py`, inventory rendering in `zet.js`.
- Add SQL-filtered/ordered `list_asset_page` with the existing response envelope; hydrate relationships for page IDs only and chunk bulk queries. Preserve Unicode casefold search, filter semantics, selected logical references and unpaged internal/picker contracts. Check file availability for page rows and show missing files explicitly; total counts catalog matches.
- Acceptance: API page results/order/totals match intended filters; large catalogs hydrate only the requested page; missing files remain visible as unavailable metadata.
- Validation: disposable comparison/query-count checks; approved S1; JS/Python syntax; `git diff --check`.
- Status: complete.

### WP10 — Batch entity and variant metadata · P2
- Dependencies: WP9. Files: `entity_library_service.py`, `entity_library_repository.py`.
- Replace per-row counts with aggregate queries; batch descriptors while preserving fields, filters, distinct-image counts and ordering.
- Acceptance: output matches current projection; query/connection counts stay bounded as entities/variants grow.
- Validation: disposable projection/query-count checks; approved S1; Python syntax; `git diff --check`.
- Status: complete.

### WP11 — Offload blocking upload work · P4
- Dependencies: none. Files: `web/app.py`, `local_character_asset_pipeline_router.py`.
- Keep body reads asynchronous, then offload service resolution, multipart parsing and blocking writes/catalog work. Cover the seven review route groups and current local Head/Head-Image Edit source and view-override uploads. Preserve limits, error mapping and universe context.
- Acceptance: slow uploads do not stall concurrent status/health requests; success/rejection behavior and limits remain intact.
- Validation: disposable slow-service and upload checks; approved S1/S2; Python syntax; `git diff --check`.
- Status: complete.

### WP12 — Deduplicate queued continuations · P5
- Dependencies: none. File: `ai_workflow_service.py`.
- Use a locked process-wide active registry keyed by lifecycle root, universe and task ID across submit/resume. Register before enqueue, release on completion, suspension, failure or submission error. Keep cross-process file locks and recovery sweeps.
- Acceptance: repeated sweeps queue one in-process instance; suspended work can resume; universes remain independent.
- Validation: disposable held-worker/resume checks; approved S4; Python syntax; `git diff --check`.
- Status: complete.

## Validation
Packet checks used isolated temporary roots. No permanent tests or live AI/render services were added. Final checks: `npm.cmd run test:e2e`, changed-file Python compilation, JavaScript syntax, `git diff --check`, and full diff review.

## Risks and alternatives
SQLite and JSON cannot share a native transaction. The publication receipt plus journal provides idempotent recovery while workspace reads are fenced. Inventory totals will count matching catalog records, including files that are missing; the page will mark availability. Existing unpaged internal and picker callers retain their contract.

## Progress and decisions
- Confirmed path traversal, numeric labels, partial chain publication, malformed selection failure and duplicate resume submission with disposable probes.
- Confirmed a 1,000-asset list hydrates all 1,000 records and stats all 1,000 paths before returning a 10-row route page; 50 entity rows generated 151 repository calls.
- Production AI continuation returns `AIPending`; C5 is limited to prompt preparation/collection lock duration.
- A1/A2 are deferred by user preference. C6 has no demonstrated path split and no migration is planned.
- Baseline `npm.cmd run test:e2e`: 4 approved scenarios passed (39.8s). `git diff --check` passed before implementation.
- Implemented all twelve packets. Publication recovery is owned by `LocalAssetPublicationRecoveryService`, invoked by startup storage recovery and before local lock reads. Inventory remains unpaged for internal callers and applies SQL filters/pagination before page hydration.
- Post-change `npm.cmd run test:e2e`: all four approved scenarios passed (final run 38.7s). Changed Python files compiled; `node --check zet/web/static/zet.js` and `git diff --check` passed.
- Disposable probes passed selection recovery and failed-write preservation; permitted/outside/foreign path resolution; descriptive Head-Image Edit lock labels; one-row catalog paging; two-query entity and variant metadata projections; pre-commit catalog rollback; committed/uncommitted publication recovery; and duplicate continuation enqueue suppression.
- The disposable probes did not exercise a mounted `/api/file` route, symlink/junction escape or nested legacy-container path, upload response/slow-upload concurrency, full two-universe prompt start/status, or settings reload with multiple cached apps. Those paths were checked by source inspection and the approved E2E baseline, so those specific route/concurrency/ownership branches remain unverified by a dedicated probe.
- Updated Library, AI Jobs, Storage Recovery, Local Characters, Data Model, Architecture, Invariants, Code Map, Testing, and ADR documentation. Added ADR 0029 for the cross-store publication protocol.

## Final results
All approved implementation packets are complete. Validation results and remaining probe limits are recorded above. C6 and A1/A2 remain deferred as agreed.
