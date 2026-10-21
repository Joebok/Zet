# Head failed-rerun dispatch
Status: complete

## Goal and verified cause
Head `rerun_failed_view` resets failed/rejected candidates but omits explicit
candidate targets. `execute_run` excludes supplemental slot candidates unless
explicit targets exist. The reported batch has ten pending supplemental candidates
across the two front-quarter views after the action returned without rendering.

## Impact and constraints
Owner: `zet/services/local_head_image_service.py`; route dispatch already invokes
the runner for the requested view. Body already persists failed-candidate targets.
Preserve good candidates, universe/queue ownership, staged progression and locked
images. No new dependencies or maintained tests. Production recovery/submission
requires Joe's approval under AGENTS.md external-write rules.
Documentation owner: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`; no responsibilities move.

## Luna sized work packets
### WP1 — Persist explicit failed-render targets
- Files: Head service and local-character component documentation.
- Dependencies: none.
- Work: persist requested view and exactly the failed/rejected candidate IDs.
- Acceptance: supplemental candidates reach the runner; kept candidates stay intact.
- Validation: disposable isolated actual-method reset/runner check.
- Status: complete.

### WP2 — Validate and record
- Files: this plan.
- Dependencies: WP1.
- Acceptance: focused S2 and diff checks pass; live recovery limits are explicit.
- Validation: `npm.cmd run test:e2e -- --grep character-to-costume`, Python syntax,
  `git diff --check`.
- Status: complete.

## Results
Head failed reruns now persist exactly the reset candidate IDs and requested view.
Disposable actual-method checks for both front quarters passed reset, dispatch,
prepared render completion, evaluation invocation, no-failed-candidate rejection,
kept-candidate/byte preservation, unopened-view preservation and target cleanup.
Only external/render collaborators were replaced; no real inference was invoked.
`npm.cmd run test:e2e -- --grep character-to-costume` passed (one scenario, 18.8s).
Python import/AST and `git diff --check` passed. Component documentation updated;
no code-map entry points or architecture contracts changed.
At implementation completion the reported live batch remained unchanged: five
pending supplemental cards in each front-quarter view required recovery.

## Authorized live recovery follow-up (2026-10-20)
Joe explicitly approved recovering the ten pending cards. A standalone helper
stopped at the worker-mode production-configuration guard before any batch change.
Recovery then used the existing dashboard slot-regeneration API with explicit
Moonsea headers and `expected_candidate_id` fencing, replacing only those ten
pending cards in their original physical slots. The dashboard owns submission and
collection through AI_Proxy; no guard was disabled or runtime restarted.
Mappings and before/after evidence are in ignored
`test-results/head-rerun-recovery/`. All ten replacement candidates had distinct
attached asks and no render errors at final inspection: three rendered and waiting
for human review, one running, six queued. The collector reported no error.
All 30 pre-existing completed image files retained their paths and verified hashes.
Remaining renders proceed under the dashboard collector. This recovery does not
deploy the local backend fix or establish image quality.
