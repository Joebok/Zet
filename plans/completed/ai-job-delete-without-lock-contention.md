# Delete failed AI jobs without lock contention
Status: complete
Related specification: Joe's AI Queue deletion report, 2026-10-26.

## Goal and verified behavior
Delete an eligible failed job immediately, even while background collection holds
the coordinator lock. Currently AIJobCleanupService.delete requires that lock and
the common job lock within one second; query snapshots resurrect incomplete
cleanup markers as failures. Existing DeletedJobs fences already prevent replay.

## Impact and constraints
Owners: AIJobCleanupService, AIJobCoordinator, AIQueueQueryService; documentation
owners: Docs/COMPONENTS/AI_JOBS.md and ADR 0019. Preserve ownership, path confinement,
active transport checks, universe isolation, library images and persistent locks.
No production queue changes, dependencies or permanent tests. In-flight application
may finish before observing the deletion fence; cleanup must retain common locks.

## Luna sized work packets
### WP1 — Separate deletion commitment from payload cleanup
- Files: zet/services/ai_job_cleanup_service.py, ai_job_coordinator.py,
  ai_queue_query_service.py.
- Dependencies: none.
- Work: validate and atomically commit the deletion fence without collection locks;
  hide it immediately; retry pending payload cleanup in coordinator sweeps under
  existing locks. Preserve pending diagnostic errors in the marker.
- Acceptance: held coordinator/job locks do not reject Delete; locked payloads
  remain hidden and are cleaned on later sweeps, including after restart.
- Validation: disposable isolated service checks; approved fast E2E suite.
- Status: complete.

### WP2 — Document and verify final behavior
- Files: affected AI jobs documentation, code map and decision record; this plan.
- Dependencies: WP1.
- Acceptance: documents distinguish immediate deletion from eventual disk cleanup.
- Validation: Python syntax, git diff --check and final diff inspection.
- Status: complete.

## Validation and progress
S4 covers shared queue/history/background collection; no maintained test covers
deletion lock contention. Use disposable temporary storage for this gap.

Implemented immediate marker commitment, coordinator cleanup retries and query
suppression (including saved startup snapshots). Updated the AI jobs owner, code
map, ADR 0019 clarification and ADR 0034. No runtime deployment or live data edits.

Observed: first approved fast suite run passed all four scenarios (41.4s).
Disposable checks passed held coordinator/job locks, immediate snapshot removal,
idempotent Delete, simulated busy-file cleanup failure, restart cleanup, persistent
locks, active-state/foreign-producer refusal and startup snapshot filtering.
The first disposable attempt used an incorrectly constructed fake local root and
was correctly refused by path confinement; the corrected isolated fixture passed.
Changed Python AST parsing and git diff --check passed; final code diff reviewed.

## Final results
Final `npm.cmd run test:e2e` passed all four approved scenarios (41.3s) after
the last code changes. Disposable checks and Python syntax passed. Final diff
review and `git diff --check` passed. No permanent tests or dependencies added.
The local fix requires deployment to the running Zet instance; no production
jobs were deleted and no live AI services were used.

## Risks
Actual storage errors while writing the deletion marker still fail the request.
Cleanup retains unsafe-path/foreign-producer refusal, records errors and retries;
it must not turn a successful deletion into a visible failed job.
