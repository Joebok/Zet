# Completed-view re-evaluation
Status: complete (local fix; production deployment requires approval)

## Goal and current behavior
Final LEFT_PROFILE in Head-Image Edit batch `20261022_130159_301043`
has eight available images but no saved Final evaluation or ranking. Other views
still have pending renders. Both the shared dashboard and workflow reject
Re-evaluate because they check the entire batch, preventing recovery of this view.
The current slot collector already dispatches ranking by view and render mode;
the live records do not establish why this historical handoff was missed.

## Desired behavior and constraints
Allow explicit re-evaluation of a completed view while other views or modes render.
Continue to block renders in the target view/mode, stopped batches and legacy batch
execution. Preserve batch-wide exclusion, image availability, anchor checks, locked
asset protections, decisions and evaluation fencing. Display an explicit ranking
state when no result exists. No production writes, live AI calls, dependencies or
permanent scenarios are authorized.

## Impact and documentation
Owners: `local_image_workflow_service.py` (shared validation and presentation),
`local_asset_pipeline.js` (actions and review), LOCAL_CHARACTERS (workflow),
CODE_MAP (entry point), Testing (observed checks). No storage format changes.
Architecture and invariant owners remain unchanged.

## Implementation packets
### WP1 — Scoped eligibility
- Dependencies: none.
- Files: `zet/services/local_image_workflow_service.py`.
- Work: share the re-evaluation blocking reason between detail projection and action;
  scope slot work to the requested view/mode for view actions.
- Acceptance: unrelated work does not block a completed view; target work, stopped
  batches and legacy execution still block; batch action remains conservative.
- Validation: disposable temporary-image service checks; Python syntax.
- Status: complete.

### WP2 — Controls, review state and verification
- Dependencies: WP1.
- Files: `zet/web/static/local_asset_pipeline.js`, affected documentation.
- Work: use projected eligibility and explain missing/queued ranking in review.
- Acceptance: completed Final LEFT_PROFILE enables Re-evaluate while RIGHT_PROFILE
  renders; Draft/Final ranking remains isolated; existing advice still displays.
- Validation: disposable Chromium prepared-response check, approved fast E2E suite,
  JavaScript syntax and `git diff --check`.
- Status: complete.

## Validation and final results
S2 protects initial ranking/publication; prepared disposable checks cover the
additional scope and display behavior. `npm.cmd run test:e2e` passed all four
approved scenarios (45.6s). `python3 -B test-results/check_view_reevaluation.py`
passed eligibility, detail projection, action dispatch, isolation, protection
calls, interrupted-bookkeeping availability and retained review checks.
`node test-results/check_view_reevaluation.cjs` passed controls and request scope
for all five pipelines, missing/queued/completed advice, Draft/Final isolation and
eligibility-only changes during polling without page errors. Initial disposable
runs required fixture setup corrections; final checks passed. Python AST,
JavaScript syntax and `git diff --check` passed.

The workflow now owns a shared transient eligibility projection used by the
dashboard. No persisted schema or invariant changed; no ADR was needed.
LOCAL_CHARACTERS, CODE_MAP and Testing were updated. CODE_MAP contains existing
non-UTF-8 bytes outside the affected entry, so its entry was replaced as bytes to
preserve unrelated content. Final diff review excluded the pre-existing plan move.

Production deployment and live ranking require separate authorization under
AGENTS.md external-write rules. No live queue, candidate, image or selection was
changed. The live missing historical handoff remains unproven; the completed
view now has an explicit recovery action once the fix is deployed.
