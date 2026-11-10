# Candidate Board consistency
Status: complete

## Goal
Unify review, slot controls, and bulk Draft cancellation across the three active boards.

## Work packets
1. Shared review CSS and comparison state. Verify equal wells, self-comparison, and missing Selected in isolated Chromium.
2. Shared slot presentation and fenced Character generation. Verify disabled reasons and explicit slot dispatch.
3. Owned Draft cancellation in image production and the three services. Verify preview, queue supersession, and late-answer fencing.
4. Shared bulk readiness and confirmation with adapter-owned requests. Verify cancel, protected effects, and stale previews.
5. Synchronize documentation and cache versions. Run the approved fast suite and diff checks before archiving.

## Constraints
Use prepared responses and private storage. Preserve publication transactions, existing stored formats, and current prompt and render evidence.

## Results
- The shared component owns comparison defaults, slot action presentation, and bulk delete controls. Narrative review uses the shared dimensions. Bulk delete requires individual approval for each protected effect.
- All three workflows withdraw owned queued Draft attempts and fence late answers and recovery. Existing preview checks and Inventory publication transactions remain in place. Backend execution already underway may finish.
- `npm.cmd run test:e2e` passed all four maintained scenarios (39.9 seconds). `git diff --check` and changed JavaScript/Python syntax checks passed.
- Disposable Chromium fixtures passed matching review dimensions, selected/self/empty comparison, slot targeting and tooltips, bulk readiness, and per-effect approval and cancellation. Disposable service fixtures passed queued/running/reserved/recovery supersession, ownership rejection, stale approval rejection, retry after cancellation failure, Final retention, and late-answer fencing after slot reuse. A disposable Narrative adapter check passed stale-preview reconfirmation and cancel.
- Validation used prepared responses and private fixtures. No live worker interruption was exercised.
