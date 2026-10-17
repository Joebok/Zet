# Recover local image harvest state during re-evaluation
Status: complete (local implementation; production rollout not performed)
Related issue/specification: reported Elder/Youth Tsaeytte Head-Image failure

## Goal
Allow explicit Re-evaluate to finish interrupted candidate-state commits for
successfully harvested images, without rendering again or weakening admission.

## Current behavior
`LocalImagePipelineWorkflowService.reevaluate` calls `require_candidate_harvest`
before ranking or observations. Older candidates can retain RUNNING state and no
`image_sha256` after the generic harvester has successfully copied their image and
written a receipt. Elder has six such existing images; Youth has eight. Their
successful receipts and original requests are in the running installation's
machine-local store under LocalAppData, rather than the checkout's configured
E: store. Read-only inspection only; no live files have been changed.

## Desired behavior
Explicit re-evaluation verifies receipt, current candidate/attempt, output ownership
and image validity, commits missing hashes under the run lock, then starts advice.
Missing/failed/foreign receipts, changed existing hashes and stale candidates remain
blocked. Human review, notes, selections and image bytes are preserved.

## Impact analysis
Owners: `image_harvest_service.py` and `local_image_workflow_service.py`.
Documentation: LOCAL_CHARACTERS owns Re-evaluate; INVARIANTS and AI_JOBS retain
their existing receipt/admission requirements. No new schema or architectural
responsibility, dependency, permanent test or scenario is needed.

## Invariants and constraints
All target images must verify before any repair is committed. Current hashes are
never replaced. Modern receipts retain checksum proof. Legacy receipts without
artifact hashes additionally require the saved request's exact source-attempt ID,
universe, character/phase and target filename. Recovery runs only on the explicit
action, not a detail read or publication admission. No live queue/model calls or
production writes/deployment are authorized by this local change.

## Implementation steps
### WP1 — Reconcile verified candidate commits
- Dependencies: none.
- Files/interfaces: shared harvest service and Re-evaluate action.
- Work: add locked verification/commit; reload the run before starting advice.
- Acceptance: valid interrupted commits recover; existing admission fences remain.
- Validation: disposable isolated service/action checks with prepared receipts.
- Status: complete.

### WP2 — Verify and document
- Dependencies: WP1.
- Files/interfaces: LOCAL_CHARACTERS and this plan.
- Work: document explicit recovery, run approved regressions and review diff.
- Acceptance: report actual results and live rollout boundary.
- Validation: `npm.cmd run test:e2e`; `git diff --check`.
- Status: complete.

## Validation
S2 protects existing Assembly/Dressing rendering, ranking and publication. It does
not cover interrupted Head state; disposable checks cover that gap without adding
permanent coverage. No live pipeline check will be run.

## Risks and alternatives
Do not infer success from an image file alone. A deployment using a different
machine-local store must first preserve the verified receipts/request records;
automatic fallback to old stores is outside scope. Legacy receipt recovery cannot
recreate an original output digest that was never recorded; it uses the existing
successful-receipt compatibility contract plus exact saved attempt ownership.

## Progress and decisions
- Confirmed missing hashes and successful legacy receipts in the reported batches.
- Production config loading is blocked by ZET_WORKER_MODE; retain that guard and
  validate exclusively with isolated fixtures.
- Disposable `python3 -B test-results/check_reevaluate_harvest.py` passed against
  isolated copies of both reported batches (eight rendered images each), with
  prepared rankings. Human reviews, observations, selections and source image
  checksums were preserved. Failed/missing/foreign receipts, failed execution,
  modern checksum mismatches, mismatched saved attempts, changed committed
  hashes and replaced candidates all blocked without partial recovery commits.
- No original output digest exists for legacy receipts; their exact saved request
  ownership and successful receipt are required, consistent with existing legacy
  receipt admission. Modern checksums remain mandatory when recorded.
- Modern receipt verification follows checksum identity rather than the original
  absolute output path, preserving existing library-relocation compatibility.

## Final results
- Shared recovery and the Re-evaluate action now commit verified missing candidate
  hashes before starting observations/ranking, without invoking rendering.
- `python3 -B test-results/check_reevaluate_harvest.py` passed on the final code.
  The disposable script and fixtures remain ignored under `test-results`.
- `npm.cmd run test:e2e`: all four approved scenarios passed in 34.2 seconds.
- `git diff --check`: passed. Final diff contains only the two service files,
  their owning component/code-map documentation and this completed plan.
- Production rollout and repairs remain operator actions. No live model calls,
  production config loading, queue-store migration or live batch writes occurred.
  Existing receipts/requests in the running installation's LocalAppData store
  must remain available to the installation that performs Re-evaluate.
