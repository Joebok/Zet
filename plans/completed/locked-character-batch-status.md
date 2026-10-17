# Completed publication status across character pipelines
Status: complete

## Goal and current behavior
Extend the Body-Reference status correction to Head-Image, Character-Assembly,
and Costume-Dressing. All three use stored status in summaries and retain stale
ranking selection indicators after publication. Head detail can also demote a
fully locked batch to REVIEW_REQUIRED. Assembly/Dressing support optional FRONT
anchors and Dressing locks must remain costume-specific.

## Impact and constraints
Own the shared verification in `LocalAssetStoreService`; call it from the four
pipeline adapters' detail and summary projections. No serialized data, library
records, immutable locks, execution transitions, or ranking policies change.
Preserve active, error, cancelled and interrupted statuses. Relevant knowledge:
LOCAL_CHARACTERS, CODE_MAP, INVARIANTS section 5, and Testing. No new maintained
tests, dependencies, live AI, or deployment.

## Luna sized work packets
### WP1 — Share verified publication matching
- Files: `local_asset_store_service.py`, `local_body_reference_service.py`.
- Dependencies: existing Body-Reference fix.
- Work: move its matching into the store with pipeline, qualifier and anchor
  requirements; preserve Body behavior.
- Acceptance: every requested selection matches same-batch verified lock and
  candidate image checksum; reject missing/mismatched/corrupt records.
- Validation: disposable isolated store checks and original-batch read-only check.
- Status: complete. Shared verification passes disposable checks for all four
  adapters, including checksum, candidate, batch, qualifier and anchor mismatches.

### WP2 — Apply status projection and verify
- Files: `local_head_image_service.py`, `local_character_asset_pipeline_service.py`,
  `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`.
- Dependencies: WP1.
- Work: recognize completed publication in detail and summaries, preserving
  optional anchors, costume scope, advisory rankings and protected statuses.
- Acceptance: fully locked batches show COMPLETE in both projections; partial or
  invalid publication never creates completion.
- Validation: disposable adapter checks, approved `npm.cmd run test:e2e`, and
  `git diff --check`. S2 is Assembly/Dressing regression; Body/Head and invalid-lock
  cases use disposable checks, not a new maintained scenario.
- Status: complete. Detail and summary checks pass for all adapters; shared
  verification replaces the original Body implementation. Documentation updated.

## Results
Disposable fixture checks passed for all four adapters: completed publication,
unchanged source records, retained stale rankings, partial selection, wrong
candidate/batch/qualifier/anchor, stale lock, missing candidate bytes, changed
candidate/published bytes, active/error/cancelled/interrupted/queued/stopped
statuses and optional anchors. Initial disposable fixture runs failed because
Body/Head require timestamp batch IDs; fixture IDs corrected before the passing run.
`npm.cmd run test:e2e` passed all four approved scenarios (33.1s).
`git diff --check` passed and final diff was reviewed for scope. The read-only
original Tsaeytte batch check still reports COMPLETE with source JSON unchanged.
The disposable checks are ignored at `test-results/locked-batch-check.py`; no
maintained tests were added. Component and code-map knowledge now describe the
shared verification owner. No data/schema changes or new durable architecture
decision required an ADR. Local fix only; deployment remains unperformed.
