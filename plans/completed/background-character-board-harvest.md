# Background Character Board Harvest
Status: complete
Related issue/specification: User-approved implementation plan

## Goal
Apply completed Character Asset Container renders through the shared background coordinator so boards are current on return.

## Current behavior
The coordinator skips `zet-character-containers`. The board progress endpoint calls `CharacterAssetContainerService.refresh_view`, which reconciles under the container file lock. Queue receipts prevent common collection from seeing results again.

## Implementation steps
### WP1 — Reuse board reconciliation
- Dependencies: none.
- Files/interfaces: `character_asset_container_service.py`.
- Work: Add a manifest-routed background entry point that acquires the container lock without waiting, rechecks owner/attempt/slot and commits through the existing refresh path.
- Acceptance: stale or foreign attempts do not change a board; busy locks defer work.
- Validation: disposable matching, stale-attempt and lock-contention checks.
- Status: complete. Disposable checks confirmed collection while away, overlap behavior, and stale-attempt fencing.

### WP2 — Discover and recover board jobs
- Dependencies: WP1.
- Files/interfaces: `ai_job_coordinator.py`, `ai_job_repository.py`, `storage_maintenance_service.py`.
- Work: Route character-container jobs to the board entry point, persist pending/settled application state, recover receipts with pending board commits and protect pending jobs from retention cleanup.
- Acceptance: coordinator and standalone one-shot collection apply prepared answers once and recover a receipt-to-board interruption.
- Validation: isolated queue checks for success, failure, retry and receipt recovery.
- Status: complete. Disposable receipt recovery passed.

### WP3 — Verify and document
- Dependencies: WP1–WP2.
- Files/interfaces: existing approved E2E scenario and `Docs/COMPONENTS/{QUEUES,LOCAL_CHARACTERS}.md`.
- Work: Verify return-to-board behavior, document ownership/recovery and record observed checks here.
- Acceptance: existing E2E suite and diff check pass.
- Validation: `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete. E2E suite and disposable return, overlap, recovery, stale-attempt and lock-contention checks passed.

## Constraints
Preserve producer/universe and attempt fencing, board revisions, lock/upscale behavior, and queue receipt semantics. Use prepared results and isolated storage. Do not run live AI.

## Progress and decisions
Plan started after confirming the coordinator skips the consumer and the foreground board refresh owns candidate reconciliation under a cross-process lock.

## Final results
`npm.cmd run test:e2e` passed all four approved scenarios (42.6s and 41.1s before final disposable checks). Temporary disposable browser scenarios passed for background harvest while away, concurrent foreground progress during collection, receipt recovery after resetting the board to its pre-save state, rejection of a mismatched attempt, and deferral/retry during real container-lock contention. Temporary scenarios and test-context additions were removed. Python 3.14 AST parsing and `git diff --check` passed. No live AI calls or production storage were used.
