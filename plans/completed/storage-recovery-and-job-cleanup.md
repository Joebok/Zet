# Storage recovery false alarm and failed AI job cleanup
Status: active
Related issue/specification: User report on 2026-10-17; none

## Goal
Stop transient stat failures from reporting an available configured library as disappeared, and let the user delete failed/recovery-required AI queue records whose producer ownership metadata is missing. Preserve active-job and explicit foreign-owner protections.

## Current behavior
- `StorageHealth.require` immediately pauses a resource when one `Path.stat()` raises `FileNotFoundError`, without asking the storage probe to confirm the path is unavailable. `StorageHealth._probe_cycle` already performs a read/write/read probe and requires two spaced successes to recover.
- `AIJobCleanupService` rejects deletion unless surviving records positively identify the current hostname. This blocks malformed retained records even when they are explicitly eligible and no foreign producer is identified.
- Existing approved E2E S4 covers queue history/activity but not these branches. No permanent test will be added without separate approval.

## Desired behavior
- A fresh successful full storage probe prevents a single stale/momentary `FileNotFoundError` from changing resource state to `PAUSED_STORAGE`; a confirmed missing or inaccessible root still pauses.
- Failed/recovery-required cleanup proceeds when ownership evidence is absent, but refuses any explicit foreign producer, active Ask/Running job, identity conflict, linked path, or out-of-root deletion.

## Impact analysis
- `zet/services/storage_health_service.py`: resource `require` behavior; storage banner/API status callers.
- `zet/services/ai_job_cleanup_service.py`: explicit cleanup admission; `ZetApp.delete_failed_ai_job`, API route and `ai_queue.js` callers unchanged.
- Documentation owners: `Docs/COMPONENTS/STORAGE_RECOVERY.md`, `Docs/COMPONENTS/AI_JOBS.md`, `Docs/COMPONENTS/QUEUES.md`, `Docs/DECISIONS/0019-failed-ai-job-deletion.md`, `Docs/CODE_MAP.md` as needed.
- Existing regression scope: S4; disposable focused checks can cover new branches without adding maintained scenarios.

## Invariants and constraints
- Preserve removable-storage pause/recovery, root identity checks, local machine ownership markers, queue coordinator/job locks, deletion fence, containment/link checks, and exclusion of images/workflow records.
- No production queue or live storage mutation during validation.
- No new dependencies or permanent tests.

## Implementation steps
### WP1 — Confirm storage disappearance before pausing
- Dependencies: none.
- Files/interfaces: `storage_health_service.py:StorageHealth.require`.
- Work: on `FileNotFoundError`, force a fresh bounded health probe and re-check the configured root before marking it paused; preserve pause behavior when probe/stat confirms failure.
- Acceptance: a transient stat error followed by successful full probe leaves resource available; a genuinely missing root is paused with recovery guidance.
- Validation: disposable isolated service check; approved E2E baseline.
- Status: complete. `require()` now forces the existing full probe after a direct
  `FileNotFoundError`, then rechecks the root; uninitialized optional roots retain
  their prior behavior.

### WP2 — Clean failed records without absent ownership metadata
- Dependencies: none.
- Files/interfaces: `ai_job_cleanup_service.py:AIJobCleanupService._delete`.
- Work: treat ownership as conflicting only when an explicit producer ID belongs to another host; allow absent metadata on otherwise eligible rows while retaining all activity, identity, path and link guards.
- Acceptance: eligible unowned record cleans and gets a deletion fence; foreign, queued/running, conflict and linked jobs remain blocked.
- Validation: disposable isolated service check for missing metadata and deletion
  fencing; approved E2E baseline. Foreign/active refusal branches were reviewed
  in source and retain their existing guards.
- Status: complete. Absent producer metadata is allowed for eligible rows; explicit
  foreign producer IDs remain rejected. Queue/running, identity, link and
  containment checks remain unchanged.

### WP3 — Update knowledge and close plan
- Dependencies: WP1, WP2.
- Files/interfaces: storage recovery, AI jobs/queues, ADR 0019, code map, this plan.
- Work: document confirmed behavior and validation limits; archive completed plan.
- Acceptance: docs match implementation and exact validation outcomes.
- Validation: `git diff --check`; review final diff.
- Status: complete. Updated storage recovery, AI jobs/queues, ADR 0019, code map and
  Development verification notes.

## Validation
Observed: disposable isolated check passed for a transient stat failure and a
metadata-free eligible job deletion/deletion fence. `npm.cmd run test:e2e` passed
all four scenarios in 39.1 seconds. `git diff --check` passed. No live library,
queue, model or render service.

## Risks and alternatives
An unowned retained folder may have been produced elsewhere on a shared queue. Explicit foreign producer metadata remains a hard rejection; deleting a missing-owner row is intentional cleanup requested by the user and still operates only on deterministic job-scoped paths.

## Progress and decisions
- Initial inspection confirmed both failures in the named owning services.
- The isolated cleanup check first failed because its synthetic paths did not
  mirror `queue_local_state_root`; correcting the disposable fixture to use the
  repository path contract made the check pass. No product change was needed for
  that fixture setup issue.

## Final results
Completed. Final diff review found only the scoped service, documentation and plan
changes listed above. Validation passed as recorded; foreign/active refusal branches
were source-reviewed and no live queue/library was touched.
