# Locked Draft batch status
Status: complete

## Goal and current behavior
Tsaeytte Youth Head-Image Edit batch `20261023_070525_864928` has eight
selected, locked Draft images. Two old BACK candidates retain RUNNING and one
rear-quarter candidate retains FAILED despite available images. The mode summary
uses raw candidate statuses, unlike detail's image-first render projection, so
Batches incorrectly reports Draft as Running. Final has independent pending work.

## Impact and constraints
Owner: `zet/services/local_mode_progress_service.py`; documentation:
`Docs/COMPONENTS/LOCAL_CHARACTERS.md`. Preserve pending-slot ownership, mode
isolation, selections, image bytes, locks, rankings and portable serialization.
No permanent tests, model calls, deployment, or other batch repairs.

## Luna sized work packets
### WP1 — Correct mode projection
- Dependencies: none.
- Files: `local_mode_progress_service.py` and disposable checks under `test-results/`.
- Work: prefer available image evidence over stale render labels, retaining
  explicit pending-slot membership as active work.
- Acceptance: image-backed stale RUNNING/FAILED candidates do not block Complete;
  absent images and explicit pending slots still block; Final remains independent.
- Validation: disposable temporary-file projection checks and approved S2.
- Status: complete.

### WP2 — Reconcile reported Draft and document
- Dependencies: WP1.
- Files: reported batch `state.json`, component documentation, this plan.
- Work: under the existing state lock, verify eight matching locks and images,
  back up the state, normalize only stale Draft candidate statuses and shared
  legacy Draft status. Preserve Final work and all image/selection/lock data.
- Acceptance: Draft projects Complete; Final pending state remains identical;
  hosted Batches no longer lists Draft as actionable.
- Validation: compare state before/after, verify lock/image hashes, hosted GET,
  `git diff --check` and final diff review.
- Status: complete.

## Risks and limits
The original interrupted status-write cause is not established. Saved image
evidence proves the render completed; overrides explain the selected replacement,
but do not establish how historical labels became stale. Hosted code deployment
is outside scope; data reconciliation should repair this batch with existing code.

## Final results
- Mode projection now uses available image evidence to disregard stale active or
  failed labels, preserving explicit pending-slot membership and review waits.
- Reconciled only Draft candidate statuses B-001, B-003 and BR-005 and the shared
  legacy Draft status (Complete), under run and asset locks. State backup:
  `test-results/locked-draft-status/state-before-20261031_164133.json`.
- Verified all eight selected originals and locked copies against stored SHA-256
  values; asset metadata and image bytes are unchanged. All other state fields,
  including Final candidates and pending IDs, were preserved.
- Hosted `/api/local/batch-status?task_universe=Moonsea` confirms this batch has
  no actionable Draft entry; its Final entry remains Running. No code deployment
  or live model execution was performed.
- Disposable projection checks passed: stale RUNNING/FAILED, available/missing/
  empty images, explicit pending ownership, review waits, rejection, independent
  modes and Batches filtering. `npm.cmd run test:e2e -- --grep character-to-costume`
  actually ran all four approved scenarios through the wrapper: 4 passed (43.1s).
  The fixture logged a background storage-maintenance lock-contention warning;
  all scenarios and the runner completed successfully.
- Python syntax, `git diff --check` and final diff review passed. No permanent
  tests or dependencies were added. Existing unrelated user edits were preserved.
