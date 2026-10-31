# Bulk render lock contention
Status: complete

## Goal and current behavior
Both reported Final Run available actions saved pending slot work. Body detail
GETs return 404 with `Workflow is busy` after timing out on the run's state lock.
`CharacterRenderSlots.collect` holds that lock across all pending candidates and
ranking dispatch; the local router maps every detail exception to 404.

## Impact and constraints
The shared slot collector and local API error mapping are affected. Preserve
candidate membership, attempt fencing, pause behavior, and concurrent slot edits.
No production batch/queue mutations, deployment, new dependencies, or maintained
tests. Relevant owners: Docs/COMPONENTS/LOCAL_CHARACTERS.md and QUEUES.md;
Docs/Testing.md records validation. No data format or architecture change.

## Implementation packets
### WP1 — Bound collector transactions
- Files: zet/services/render_slot_service.py.
- Dependencies: none.
- Work: release the run state lock between candidates; reload current membership
  and pause state inside each candidate transaction. Merge final bookkeeping into
  current state and check remaining work before ranking.
- Acceptance: reads and pause can acquire the lock during a large sweep; detached
  candidates cannot receive results and new slot work is retained.
- Validation: disposable isolated threaded collector check and approved S2.
- Status: complete.

### WP2 — Report contention correctly
- Files: zet/web/local_character_asset_pipeline_router.py.
- Dependencies: WP1.
- Work: map workflow lock timeouts to HTTP 409 instead of missing-resource 404.
- Acceptance: busy details identify a temporary conflict; missing runs remain 404.
- Validation: disposable router check and approved fast suite.
- Status: complete.

### WP3 — Verify and document
- Files: relevant component docs, Docs/Testing.md, this plan.
- Dependencies: WP1–WP2.
- Work: record isolated validation, syntax/diff checks, and live inspection limits.
- Acceptance: final diff is scoped and observed results are documented.
- Validation: npm.cmd run test:e2e; git diff --check.
- Status: complete.

## Findings and limits
Read-only live inspection: Head-Image Edit had 56 pending Final candidates and
eight completed FRONT images. Body had 24 pending Final candidates (eight each
for FRONT_LEFT_3_4, BACK, FRONT_RIGHT_3_4), eight completed FRONT images, and one
selected Final FRONT. Actual model completion is not part of isolated validation.

## Final results
Collector transactions now release the state lock between candidates and ranking
views, reload pending membership and pause state, merge completion bookkeeping,
and defer ranking while newly reserved candidates remain pending. Router lock
timeouts now return an actionable 409; missing runs retain 404.

All four approved fast scenarios passed (`npm.cmd run test:e2e`, 42.2s).
`python3 -B test-results/check_bulk_lock.py --before` reproduced the old read
timeout (expected failure). The updated disposable check passed concurrent reads,
pause, detached-candidate skipping, retained new reservations, completion merging,
and deferred ranking. All five router busy responses and missing-run behavior
passed. Python AST checks and `git diff --check` passed; the final diff was reviewed.

Read-only live follow-up found Body pending work decrease from 24 to 23 with one
additional completed Final image. Head-Image Edit retained 56 pending candidates,
with 33 asks queued and the remainder reserved at that observation. No live
renders were submitted, production data edited, or deployment performed. The fix
is local and requires the normal approved deployment before hosted behavior changes.
Documentation owners updated: Local Characters, Queues, Testing. No schema,
responsibility move, durable design decision, or ADR was needed.
