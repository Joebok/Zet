# Failed AI queue job cleanup
Status: complete

## Goal and desired behavior
Confirmed per-job deletion for HARVEST_FAILED / RECOVERY_REQUIRED activity removes
owned queue payloads and local job state. Preserve library assets and active work.
No live queue cleanup, deployment, dependencies or permanent tests are authorized.

## Current behavior and impact
AIQueueQueryService merges transport, Inbox, Jobs and Receipts. FileProxyClient,
AIJobService, the coordinator and legacy harvester can adopt retained answers.
Ownership, common job locks and universe isolation must survive deletion.
Docs owners: AI_JOBS, QUEUES, DATA_MODEL and CODE_MAP; S4 is regression coverage,
not dedicated cleanup coverage.

## Implementation steps (Luna sized packets)
### WP1 — Owned deletion and late-answer fence
- Dependencies: none.
- Files: focused ai_job_cleanup_service; AIJobRepository, AIJobService,
  FileProxyClient, lifecycle and harvester deletion guards.
- Work: validate status/ownership/paths under coordinator and job locks; delete
  only known job-scoped queue/state paths; retain a hashed deletion fence.
- Acceptance: reject active/foreign/linked paths; report partial failures and
  allow retry; do not adopt, apply or republish a deleted identity.
- Validation: disposable private-queue checks, Python syntax.
- Status: complete.
### WP2 — Queue controls
- Dependencies: WP1.
- Files: web/app.py, static/ai_queue.js, templates/index.html, query service.
- Work: thin DELETE endpoint and confirmed per-row action; refresh activity and
  surface cleanup errors, including retryable partial deletion.
- Acceptance: only eligible rows offer deletion; deleted jobs stay absent after reload.
- Validation: disposable isolated API/browser checks; JS syntax; approved fast E2E.
- Status: complete.
### WP3 — Knowledge and final review
- Dependencies: WP1/WP2.
- Files: affected component/data/code-map docs and short durable-contract ADR.
- Work: record cleanup boundary, fencing and observed validation; review diff.
- Acceptance: docs reflect actual behavior and validation limits.
- Validation: git diff --check; final diff inspection.
- Status: complete.

## Risks and decisions
Deletion is irreversible at runtime and needs browser confirmation. Shared answers
without any verifiable local ownership must be refused. A minimal producer-local
deletion marker survives payload cleanup to fence late sync and continuation replay.
Library outputs and shared lock files are never deletion targets. A busy file must
leave a visible retryable cleanup error rather than silently claim full deletion.

## Progress and decisions
- Implemented the focused service, ZetApp/API/browser action and deletion guards.
- Deletion removes known job-scoped queue/local artifacts, including legacy
  archive suffixes and interrupted local transfers; it never follows diagnostic
  output destinations into library/domain state.
- Shared ownership must be verifiable; a local Inbox establishes local provenance.
- A minimal version-1 DeletedJobs fence survives deletion. Incomplete cleanup is
  visible and retryable. See ADR 0019; no new dependency or maintained test added.

## Final results
- `npm.cmd run test:e2e` with verified `C:\Python314\python.exe`:
  all four approved scenarios passed (36.3s).
- Disposable `test-results/check_ai_job_cleanup.py`: passed failed/recovery
  cleanup, idempotency/late sync, library preservation, foreign/active/terminal/
  invalid/link refusal and busy-file partial cleanup/retry. Ran under Python 3.14.
- Disposable API/Chromium journey: passed terminal DELETE rejection, Cancel and
  Confirm, HARVEST_FAILED and RECOVERY_REQUIRED deletion, immediate removal/reload.
  The first run exposed an incomplete disposable fixture (TRANSFERRING instead of
  missing-route RECOVERY_REQUIRED); corrected fixture and rerun passed.
- Python AST, JS syntax and `git diff --check` passed; final diff reviewed.
- AI_JOBS, QUEUES, DATA_MODEL, CODE_MAP and ADR index updated. No live queue files
  were deleted, no live inference ran, and no production deployment was performed.
